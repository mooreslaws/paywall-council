// Round-trips every bundled report sample through the v3 parser.
//
// These fixtures are the ones Misha's own validate_report.py accepts, so they
// are the closest thing to production output we can check offline: if the
// parser disagrees with them, the app would mis-store a report the KB
// considers valid.
//
// Run: npm run verify:parser   (compiles the parser with the repo's tsc first)
import { readFileSync, readdirSync } from "node:fs";
import { createRequire } from "node:module";
import { join } from "node:path";

// The parser is TypeScript; npm run verify:parser compiles it to CommonJS
// first so relative imports resolve without an extension rewrite step.
const require = createRequire(import.meta.url);
const { parseReport } = require("../.parser-build/council/skill/parse-report.js");

const SAMPLES = "kb/applaw/eval/report_samples";

const REQUIRED_FINDING_FIELDS = [
  "observedEvidence",
  "pattern",
  "riskExplanation",
  "applicableNorm",
  "comparableAuthority",
  "recommendedCorrection",
];
const REQUIRED_LIABILITY_FIELDS = [
  "liabilityTrigger",
  "publicEnforcement",
  "monetaryExposure",
  "observedBenchmark",
  "authorityCitations",
  "estimateStatus",
];

let failures = 0;
let checked = 0;

for (const name of readdirSync(SAMPLES).filter((f) => f.endsWith(".md")).sort()) {
  const text = readFileSync(join(SAMPLES, name), "utf8");
  const problems = [];
  let r;
  try {
    r = parseReport(text);
  } catch (e) {
    console.error(`FAIL ${name}: ${e.message}`);
    failures++;
    continue;
  }
  checked++;

  if (!r.productOrFlow) problems.push("no product/flow in the title");
  if (!/^\d{4}-\d{2}-\d{2}$/.test(r.assessmentDate)) problems.push(`bad date: ${r.assessmentDate}`);
  if (!r.jurisdictionsAssessed) problems.push("no jurisdictions line");
  if (!r.verdict) problems.push("no verdict");
  if (!r.disclaimer.startsWith("This report is a risk assessment"))
    problems.push(`disclaimer not carried: ${r.disclaimer.slice(0, 40)}`);
  if (r.priorityActions.length === 0) problems.push("priority actions empty");

  // Refs must be unique and links must resolve in both directions (v3
  // requires every finding to link a block and every block to link back).
  const fRefs = new Set(r.findings.map((f) => f.ref));
  const lRefs = new Set(r.liability.map((b) => b.ref));
  if (fRefs.size !== r.findings.length) problems.push("duplicate F refs");
  if (lRefs.size !== r.liability.length) problems.push("duplicate L refs");
  for (const f of r.findings) {
    for (const field of REQUIRED_FINDING_FIELDS) {
      if (!f[field]) problems.push(`${f.ref}.${field} empty`);
    }
    if (f.liabilityRefs.length === 0) problems.push(`${f.ref} links no liability block`);
    for (const ref of f.liabilityRefs) {
      if (!lRefs.has(ref)) problems.push(`${f.ref} links missing ${ref}`);
    }
  }
  for (const b of r.liability) {
    for (const field of REQUIRED_LIABILITY_FIELDS) {
      if (!b[field]) problems.push(`${b.ref}.${field} empty`);
    }
    if (b.findingRefs.length === 0) problems.push(`${b.ref} links no finding`);
    for (const ref of b.findingRefs) {
      if (!fRefs.has(ref)) problems.push(`${b.ref} links missing ${ref}`);
    }
  }

  const shape = `${r.risk} · ${r.findings.length}F/${r.liability.length}L · ` +
    `${r.mitigating.length}m/${r.missingContext.length}c/${r.priorityActions.length}a` +
    (r.reviewQuestions.length ? ` · ${r.reviewQuestions.length}?` : "");
  if (problems.length) {
    failures++;
    console.error(`FAIL ${name} (${shape})`);
    for (const p of problems) console.error(`     - ${p}`);
  } else {
    console.log(`ok   ${name}: ${shape}`);
  }
}

console.log(`\nparser: ${checked - failures}/${checked} samples clean`);

// Link lines the validator accepts but the samples never spell this way.
// validate_report.py reads refs as re.findall(r"\bL\d+\b"), so punctuation
// around a ref is legal, and the parser used to split on commas and spaces:
// "L1; L2" came back as [L2], and "L1." or "(L1)" as nothing, which put a
// finding with no liability block on the verdict. Each case rewrites one
// link line of a real sample and parses the whole report.
const BASE = "2026-07-14-us-negative-option-standard.md";
const base = readFileSync(join(SAMPLES, BASE), "utf8");
const LINK_CASES = [
  ["Linked liability blocks", "L1; L2", (r) => r.findings[0].liabilityRefs, ["L1", "L2"]],
  ["Linked liability blocks", "L1.", (r) => r.findings[0].liabilityRefs, ["L1"]],
  ["Linked liability blocks", "(L1)", (r) => r.findings[0].liabilityRefs, ["L1"]],
  ["Linked findings", "F1;", (r) => r.liability[0].findingRefs, ["F1"]],
];
let linkFailures = 0;
for (const [label, value, read, want] of LINK_CASES) {
  const line = new RegExp(`^${label}: .*$`, "m");
  if (!line.test(base)) {
    console.error(`FAIL ${BASE} has no "${label}:" line to rewrite`);
    linkFailures++;
    continue;
  }
  let got;
  try {
    got = read(parseReport(base.replace(line, `${label}: ${value}`)));
  } catch (e) {
    got = `threw: ${e.message}`;
  }
  if (JSON.stringify(got) === JSON.stringify(want)) {
    console.log(`ok   "${label}: ${value}" -> ${want.join(", ")}`);
  } else {
    console.error(`FAIL "${label}: ${value}" -> ${JSON.stringify(got)}, expected ${JSON.stringify(want)}`);
    linkFailures++;
  }
}
console.log(`\nlink lines: ${LINK_CASES.length - linkFailures}/${LINK_CASES.length} cases clean`);

process.exit(failures > 0 || linkFailures > 0 ? 1 : 0);
