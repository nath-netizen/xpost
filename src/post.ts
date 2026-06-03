import { listQueueFiles, readQueueFile, saveQueueFile } from "./queue.js";
import type { QueueItem } from "./queue.js";

/**
 * Posts every `approved` draft to X, then marks it `posted`.
 *
 * Requires X (Twitter) API v2 user-context credentials in the environment:
 *   X_API_KEY, X_API_SECRET, X_ACCESS_TOKEN, X_ACCESS_SECRET
 * (free developer tier permits posting). The `twitter-api-v2` package is an
 * optional dependency — install it if you want to use this step.
 *
 * Run with --dry-run to preview without posting (also the default when
 * credentials are missing).
 */
async function main(): Promise<void> {
  const dryRun =
    process.argv.includes("--dry-run") ||
    !process.env.X_API_KEY ||
    !process.env.X_ACCESS_TOKEN;

  const approved: Array<{ path: string; item: QueueItem }> = [];
  for (const path of listQueueFiles()) {
    const file = readQueueFile(path);
    for (const item of file.items) {
      if (item.status === "approved") approved.push({ path, item });
    }
  }

  if (approved.length === 0) {
    console.log("No approved drafts to post. Approve some with `npm run approve`.");
    return;
  }

  const overLimit = approved.filter(({ item }) => item.over_limit);
  if (overLimit.length) {
    console.error(
      `Refusing to post ${overLimit.length} over-limit draft(s): ${overLimit
        .map(({ item }) => item.id)
        .join(", ")}. Trim them first.`,
    );
    process.exit(1);
  }

  if (dryRun) {
    console.log(`[dry-run] Would post ${approved.length} approved draft(s):\n`);
    for (const { item } of approved) console.log(`— (${item.char_count}c) ${item.text}\n`);
    console.log("Set X_* credentials (see .env.example) and re-run to post for real.");
    return;
  }

  // Lazy import so the package is only needed when actually posting.
  const { TwitterApi } = await import("twitter-api-v2");
  const client = new TwitterApi({
    appKey: process.env.X_API_KEY!,
    appSecret: process.env.X_API_SECRET!,
    accessToken: process.env.X_ACCESS_TOKEN!,
    accessSecret: process.env.X_ACCESS_SECRET!,
  });

  // Cache file contents so we persist status updates per file.
  const files = new Map<string, ReturnType<typeof readQueueFile>>();
  const getFile = (p: string) => {
    if (!files.has(p)) files.set(p, readQueueFile(p));
    return files.get(p)!;
  };

  let posted = 0;
  for (const { path, item } of approved) {
    try {
      const res = await client.v2.tweet(item.text);
      const file = getFile(path);
      const target = file.items.find((i) => i.id === item.id)!;
      target.status = "posted";
      target.posted_id = res.data.id;
      posted++;
      console.log(`posted ${item.id} → https://x.com/i/web/status/${res.data.id}`);
    } catch (err) {
      console.error(`failed ${item.id}:`, err instanceof Error ? err.message : err);
    }
  }

  for (const [path, file] of files) saveQueueFile(path, file);
  console.log(`Done. Posted ${posted}/${approved.length}.`);
}

main().catch((err) => {
  console.error("Post step failed:", err instanceof Error ? err.message : err);
  process.exit(1);
});
