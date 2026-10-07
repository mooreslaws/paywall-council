// Model-provider adapter for the two Council model calls.
//
// The point of this file is that everything AROUND the model stays identical
// when the provider changes: the same Examiner prompt, the same deterministic
// legal slice, the same Report Contract v3 validator and retry loop. Only the
// wire format differs. That is what makes a cross-provider wave comparable,
// a separate hand-written OpenAI pipeline would be measuring two engines, not
// two models.
//
// Selected by COUNCIL_PROVIDER (default "anthropic"); the model id per
// provider lives in config/models.ts.

import { appendFileSync, readFileSync } from "node:fs";

import Anthropic from "@anthropic-ai/sdk";
import type { AgentEffort, ProviderId } from "@/config/models";

export type { ProviderId };

export interface NeutralImage {
  type: "image";
  mime: string;
  base64: string;
}
export interface NeutralText {
  type: "text";
  text: string;
}
export type NeutralContent = NeutralText | NeutralImage;

export interface NeutralMessage {
  role: "user" | "assistant";
  content: NeutralContent[];
}

export interface ModelCall {
  system: string;
  messages: NeutralMessage[];
  maxTokens: number;
  effort: AgentEffort;
  // Ends the call when the run's deadline passes. Without it a stalled call
  // sat inside the SDK's own ten-minute timeout and two retries.
  signal?: AbortSignal;
}

export interface ModelUsage {
  /** Uncached input tokens only, normalized across providers. */
  inputTokens: number;
  outputTokens: number;
  cacheCreationInputTokens: number;
  cacheReadInputTokens: number;
}

export interface ModelResult {
  text: string;
  /** The response was cut off by the token limit and cannot be salvaged. */
  truncated: boolean;
  usage: ModelUsage;
}

export interface CouncilProvider {
  id: ProviderId;
  model: string;
  call(request: ModelCall): Promise<ModelResult>;
}

// One secrets file holds the keys for every project on this machine, so a bare
// ANTHROPIC_API_KEY there is ambiguous: it does not say which product may
// spend it. A project-scoped name does. The scoped name is read first and the
// bare one still works, which is what keeps CI, the container and any
// checkout that never heard of the convention running unchanged.
function requireKey(names: string[], why: string): string {
  for (const name of names) {
    const value = process.env[name];
    if (value) return value;
  }
  throw new Error(`${why} needs one of ${names.join(", ")}`);
}

// --------------------------------------------------------------- Anthropic

function anthropicContent(content: NeutralContent[]): Anthropic.ContentBlockParam[] {
  return content.map((part) =>
    part.type === "text"
      ? { type: "text" as const, text: part.text }
      : {
          type: "image" as const,
          source: {
            type: "base64" as const,
            media_type: part.mime as "image/png" | "image/jpeg" | "image/webp" | "image/gif",
            data: part.base64,
          },
        },
  );
}

function anthropicProvider(model: string): CouncilProvider {
  const client = new Anthropic({
    apiKey: requireKey(
      ["APPLAW_ANTHROPIC_API_KEY", "APPLAW_API_KEY", "ANTHROPIC_API_KEY"],
      "COUNCIL_MODULE=real on Anthropic",
    ),
  });
  return {
    id: "anthropic",
    model,
    async call({ system, messages, maxTokens, effort, signal }) {
      // Streamed because the SDK's 10-minute timeout wraps the whole body of
      // a non-streamed call, and a heavy-thinking draft can outlast it.
      const msg = await client.messages
        .stream(
          {
            model,
            max_tokens: maxTokens,
            output_config: { effort },
            // The workflow/contract docs are identical for every submission.
            system: [{ type: "text", text: system, cache_control: { type: "ephemeral" } }],
            messages: messages.map((m) => ({ role: m.role, content: anthropicContent(m.content) })),
          },
          { signal },
        )
        .finalMessage();
      const usage = msg.usage;
      return {
        text: msg.content
          .filter((b): b is Anthropic.TextBlock => b.type === "text")
          .map((b) => b.text)
          .join(""),
        truncated: msg.stop_reason === "max_tokens",
        usage: {
          inputTokens: usage.input_tokens,
          outputTokens: usage.output_tokens,
          cacheCreationInputTokens: usage.cache_creation_input_tokens ?? 0,
          cacheReadInputTokens: usage.cache_read_input_tokens ?? 0,
        },
      };
    },
  };
}

// ------------------------------------------------------------------ OpenAI

interface OpenAIChoice {
  message?: { content?: string | null };
  finish_reason?: string;
}
interface OpenAIResponse {
  choices?: OpenAIChoice[];
  usage?: {
    prompt_tokens?: number;
    completion_tokens?: number;
    prompt_tokens_details?: { cached_tokens?: number };
  };
  error?: { message?: string };
}

function openAiContent(content: NeutralContent[]): unknown[] {
  return content.map((part) =>
    part.type === "text"
      ? { type: "text", text: part.text }
      : {
          type: "image_url",
          image_url: { url: `data:${part.mime};base64,${part.base64}` },
        },
  );
}

function openAiProvider(model: string): CouncilProvider {
  const apiKey = requireKey(["APPLAW_OPENAI_API_KEY", "OPENAI_API_KEY"], "COUNCIL_PROVIDER=openai");
  const baseUrl = process.env.OPENAI_BASE_URL ?? "https://api.openai.com/v1";
  return {
    id: "openai",
    model,
    async call({ system, messages, maxTokens, effort, signal }) {
      const body = {
        model,
        // GPT-5-family reasoning models take max_completion_tokens, not
        // max_tokens, and reasoning tokens are billed inside it, same shape
        // of constraint as Anthropic's adaptive thinking sharing max_tokens.
        max_completion_tokens: maxTokens,
        reasoning_effort: effort,
        messages: [
          // OpenAI caches long prefixes automatically; there is no explicit
          // cache_control to set, so the system prompt is just message zero.
          { role: "system", content: system },
          ...messages.map((m) => ({ role: m.role, content: openAiContent(m.content) })),
        ],
      };
      const response = await fetch(`${baseUrl}/chat/completions`, {
        method: "POST",
        headers: { "content-type": "application/json", authorization: `Bearer ${apiKey}` },
        body: JSON.stringify(body),
        signal,
      });
      if (!response.ok) {
        // The status travels with the error, as the Anthropic SDK's does:
        // it is what tells a refusal that will repeat from a hiccup.
        throw Object.assign(
          new Error(`OpenAI ${response.status}: ${(await response.text()).slice(0, 400)}`),
          { status: response.status },
        );
      }
      const data = (await response.json()) as OpenAIResponse;
      if (data.error) throw new Error(`OpenAI error: ${data.error.message ?? "unknown"}`);
      const choice = data.choices?.[0];
      const promptTokens = data.usage?.prompt_tokens ?? 0;
      const cachedTokens = data.usage?.prompt_tokens_details?.cached_tokens ?? 0;
      return {
        text: choice?.message?.content ?? "",
        truncated: choice?.finish_reason === "length",
        usage: {
          // OpenAI's prompt_tokens INCLUDES cached tokens; Anthropic's
          // input_tokens excludes them. Normalize to Anthropic's meaning so
          // the shared cost formula stays correct for both.
          inputTokens: Math.max(0, promptTokens - cachedTokens),
          outputTokens: data.usage?.completion_tokens ?? 0,
          // OpenAI does not bill a separate cache-write rate.
          cacheCreationInputTokens: 0,
          cacheReadInputTokens: cachedTokens,
        },
      };
    },
  };
}

// ------------------------------------------------------------------ Replay

// A scripted stand-in for a model, used by `npm run verify:council`.
//
// Until this existed, the orchestration in ./index.ts, the validator retry
// loop, the truncation guards, cost accounting, the stage events the
// deliberation screen renders, and every abstention path, could only be
// executed by paying for real model calls. It was the one part of the engine
// no offline check reached, so its first exercise would have been the first
// live run, on Alexey's key, with a real user waiting.
//
// The seam is deliberately narrow: id, model and therefore pricing stay
// exactly what a live run would use, so cost accounting is exercised for
// real. Only the text comes from a file.
function replayProvider(id: ProviderId, model: string, scriptPath: string): CouncilProvider {
  interface ReplayResponse {
    text?: string;
    truncated?: boolean;
    usage?: Partial<ModelUsage>;
    // The provider turning the request down, the way the SDK reports it: an
    // error carrying the HTTP status. Nothing is billed for it.
    refusal?: { status: number; message: string };
  }
  const script = JSON.parse(readFileSync(scriptPath, "utf8")) as { responses: ReplayResponse[] };
  const queue = [...script.responses];
  const tracePath = process.env.COUNCIL_REPLAY_TRACE;
  let calls = 0;

  return {
    id,
    model,
    async call({ system, messages, maxTokens, effort }) {
      calls += 1;
      // Traced before the queue is checked: an unexpected extra call is
      // itself a finding, and its prompt is what explains why it happened.
      if (tracePath) {
        const last = messages[messages.length - 1];
        appendFileSync(
          tracePath,
          JSON.stringify({
            call: calls,
            systemBytes: system.length,
            maxTokens,
            effort,
            roles: messages.map((m) => m.role),
            // Prompts carry the routed working set and the retry complaint,
            // the things worth asserting on: so they are kept whole.
            texts: messages.map((m) =>
              m.content
                .filter((c): c is NeutralText => c.type === "text")
                .map((c) => c.text)
                .join("\n"),
            ),
            imageCount: messages.reduce(
              (n, m) => n + m.content.filter((c) => c.type === "image").length,
              0,
            ),
          }) + "\n",
          "utf8",
        );
      }
      const next = queue.shift();
      if (!next) {
        // Loudly, rather than hanging or silently replaying the last answer:
        // a scenario that makes an unexpected extra call is itself the bug
        // the harness is looking for.
        throw new Error(
          `replay script ${scriptPath} ran out of responses at call ${calls}; ` +
            `it scripted ${script.responses.length}`,
        );
      }
      if (next.refusal) {
        throw Object.assign(new Error(`${next.refusal.status} ${next.refusal.message}`), {
          status: next.refusal.status,
        });
      }
      return {
        text: next.text ?? "",
        truncated: next.truncated ?? false,
        usage: {
          inputTokens: next.usage?.inputTokens ?? 1000,
          outputTokens: next.usage?.outputTokens ?? 500,
          cacheCreationInputTokens: next.usage?.cacheCreationInputTokens ?? 0,
          cacheReadInputTokens: next.usage?.cacheReadInputTokens ?? 0,
        },
      };
    },
  };
}

export function loadProvider(id: ProviderId, model: string): CouncilProvider {
  const replay = process.env.COUNCIL_REPLAY;
  if (replay) {
    // No escape hatch on purpose. Replaying canned verdicts in production
    // would serve a user a legal assessment no model ever made.
    if (process.env.NODE_ENV === "production") {
      throw new Error("COUNCIL_REPLAY is a test seam and is refused in production builds");
    }
    return replayProvider(id, model, replay);
  }
  return id === "openai" ? openAiProvider(model) : anthropicProvider(model);
}
