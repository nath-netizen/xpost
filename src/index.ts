import { loadConfig } from "./config.js";
import { research } from "./research.js";
import { generate } from "./generate.js";
import { writeQueue } from "./queue.js";

async function main(): Promise<void> {
  const cfg = loadConfig();

  console.log(
    `signal-to-post · model=${cfg.model} · target=${cfg.postCount} posts · lookback=${cfg.lookbackHours}h`,
  );

  console.log("→ Stage 1: scanning current discourse...");
  const briefing = await research(cfg);

  console.log("→ Stage 2: drafting posts...");
  const posts = await generate(cfg, briefing);

  const flagged = posts.filter((p) => p.sensitivity_flag || [...p.text].length > 280).length;
  const { json, md } = writeQueue(cfg.model, posts);

  console.log(`✓ Wrote ${posts.length} drafts (${flagged} flagged for review)`);
  console.log(`  ${md}`);
  console.log(`  ${json}`);
  console.log("Review the queue, mark drafts approved, then `npm run post`.");
}

main().catch((err) => {
  console.error("Run failed:", err instanceof Error ? err.message : err);
  process.exit(1);
});
