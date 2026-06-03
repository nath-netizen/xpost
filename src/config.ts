import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const __dirname = dirname(fileURLToPath(import.meta.url));
const root = join(__dirname, "..");

export interface SignalConfig {
  topics: string[];
  accounts: string[];
  avoid: string[];
  preferred_post_shapes: string[];
}

export interface RunConfig {
  model: string;
  postCount: number;
  lookbackHours: number;
  signal: SignalConfig;
  voice: string;
}

function clamp(n: number, lo: number, hi: number): number {
  return Math.max(lo, Math.min(hi, n));
}

export function loadConfig(): RunConfig {
  const apiKey = process.env.ANTHROPIC_API_KEY;
  if (!apiKey) {
    throw new Error(
      "ANTHROPIC_API_KEY is not set. Copy .env.example to .env and fill it in.",
    );
  }

  const signalRaw = readFileSync(join(root, "config", "signal.config.json"), "utf8");
  const signal = JSON.parse(signalRaw) as SignalConfig;
  const voice = readFileSync(join(root, "config", "voice.md"), "utf8");

  // Strip the "//" doc keys and any instructional placeholder lines in accounts.
  const accounts = (signal.accounts ?? []).filter(
    (a) => a.trim().startsWith("@") || /@\w/.test(a),
  );

  return {
    model: process.env.STP_MODEL?.trim() || "claude-opus-4-8",
    postCount: clamp(Number(process.env.STP_POST_COUNT ?? 12) || 12, 1, 20),
    lookbackHours: clamp(Number(process.env.STP_LOOKBACK_HOURS ?? 24) || 24, 1, 168),
    signal: { ...signal, accounts },
    voice,
  };
}

export { root };
