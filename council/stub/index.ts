// Local stub Council (spec §4.1b): deterministic fixture verdicts so the
// whole product works end-to-end before the real module is wired (M5b).
//
// Deterministic: the same submission always yields the same verdict (hash of
// hooks+markets). Hidden dev triggers: anywhere in the description:
//   #very-low / #low / #medium / #high / #very-high → force that risk label
//   #review                       → attach an unresolved review module
//   #budget-bomb                  → report usage that busts the $1.00 cap
//   #fail-bomb                    → throw (exercises retries → failed screen)
// These live only in the stub module and disappear with the real Council.
// (The §0.7 "no demo outcome toggle" rule is about product UI, untouched.)
//
// Shapes follow Report Contract v3: findings carry no remedies or penalties,
// those live in liability blocks, and the numeric score stays private.
import type {
  CouncilFinding,
  CouncilLiabilityBlock,
  CouncilModule,
  CouncilResult,
  CouncilSubmission,
  CouncilUsage,
  RiskLabel,
  ScreenElement,
} from "../interface";
import { COUNCIL_AGENTS, CouncilRunError, riskFromScore } from "../interface";
import { attachMarks } from "../skill/marks";
import { COUNCIL_MODEL } from "@/config/models";

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

// The elements of the paywall the fixtures describe, so the offline path
// exercises the finding-to-element matcher rather than only the live one.
// Text here must keep matching the fixture findings' observed evidence: the
// matcher ties a finding to an element only when it quotes a run of the
// element's words, so a paraphrase ("a discounted amount") draws nothing.
const STUB_ELEMENTS: ScreenElement[] = [
  { id: "el-01", kind: "timer", text: "Your discount expires in 09:57", box: { x: 0.04, y: 0.02, w: 0.92, h: 0.04 }, confidence: 0.95 },
  { id: "el-02", kind: "badge", text: "97% choose this", box: { x: 0.08, y: 0.22, w: 0.34, h: 0.04 }, confidence: 0.9 },
  { id: "el-03", kind: "price", text: "$0.44 per day", box: { x: 0.55, y: 0.25, w: 0.35, h: 0.08 }, confidence: 0.93 },
  { id: "el-04", kind: "phrase", text: "billed as $159.99 yearly", box: { x: 0.08, y: 0.33, w: 0.5, h: 0.03 }, confidence: 0.88 },
  { id: "el-05", kind: "checkbox", text: "Personal coach +$9.99/mo", box: { x: 0.06, y: 0.52, w: 0.88, h: 0.08 }, confidence: 0.91 },
  { id: "el-06", kind: "button", text: "Get my plan", box: { x: 0.06, y: 0.64, w: 0.88, h: 0.07 }, confidence: 0.97 },
  { id: "el-07", kind: "fine_print", text: "renews automatically at $159.99 every 12 months, until cancelled", box: { x: 0.06, y: 0.75, w: 0.88, h: 0.09 }, confidence: 0.86 },
];

function hash(s: string): number {
  let h = 5381;
  for (let i = 0; i < s.length; i++) h = ((h << 5) + h + s.charCodeAt(i)) >>> 0;
  return h;
}

const REVIEW_QUESTION =
  "Are the displayed social-platform reviews or testimonials fake, fabricated, " +
  "purchased, or presented without a genuine underlying customer experience? " +
  "Reply Yes, No, or Unknown. If No, you may optionally provide the original " +
  "post, review-page, platform ID, or official-widget confirmation.";

function findingFixtures(risk: RiskLabel): CouncilFinding[] {
  const base: CouncilFinding[] = [
    {
      ref: "F1",
      title: "Renewal price is not disclosed before billing information",
      severity: "high",
      observedEvidence:
        'The plan block leads with "$0.44 per day"; the recurring charge appears only as "renews automatically at $159.99 every 12 months, until cancelled", in smaller text placed after the payment control.',
      pattern: "Hidden renewal; delayed price disclosure",
      riskExplanation:
        "The primary commercial impression leaves the shopper without equal prominence for the recurring amount before enrollment.",
      applicableNorm:
        "Restore Online Shoppers' Confidence Act, section 4(1), requires clear and conspicuous disclosure of material negative-option terms before billing information is obtained.",
      comparableAuthority:
        "FTC v. Vonage, entered court order, addressed recurring enrollment and cancellation practices; the comparison is limited to interface themes and posture.",
      liabilityRefs: ["L1"],
      confidence: "Medium",
      confidenceLimits:
        "The pricing hierarchy is visible, but the final billing screen and consent record were not supplied.",
      recommendedCorrection:
        "Show the total initial charge, the recurring charge, the cadence and the cancellation method with equal prominence before billing information is collected.",
    },
    {
      ref: "F2",
      title: "Countdown implies a deadline the offer does not have",
      severity: "medium",
      observedEvidence:
        'A countdown, "Your discount expires in 09:57", sits beside the plan cards and restarts on reload, while the discount remains available afterwards.',
      pattern: "Manufactured urgency",
      riskExplanation:
        "A deadline that does not bind can push a decision before the shopper reads the recurring terms placed below it.",
      applicableNorm:
        "FTC Act section 5(a) prohibits unfair or deceptive acts or practices in or affecting commerce.",
      comparableAuthority:
        "Canal Digital Danmark, judgment, treated obscured subscription economics as a misleading practice; non-monetary outcome.",
      liabilityRefs: ["L1"],
      confidence: "Medium",
      confidenceLimits:
        "Timer behaviour across sessions was inferred from a single capture.",
      recommendedCorrection:
        "Remove the countdown, or make it reflect a real deadline and keep the renewal terms equally prominent beside it.",
    },
  ];
  if (risk === "very high") return base;
  if (risk === "high" || risk === "medium") return base.slice(0, risk === "high" ? 2 : 1);
  return [];
}

function liabilityFixtures(findings: CouncilFinding[]): CouncilLiabilityBlock[] {
  if (findings.length === 0) return [];
  return [
    {
      ref: "L1",
      title: "United States online negative-option exposure",
      findingRefs: findings.map((f) => f.ref),
      liabilityTrigger:
        "A covered online negative-option seller fails to disclose material recurring terms before billing information, obtain express informed consent, or provide a simple stop mechanism, with coverage established.",
      consumerRemedies:
        "Consumer redress or refunds may be available through authorized federal or state routes when their statutory predicates are proven.",
      publicEnforcement:
        "The Federal Trade Commission may pursue covered violations through the applicable federal enforcement route.",
      privateExposure:
        "The federal statute does not itself create a standalone private action; state-law or contract claims require separate analysis.",
      monetaryExposure:
        "Statutory ceiling - not an expected outcome: no verified ceiling is selected for this report; any amount depends on the applicable predicate and proven violation unit.",
      observedBenchmark: "None identified.",
      nonMonetaryOrders:
        "Clear recurring terms, express consent, direct cancellation, confirmations, refunds, monitoring or reporting may be ordered when authorized.",
      authorityCitations:
        "Restore Online Shoppers' Confidence Act, section 4; Federal Trade Commission Act sections 5 and 19.",
      estimateStatus:
        "Estimate status: Not estimable from the supplied interface and business data. Final billing, consumers, charges, duration, cancellation performance, injury and revenue are unknown.",
    },
  ];
}

// The exact section order of report-contract.md, so "Copy report" produces
// something the live validator would recognise.
function renderReport(
  r: Omit<CouncilResult, "reportMarkdown" | "usage" | "validationComplaints" | "routing">,
): string {
  const lines = [
    `# Checkout-Funnel Risk Assessment: ${r.productOrFlow}`,
    "",
    `Assessment date: ${r.assessmentDate}`,
    `Jurisdictions assessed: ${r.jurisdictionsAssessed}`,
    "",
    "## Assessment Summary",
    "",
    `RISK: ${r.risk}`,
    `Verdict: ${r.verdict}`,
    "",
    "## Material Findings",
    "",
  ];
  if (r.findings.length === 0) {
    lines.push("None.", "");
  } else {
    for (const f of r.findings) {
      lines.push(
        `### ${f.ref} - ${f.title}`,
        "",
        `Severity: ${f.severity === "high" ? "High" : "Medium"}`,
        `Observed evidence: ${f.observedEvidence}`,
        `Pattern: ${f.pattern}`,
        `Risk explanation: ${f.riskExplanation}`,
        `Applicable norm: ${f.applicableNorm}`,
        `Comparable KB authority: ${f.comparableAuthority}`,
        `Linked liability blocks: ${f.liabilityRefs.join(", ")}`,
        `Confidence and limitations: ${f.confidence} - ${f.confidenceLimits}`,
        `Recommended correction: ${f.recommendedCorrection}`,
        "",
      );
    }
  }
  lines.push("## Liability and Consequences", "");
  if (r.liability.length === 0) {
    lines.push("None.", "");
  } else {
    for (const b of r.liability) {
      lines.push(
        `### ${b.ref} - ${b.title}`,
        "",
        `Linked findings: ${b.findingRefs.join(", ")}`,
        `Liability trigger: ${b.liabilityTrigger}`,
        `Consumer or contract remedies: ${b.consumerRemedies}`,
        `Public enforcement: ${b.publicEnforcement}`,
        `Private exposure: ${b.privateExposure}`,
        `Monetary exposure: ${b.monetaryExposure}`,
        `Observed enforcement benchmark: ${b.observedBenchmark}`,
        `Non-monetary orders: ${b.nonMonetaryOrders}`,
        `Authority citations: ${b.authorityCitations}`,
        `Estimate status and limitations: ${b.estimateStatus}`,
        "",
      );
    }
  }
  const block = (title: string, items: string[]) => {
    lines.push(`## ${title}`, "");
    lines.push(items.length ? items.map((i) => `- ${i}`).join("\n") : "None.", "");
  };
  block("Mitigating and Low-Risk Elements", r.mitigating);
  block("Observed Without a Mapped Norm", r.observedWithoutNorm);
  block("Missing Context", r.missingContext);
  block("Priority Actions", r.priorityActions);
  lines.push("## Disclaimer", "", r.disclaimer);
  return lines.join("\n");
}

// A dev trigger for the out-of-scope screen. The live path gets here through
// the scope gate; offline there is no gate to convince.
const OUT_OF_SCOPE_TRIGGER = "#not-paywall";

const FORCED: [string, RiskLabel][] = [
  ["#very-high", "very high"],
  ["#very-low", "very low"],
  ["#high", "high"],
  ["#medium", "medium"],
  ["#low", "low"],
];

const stub: CouncilModule = {
  async run(sub: CouncilSubmission, opts): Promise<CouncilResult> {
    const seed = hash(sub.hooks.join("|") + "::" + sub.markets.join(","));
    const desc = sub.description ?? "";

    const usage: CouncilUsage[] = [];
    const emit = (agent: string, status: "deliberating" | "done") =>
      opts.onStage({ agent, status });
    const record = (agent: string, inTok: number, outTok: number) =>
      usage.push({ agent, model: COUNCIL_MODEL, inputTokens: inTok, outputTokens: outTok });

    emit("scope_gate", "deliberating");
    await sleep(300);
    record("scope_gate", 400, 60);
    emit("scope_gate", "done");

    emit("examiner", "deliberating");
    await sleep(900 + (seed % 300));
    if (desc.includes("#fail-bomb")) {
      // Carries what was spent before the failure, as the real module does,
      // so the offline path shows a failed run's cost reaching the check.
      throw new CouncilRunError("stub: simulated examiner failure (#fail-bomb)", "transient", [
        ...usage,
      ]);
    }
    record("examiner", 2600 + sub.screenshots.length * 1200, 950);
    emit("examiner", "done");

    // Pattern families in parallel (§4.1), staggered so the bench feels alive.
    const specialists = COUNCIL_AGENTS.filter((a) => a.key.startsWith("pattern_"));
    await Promise.all(
      specialists.map(async (s, i) => {
        emit(s.key, "deliberating");
        await sleep(900 + ((seed >> (i + 2)) % 800) + i * 150);
        record(s.key, 1500, 420);
        emit(s.key, "done");
      }),
    );

    for (const key of ["legal_dossier", "counsel", "validator"] as const) {
      emit(key, "deliberating");
      await sleep(600 + (seed % 300));
      record(key, key === "validator" ? 300 : 2400, key === "validator" ? 40 : 700);
      emit(key, "done");
    }

    if (desc.includes("#budget-bomb")) {
      // Blow the cap decisively (≈$1.6 even at intro prices): the app must
      // abort, refund the round and flag the run.
      record("examiner", 400_000, 80_000);
    }

    // Score first, label second: the rubric maps one onto the other, and the
    // app must never invent a label independently of the score.
    let privateScore = 8 + (seed % 92);
    for (const [token, label] of FORCED) {
      if (desc.includes(token)) {
        privateScore = { "very low": 8, low: 22, medium: 45, high: 72, "very high": 90 }[label];
        break;
      }
    }
    const risk = riskFromScore(privateScore);

    const findings = findingFixtures(risk);
    const liability = liabilityFixtures(findings);
    const reviewQuestions = desc.includes("#review")
      ? [{ module: "Instagram testimonial carousel", question: REVIEW_QUESTION }]
      : [];

    const core = {
      risk,
      privateScore,
      productOrFlow: sub.hooks[0] ?? "Checkout",
      assessmentDate: new Date().toISOString().slice(0, 10),
      // #no-jurisdiction forces the state the real engine reaches when it
      // cannot pin a market: findings come back empty because nothing was
      // measured, which the verdict must not present as a clean pass.
      jurisdictionsAssessed:
        sub.markets.length && !desc.includes("#no-jurisdiction")
          ? sub.markets.join(", ")
          : "Not established; no jurisdiction-specific legal conclusion was made.",
      verdict:
        findings.length === 0
          ? "The supplied screen discloses its price, cadence and cancellation route where the shopper decides, and nothing material was left unresolved under the stated scope."
          : "The checkout foregrounds a low introductory price while the recurring charge sits below the payment control. Under the stated scope the interface supports a material negative-option disclosure concern.",
      findings,
      liability,
      mitigating:
        findings.length === 0
          ? ["Price, cadence and total appear together above the payment control."]
          : ["The page states a recurring amount rather than omitting renewal entirely."],
      observedWithoutNorm: [],
      missingContext: [
        "The final payment-review screen and express-consent record were not supplied.",
        "The complete cancellation path and post-cancellation billing behaviour were not supplied.",
      ],
      priorityActions:
        findings.length === 0
          ? ["Keep the current disclosure placement when the plan table changes."]
          : [
              "Put the full initial and recurring economics beside the purchase action before billing information is collected.",
              "Obtain an express, separate acknowledgement of the recurring obligation.",
              "Provide direct online cancellation with immediate durable confirmation.",
            ],
      disclaimer:
        "This report is a risk assessment based on the supplied interface and available context. It is not legal advice.",
      reviewQuestions,
      elements: STUB_ELEMENTS,
      scope: desc.includes(OUT_OF_SCOPE_TRIGGER)
        ? ("non_checkout" as const)
        : ("checkout_or_pricing" as const),
    };

    // The stub never runs the validator, so it has no complaints to report,
    // and it does no routing, so the trace is empty rather than absent:
    // consumers can read result.routing without a provider-specific branch.
    attachMarks(core.findings, STUB_ELEMENTS);
    return {
      ...core,
      reportMarkdown: renderReport(core),
      usage,
      validationComplaints: [],
      routing: {
        confirmedFacts: [],
        rejectedFacts: [],
        candidatePatterns: [],
        establishedAuthorityIds: [],
        conditionalAuthorityIds: [],
      },
    };
  },
};

export default stub;
