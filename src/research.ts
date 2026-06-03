import Anthropic from "@anthropic-ai/sdk";
import type { RunConfig } from "./config.js";
import { researchSystemPrompt, researchUserPrompt } from "./prompts.js";

/**
 * Stage 1 — scan current discourse via web search and return a free-form
 * "angle briefing" the writer stage consumes. Web search runs server-side;
 * we stream (to avoid HTTP timeouts on long search loops) and resume on
 * `pause_turn` until the model finishes.
 */
export async function research(client: Anthropic, cfg: RunConfig): Promise<string> {
  const system: Anthropic.TextBlockParam[] = [
    {
      type: "text",
      text: researchSystemPrompt(cfg),
      cache_control: { type: "ephemeral" },
    },
  ];

  const messages: Anthropic.MessageParam[] = [
    { role: "user", content: researchUserPrompt(cfg) },
  ];

  let lastUsage: Anthropic.Usage | undefined;

  for (let i = 0; i < 6; i++) {
    const stream = client.messages.stream({
      model: cfg.model,
      max_tokens: 8000,
      system,
      messages,
      tools: [{ type: "web_search_20260209", name: "web_search" }],
    });
    const message = await stream.finalMessage();
    lastUsage = message.usage;

    if (message.stop_reason === "pause_turn") {
      // Server-side tool loop hit its iteration cap — append and resume.
      messages.push({ role: "assistant", content: message.content });
      continue;
    }

    const text = message.content
      .filter((b): b is Anthropic.TextBlock => b.type === "text")
      .map((b) => b.text)
      .join("\n")
      .trim();

    if (!text) {
      throw new Error("Research stage returned no text. Check API access / web search availability.");
    }
    logUsage("research", lastUsage);
    return text;
  }

  throw new Error("Research stage did not converge after 6 continuations.");
}

function logUsage(stage: string, usage?: Anthropic.Usage): void {
  if (!usage) return;
  const cached = usage.cache_read_input_tokens ?? 0;
  console.log(
    `[${stage}] in=${usage.input_tokens} cached=${cached} out=${usage.output_tokens}`,
  );
}
