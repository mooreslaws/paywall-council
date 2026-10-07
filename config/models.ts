// Single model across the Council (spec §4, §8; assumption A5).
export const COUNCIL_MODEL = "claude-sonnet-5-5" as const;

// Cross-provider evaluation (added 2026-08-28). The pipeline is provider-
// agnostic: same Examiner prompt, same deterministic legal slice, same
// Report Contract v3 validator, so a wave can be run on another vendor's
// model and compared like for like. COUNCIL_PROVIDER selects the adapter in
// council/skill/provider.ts; anything other than "openai" means Anthropic.
export type ProviderId = "anthropic" | "openai";

export function councilProvider(): ProviderId {
  return process.env.COUNCIL_PROVIDER === "openai" ? "openai" : "anthropic";
}

// The model actually called, per provider. OPENAI_CHAT_MODEL overrides the
// OpenAI default so a wave can pin a specific snapshot. A pinned id needs a
// row in config/model-prices.ts; the engine refuses to start without one
// rather than pay for an Examiner call it cannot cost.
//
// The OpenAI default is NOT the cheapest model on the account. gpt-5.4-nano
// held that slot from the cross-provider work in August and Wave 7 measured
// what it does here: 20/20 reports accepted by the validator, 23s median,
// $1.37, and ZERO findings on a pack where the same code found 8 the same
// day. A recognition engine that accepts every report and reports nothing
// costs less precisely because it does no work, so the default moved to a
// model that can carry the catalog.
export function councilModel(provider: ProviderId = councilProvider()): string {
  if (provider === "openai") return process.env.OPENAI_CHAT_MODEL ?? "gpt-6-sol";
  // Same escape hatch the OpenAI side has had since August: a wave can pin a
  // different Anthropic model without a code change, which is what lets two
  // models run side by side on one build. Production never sets it.
  return process.env.ANTHROPIC_CHAT_MODEL ?? COUNCIL_MODEL;
}

export type AgentEffort = "low" | "medium" | "high";

// Sonnet 5: adaptive thinking is always on and `effort` DEFAULTS TO HIGH on
// the API: every call must pass effort explicitly or the $0.50/round budget
// will not hold (§8). Tune via evals, change here only.
// One key per model call, and the engine makes two. The scope gate and the
// pattern families are read inside the examiner call, and the legal dossier
// and the validator are code, so none of them has an effort of its own: the
// keys they used to have here were never read, and tuning them changed
// nothing.
export const AGENT_EFFORT: { examiner: AgentEffort; counsel: AgentEffort } = {
  examiner: "medium",
  // A/B on the six heaviest live funnels, 2026-08-15, same code (id-free
  // slice, ready-made benchmark citations, streaming): low = 6/6 pass, 5/6
  // first draft, median 81s / $0.13; medium = 6/6 pass, 6/6 first draft,
  // median 141s / $0.19. Medium buys the last retry at +60s on every run;
  // the product target is <=85s per screen, so low stays. Flip to "medium"
  // if first-draft reliability ever outranks latency - both are validated.
  counsel: "low",
};
