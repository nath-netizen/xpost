import { query } from "@anthropic-ai/claude-agent-sdk";
import type { RunConfig } from "./config.js";
import { researchSystemPrompt, researchUserPrompt } from "./prompts.js";

/**
 * Stage 1 — scan current discourse via the Agent SDK's web search and return a
 * free-form "angle briefing" the writer stage consumes.
 *
 * Runs on your Claude Code subscription (no API key): the SDK picks up your
 * interactive `claude` login locally, or `CLAUDE_CODE_OAUTH_TOKEN` in CI. The
 * SDK manages the server-side search/tool loop internally, so we just collect
 * the final result.
 */
export async function research(cfg: RunConfig): Promise<string> {
  let result = "";

  for await (const message of query({
    prompt: researchUserPrompt(cfg),
    options: {
      model: cfg.model,
      systemPrompt: researchSystemPrompt(cfg),
      // Pre-approve only the search tools so the run is fully unattended
      // without `--dangerously-skip-permissions` (which refuses to run as root).
      allowedTools: ["WebSearch", "WebFetch"],
      permissionMode: "default",
      maxTurns: 30,
    },
  })) {
    if (message.type === "result") {
      if (message.subtype === "success") {
        result = message.result.trim();
        console.log(`[research] turns=${message.num_turns}`);
      } else {
        throw new Error(
          `Research stage failed (${message.subtype}). Check Claude Code auth / web search access.`,
        );
      }
    }
  }

  if (!result) {
    throw new Error(
      "Research stage returned no text. Check Claude Code auth / web search availability.",
    );
  }
  return result;
}
