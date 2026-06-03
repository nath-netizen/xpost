import { listQueueFiles, readQueueFile, saveQueueFile } from "./queue.js";

/**
 * Usage:
 *   npm run approve <id> [<id> ...]   approve specific drafts
 *   npm run approve --all             approve every remaining draft
 *   npm run approve --reject <id>     reject a draft
 */
function main(): void {
  const args = process.argv.slice(2);
  if (args.length === 0) {
    console.error("Pass draft id(s), or --all. e.g. npm run approve 2026-06-03T14-22-07-03");
    process.exit(1);
  }

  const all = args.includes("--all");
  const reject = args.includes("--reject");
  const ids = new Set(args.filter((a) => !a.startsWith("--")));
  const target = reject ? "rejected" : "approved";

  let changed = 0;
  for (const path of listQueueFiles()) {
    const file = readQueueFile(path);
    let touched = false;
    for (const item of file.items) {
      const match = all ? item.status === "draft" : ids.has(item.id);
      if (match && item.status !== "posted") {
        item.status = target;
        changed++;
        touched = true;
      }
    }
    if (touched) saveQueueFile(path, file);
  }

  console.log(`Marked ${changed} draft(s) as ${target}.`);
}

main();
