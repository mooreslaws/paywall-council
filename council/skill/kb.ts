// Bridge to the knowledge base shipped in kb/applaw.
//
// The KB owns two runtime steps and we call them rather than reimplementing
// them: build_evaluation_context.py returns the bounded legal slice, and
// validate_live_report.py is the gate a draft must pass. SECURITY_BOUNDARY.md
// is explicit that a rule the host does not actually invoke "remains advisory
// rather than runtime-enforced": which is the whole reason to run these here
// instead of trusting the model to have followed them.
//
// Everything is spawned with execFile and an argument array: no shell, so a
// pattern id or jurisdiction string can never be interpreted as a command.

import { execFile } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import { promisify } from "node:util";
import { partitionRequestedJurisdictions } from "../interface";

const run = promisify(execFile);

const PYTHON = process.env.KB_PYTHON ?? "python3";
const EXEC_TIMEOUT_MS = 30_000;
const MAX_OUTPUT_BYTES = 8 * 1024 * 1024;

export function skillRoot(): string {
  return process.env.KB_ROOT ?? path.join(process.cwd(), "kb", "applaw");
}

export function readReference(name: string): string {
  return fs.readFileSync(path.join(skillRoot(), "references", name), "utf8");
}

export function readSkillFile(relative: string): string {
  return fs.readFileSync(path.join(skillRoot(), relative), "utf8");
}

type FlatYamlValue = string | string[];
type FlatYamlItem = Record<string, FlatYamlValue>;

function yamlScalar(raw: string): string {
  const value = raw.trim();
  if (value.length >= 2 && value.startsWith('"') && value.endsWith('"')) {
    try {
      return JSON.parse(value) as string;
    } catch {
      return value.slice(1, -1);
    }
  }
  if (value.length >= 2 && value.startsWith("'") && value.endsWith("'")) {
    return value.slice(1, -1);
  }
  return value;
}

function yamlInlineList(raw: string): string[] {
  const value = raw.trim();
  if (!value.startsWith("[") || !value.endsWith("]")) return [yamlScalar(value)];
  const items: string[] = [];
  let quote = "";
  let buffer = "";
  for (const char of value.slice(1, -1)) {
    if (quote) {
      if (char === quote) quote = "";
      buffer += char;
    } else if (char === '"' || char === "'") {
      quote = char;
      buffer += char;
    } else if (char === ",") {
      if (buffer.trim()) items.push(yamlScalar(buffer));
      buffer = "";
    } else {
      buffer += char;
    }
  }
  if (buffer.trim()) items.push(yamlScalar(buffer));
  return items;
}

// The canonical registries use a deliberately small, flat YAML subset. This
// mirrors the KB's stdlib parser instead of adding a second YAML dependency or
// a generated catalog that could drift from patterns.yml.
export function parseFlatYamlItems(text: string): FlatYamlItem[] {
  const items: FlatYamlItem[] = [];
  let current: FlatYamlItem | undefined;
  let listKey = "";
  for (const line of text.replace(/^\uFEFF/, "").split(/\r?\n/)) {
    const itemMatch = line.match(/^-\s+id:\s*(.+?)\s*$/);
    if (itemMatch) {
      if (current) items.push(current);
      current = { id: yamlScalar(itemMatch[1]) };
      listKey = "";
      continue;
    }
    if (!current || !line.trim() || line.trimStart().startsWith("#")) continue;
    const fieldMatch = line.match(/^\s{2}([a-zA-Z0-9_]+):(?:\s*(.*))?$/);
    if (fieldMatch) {
      const raw = (fieldMatch[2] ?? "").trim();
      if (!raw) {
        current[fieldMatch[1]] = [];
        listKey = fieldMatch[1];
      } else {
        current[fieldMatch[1]] = raw.startsWith("[") ? yamlInlineList(raw) : yamlScalar(raw);
        listKey = "";
      }
      continue;
    }
    const listMatch = line.match(/^\s{4}-\s*(.+?)\s*$/);
    if (listMatch && listKey) {
      const values = current[listKey];
      if (Array.isArray(values)) values.push(yamlScalar(listMatch[1]));
    }
  }
  if (current) items.push(current);
  return items;
}

// Every cue a record carries, not only its first. A pattern is written with
// several cues because one screen rarely matches the opening sentence: the
// second cue of daily-price-framing is the one describing a plan card that
// reads "1 day - EUR 0.61" with the real charge in fine print below the
// button. While only the first cue reached the Examiner, that exact screen
// came back labelled nominal-price-framing and the daily framing went
// unreported (issue #84), and 11k characters of authored cues were dropped on
// every run. The budget still bounds a runaway record; it is now spent per
// field rather than per sentence.
const CATALOG_FIELD_MAX_CHARACTERS = 1200;

function compactCatalogField(values: FlatYamlValue | undefined): string {
  const list = Array.isArray(values) ? values : values === undefined ? [] : [values];
  const compact = list
    .map((value) => String(value).replace(/\s+/g, " ").trim())
    .filter(Boolean)
    .join(" ");
  if (!compact) return "Not specified.";
  if (compact.length <= CATALOG_FIELD_MAX_CHARACTERS) return compact;
  const prefix = compact.slice(0, CATALOG_FIELD_MAX_CHARACTERS - 1);
  const boundary = prefix.lastIndexOf(" ");
  return `${prefix.slice(0, Math.max(boundary, 1)).trimEnd()}…`;
}

export function buildExaminerPatternCatalog(patternYaml: string): string {
  return parseFlatYamlItems(patternYaml)
    .map((pattern) => {
      const id = String(pattern.id ?? "");
      const name = String(pattern.name ?? id);
      return (
        `- ${id} | ${name} | Detect: ${compactCatalogField(pattern.detection_cues)} | ` +
        `Avoid: ${compactCatalogField(pattern.false_positive_traps)}`
      );
    })
    .join("\n");
}

// The same treatment the patterns get, for the facts that decide whether a
// norm is citable at all. Before taxonomy/factual_gates.yml existed the
// Examiner received only the bare slugs and had to infer each meaning from
// the name; the first live run left an obvious payment screen's billing fact
// unconfirmed, which emptied the established-authority list and cost two
// report regenerations. A token with no entry still appears, so a new route
// can never make one silently vanish from the allowed set.
export function buildExaminerFactualGateCatalog(
  gateYaml: string | null,
  tokens: string[],
): string {
  const described = new Map<string, FlatYamlItem>();
  for (const gate of gateYaml ? parseFlatYamlItems(gateYaml) : []) {
    described.set(String(gate.id ?? ""), gate);
  }
  return tokens
    .map((token) => {
      const gate = described.get(token);
      if (!gate) return `- ${token}`;
      return (
        `- ${token} | ${String(gate.name ?? token)} | Detect: ${compactCatalogField(gate.detect)} | ` +
        `Avoid: ${compactCatalogField(gate.avoid)}`
      );
    })
    .join("\n");
}

export function examinerFactualGateCatalog(): string {
  const file = path.join(skillRoot(), "taxonomy", "factual_gates.yml");
  const text = fs.existsSync(file) ? fs.readFileSync(file, "utf8") : null;
  return buildExaminerFactualGateCatalog(text, knownFactualGateTokens());
}

export function examinerPatternCatalog(): string {
  const text = fs.readFileSync(path.join(skillRoot(), "taxonomy", "patterns.yml"), "utf8");
  return buildExaminerPatternCatalog(text);
}

export function knownFactualGateTokens(routeYaml?: string): string[] {
  const text =
    routeYaml ??
    fs.readFileSync(path.join(skillRoot(), "taxonomy", "jurisdiction_routes.yml"), "utf8");
  const tokens = new Set<string>();
  for (const route of parseFlatYamlItems(text)) {
    for (const key of ["required_facts", "disqualifying_facts"]) {
      const values = route[key];
      for (const token of Array.isArray(values) ? values : values ? [values] : []) {
        if (token) tokens.add(String(token));
      }
    }
  }
  return [...tokens].sort();
}

export interface FactualGateState {
  confirmed: string[];
  rejected: string[];
  unknown: string[];
}

export interface FactualGateEvidence {
  token: string;
  observation: string;
}

export type FactualGateInput =
  | string[]
  | {
      confirmed?: unknown;
      rejected?: unknown;
      unknown?: unknown;
      evidence?: unknown;
    };

export function normalizeFactualGateInput(input: FactualGateInput | undefined): {
  state: FactualGateState;
  evidence: FactualGateEvidence[];
  warnings: string[];
} {
  const allowed = new Set(knownFactualGateTokens());
  const warnings: string[] = [];
  let ignored = false;
  const source = Array.isArray(input) ? { confirmed: input } : input ?? {};
  const readState = (key: "confirmed" | "rejected" | "unknown"): string[] => {
    const raw = source[key];
    if (raw === undefined) return [];
    if (!Array.isArray(raw)) {
      ignored = true;
      return [];
    }
    const values: string[] = [];
    for (const item of raw) {
      const token = typeof item === "string" ? item.trim() : "";
      if (!allowed.has(token)) {
        ignored = true;
      } else if (!values.includes(token)) {
        values.push(token);
      }
    }
    return values;
  };
  const state: FactualGateState = {
    confirmed: readState("confirmed"),
    rejected: readState("rejected"),
    unknown: readState("unknown"),
  };
  const conflicts = new Set(
    [...state.confirmed, ...state.rejected, ...state.unknown].filter(
      (token, _index, all) => all.filter((candidate) => candidate === token).length > 1,
    ),
  );
  if (conflicts.size) {
    state.confirmed = state.confirmed.filter((token) => !conflicts.has(token));
    state.rejected = state.rejected.filter((token) => !conflicts.has(token));
    state.unknown = [...state.unknown.filter((token) => !conflicts.has(token)), ...conflicts];
    warnings.push("Conflicting factual-gate states were treated as unknown.");
  }
  const evidence: FactualGateEvidence[] = [];
  const rawEvidence = Array.isArray(source.evidence) ? source.evidence : [];
  for (const item of rawEvidence) {
    if (!item || typeof item !== "object") {
      ignored = true;
      continue;
    }
    const token = String((item as { token?: unknown }).token ?? "").trim();
    const observation = String((item as { observation?: unknown }).observation ?? "").trim();
    if (!allowed.has(token) || !observation) {
      ignored = true;
      continue;
    }
    evidence.push({ token, observation });
  }
  if (ignored) {
    warnings.push(
      "One or more unrecognized factual-gate values were ignored; they did not satisfy or reject any legal route.",
    );
  }
  return { state, evidence, warnings };
}

// The catalog and fact-token vocabulary are part of the same cacheable static
// Examiner instructions as the workflow references. No per-run model or KB
// call is added, and legal mappings never enter the recognition catalog.
export function examinerWorkflowSystemPrompt(): string {
  return [
    readSkillFile("SKILL.md"),
    readReference("scope-gate.md"),
    readReference("evaluation-workflow.md"),
    readReference("jurisdiction-routing.md"),
    readReference("output-style.md"),
    [
      "EXAMINER PATTERN CATALOG (recognition only; use these exact ids):",
      examinerPatternCatalog(),
      "",
      "ALLOWED FACTUAL-GATE TOKENS (return exact tokens only; never put prose here):",
      examinerFactualGateCatalog(),
      "Use confirmed for facts established by the supplied evidence, rejected for facts the evidence expressly negates, and unknown for unresolved facts. Put human-readable support only in factual_gates.evidence. Missing facts are unknown, never false. Do not create tokens.",
    ].join("\n"),
  ].join("\n\n---\n\n");
}

export interface EvaluationContext {
  [key: string]: unknown;
}

// The deterministic slice: candidate patterns plus explicitly supplied
// jurisdictions in, bounded JSON of norms and comparable authorities out.
// Jurisdiction is never inferred: the KB refuses to guess it and so do we.
export async function buildEvaluationContext(opts: {
  patterns: string[];
  jurisdictions: string[];
  facts?: FactualGateInput;
}): Promise<EvaluationContext> {
  const root = skillRoot();
  const scope = partitionRequestedJurisdictions(opts.jurisdictions);
  if (scope.supported.length === 0) {
    throw new Error("No supported jurisdiction was supplied. AppLaw supports US, EU, and UK.");
  }
  const normalizedFacts = normalizeFactualGateInput(opts.facts);
  const baseArgs = [
    "-B",
    path.join(root, "scripts", "build_evaluation_context.py"),
    "--kb",
    root,
  ];
  for (const p of opts.patterns) baseArgs.push("--pattern", p);
  for (const j of scope.supported) baseArgs.push("--jurisdiction", j);
  for (const f of normalizedFacts.state.confirmed) baseArgs.push("--confirmed-fact", f);
  for (const f of normalizedFacts.state.rejected) baseArgs.push("--rejected-fact", f);
  for (const f of normalizedFacts.state.unknown) baseArgs.push("--unknown-fact", f);

  // The trust-signal checklist (#18) legitimately produces 15+ candidate
  // patterns on funnels that stack social proof, and the raw slice can then
  // exceed the KB's --max-bytes guardrail: the script exits 3 rather than
  // truncating silently. Degrade deterministically through the script's own
  // caps (fewer example cases per pattern, fewer outcomes per norm) instead
  // of dying: the norms themselves are never dropped, so cite-or-abstain is
  // unaffected; only the volume of comparator material shrinks.
  const capLadder: string[][] = [
    [],
    ["--max-cases-per-pattern", "2", "--max-outcomes-per-norm", "3"],
    ["--max-cases-per-pattern", "1", "--max-outcomes-per-norm", "2"],
    // Last rung: 17+ patterns exceed 160KB even at the tightest caps because
    // the norm and route records themselves dominate. The KB's default
    // --max-bytes assumes the slice is prompted verbatim; the module trims
    // roughly half of it before the counsel prompt (see
    // trimContextForCounsel), so a raised raw ceiling here still lands under
    // the KB's intended in-prompt bound.
    ["--max-cases-per-pattern", "1", "--max-outcomes-per-norm", "2", "--max-bytes", "400000"],
  ];
  let lastError: unknown;
  for (const caps of capLadder) {
    try {
      const { stdout } = await run(PYTHON, [...baseArgs, ...caps], {
        timeout: EXEC_TIMEOUT_MS,
        maxBuffer: MAX_OUTPUT_BYTES,
      });
      const context = JSON.parse(stdout) as EvaluationContext;
      const boundaryWarnings = [
        ...normalizedFacts.warnings,
        ...(scope.unsupported.length
          ? ["Unsupported market selections were excluded before legal routing."]
          : []),
      ];
      if (boundaryWarnings.length) {
        const existing = Array.isArray(context.warnings)
          ? context.warnings.map((warning) => String(warning))
          : [];
        context.warnings = [...new Set([...existing, ...boundaryWarnings])];
      }
      return context;
    } catch (e) {
      lastError = e;
      const stderr = String((e as { stderr?: string }).stderr ?? "");
      if (!stderr.includes("above --max-bytes")) throw e;
    }
  }
  throw lastError;
}

export interface ValidationResult {
  ok: boolean;
  output: string;
}

// Validates the exact text that would be delivered. The validator reads the
// draft on stdin so nothing is written to disk between checking and storing.
export async function validateLiveReport(
  reportText: string,
  allowedMaterialNormIds: string[],
  conditionalMaterialNormIds: string[] = [],
  requireUnsupportedJurisdictionDisclosure = false,
): Promise<ValidationResult> {
  const root = skillRoot();
  const args = [
    "-B",
    path.join(root, "scripts", "validate_live_report.py"),
    "--stdin",
    "--kb",
    root,
    "--enforce-authority-slice",
  ];
  if (requireUnsupportedJurisdictionDisclosure) {
    args.push("--require-unsupported-jurisdiction-disclosure");
  }
  for (const normId of [...new Set(allowedMaterialNormIds)]) {
    args.push("--allowed-material-norm-id", normId);
  }
  for (const normId of [...new Set(conditionalMaterialNormIds)]) {
    args.push("--conditional-material-norm-id", normId);
  }
  const child = run(
    PYTHON,
    args,
    { timeout: EXEC_TIMEOUT_MS, maxBuffer: MAX_OUTPUT_BYTES },
  );
  child.child.stdin?.end(reportText, "utf8");
  try {
    const { stdout, stderr } = await child;
    return { ok: true, output: `${stdout}${stderr}`.trim() };
  } catch (e) {
    const err = e as { stdout?: string; stderr?: string; message?: string };
    return {
      ok: false,
      output: `${err.stdout ?? ""}${err.stderr ?? ""}`.trim() || String(err.message ?? e),
    };
  }
}

// Pattern ids the model may propose. Reading them from the taxonomy keeps the
// prompt honest: a pattern the KB does not define cannot reach retrieval.
export function knownPatternIds(): string[] {
  const text = fs.readFileSync(path.join(skillRoot(), "taxonomy", "patterns.yml"), "utf8");
  return parseFlatYamlItems(text).map((item) => String(item.id));
}

// Norm ids, for the same reason, and for output safety: the validator's
// public complaint deliberately does not say WHICH internal id a draft
// contains, so the module removes every known id from the rejected draft
// before it goes back to Counsel (redactInternalIdsForRetry in index.ts).
export function knownNormIds(): string[] {
  const text = fs.readFileSync(path.join(skillRoot(), "taxonomy", "norms.yml"), "utf8");
  return [...text.matchAll(/^\s*-?\s*id:\s*"?([a-z0-9-]+)"?\s*$/gm)].map((m) => m[1]);
}
