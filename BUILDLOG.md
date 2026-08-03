# Build Log — AI usage

Honest record of where AI (Claude Code) helped, where it was wrong, and what
got changed as a result. This project has been built with heavy AI
assistance from the start — that's disclosed here, not hidden.

---

## 2026-08-03 — Wrong vision-model stack, corrected

**Where AI was wrong:** `BRIEF.md` (my own planning doc, written earlier in
this project) specified the `anthropic` SDK for vision tagging, with
structured output via forced tool use. That's a paid API. I built Step 1
(`guard.py`) and Step 2 (the data model, `db.py`) against that plan without
flagging the cost implication.

**What caught it:** the user shared the actual official capstone brief (a
PDF from the FlyRank internship program) and pointed out its explicit,
non-negotiable constraint: **$0, no credit card, ever** — Gemini Flash free
tier (or fully local Ollama) for vision, Gemini embeddings free tier (or
Ollama `all-minilm`) for embeddings.

**What changed:**
- `BRIEF.md`'s stack table and Flow A pseudocode updated: Gemini Flash
  (`google-genai`, `response_schema` JSON mode) replaces the `anthropic` SDK
  and forced tool use; Gemini embeddings (`text-embedding-004`) replace the
  unspecified "one embedding model."
- Nothing built in Steps 1–2 needed to change — `guard.py` operates on
  provider-agnostic `Candidate` objects, and the data model's `vector(N)`
  columns were already flagged as a placeholder pending the real embedding
  model's dimension, so no rework there either. The cost was caught before
  it compounded, not after.
- Added the required submission-pack files this project was missing
  (`README.md`, `LICENSE`, `capstone.yaml`, `EVIDENCE.md`, this file) — they
  should have been present from the first commit per the source brief's
  GitHub rules; added now, kept honest going forward.

**Lesson for the rest of the build:** don't assume a stack choice from an
earlier, self-authored planning doc is still ground truth — check it against
the actual source requirements when they're available, especially anywhere
cost or credentials are involved.

---

## Ongoing

Each subsequent phase gets an entry here noting anything AI got wrong or had
to be corrected on, alongside what it helped with. See
[IMPLEMENTATION_LOG.md](IMPLEMENTATION_LOG.md) for the technical
step-by-step build record — this file is specifically about AI-assistance
honesty, not a duplicate of that log.
