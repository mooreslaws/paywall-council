// Parser for Public Report Contract v3 (kb/applaw/references/
// report-contract.md).
//
// The report is the deliverable, not an intermediate: the skill produces text
// that validate_live_report.py has already accepted, and this turns that exact
// text into rows. So the parser is deliberately strict, a shape it does not
// recognise is a contract violation worth failing on, not something to guess
// around. The one place it is lenient is line wrapping: a field value may run
// onto following lines, which long legal prose does in practice.

import type {
  CouncilFinding,
  CouncilLiabilityBlock,
  CouncilReviewQuestion,
  RiskLabel,
} from "../interface";
import { RISK_LABELS } from "../interface";

export interface ParsedReport {
  productOrFlow: string;
  assessmentDate: string;
  jurisdictionsAssessed: string;
  risk: RiskLabel;
  verdict: string;
  findings: CouncilFinding[];
  liability: CouncilLiabilityBlock[];
  mitigating: string[];
  observedWithoutNorm: string[];
  missingContext: string[];
  priorityActions: string[];
  disclaimer: string;
  reviewQuestions: CouncilReviewQuestion[];
}

export class ReportFormatError extends Error {}

const SECTIONS = [
  "Assessment Summary",
  "Material Findings",
  "Liability and Consequences",
  "Mitigating and Low-Risk Elements",
  "Observed Without a Mapped Norm",
  "Missing Context",
  "Priority Actions",
  "Disclaimer",
] as const;

export function parseReport(text: string): ParsedReport {
  const body = text.replace(/\r\n/g, "\n").trim();

  const title = body.match(/^#[ \t]+Checkout-Funnel Risk Assessment:[ \t]*(.+)$/m);
  if (!title) throw new ReportFormatError("missing the report title line");

  const sections = splitSections(body);
  const summary = sections.get("Assessment Summary") ?? "";
  const disclaimerSection = sections.get("Disclaimer") ?? "";

  const verdict = readField(summary, "Verdict");
  if (!verdict) throw new ReportFormatError("Assessment Summary has no Verdict");

  return {
    productOrFlow: title[1].trim(),
    assessmentDate: readField(body, "Assessment date") ?? "",
    jurisdictionsAssessed: readField(body, "Jurisdictions assessed") ?? "",
    risk: readRisk(summary),
    verdict,
    findings: parseFindings(sections.get("Material Findings") ?? ""),
    liability: parseLiability(sections.get("Liability and Consequences") ?? ""),
    mitigating: parseBullets(sections.get("Mitigating and Low-Risk Elements") ?? ""),
    observedWithoutNorm: parseBullets(sections.get("Observed Without a Mapped Norm") ?? ""),
    missingContext: parseBullets(sections.get("Missing Context") ?? ""),
    priorityActions: parseBullets(sections.get("Priority Actions") ?? ""),
    disclaimer: disclaimerSection.split("\n")[0]?.trim() ?? "",
    reviewQuestions: parseReviewQuestions(disclaimerSection),
  };
}

// Level-two headings only; "### F1 - ..." stays inside its section.
function splitSections(body: string): Map<string, string> {
  const marks = [...body.matchAll(/^##[ \t]+(.+?)[ \t]*$/gm)].map((m) => ({
    name: m[1],
    start: (m.index ?? 0) + m[0].length,
    headStart: m.index ?? 0,
  }));
  const out = new Map<string, string>();
  marks.forEach((mark, i) => {
    const end = i + 1 < marks.length ? marks[i + 1].headStart : body.length;
    out.set(mark.name, body.slice(mark.start, end).trim());
  });
  for (const name of SECTIONS) {
    if (!out.has(name)) throw new ReportFormatError(`missing section: ${name}`);
  }
  return out;
}

function readRisk(summary: string): RiskLabel {
  const raw = readField(summary, "RISK");
  const value = (raw ?? "").toLowerCase().trim();
  if (!RISK_LABELS.includes(value as RiskLabel)) {
    throw new ReportFormatError(`RISK is not one of the five labels: ${raw ?? "(absent)"}`);
  }
  return value as RiskLabel;
}

// Reads "Label: value", continuing onto wrapped lines until the next field,
// heading, bullet, table row or blank line.
function readField(block: string, label: string): string | null {
  const lines = block.split("\n");
  const head = new RegExp(`^${escapeRe(label)}:[ \\t]*(.*)$`);
  for (let i = 0; i < lines.length; i++) {
    const hit = lines[i].match(head);
    if (!hit) continue;
    const parts = [hit[1].trim()];
    for (let j = i + 1; j < lines.length; j++) {
      const next = lines[j];
      if (
        !next.trim() ||
        /^#{1,6}\s/.test(next) ||
        /^[-|]\s?/.test(next.trim()) ||
        /^[A-Z][^:\n]{0,60}:[ \t]/.test(next)
      ) {
        break;
      }
      parts.push(next.trim());
    }
    return parts.join(" ").trim();
  }
  return null;
}

function escapeRe(s: string): string {
  return s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function isNone(section: string): boolean {
  return /^None\.?$/i.test(section.trim());
}

function splitBlocks(
  section: string,
  prefix: "F" | "L",
): { ref: string; title: string; body: string }[] {
  const heads = [
    ...section.matchAll(new RegExp(`^###[ \\t]+(${prefix}\\d+)[ \\t]*[-–—][ \\t]*(.+?)[ \\t]*$`, "gm")),
  ].map((m) => ({
    ref: m[1],
    title: m[2],
    start: (m.index ?? 0) + m[0].length,
    headStart: m.index ?? 0,
  }));
  return heads.map((h, i) => ({
    ref: h.ref,
    title: h.title,
    body: section.slice(h.start, i + 1 < heads.length ? heads[i + 1].headStart : section.length).trim(),
  }));
}

// Read the way validate_report.py reads it (re.findall of \bL\d+\b), so a
// link the validator accepted is a link we store. Splitting on commas and
// spaces dropped "L1; L2" to L2 and "L1." or "(L1)" to nothing, and the
// verdict then showed a finding with no liability block.
function refList(raw: string | null, prefix: "F" | "L"): string[] {
  const ids = [...(raw ?? "").matchAll(new RegExp(`\\b${prefix}\\d+\\b`, "g"))].map((m) => m[0]);
  return [...new Set(ids)];
}

function parseFindings(section: string): CouncilFinding[] {
  if (isNone(section)) return [];
  const blocks = splitBlocks(section, "F");
  if (blocks.length === 0) {
    throw new ReportFormatError("Material Findings is neither 'None.' nor a list of F blocks");
  }
  return blocks.map((b) => {
    const severity = (readField(b.body, "Severity") ?? "").toLowerCase();
    if (severity !== "high" && severity !== "medium") {
      throw new ReportFormatError(`${b.ref} severity must be High or Medium, got: ${severity}`);
    }
    // "Confidence and limitations: High - <limits>"
    const confidenceRaw = (readField(b.body, "Confidence and limitations") ?? "").trim();
    const split = confidenceRaw.match(/^(High|Medium)[ \t]*[-–—][ \t]*(.*)$/i);
    return {
      ref: b.ref,
      title: b.title,
      severity,
      observedEvidence: readField(b.body, "Observed evidence") ?? "",
      pattern: readField(b.body, "Pattern") ?? "",
      riskExplanation: readField(b.body, "Risk explanation") ?? "",
      applicableNorm: readField(b.body, "Applicable norm") ?? "",
      comparableAuthority: readField(b.body, "Comparable KB authority") ?? "",
      liabilityRefs: refList(readField(b.body, "Linked liability blocks"), "L"),
      confidence: split
        ? ((split[1][0].toUpperCase() + split[1].slice(1).toLowerCase()) as "High" | "Medium")
        : "Medium",
      confidenceLimits: split ? split[2].trim() : confidenceRaw,
      recommendedCorrection: readField(b.body, "Recommended correction") ?? "",
    };
  });
}

function parseLiability(section: string): CouncilLiabilityBlock[] {
  if (isNone(section)) return [];
  const blocks = splitBlocks(section, "L");
  if (blocks.length === 0) {
    throw new ReportFormatError("Liability and Consequences is neither 'None.' nor a list of L blocks");
  }
  return blocks.map((b) => ({
    ref: b.ref,
    title: b.title,
    findingRefs: refList(readField(b.body, "Linked findings"), "F"),
    liabilityTrigger: readField(b.body, "Liability trigger") ?? "",
    consumerRemedies: readField(b.body, "Consumer or contract remedies") ?? "",
    publicEnforcement: readField(b.body, "Public enforcement") ?? "",
    privateExposure: readField(b.body, "Private exposure") ?? "",
    monetaryExposure: readField(b.body, "Monetary exposure") ?? "",
    observedBenchmark: readField(b.body, "Observed enforcement benchmark") ?? "",
    nonMonetaryOrders: readField(b.body, "Non-monetary orders") ?? "",
    authorityCitations: readField(b.body, "Authority citations") ?? "",
    estimateStatus: readField(b.body, "Estimate status and limitations") ?? "",
  }));
}

function parseBullets(section: string): string[] {
  if (isNone(section)) return [];
  const out: string[] = [];
  for (const line of section.split("\n")) {
    const hit = line.trim().match(/^-[ \t]+(.*)$/);
    if (hit) out.push(hit[1].trim());
    else if (out.length > 0 && line.trim()) out[out.length - 1] += ` ${line.trim()}`;
  }
  return out;
}

// The follow-up sits after the Disclaimer sentence, outside the artifact:
// either the one exact question, or a one-row-per-module table.
function parseReviewQuestions(disclaimerSection: string): CouncilReviewQuestion[] {
  const rest = disclaimerSection.split("\n").slice(1).join("\n").trim();
  if (!rest) return [];

  const rows = [...rest.matchAll(/^\|[ \t]*(.+?)[ \t]*\|[ \t]*(Are the displayed .+?)[ \t]*\|$/gm)];
  if (rows.length > 0) {
    return rows
      .filter((r) => !/^-+$/.test(r[1]) && r[1] !== "Module")
      .map((r) => ({ module: r[1], question: normalise(r[2]) }));
  }

  const single = rest.match(/Are the displayed social-platform reviews[\s\S]+?confirmation\./);
  return single ? [{ module: "Displayed reviews", question: normalise(single[0]) }] : [];
}

// The contract's question is one sentence; a wrapped copy must compare equal
// to it, so collapse the whitespace and the smart quotes the wrapper adds.
function normalise(s: string): string {
  return s.replace(/[“”]/g, "").replace(/\s+/g, " ").trim();
}
