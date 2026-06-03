import Anthropic from "@anthropic-ai/sdk";
import { zodOutputFormat } from "@anthropic-ai/sdk/helpers/zod";
import * as z from "zod/v4";
import type { RunConfig } from "./config.js";
import { writerSystemPrompt, writerUserPrompt } from "./prompts.js";

export const POST_SHAPES = [
  "reframe",
  "validation",
  "micro-insight",
  "practical",
  "question",
] as const;

const PostSchema = z.object({
  text: z.string().describe("The paste-ready post, under 280 characters."),
  shape: z.enum(POST_SHAPES),
  rationale: z
    .string()
    .describe("One line: why this should engage this audience honestly."),
  source_url: z
    .string()
    .nullable()
    .describe("A source URL from the briefing if the post leans on a current fact, else null."),
  sensitivity_flag: z
    .string()
    .nullable()
    .describe("null if the post clears every hard rule; otherwise a short note on the concern."),
});

const OutputSchema = z.object({ posts: z.array(PostSchema) });

export type Post = z.infer<typeof PostSchema>;

/**
 * Stage 2 — turn the briefing into N structured, voice-controlled drafts.
 */
export async function generate(
  client: Anthropic,
  cfg: RunConfig,
  briefing: string,
): Promise<Post[]> {
  const system: Anthropic.TextBlockParam[] = [
    {
      type: "text",
      text: writerSystemPrompt(cfg),
      cache_control: { type: "ephemeral" },
    },
  ];

  const response = await client.messages.parse({
    model: cfg.model,
    max_tokens: 8000,
    system,
    messages: [{ role: "user", content: writerUserPrompt(cfg, briefing) }],
    output_config: { format: zodOutputFormat(OutputSchema) },
  });

  const usage = response.usage;
  console.log(
    `[writer] in=${usage.input_tokens} cached=${usage.cache_read_input_tokens ?? 0} out=${usage.output_tokens}`,
  );

  const parsed = response.parsed_output;
  if (!parsed) {
    throw new Error(
      `Writer stage failed to produce structured output (stop_reason=${response.stop_reason}).`,
    );
  }
  return parsed.posts;
}
