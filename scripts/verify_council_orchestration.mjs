// Exercises the real Council orchestration (council/skill/index.ts) offline.
//
// Everything else in the engine already had an offline check, verify:parser
// covers the report parser, verify:boundaries covers retrieval and the
// authority split, kb:reachability covers the norm graph. The orchestration
// itself had none: the validator retry loop, the truncation guards, cost
// accounting, the stage events the deliberation screen renders, and the
// abstention paths could only be executed by paying for real model calls.
// Its first exercise would have been the first live run.
//
// So the model is replaced by a scripted stand-in (COUNCIL_REPLAY, see
// council/skill/provider.ts) and everything around it stays real: the actual
// KB retrieval, the actual Python validator, the actual pricing table.
//
// The counsel drafts are the KB's own report samples rather than reports
// written here, so the fixtures cannot drift from what Misha's validator
// accepts: and one of them (us-negative-option) genuinely fails the
// authority-slice check against an empty routed slice, which is what makes
// the retry scenarios real rejections rather than simulated ones.
//
// Run: npm run verify:council
import assert from "node:assert/strict";
import { mkdirSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { createRequire } from "node:module";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { ensureBenchBuild } from "./bench-build.mjs";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const require = createRequire(import.meta.url);

process.chdir(ROOT); // kb.js resolves the KB from cwd
ensureBenchBuild(ROOT);
const { default: skill } = require(path.join(ROOT, ".bench/council/skill/index.js"));

const SAMPLES = path.join(ROOT, "kb/applaw/eval/report_samples");
const sample = (name) => readFileSync(path.join(SAMPLES, `${name}.md`), "utf8");

// Cites nothing, so it passes the live validator against an empty routed
// slice: the report the engine produces when no authority was reached.
const CLEAN_REPORT = sample("2026-07-11-insufficient-jurisdiction-standard");
// Cites a US negative-option authority. Against an empty slice the validator
// rejects it with "names an authority outside the routed legal slice".
const OFF_SLICE_REPORT = sample("2026-07-14-us-negative-option-standard");

const WORK = path.join(ROOT, ".bench", "replay");
rmSync(WORK, { recursive: true, force: true });
mkdirSync(WORK, { recursive: true });

const BASE_SUBMISSION = {
  markets: ["US"],
  hooks: ["Lose 10 kg in 30 days"],
  description: "Quiz funnel ending on a subscription paywall.",
  extraCharges: { declared: false },
  cancellation: "Cancel any time in the app.",
  screenshots: [{ buffer: Buffer.from("not-a-real-image"), mime: "image/png" }],
};

function examinerJson(overrides = {}) {
  return JSON.stringify({
    scope: "checkout_or_pricing",
    product_or_flow: "Subscription paywall",
    observations: ["A weekly plan is preselected.", "The renewal price is not shown."],
    candidate_patterns: [],
    factual_gates: { confirmed: [], rejected: [], unknown: [], evidence: [] },
    review_modules: [],
    trust_signal_checklist: {
      reviews_or_ratings: false,
      awards_or_badges: false,
      press_or_media_logos: false,
      university_or_clinical_claims: false,
      before_after_or_progress: false,
      forecast_or_results_graph: false,
      money_back_guarantee_claim: false,
      outcome_or_personalization_promise: false,
    },
    ...overrides,
  });
}

let scenarioIndex = 0;

async function run({ responses, submission = {}, budgetUsd = 1 }) {
  scenarioIndex += 1;
  const scriptPath = path.join(WORK, `script-${scenarioIndex}.json`);
  const tracePath = path.join(WORK, `trace-${scenarioIndex}.jsonl`);
  writeFileSync(scriptPath, JSON.stringify({ responses }), "utf8");
  writeFileSync(tracePath, "", "utf8");

  const stages = [];
  process.env.COUNCIL_REPLAY = scriptPath;
  process.env.COUNCIL_REPLAY_TRACE = tracePath;
  let result = null;
  let error = null;
  try {
    result = await skill.run(
      { ...BASE_SUBMISSION, ...submission },
      { budgetUsd, onStage: (e) => stages.push(`${e.agent}:${e.status}`) },
    );
  } catch (e) {
    error = e;
  } finally {
    delete process.env.COUNCIL_REPLAY;
    delete process.env.COUNCIL_REPLAY_TRACE;
  }
  const trace = readFileSync(tracePath, "utf8")
    .split("\n")
    .filter(Boolean)
    .map((l) => JSON.parse(l));
  return { result, error, stages, trace };
}

const checks = [];
const check = (name, fn) => checks.push({ name, fn });

// The runner reads two things off a throw (CouncilRunError in
// council/interface.ts). `kind` decides the outcome: budget ends the check as
// aborted_budget, final as failed, and neither is retried, because the same
// input fails the same way again. `usage` is what the run had already paid
// for, one row per model call, and it is how a failed run reaches the check's
// cost and the daily caps instead of looking free.
function failedAs(error, kind, paidCalls, trace) {
  assert.ok(error, "the run threw");
  assert.equal(error.kind, kind, `error.kind is "${kind}"`);
  assert.ok(Array.isArray(error.usage), "error.usage is a list");
  assert.equal(error.usage.length, paidCalls, `error.usage has one row per paid call (${paidCalls})`);
  assert.equal(error.usage.length, trace.length, "every call the stand-in served is billed");
}

// --------------------------------------------------------------------------

check("happy path: one examiner call, one counsel draft, validator passes", async () => {
  const { result, error, stages, trace } = await run({
    responses: [{ text: examinerJson() }, { text: CLEAN_REPORT }],
  });
  assert.equal(error, null, `unexpected throw: ${error?.message}`);
  assert.equal(trace.length, 2, "exactly two model calls");
  assert.equal(result.validationComplaints.length, 0, "first draft accepted");
  assert.ok(result.risk, "a risk band was parsed");
  // Stored verbatim apart from the one line the module owns: the model has no
  // clock, so the date it writes is a guess and gets corrected to today's.
  const today = new Date().toISOString().slice(0, 10);
  assert.match(result.reportMarkdown, new RegExp(`^Assessment date: ${today}$`, "m"));
  const stripDate = (t) => t.replace(/^Assessment date: \d{4}-\d{2}-\d{2}$/m, "").trim();
  assert.equal(
    stripDate(result.reportMarkdown),
    stripDate(CLEAN_REPORT),
    "nothing else in the validated text is rewritten",
  );
  // The deliberation screen renders these keys; a rename here silently empties it.
  for (const key of [
    "scope_gate",
    "examiner",
    "pattern_disclosure",
    "pattern_consent",
    "pattern_pressure",
    "pattern_upsell",
    "pattern_cancellation",
    "legal_dossier",
    "counsel",
    "validator",
  ]) {
    assert.ok(stages.includes(`${key}:done`), `stage ${key} reported done`);
  }
  assert.deepEqual(
    result.usage.map((u) => u.agent),
    ["examiner", "counsel"],
    "usage is recorded per stage",
  );
  // The examiner is the only stage that receives the screenshots.
  assert.equal(trace[0].imageCount, 1, "the examiner call carries the screenshot");
  assert.equal(trace[1].imageCount, 0, "the counsel call does not");
});

check("a draft with no date line gets one instead of costing a retry", async () => {
  const undated = CLEAN_REPORT.replace(/^Assessment date: \d{4}-\d{2}-\d{2}$/m, "").replace(/\n\n\n/, "\n");
  assert.ok(!/Assessment date:/.test(undated), "the fixture really has no date line");
  const { result, error, trace } = await run({
    responses: [{ text: examinerJson() }, { text: undated }],
  });
  assert.equal(error, null, `unexpected throw: ${error?.message}`);
  assert.equal(trace.length, 2, "no regeneration was spent on a line we know the value of");
  const today = new Date().toISOString().slice(0, 10);
  assert.match(result.reportMarkdown, new RegExp(`^Assessment date: ${today}$`, "m"));
  assert.equal(result.assessmentDate, today, "and the app stores the real date");
});

check("validator rejection is fed back and the second draft is accepted", async () => {
  const { result, error, trace } = await run({
    responses: [{ text: examinerJson() }, { text: OFF_SLICE_REPORT }, { text: CLEAN_REPORT }],
  });
  assert.equal(error, null, `unexpected throw: ${error?.message}`);
  assert.equal(trace.length, 3, "the rejected draft cost one extra call");
  assert.equal(result.validationComplaints.length, 1, "the complaint is reported to the app");
  assert.match(
    result.validationComplaints[0],
    /outside the routed legal slice/,
    "the complaint is the validator's own words",
  );
  assert.deepEqual(
    result.usage.map((u) => u.agent),
    ["examiner", "counsel", "counsel_retry_2"],
    "the retry is billed separately so a wave can see what rejections cost",
  );
  // The retry turn: rejected draft as assistant, complaint as user.
  assert.deepEqual(trace[2].roles, ["user", "assistant", "user"], "the retry replays the conversation");
  assert.match(trace[2].texts[2], /validator rejected that draft/, "the complaint is handed back");
  assert.match(trace[2].texts[2], /Fix ONLY what the complaint identifies/, "the retry is scoped");
});

check("a draft rejected three times fails with the routing diagnostic", async () => {
  const { result, error, stages, trace } = await run({
    responses: [
      { text: examinerJson() },
      { text: OFF_SLICE_REPORT },
      { text: OFF_SLICE_REPORT },
      { text: OFF_SLICE_REPORT },
    ],
  });
  assert.equal(result, null, "no report is returned");
  assert.match(error.message, /failed validation after 3 attempts/);
  // Without these lists a reader cannot tell a hallucination from a routing
  // layer that withheld every candidate: the Wave 6 / Wave 9 confusion.
  assert.match(error.message, /established=\[/);
  assert.match(error.message, /conditional=\[/);
  assert.match(error.message, /patterns=\[/);
  assert.match(error.message, /confirmed=\[/);
  assert.equal(trace.length, 4, "it stops at the attempt cap rather than looping");
  assert.ok(stages.includes("validator:failed"), "the screen is told the validator failed");
  failedAs(error, "final", 4, trace);
  assert.deepEqual(
    error.usage.map((u) => u.agent),
    ["examiner", "counsel", "counsel_retry_2", "counsel_retry_3"],
    "the three rejected drafts are each billed",
  );
});

check("a truncated counsel draft fails with the true cause, without retrying", async () => {
  const { error, stages, trace } = await run({
    responses: [{ text: examinerJson() }, { text: CLEAN_REPORT, truncated: true }],
  });
  assert.match(error.message, /counsel draft hit max_tokens/);
  // A retry under the same limit re-truncates; looping would burn the budget
  // and report a misleading section-order failure instead.
  assert.equal(trace.length, 2, "no retry is attempted");
  assert.ok(stages.includes("validator:failed"));
  failedAs(error, "final", 2, trace);
});

check("a truncated examiner fails before any report is written", async () => {
  const { error, trace } = await run({
    responses: [{ text: examinerJson(), truncated: true }],
  });
  assert.match(error.message, /examiner output hit max_tokens/);
  assert.equal(trace.length, 1, "the counsel stage is never reached");
  failedAs(error, "final", 1, trace);
});

check("an unknown pattern id from the examiner is dropped, not routed", async () => {
  const { result, error } = await run({
    responses: [
      { text: examinerJson({ candidate_patterns: ["totally-made-up-pattern"] }) },
      { text: CLEAN_REPORT },
    ],
  });
  assert.equal(error, null, `unexpected throw: ${error?.message}`);
  assert.deepEqual(result.routing.candidatePatterns, [], "the id never reaches retrieval");
});

check("a present trust signal adds its pattern even when the examiner forgot it", async () => {
  // The Wave 2 regression: fake reviews, awards, press logos, before/after
  // and money-back guarantees were dropped near-uniformly because the
  // examiner filled the checklist but not candidate_patterns.
  const { result, error, trace } = await run({
    responses: [
      {
        text: examinerJson({
          candidate_patterns: [],
          trust_signal_checklist: {
            reviews_or_ratings: true,
            awards_or_badges: false,
            press_or_media_logos: false,
            university_or_clinical_claims: false,
            before_after_or_progress: false,
            forecast_or_results_graph: false,
            money_back_guarantee_claim: true,
            outcome_or_personalization_promise: false,
          },
        }),
      },
      { text: CLEAN_REPORT },
    ],
  });
  assert.equal(error, null, `unexpected throw: ${error?.message}`);
  assert.ok(
    result.routing.candidatePatterns.includes("fake-social-proof"),
    "a visible review module is routed even if the examiner listed no pattern",
  );
  assert.ok(
    result.routing.candidatePatterns.includes("money-back-misdirection"),
    "so is a money-back guarantee claim",
  );
  assert.equal(trace.length, 2);
});

// A refusal is not a reply: nothing is billed for it, so these assert on the
// trace and the kind rather than through failedAs, which pairs every call
// with a usage row.
check("an empty credit balance fails at once, without retrying", async () => {
  const { error, trace } = await run({
    responses: [
      {
        refusal: {
          status: 400,
          message: '{"type":"error","error":{"type":"invalid_request_error","message":"Your credit balance is too low to access the Anthropic API."}}',
        },
      },
    ],
  });
  assert.ok(error, "the run threw");
  assert.equal(error.kind, "final", "a refusal that will repeat is final");
  assert.match(error.message, /credit balance is too low/, "the provider's words reach the alert");
  assert.equal(trace.length, 1, "one call, and no retry inside the engine");
  assert.equal(error.usage.length, 0, "nothing billed for a refused call");
});

check("an overloaded provider is worth another attempt", async () => {
  const { error, trace } = await run({
    responses: [{ refusal: { status: 529, message: "Overloaded" } }],
  });
  assert.ok(error, "the run threw");
  assert.equal(error.kind, "transient", "a 529 may pass on its own");
  assert.equal(trace.length, 1);
});

check("an OTHER-only submission is refused before any model call", async () => {
  const { error, trace } = await run({
    responses: [{ text: examinerJson() }],
    submission: { markets: ["OTHER"] },
  });
  assert.match(error.message, /Unsupported jurisdiction/);
  assert.equal(trace.length, 0, "nothing is spent on an unroutable submission");
  failedAs(error, "final", 0, trace);
});

check("an exhausted budget stops before the report stage", async () => {
  const { error, trace } = await run({
    responses: [{ text: examinerJson() }, { text: CLEAN_REPORT }],
    budgetUsd: 0.0000001,
  });
  assert.match(error.message, /budget exhausted before the report stage/);
  assert.equal(trace.length, 1, "the expensive stage never runs");
  failedAs(error, "budget", 1, trace);
});

check("a budget exhausted mid-retry stops the loop", async () => {
  const { error, stages, trace } = await run({
    responses: [
      { text: examinerJson(), usage: { inputTokens: 1, outputTokens: 1 } },
      // Priced above the cap, but only after the first draft is already paid
      // for: the pre-counsel check cannot see this.
      { text: OFF_SLICE_REPORT, usage: { inputTokens: 5_000_000, outputTokens: 5_000_000 } },
      { text: CLEAN_REPORT },
    ],
    budgetUsd: 0.5,
  });
  assert.match(error.message, /budget exhausted during report validation retries/);
  assert.equal(trace.length, 2, "the retry is not issued");
  assert.ok(stages.includes("validator:failed"));
  failedAs(error, "budget", 2, trace);
});

check("an excluded market makes the validator demand the disclosure", async () => {
  // The same draft that passes in the happy path above is rejected here:
  // selecting OTHER alongside US sets excludedMarkets, which turns on
  // --require-unsupported-jurisdiction-disclosure. This asserts the flag is
  // actually wired from the intake through to the Python validator, a
  // report that quietly implied worldwide coverage would otherwise ship.
  const { error, trace } = await run({
    responses: [
      { text: examinerJson() },
      { text: CLEAN_REPORT },
      { text: CLEAN_REPORT },
      { text: CLEAN_REPORT },
    ],
    submission: { markets: ["US", "OTHER"] },
  });
  assert.match(error.message, /failed validation after 3 attempts/);
  assert.match(error.message, /unsupported-jurisdiction exclusion disclosure/);
  assert.equal(trace.length, 4);
  failedAs(error, "final", 4, trace);
});

check("the replay seam is refused in a production build", async () => {
  // The whole harness rests on this guard: without it, an env var could make
  // a deployed instance serve a canned legal assessment no model ever made.
  const before = process.env.NODE_ENV;
  process.env.NODE_ENV = "production";
  try {
    const { error, trace } = await run({ responses: [{ text: examinerJson() }] });
    assert.match(error.message, /refused in production builds/);
    assert.equal(trace.length, 0, "no scripted response is served");
  } finally {
    if (before === undefined) delete process.env.NODE_ENV;
    else process.env.NODE_ENV = before;
  }
});

// --------------------------------------------------------------------------

let failed = 0;
for (const { name, fn } of checks) {
  try {
    await fn();
    console.log(`ok   ${name}`);
  } catch (e) {
    failed += 1;
    console.log(`FAIL ${name}`);
    console.log(`     ${e.message.split("\n").join("\n     ")}`);
  }
}

console.log(
  `\ncouncil orchestration: ${checks.length - failed}/${checks.length} scenarios clean` +
    ` (${scenarioIndex} replayed runs, no API calls)`,
);
process.exit(failed === 0 ? 0 : 1);
