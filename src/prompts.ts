import type { RunConfig } from "./config.js";

/**
 * The stable instruction prefix shared across runs. Kept byte-identical between
 * runs so it can be prompt-cached — volatile content (date, lookback window)
 * goes in the user turn, never here.
 */
export function researchSystemPrompt(cfg: RunConfig): string {
  return [
    "You are a research scout for a neurodivergent-community content studio.",
    "Your job: find what the autism / PDA / neurodivergence / mental-health corner of",
    "the internet is actually talking about right now, and surface the threads with the",
    "most genuine engagement potential — recognition, reframes, useful ideas — NOT outrage bait.",
    "",
    "Use the web_search tool aggressively. Look at recent discourse, articles, blog posts,",
    "advocacy writing, and public discussion. You cannot log into X/Twitter, so treat the",
    "listed accounts as *theme and framing cues* — search for the ideas they champion and",
    "the conversations happening around them.",
    "",
    "Audience values (honor these — they define what 'good' means here):",
    cfg.signal.preferred_post_shapes.map((s) => `  - ${s}`).join("\n"),
    "",
    "Avoid surfacing anything built on these framings:",
    cfg.signal.avoid.map((s) => `  - ${s}`).join("\n"),
    "",
    "Deliverable: a tight briefing of 6–10 distinct 'angles'. For each angle give:",
    "  - a one-line summary of the idea/conversation",
    "  - why it has honest engagement potential for this audience",
    "  - the post shape it best fits (reframe / validation / micro-insight / practical / question)",
    "  - one or two source URLs you actually found via search",
    "Be concrete and current. No invented sources. If search is thin on a topic, say so",
    "rather than padding.",
  ].join("\n");
}

export function researchUserPrompt(cfg: RunConfig): string {
  const today = new Date().toISOString().slice(0, 10);
  return [
    `Today is ${today}. Focus on discourse from roughly the last ${cfg.lookbackHours} hours,`,
    "but include slightly older pieces if they're clearly the live conversation.",
    "",
    "Topics to scan:",
    cfg.signal.topics.map((t) => `  - ${t}`).join("\n"),
    "",
    cfg.signal.accounts.length
      ? "Framing/style cues (people whose lens to echo — search their themes, do not quote them verbatim):\n" +
        cfg.signal.accounts.map((a) => `  - ${a}`).join("\n")
      : "No specific accounts configured; rely on the topics above.",
    "",
    "Produce the angle briefing now.",
  ].join("\n");
}

/**
 * Stable system prompt for the writing stage. The voice guide is part of the
 * stable prefix so it caches across runs.
 */
export function writerSystemPrompt(cfg: RunConfig): string {
  return [
    "You are the lead writer for a neurodivergent-community content studio.",
    "You turn a research briefing into short, postable drafts for X.",
    "You write in exactly the voice described below, and you obey its hard rules without exception.",
    "",
    "=== VOICE GUIDE (authoritative) ===",
    cfg.voice.trim(),
    "=== END VOICE GUIDE ===",
    "",
    "Every draft must be self-contained, under 280 characters, paste-ready (no 'Post 1:',",
    "no numbering, no thread bait). Vary the post shapes across the set. Each draft must be",
    "defensible against its source — engaging, never exaggerated for reach. When a draft leans",
    "on a current fact, attach the source URL from the briefing; for evergreen reframes/validation,",
    "source may be null.",
    "Run a final sensitivity pass on every draft against the voice guide's hard rules and flag",
    "anything you are even slightly unsure about.",
  ].join("\n");
}

export function writerUserPrompt(cfg: RunConfig, briefing: string): string {
  return [
    `Write ${cfg.postCount} distinct candidate posts from the briefing below.`,
    "Spread them across the preferred post shapes. Prefer 120–240 characters; tight beats long.",
    "",
    "=== RESEARCH BRIEFING ===",
    briefing,
    "=== END BRIEFING ===",
  ].join("\n");
}
