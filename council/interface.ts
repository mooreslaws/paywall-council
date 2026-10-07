// The ONLY contract the web app knows about the Council (spec §4.1).
// The app never hardcodes agent logic; modules implement CouncilModule and
// are selected via COUNCIL_MODULE (decision #2: modules live in this repo).
//
// Shapes follow Public Report Contract v3 (kb/applaw/references/
// report-contract.md). Three things changed from the v1.3/v2 interface:
//
//   1. Risk is a five-level label. The 1-100 score is still calculated, but
//      v3 lists a public numeric score under "Prohibited Public Content", so
//      it stays in `privateScore` and must never reach the UI.
//   2. Liability is no longer a string on a finding. It is its own block,
//      linked to findings in both directions, because v3 forbids remedies,
//      penalties and estimates inside a finding.
//   3. The report carries three closing sections and, for an unresolved
//      review module, a follow-up question that can produce a revised report.
//
// Deviation from the v1.3 interface text, per decision #8: the module
// receives `screenshots[]`: the original re-encoded into one ≤1568px image
// or several vertical tiles for tall stitches (lib/images.examinerImages).

export type RiskLabel = "very low" | "low" | "medium" | "high" | "very high";

export const RISK_LABELS: readonly RiskLabel[] = [
  "very low",
  "low",
  "medium",
  "high",
  "very high",
] as const;

// Deterministic mapping defined by references/scoring-rubric.md. Exported so
// the app can assert a module honoured it rather than trusting the label.
export function riskFromScore(score: number): RiskLabel {
  if (score <= 15) return "very low";
  if (score <= 30) return "low";
  if (score <= 60) return "medium";
  if (score <= 80) return "high";
  return "very high";
}

export type ReviewAnswer = "yes" | "no" | "unknown";

// OTHER is an intake value, not a legal jurisdiction. Keep the routable set
// next to the Council contract so the web runner and the real module apply the
// same defensive partition without teaching the KB a worldwide fallback.
export const ROUTABLE_JURISDICTIONS = ["US", "EU", "UK"] as const;
export type RoutableJurisdiction = (typeof ROUTABLE_JURISDICTIONS)[number];

export function partitionRequestedJurisdictions(markets: readonly string[]): {
  supported: string[];
  unsupported: string[];
} {
  const supported: string[] = [];
  const unsupported: string[] = [];
  for (const raw of markets) {
    const value = String(raw).trim().toUpperCase();
    if (!value) continue;
    const isEuCountryAlias = /^EU(?::|-)(?:FR|FRANCE|NL|NETHERLANDS)$/.test(value);
    if ((ROUTABLE_JURISDICTIONS as readonly string[]).includes(value) || isEuCountryAlias) {
      if (!supported.includes(value)) supported.push(value);
    } else if (!unsupported.includes(value)) {
      unsupported.push(value);
    }
  }
  return { supported, unsupported };
}

export interface CouncilSubmission {
  markets: string[];
  // Intake values such as OTHER that were explicitly excluded before legal
  // routing. They may be disclosed as unsupported, never as assessed scope.
  excludedMarkets?: string[];
  hooks: string[];
  description?: string;
  extraCharges: { declared: boolean; details?: string };
  cancellation: string;
  // `slice` says which fraction of the whole screenshot this image is, so
  // element boxes reported inside a tile can be mapped back onto the page the
  // user uploaded. A single untiled image is the whole page.
  screenshots: { buffer: Buffer; mime: string; slice?: { y: number; h: number } }[];
  // True when lib/images.examinerImages had to crop the bottom of an
  // unusually tall full-page capture even after widening tiles. Long
  // scroll-captured funnels keep reviews, awards, press logos, before/after,
  // and money-back guarantee sections BELOW the price/CTA, so a silent crop
  // was reliably removing exactly the evidence those pattern families need.
  // The module must disclose this in Missing Context, not just drop it.
  screenshotCoverageLimited?: boolean;
  // Present only on the revision round (§ Review-Module Follow-Up And
  // Revision). Answering re-runs the whole rubric; it is not a score delta.
  reviewAnswers?: { module: string; answer: ReviewAnswer; evidence?: string }[];
}

export type CouncilAgentStatus = "waiting" | "deliberating" | "done" | "failed";

export interface CouncilStageEvent {
  agent: string;
  status: CouncilAgentStatus;
}

// One "### F<n> - <title>" block.
// What the Examiner read, with where it read it. Coordinates are fractions
// of the WHOLE submitted screenshot (0..1), never of a tile, so the interface
// can draw them at any display size without knowing how the image was sliced.
export interface ScreenElement {
  id: string;
  kind:
    | "button"
    | "badge"
    | "price"
    | "toggle"
    | "checkbox"
    | "timer"
    | "image"
    | "fine_print"
    | "phrase"
    | "text";
  text: string;
  box: { x: number; y: number; w: number; h: number };
  confidence: number;
}

// "bracket" is no longer produced (council/skill/marks.ts); reports stored
// before 2026-10-04 still carry it, and the screens draw it as a circle.
export type MarkKind = "circle" | "underline" | "bracket" | "highlight";

export interface FindingMark {
  kind: MarkKind;
  box: { x: number; y: number; w: number; h: number };
  // One mark per finding carries its label; the rest are drawn quietly.
  primary: boolean;
  elementId: string;
}

export interface CouncilFinding {
  ref: string; // "F1"
  title: string;
  severity: "high" | "medium";
  observedEvidence: string;
  pattern: string;
  riskExplanation: string;
  applicableNorm: string;
  comparableAuthority: string;
  liabilityRefs: string[]; // -> CouncilLiabilityBlock.ref
  confidence: "High" | "Medium";
  confidenceLimits: string;
  recommendedCorrection: string;
  // Added after the report parses, by matching the finding's own words back
  // to the elements the Examiner reported. Absent when nothing matched, which
  // is a deliberate silence rather than a guess.
  marks?: FindingMark[];
  elementIds?: string[];
}

// One "### L<n> - <jurisdiction and exposure category>" block. v3 keeps
// statutory ceiling, observed outcome and case-specific estimate apart, so
// they stay separate fields here rather than one prose blob.
export interface CouncilLiabilityBlock {
  ref: string; // "L1"
  title: string;
  findingRefs: string[]; // -> CouncilFinding.ref
  liabilityTrigger: string;
  consumerRemedies: string;
  publicEnforcement: string;
  privateExposure: string;
  monetaryExposure: string;
  observedBenchmark: string;
  nonMonetaryOrders: string;
  authorityCitations: string;
  estimateStatus: string;
}

// An unresolved social/review-platform module. The question text is fixed by
// the contract and the validator accepts only that exact wording.
export interface CouncilReviewQuestion {
  module: string;
  question: string;
}

export interface CouncilUsage {
  agent: string;
  model: string;
  inputTokens: number;
  outputTokens: number;
  // Prompt-cache traffic bills at different rates (write ~1.25x input, read
  // ~0.1x input), so once the module caches its system prompts these must be
  // carried or the budget cap and cost telemetry undercount reality.
  cacheCreationInputTokens?: number;
  cacheReadInputTokens?: number;
}

export interface CouncilResult {
  risk: RiskLabel;
  // What the scope gate decided. The knowledge base already defines the short
  // report a non-checkout screen gets, and the engine already produces it;
  // what was missing was any way for the product to know that is what it is
  // looking at, and therefore to give the round back.
  scope: "checkout_or_pricing" | "non_checkout";
  // Private by contract. Persisted for internal metrics and for the revision
  // round; never rendered. Verdict.tsx is not given this field.
  privateScore: number;
  productOrFlow: string;
  assessmentDate: string; // YYYY-MM-DD
  jurisdictionsAssessed: string;
  verdict: string;
  findings: CouncilFinding[];
  // Everything the Examiner read, whether or not a finding points at it. The
  // verdict screen needs the boxes; a later pass may want the inventory.
  elements: ScreenElement[];
  liability: CouncilLiabilityBlock[];
  mitigating: string[];
  // Patterns the review saw that no supplied authority reaches. Never a
  // finding and never a statement of lawfulness: the knowledge base is
  // silent about them, and this is where that silence is made visible.
  observedWithoutNorm: string[];
  missingContext: string[];
  priorityActions: string[];
  disclaimer: string;
  reviewQuestions: CouncilReviewQuestion[];
  // The exact text that passed validate_live_report.py. Stored verbatim so a
  // report can be re-served or re-validated without regenerating it.
  reportMarkdown: string;
  usage: CouncilUsage[];
  // Validator complaints for every draft that was rejected, oldest first
  // (empty when the first draft passed). A rejected draft costs a full report
  // regeneration, so which rules bite is the single most useful signal for
  // tuning the report stage: without this it is invisible after the run.
  validationComplaints: string[];
  // What the deterministic legal layer offered the report stage: the facts the
  // Examiner established and the two authority lists that follow from them.
  // Findings counts alone cannot distinguish "the screen was clean" from "the
  // routing layer withheld every authority": the confusion that hid the Wave 6
  // and Wave 9 regressions behind healthy pass-rate, latency and cost numbers.
  routing: CouncilRoutingTrace;
}

export interface CouncilRoutingTrace {
  confirmedFacts: string[];
  rejectedFacts: string[];
  candidatePatterns: string[];
  establishedAuthorityIds: string[];
  conditionalAuthorityIds: string[];
}

export interface CouncilModule {
  run(
    sub: CouncilSubmission,
    opts: {
      budgetUsd: number;
      onStage: (e: CouncilStageEvent) => void;
      // The runner's deadline. A module passes it to every model call so a
      // stalled provider ends the run inside the stale window, rather than
      // running on after the janitor has already settled the check.
      signal?: AbortSignal;
    },
  ): Promise<CouncilResult>;
}

// How a run that throws should be treated by the runner.
//
//   budget     the spend crossed the cap: aborted_budget, never retried
//   final      the same input fails the same way again (a truncated draft,
//              a report the validator rejected three times, a jurisdiction
//              the KB does not cover, a model with no price): failed, not
//              retried, because a retry only pays for the failure again
//   transient  anything else (a provider error, a malformed reply): retried
//
// The usage is what the run had already spent when it threw. Without it a
// failed run looked free: its cost never reached checks.cost_usd, so the
// daily caps could not see it.
export type CouncilFailureKind = "budget" | "final" | "transient";

export class CouncilRunError extends Error {
  readonly kind: CouncilFailureKind;
  usage: CouncilUsage[];

  constructor(message: string, kind: CouncilFailureKind, usage: CouncilUsage[] = []) {
    super(message);
    this.name = "CouncilRunError";
    this.kind = kind;
    this.usage = usage;
  }
}

// Read by shape rather than instanceof: the runner and a module can end up
// holding two copies of this class (the eval scripts load a separately
// compiled engine), and a plain Error from anywhere is a transient.
export function readCouncilFailure(e: unknown): { kind: CouncilFailureKind; usage: CouncilUsage[] } {
  const err = e as { kind?: unknown; usage?: unknown } | null;
  const kind =
    err && (err.kind === "budget" || err.kind === "final" || err.kind === "transient")
      ? err.kind
      : "transient";
  const usage = err && Array.isArray(err.usage) ? (err.usage as CouncilUsage[]) : [];
  return { kind, usage };
}

// The bench (§4): display order and roles. These are the A0-A8 stages of
// references/evaluation-workflow.md: the v0.5.0 core decomposes the work by
// pattern family and jurisdiction rather than into numbered judges.
export const COUNCIL_AGENTS = [
  { key: "scope_gate", seal: "A0", name: "Scope gate", role: "Is this a checkout screen?", wide: true },
  { key: "examiner", seal: "Ex", name: "Examiner", role: "Reads the screenshots · vision", wide: true },
  { key: "pattern_disclosure", seal: "I", name: "Disclosure", role: "Price & terms visibility", wide: false },
  { key: "pattern_consent", seal: "II", name: "Consent", role: "Preselection & agreement", wide: false },
  { key: "pattern_pressure", seal: "III", name: "Pressure", role: "Urgency & scarcity", wide: false },
  { key: "pattern_upsell", seal: "IV", name: "Upsell", role: "Add-ons & bundling", wide: false },
  { key: "pattern_cancellation", seal: "V", name: "Cancellation", role: "Exit path", wide: false },
  { key: "legal_dossier", seal: "LD", name: "Legal dossier", role: "Routes norms · cites or abstains", wide: true },
  { key: "counsel", seal: "CO", name: "Counsel", role: "Synthesis · writes the report", wide: true },
  { key: "validator", seal: "OK", name: "Validator", role: "Checks the report before release", wide: true },
] as const;

export type CouncilAgentKey = (typeof COUNCIL_AGENTS)[number]["key"];
