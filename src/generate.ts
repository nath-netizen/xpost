import { query } from "@anthropic-ai/claude-agent-sdk";
import * as z from "zod";
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
 *
 * Runs on your Claude Code subscription (no API key). The Agent SDK returns
 * free-form text, so we instruct the model to emit a strict JSON object and
 * validate it with the zod schema for type safety.
 */
export async function generate(cfg: RunConfig, briefing: string): Promise<Post[]> {
  const shapes = POST_SHAPES.map((s) => `"${s}"`).join(" | ");
  const jsonContract = [
    "",
    "Output ONLY a single JSON object — no prose, no explanation, no markdown code fences.",
    "It must match exactly this shape:",
    `{ "posts": [ { "text": string, "shape": ${shapes}, "rationale": string, "source_url": string | null, "sensitivity_flag": string | null } ] }`,
    `The "posts" array must contain exactly ${cfg.postCount} items.`,
    'Use null (not the string "null") for source_url / sensitivity_flag when they do not apply.',
  ].join("\n");

  let text = "";
  for await (const message of query({
    prompt: writerUserPrompt(cfg, briefing) + "\n" + jsonContract,
    options: {
      model: cfg.model,
      systemPrompt: writerSystemPrompt(cfg),
      allowedTools: [],
      permissionMode: "default",
      maxTurns: 2,
    },
  })) {
    if (message.type === "result") {
      if (message.subtype === "success") {
        text = message.result;
      } else {
        throw new Error(`Writer stage failed (${message.subtype}).`);
      }
    }
  }

  const parsed = OutputSchema.safeParse(parseJsonObject(text));
  if (!parsed.success) {
    throw new Error(
      `Writer stage did not return valid structured output: ${parsed.error.message}`,
    );
  }
  return parsed.data.posts;
}

/** Pull the JSON object out of the model's reply, tolerating code fences / stray prose. */
function parseJsonObject(text: string): unknown {
  const fenced = text.match(/```(?:json)?\s*([\s\S]*?)```/i);
  const body = fenced?.[1] ?? text;
  const start = body.indexOf("{");
  const end = body.lastIndexOf("}");
  if (start === -1 || end === -1 || end < start) {
    throw new Error("Writer stage returned no JSON object.");
  }
  return JSON.parse(body.slice(start, end + 1));
}
