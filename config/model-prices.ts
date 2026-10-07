// USD per million tokens. The ONLY place prices live (§8) - never inline them.
//
// Every rate below was read from the vendor's own pricing page on 2026-09-26.
// Prompt-cache traffic bills at its own rates: a cache write costs 1.25x the
// base input price and a cache read 0.1x, on both vendors at these rates.
// costUsd below applies both multipliers, and it is the one formula the app
// uses, so the runner's recorded cost, the engine's in-run budget check and
// the daily spend caps all count the same money. Two models read their cache
// cheaper than 0.1x (Fable 5.1 at 0.025x, Opus 5.5 at 0.05x). Fable is not
// priced here. Opus 5.5 is, for waves that pin it, and costUsd charges its
// cache reads at the shared 0.1x: that overstates an Opus run, which is the
// safe direction for a cap, and an exact figure means giving it its own
// multiplier.

export const PRICES = {
  // platform.claude.com/docs/en/about-claude/pricing, read 2026-09-26.
  // The $2/$10 launch rate was announced as introductory through 2026-08-31
  // with a rise to $3/$15 on 2026-09-01. Anthropic CANCELLED that rise and
  // made $2/$10 the standard price. The engine had been billing every run
  // after 1 September at the increase that never happened, overstating the
  // cost of each wave by exactly half.
  // Sonnet 5.5 is priced identically to Sonnet 5, $2/$10, with the standard
  // 0.1x cache read. Read from the vendor page 2026-09-29.
  "claude-sonnet-5-5": { inputPerMTok: 2, outputPerMTok: 10 },
  "claude-sonnet-5": { inputPerMTok: 2, outputPerMTok: 10 },
  "claude-opus-5-5": { inputPerMTok: 4, outputPerMTok: 20 },
  // developers.openai.com/api/docs/pricing, read 2026-09-26.
  "gpt-6-sol": { inputPerMTok: 2, outputPerMTok: 10 },
  "gpt-6-luna": { inputPerMTok: 0.1, outputPerMTok: 0.5 },
  "gpt-5.5": { inputPerMTok: 5, outputPerMTok: 30 },
  "gpt-5.4-nano": { inputPerMTok: 0.2, outputPerMTok: 1.25 },
} as const;

export type PricedModel = keyof typeof PRICES;

// Multipliers on the base input price. OpenAI bills no separate cache write,
// and its adapter reports zero write tokens, so the write rate never reaches
// an OpenAI run.
export const CACHE_WRITE_MULTIPLIER = 1.25;
export const CACHE_READ_MULTIPLIER = 0.1;

// Undefined for a model with no price. A wave can pin a dated snapshot id
// through ANTHROPIC_CHAT_MODEL or OPENAI_CHAT_MODEL, and those ids are never
// listed here, so callers have to be able to ask before they spend.
export function priceFor(model: string): (typeof PRICES)[PricedModel] | undefined {
  return (PRICES as Record<string, (typeof PRICES)[PricedModel]>)[model];
}

export interface TokenUsage {
  // Uncached input only. Anthropic reports it that way and the OpenAI
  // adapter normalises to the same meaning.
  inputTokens: number;
  outputTokens: number;
  cacheCreationInputTokens?: number;
  cacheReadInputTokens?: number;
}

export function costUsd(model: string, usage: TokenUsage): number {
  const p = priceFor(model);
  if (!p) throw new Error(`no price registered for model ${model} in config/model-prices.ts`);
  return (
    (usage.inputTokens * p.inputPerMTok +
      (usage.cacheCreationInputTokens ?? 0) * p.inputPerMTok * CACHE_WRITE_MULTIPLIER +
      (usage.cacheReadInputTokens ?? 0) * p.inputPerMTok * CACHE_READ_MULTIPLIER +
      usage.outputTokens * p.outputPerMTok) /
    1_000_000
  );
}
