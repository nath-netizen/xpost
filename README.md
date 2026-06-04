# signal-to-post

An agentic harness that scans what the **autism / PDA / neurodivergence / mental-health**
corner of the internet is talking about right now, and drafts **5–20 short, engaging posts**
into a review queue — several times a day, automatically. Nothing posts without your approval.

It runs on your **Claude Code subscription** (Pro/Max) via the **Claude Agent SDK** with
Claude's **built-in web search** — so it needs **no Anthropic API key** (no per-token
billing) and **no paid X/Twitter API** to find trends.

---

## How the harness works

It's a small two-stage agentic workflow plus a review gate:

```
            ┌────────────────────────────────────────────────────────────┐
            │  config/signal.config.json   (topics, accounts, what to avoid)│
            │  config/voice.md             (your voice + hard rules)        │
            └───────────────┬────────────────────────────────────────────┘
                            │
   Stage 1: RESEARCH        ▼            Claude + web_search (server-side)
   ───────────────────  "What's the live conversation? Find 6–10 angles
                         with honest engagement potential." → briefing
                            │
   Stage 2: WRITE           ▼            Claude + structured output (Zod)
   ───────────────────  Turn the briefing into N drafts in *your* voice,
                         each shape-tagged, sourced, and sensitivity-checked.
                            │
   QUEUE                    ▼
   ───────────────────  queue/<timestamp>.json  (data: text, shape, source, status)
                         queue/<timestamp>.md    (readable, with flags)
                            │
   REVIEW GATE              ▼            You: read → approve → post
   ───────────────────  Mark drafts `approved`, then `npm run post`.
```

Why two stages instead of one prompt: the research stage is allowed to roam the web and
be messy; the writing stage is tightly constrained to your voice and returns clean,
typed data. Separating them makes each cheaper to run, easier to tune, and easier to trust.

**Steer it by editing two files — no code:**

- `config/signal.config.json` — the topics to track, the `@handles` whose framing you want
  echoed (used as _search cues_; the harness does **not** log into X), and what to avoid.
- `config/voice.md` — who's speaking, tone, and the hard rules. This is loaded verbatim into
  the writer's system prompt and is the single biggest lever on quality. **Rewrite it in your
  own voice first.**

---

## Quick start (local)

```bash
npm install
claude login                # one-time: authenticate with your Claude subscription
npm run generate            # scan + draft a batch into queue/
```

The harness authenticates through the Claude Agent SDK using your Claude Code login —
**no `ANTHROPIC_API_KEY` required.** (If `ANTHROPIC_API_KEY` is set in your environment it
takes precedence over the subscription, so `unset` it if you want to run on your plan.)

Open the newest `queue/*.md`, read the drafts, then:

```bash
npm run approve <id> [<id> ...]   # or: npm run approve --all
npm run post                       # posts approved drafts (dry-run until X creds are set)
```

`npm run post` is a **dry run** until you add X credentials — it prints exactly what it
_would_ post, so you can use the whole loop today without ever connecting to X.

---

## Running it on a schedule (GitHub Actions)

`.github/workflows/generate.yml` runs the harness three times a day (UTC) and opens a
**pull request** with each new batch. The PR _is_ your review surface — read the drafts in
the PR, approve the ones you want, merge.

The workflow runs on your subscription too — it authenticates with a long-lived OAuth token
minted from your plan, not an API key.

After pushing this repo to GitHub:

1. Mint a subscription token locally:
   ```bash
   claude setup-token
   ```
2. **Settings → Secrets and variables → Actions → New repository secret**
   - `CLAUDE_CODE_OAUTH_TOKEN` = the token from step 1
3. (Optional) add repository **variables**: `STP_MODEL`, `STP_POST_COUNT`, `STP_LOOKBACK_HOURS`.
4. Adjust the `cron:` lines to the times/frequency you want (they're in UTC).

> The OAuth token is long-lived but not permanent — if scheduled runs start failing with an
> auth error down the line, re-run `claude setup-token` and update the secret.

You can also trigger a run by hand from the **Actions** tab (workflow_dispatch).

---

## Posting to X (optional)

Reading trends is free (web search). _Posting_ to X needs X's API, but the **free developer
tier allows posting** — that part is cheap. Create an app at <https://developer.x.com>, generate
user-context (OAuth 1.0a) keys, and set them in `.env`:

```
X_API_KEY=...
X_API_SECRET=...
X_ACCESS_TOKEN=...
X_ACCESS_SECRET=...
```

Then `npm run post` will publish every `approved` draft and mark it `posted`. The poster
refuses to publish over-280-character drafts and skips anything not explicitly approved.

> Why web search instead of the X API for trends? Pulling your real home timeline, your
> following list, and trending topics from X requires a **paid** API tier (Basic ~$200/mo+).
> Web search reaches the same public discourse for free — it just can't see your private
> timeline. If you later want true "people I follow" precision, that's the upgrade path:
> swap `src/research.ts` to call the X API and feed those posts into Stage 2 unchanged.

---

## Configuration reference

| Env var                   | Default           | Meaning                                                         |
| ------------------------- | ----------------- | --------------------------------------------------------------- |
| `CLAUDE_CODE_OAUTH_TOKEN` | —                 | Subscription token for CI (`claude setup-token`). Not needed locally if you've run `claude login`. |
| `STP_MODEL`               | `claude-sonnet-4-6` | Lighter on your subscription. Set to `claude-opus-4-8` for the most capable (heavier) model. |
| `STP_POST_COUNT`          | `12`              | Drafts per run (clamped 1–20).                                  |
| `STP_LOOKBACK_HOURS`      | `24`              | How far back the trend scan looks.                              |

**Usage note:** each run is two Claude calls (one with web search), drawn from your Claude
**subscription** rather than per-token API usage. The default is Sonnet to keep within your
plan's usage limits across multiple runs a day; switch to `STP_MODEL=claude-opus-4-8` for
higher quality if your plan has the headroom.

---

## Project layout

```
config/signal.config.json   what to track / avoid (edit freely)
config/voice.md             your voice + hard rules (edit freely)
src/research.ts             Stage 1 — web-search trend scan
src/generate.ts             Stage 2 — structured draft writing
src/queue.ts                writes queue/*.json + *.md
src/index.ts                orchestrator (npm run generate)
src/approve.ts              flip drafts to approved/rejected
src/post.ts                 optional X poster (npm run post)
.github/workflows/          scheduled runs → review PRs
```

## Safety posture

This audience is sensitive and the topic is health-adjacent, so the harness is deliberately
**draft-first**: it never posts on its own, every draft carries a self-applied sensitivity
flag, the voice guide forbids medical advice / functioning labels / inspiration-porn, and the
poster blocks over-limit text. Keep a human in the loop — that's the whole design.
