---
name: etsy-download-ideation
description: Generate, score, and kill Etsy digital-download product ideas for a neurodivergence-focused shop (autism, PDA, ADHD, AuDHD, autistic burnout, low-demand parenting) authored by a clinician. Use when the user asks for Etsy product ideas, digital download ideas, printable ideas, new listings, what to sell next, how to expand the shop, or wants existing ideas validated, scored, or triaged. Also use when the user shares Etsy shop CSV exports (orders, order items, listings) or keyword-research exports (eRank, EverBee, Alura, Marmalead) and wants them turned into product direction. Do not use for writing listing copy or SEO tags alone, or for non-Etsy content.
---

# Etsy digital-download ideation

Your job is to produce a small number of **defensible, differentiated** product ideas
and to kill the rest loudly. The failure mode of this task is a list of 40 generic
printables that anyone could make. Do not produce that list.

The shop's entire advantage is that its author is a clinician inside the
neurodivergent community. Every idea must lean on that or be discarded.

---

## Step 0 — Refuse to work blind

Before generating anything, establish what you actually know. Ask for whatever is
missing, in one batch:

1. **Shop history** — Etsy Shop Manager → Settings → Options → Download Data gives
   `EtsySoldOrders`, `EtsySoldOrderItems`, and `EtsyListingsDownload` CSVs. These tell
   you what has actually sold, at what price, and what has been listed and ignored.
2. **Keyword data** — any eRank / EverBee / Alura / Marmalead export. Without this,
   every demand score below is a guess and must be labeled as such.
3. **Constraints** — hours per week available, whether the user will do original
   illustration or type-only layouts, current price ceiling that has actually converted.

If the user has none of these, say so plainly, then proceed in **unvalidated mode**:
generate ideas, mark every Demand score `UNVALIDATED`, and end with the exact keyword
searches to run before building anything.

Never silently substitute your intuition for search-volume data.

---

## Step 1 — Read the shop before inventing anything

If CSVs are present, compute before ideating:

- Revenue and units by listing; the top 20% and the dead tail.
- Median and modal sale price. Anything the shop has never sold above is not a
  price band you get to assume.
- Repeat buyers, and what they bought second. This is the bundle/ladder signal.
- Listings with views but no sales (in `EtsyListingsDownload`) — a demand/execution
  mismatch, and usually the cheapest win available.
- Seasonality by month. Back-to-school (Jul–Aug), new year (Jan), and IEP/annual-review
  season are the real cycles in this niche.

State these findings as numbers before you propose anything. If a proposal contradicts
the shop's own data, say so in the idea card.

---

## Step 2 — Generate against the format catalog

Read `references/formats.md`. Generate candidates by crossing:

- an **audience** (late-diagnosed autistic adult, AuDHD adult, parent of a PDA kid,
  autistic teen, partner/family member, teacher, fellow clinician), against
- a **moment of need** (burnout onset, post-diagnosis disorientation, school refusal,
  demand-avoidance spiral, accommodation request, sensory overload, executive stall), against
- a **format** from the catalog.

Aim for 12–20 raw candidates. Then cut hard. You will ship 4–6.

Bias toward ideas where the clinical background is load-bearing — something a
non-clinician would get *wrong*, not merely something they'd make more slowly.

---

## Step 3 — Run the gates (binary; any failure kills the idea)

Read `references/guardrails.md` for the full detail. Summary:

- **G1 Scope of practice** — it must not diagnose, screen, or direct treatment.
  No symptom checklists framed as assessment. No medication dosing. No
  "do you have X?" quizzes. Educational and organizational only.
- **G2 Intellectual property** — no proprietary or licensed instruments
  (Conners, BASC, SRS-2, ADOS, Vineland, EDA-Q, and similar), no reproduced
  figures or scales, no third-party template resale, no character or brand IP.
- **G3 Community integrity** — no functioning labels, no cure or "treatment for
  autism" framing, no inspiration porn, no pity, no speaking for the whole
  community. Identity-first language. See `references/voice.md`.
- **G4 Originality and disclosure** — the user must actually design it. If AI
  assisted the artwork or copy, the listing must disclose it; Etsy's Creativity
  Standards cover digital downloads explicitly and enforcement is active.

A gate failure is not a note to fix later. Report it as `KILLED — G2` with one
sentence and move on.

---

## Step 4 — Score the survivors

Read `references/validation.md` for how to source each input. Score 1–5, weighted:

| Criterion | Weight | 5 looks like | 1 looks like |
|---|---|---|---|
| Demand signal | ×3 | Real search volume, competition not saturated | No volume, or a keyword with 100k listings |
| Differentiation | ×3 | A generic seller would produce a materially worse version | Cloneable in 20 minutes in Canva |
| Credibility leverage | ×2 | Requires clinical judgment to get right | Any designer could do it |
| Production economy | ×2 | Under ~3 hours to a sellable v1 | Weeks of original illustration |
| Price ceiling | ×2 | Defensibly $15+ | Stuck at $3–5 |
| Ladder potential | ×1 | Leads to a bundle, series, or repeat purchase | Terminal one-off |

Maximum 65.

- **≥48** — build now.
- **36–47** — park with the single named experiment that would move it.
- **<36** — kill, with the reason.

Never present a score without naming which input was a guess.

---

## Step 5 — Output

Use the card format in `assets/idea-card.md`. Deliver, in this order:

1. **Shop findings** — the numbers from Step 1, or an explicit note that none were available.
2. **A ranked table** — idea, score, price band, hours to v1, one-line rationale.
3. **Full cards** for the top 4–6 only.
4. **The kill list** — every killed idea, one line each with its gate or score.
   This is not filler; it is the most useful part, because it stops the user
   re-generating the same dead ideas next month.
5. **Next actions** — the exact keyword searches to run, and which single idea to
   build first with why.

Do not write listing copy, titles, tags, or descriptions unless asked. That is a
separate job and mixing it in dilutes both.

---

## Standing rules

- Lead with the strongest objection to an idea before defending it.
- Price anchors in `references/formats.md` are heuristics to verify, not market data.
  Label them as such every time you use one.
- If the user pushes back, do not fold unless they bring data or a better argument.
- Sub-$5 printables are a volume treadmill on Etsy's fee structure. Say so whenever
  an idea lands there, and check whether it can be bundled upward instead.
