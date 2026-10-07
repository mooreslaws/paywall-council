// Deterministic, offline checks for the Examiner -> router -> Counsel ->
// validator boundaries. The npm script compiles only the pure bridge modules
// to CommonJS first; no model or network call is made.

import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import { join } from "node:path";

process.env.KB_ROOT = join(process.cwd(), "kb", "applaw");
process.env.KB_PYTHON = process.platform === "win32" ? "python" : "python3";

const require = createRequire(import.meta.url);
const kb = require("../.boundary-build/council/skill/kb.js");
const contextBoundary = require("../.boundary-build/council/skill/context.js");
const jurisdictions = require("../.boundary-build/council/interface.js");

const patternsPath = join(process.env.KB_ROOT, "taxonomy", "patterns.yml");
const patternYaml = readFileSync(patternsPath, "utf8");
const catalog = kb.buildExaminerPatternCatalog(patternYaml);
const catalogLines = catalog.split("\n").filter(Boolean);
const catalogIds = catalogLines.map((line) => line.match(/^- ([a-z0-9-]+) \|/)?.[1]);
const knownPatternIds = kb.knownPatternIds();

assert.deepEqual(catalogIds, knownPatternIds, "catalog ids must follow patterns.yml exactly");
assert.ok(
  catalogLines.some(
    (line) =>
      line.startsWith("- hidden-renewal | Hidden auto-renewal |") &&
      line.includes("renewal price") &&
      line.includes("Do not flag"),
  ),
  "hidden-renewal must carry its name, detection cue, and false-positive trap",
);
assert.ok(
  catalogLines.some(
    (line) =>
      line.startsWith("- fake-social-proof | Unverified social proof |") &&
      line.includes("reviews") &&
      line.includes("ordinary footer social-media icons"),
  ),
  "trust-signal catalog entry must carry recognition and false-positive guidance",
);
for (const normId of kb.knownNormIds()) {
  assert.ok(!catalog.includes(normId), `Examiner catalog leaked norm id ${normId}`);
}

const syntheticPattern = [
  "- id: synthetic-catalog-check",
  '  name: "Synthetic catalog check"',
  "  detection_cues:",
  '    - "A deterministic test cue."',
  "  false_positive_traps:",
  '    - "Do not flag the deterministic clean case."',
  "  maps_to_norms: []",
  "  example_cases: []",
].join("\n");
assert.ok(
  kb.buildExaminerPatternCatalog(`${patternYaml.trim()}\n\n${syntheticPattern}\n`).includes(
    "synthetic-catalog-check",
  ),
  "a new patterns.yml record must appear without a manual catalog edit",
);
const withoutHidden = patternYaml
  .split(/\n(?=- id: )/)
  .filter((block) => !block.startsWith("- id: hidden-renewal\n"))
  .join("\n");
assert.ok(
  !kb.buildExaminerPatternCatalog(withoutHidden).includes("- hidden-renewal |"),
  "a removed patterns.yml record must disappear without a manual catalog edit",
);

const catalogBytes = Buffer.byteLength(catalog, "utf8");
const sourceBytes = Buffer.byteLength(patternYaml, "utf8");
assert.ok(catalogBytes < sourceBytes, "compact catalog must be smaller than patterns.yml");
assert.ok(catalogLines.every((line) => line.length < 2000), "each catalog entry must stay bounded");

// The catalog used to carry only the first detection cue and the first trap of
// each record, which silently discarded most of what the KB authors wrote and
// is why a plan card priced per day was reported as nominal-price framing
// (issue #84). Assert the whole authored vocabulary arrives, so a future
// budget cut has to fail here rather than quietly narrow what the Examiner can
// recognize.
const authoredPatterns = kb.parseFlatYamlItems(patternYaml);
assert.equal(authoredPatterns.length, catalogLines.length, "every record must get a catalog line");
for (const pattern of authoredPatterns) {
  const line = catalogLines.find((entry) => entry.startsWith(`- ${pattern.id} |`));
  assert.ok(line, `patterns.yml record ${pattern.id} is missing from the catalog`);
  for (const field of ["detection_cues", "false_positive_traps"]) {
    for (const sentence of pattern[field] ?? []) {
      assert.ok(
        line.includes(String(sentence).replace(/\s+/g, " ").trim()),
        `${pattern.id}: the Examiner never sees this ${field} sentence: ${sentence}`,
      );
    }
  }
}
assert.ok(
  catalogLines.some(
    (line) =>
      line.startsWith("- daily-price-framing |") &&
      line.includes("must inspect smaller text"),
  ),
  "daily-price-framing must reach the Examiner with the cue that names a per-day plan card",
);
const examinerSystem = kb.examinerWorkflowSystemPrompt();
assert.ok(examinerSystem.includes(catalog), "catalog must reach the cacheable Examiner system prompt");
assert.ok(
  examinerSystem.includes("covered-online-negative-option-transaction"),
  "allowed factual-gate tokens must reach the Examiner instructions",
);

const exactFacts = kb.normalizeFactualGateInput([
  "invitation-to-purchase",
  "recurring-or-total-price-less-prominent",
]);
assert.deepEqual(exactFacts.state.confirmed, [
  "invitation-to-purchase",
  "recurring-or-total-price-less-prominent",
]);
const proseFacts = kb.normalizeFactualGateInput({ confirmed: ["invitation to purchase"] });
assert.deepEqual(proseFacts.state.confirmed, []);
assert.ok(proseFacts.warnings.some((warning) => warning.includes("unrecognized")));
const conflictedFacts = kb.normalizeFactualGateInput({
  confirmed: ["consumer-subscription"],
  rejected: ["consumer-subscription"],
});
assert.deepEqual(conflictedFacts.state.confirmed, []);
assert.deepEqual(conflictedFacts.state.rejected, []);
assert.deepEqual(conflictedFacts.state.unknown, ["consumer-subscription"]);

assert.deepEqual(jurisdictions.partitionRequestedJurisdictions(["US", "OTHER", "UK"]), {
  supported: ["US", "UK"],
  unsupported: ["OTHER"],
});
assert.deepEqual(jurisdictions.partitionRequestedJurisdictions(["OTHER"]), {
  supported: [],
  unsupported: ["OTHER"],
});

const ukContext = await kb.buildEvaluationContext({
  patterns: ["hidden-renewal"],
  jurisdictions: ["UK"],
});
const ukCounsel = contextBoundary.trimContextForCounsel(ukContext, ["UK"]);
const ukAuthorities = ukCounsel.patterns[0].applies_to_norms;
assert.ok(ukAuthorities.length >= 1 && ukAuthorities.every((item) => item.jurisdiction === "UK"));
assert.ok(ukAuthorities.every((item) => item.applicability.includes("Conditional candidate")));
assert.ok(!JSON.stringify(ukCounsel).includes("ROSCA"), "UK-only context must not rebuild US ROSCA");

const euContext = await kb.buildEvaluationContext({
  patterns: ["hidden-renewal"],
  jurisdictions: ["EU"],
});
const euCounsel = contextBoundary.trimContextForCounsel(euContext, ["EU"]);
assert.ok(
  euCounsel.patterns[0].applies_to_norms.every((item) => item.jurisdiction === "EU"),
  "EU-only context must retain only routed EU authorities",
);

const roscaFacts = {
  confirmed: [
    "covered-online-negative-option-transaction",
    "billing-information-requested-in-flow",
    "negative-option-terms-omitted-or-subordinated-at-billing-point",
  ],
  rejected: [],
  unknown: [],
};
const usContext = await kb.buildEvaluationContext({
  patterns: ["hidden-renewal"],
  jurisdictions: ["US"],
  facts: roscaFacts,
});
assert.deepEqual(contextBoundary.selectedSupportedMaterialNormIds(usContext), ["us-rosca-4-1"]);
const usCounsel = contextBoundary.trimContextForCounsel(usContext, ["US"]);
assert.ok(
  usCounsel.patterns[0].applies_to_norms.some(
    (item) => item.authority.includes("ROSCA Section 4(1)") && item.applicability.startsWith("Supported"),
  ),
  "confirmed US negative-option facts must preserve the routed supported authority",
);

const mixedContext = await kb.buildEvaluationContext({
  patterns: ["hidden-renewal"],
  jurisdictions: ["US", "EU", "UK", "OTHER"],
  facts: roscaFacts,
});
assert.deepEqual(mixedContext.request.jurisdictions, ["US", "EU", "UK"]);
const mixedCounsel = contextBoundary.trimContextForCounsel(mixedContext, ["US", "EU", "UK"]);
const mixedAuthorities = mixedCounsel.patterns[0].applies_to_norms;
assert.deepEqual(
  new Set(mixedAuthorities.map((item) => item.jurisdiction)),
  new Set(["US", "EU", "UK"]),
);
assert.equal(
  mixedAuthorities.length,
  new Set(mixedAuthorities.map((item) => item.authority)).size,
  "mixed routed authorities must be deduplicated by human-readable authority",
);

const trimmedText = JSON.stringify(mixedCounsel);
for (const id of [...kb.knownPatternIds(), ...kb.knownNormIds()]) {
  assert.ok(!trimmedText.includes(id), `Counsel working set leaked internal taxonomy id ${id}`);
}
await assert.rejects(
  () => kb.buildEvaluationContext({ patterns: ["hidden-renewal"], jurisdictions: ["OTHER"] }),
  /supports US, EU, and UK/,
  "OTHER-only must stop before the router process is started",
);

const validReport = readFileSync(
  join(process.env.KB_ROOT, "eval", "report_samples", "2026-07-14-us-negative-option-standard.md"),
  "utf8",
);
assert.equal((await kb.validateLiveReport(validReport, ["us-rosca-4-1"])).ok, true);
const outsideSlice = await kb.validateLiveReport(validReport, ["us-ftc-5a"]);
assert.equal(outsideSlice.ok, false);
assert.ok(outsideSlice.output.includes("outside the routed legal slice"));
assert.ok(!outsideSlice.output.includes("us-rosca-4-1"), "validator complaint must not leak norm ids");

// Conditional-citation discipline: the same norm moved to the conditional
// list is rejected without the disclosed condition (the sample's Confidence
// line has no 'conditional on' clause), so two-tier citability cannot relax
// into free citation of unrouted authorities.
const conditionalWithoutClause = await kb.validateLiveReport(validReport, [], ["us-rosca-4-1"]);
assert.equal(conditionalWithoutClause.ok, false);
assert.ok(conditionalWithoutClause.output.includes("conditional on"));
const conditionalReport = validReport.replace(
  /Confidence and limitations: Medium - [^\n]+/,
  "Confidence and limitations: Medium - conditional on covered-transaction status and pre-billing disclosure timing, which the screen does not establish.",
);
assert.equal((await kb.validateLiveReport(conditionalReport, [], ["us-rosca-4-1"])).ok, true);
const missingUnsupportedDisclosure = await kb.validateLiveReport(
  validReport,
  ["us-rosca-4-1"],
  [],
  true,
);
assert.equal(missingUnsupportedDisclosure.ok, false);
assert.ok(missingUnsupportedDisclosure.output.includes("unsupported-jurisdiction exclusion disclosure"));

console.log(
  `council boundaries: PASS (${catalogLines.length} patterns; catalog ${catalogBytes} bytes; ` +
    `patterns.yml ${sourceBytes} bytes; ${(100 * catalogBytes / sourceBytes).toFixed(1)}% of source)`,
);
