import { readFileSync, writeFileSync, readdirSync } from "node:fs";
import { join } from "node:path";
import { root } from "./config.js";
import type { Post } from "./generate.js";

export type Status = "draft" | "approved" | "posted" | "rejected";

export interface QueueItem extends Post {
  id: string;
  status: Status;
  char_count: number;
  over_limit: boolean;
  posted_id?: string;
}

export interface QueueFile {
  run_at: string;
  model: string;
  items: QueueItem[];
}

const queueDir = join(root, "queue");

function stamp(d = new Date()): string {
  return d.toISOString().replace(/[:.]/g, "-").slice(0, 19); // 2026-06-03T14-22-07
}

export function writeQueue(model: string, posts: Post[]): { json: string; md: string } {
  const runAt = new Date().toISOString();
  const base = stamp();
  const items: QueueItem[] = posts.map((p, i) => {
    const charCount = [...p.text].length;
    return {
      ...p,
      id: `${base}-${String(i + 1).padStart(2, "0")}`,
      status: "draft",
      char_count: charCount,
      over_limit: charCount > 280,
    };
  });

  const file: QueueFile = { run_at: runAt, model, items };
  const jsonPath = join(queueDir, `${base}.json`);
  const mdPath = join(queueDir, `${base}.md`);
  writeFileSync(jsonPath, JSON.stringify(file, null, 2) + "\n");
  writeFileSync(mdPath, renderMarkdown(file));
  return { json: jsonPath, md: mdPath };
}

function renderMarkdown(file: QueueFile): string {
  const lines: string[] = [
    `# Draft posts — ${file.run_at}`,
    "",
    `Model: \`${file.model}\` · ${file.items.length} candidates`,
    "",
    "To approve a draft: set its `status` to `approved` in the matching `.json` file",
    "(or run `npm run approve <id>`), then `npm run post`.",
    "",
    "---",
    "",
  ];
  for (const it of file.items) {
    lines.push(`### ${it.id} · _${it.shape}_ · ${it.char_count} chars`);
    if (it.over_limit) lines.push("> ⚠️ **Over 280 characters — trim before posting.**");
    if (it.sensitivity_flag)
      lines.push(`> 🚩 **Sensitivity flag:** ${it.sensitivity_flag}`);
    lines.push("");
    lines.push("```");
    lines.push(it.text);
    lines.push("```");
    lines.push(`*Why:* ${it.rationale}`);
    if (it.source_url) lines.push(`*Source:* ${it.source_url}`);
    lines.push("");
    lines.push("---");
    lines.push("");
  }
  return lines.join("\n");
}

// --- helpers used by approve.ts / post.ts ---

export function listQueueFiles(): string[] {
  return readdirSync(queueDir)
    .filter((f) => f.endsWith(".json"))
    .map((f) => join(queueDir, f))
    .sort();
}

export function readQueueFile(path: string): QueueFile {
  return JSON.parse(readFileSync(path, "utf8")) as QueueFile;
}

export function saveQueueFile(path: string, file: QueueFile): void {
  writeFileSync(path, JSON.stringify(file, null, 2) + "\n");
}
