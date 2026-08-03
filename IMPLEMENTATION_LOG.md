# Implementation Log

Step-by-step record of how this project was built, updated as each step in
`BRIEF.md`'s build sequence lands. Each entry says what was built, the key
decisions made, and how it was verified — not a restatement of the diff.

---

## Step 1 — the guard, on mocks (2026-08-03)

**Scope:** `guard.py` + `tests/test_guard.py` only. No DB, no vision calls, no
embeddings — hand-built `Candidate` objects, per BRIEF.md's Step 1 build
sequence.

**What was built:**
- [`guard.py`](guard.py) — `guard(post_subject, candidates, sim_floor, conf_floor) -> GuardDecision`,
  implementing the three-check pseudocode from BRIEF.md section 4:
  1. similarity floor → "is anything relevant at all?"
  2. canonical subject equality (with a rescue pass over lower-ranked
     candidates) → "is it the right animal?"
  3. trust check → unknown subject or low tag confidence on an otherwise
     correct top hit.
- [`tests/test_guard.py`](tests/test_guard.py) — all 7 must-pass cases from
  the brief: wrong top hit with/without a rescue candidate, correct top hit
  at high/low confidence, all candidates below the similarity floor, unknown
  top-hit subject, and an empty candidate list.

**Decisions:**
- `sim_floor` / `conf_floor` are function parameters, not literals or a
  config file — Step 1 doesn't call for a `config.py`, and the brief's
  instruction was "thresholds come from config parameters," which the
  function signature already satisfies. A real config module can arrive with
  the API/matching wiring in Step 4–5 without touching `guard.py`.
  Local `.venv` with `pydantic` + `pytest`, frozen to `requirements.txt` —
  neither was installed anywhere on the machine.
- Added an empty root `conftest.py` so pytest resolves `tests/test_guard.py`'s
  imports (`guard`, `schemas`, `vocab`) against the project root rather than
  just the `tests/` directory.

**Verified:**
```
.venv/bin/pytest tests/test_guard.py -v
7 passed in 0.12s
```
Zero external calls — no DB, no vision, no embeddings, as required for this
step to be verifiable in isolation.

**Next:** Step 2 — `migrations/001_init.sql`, `migrations/002_seed_subjects.sql`,
`db.py`. Done when a dummy image + vector can be inserted and queried by
similarity.

---

## Step 2 — data model (2026-08-03)

**Scope:** `migrations/001_init.sql`, `migrations/002_seed_subjects.sql`, plus
`db.py`, per BRIEF.md's Step 2.

**What was built:**
- [`migrations/001_init.sql`](migrations/001_init.sql) — all 8 tables from
  BRIEF.md section 4 (`subjects`, `images`, `image_tags`, `image_vectors`,
  `posts`, `post_vectors`, `pairings`, `model_calls`) plus every index listed
  there (HNSW cosine indexes on both vector columns, the two `image_tags`
  indexes, `pairings(post_id, status)`, `model_calls(kind, created_at)`).
- [`migrations/002_seed_subjects.sql`](migrations/002_seed_subjects.sql) —
  hand-written INSERT mirroring `vocab.py`'s `VOCAB` dict exactly (7 subjects
  including `unknown`). Not generated automatically; must be updated by hand
  if `VOCAB` changes, same one-direction rule `vocab.py`'s docstring states.
- [`migrations/003_enable_rls.sql`](migrations/003_enable_rls.sql) — not in
  the brief, added after Supabase's security advisor flagged all 8 tables as
  publicly readable/writable via PostgREST with RLS off. Enables RLS with no
  policies on every table, closing that path; the app's direct `psycopg`
  connection is unaffected.
- [`db.py`](db.py) — `Settings` (pydantic-settings, reads `DATABASE_URL` from
  `.env`) and `get_connection()`, a context manager wrapping
  `psycopg.connect` with `pgvector`'s `register_vector` so `vector` columns
  round-trip as Python lists/arrays.
- `.env.example` — template for `DATABASE_URL`; real `.env` is gitignored and
  not committed.

**Decisions:**
- Provisioned a new Supabase project (`autotagging`, `us-east-1`, free tier,
  project ref `qfoeblplrgjrcjfutsia`) rather than reusing existing unrelated
  projects on the account — confirmed with the user first.
- `vector(1536)` is a placeholder dimension. No embedding model is chosen
  until Step 4; captions and posts must share one model, so this may need to
  change then. Flagged here so it isn't forgotten.
- Added `psycopg[binary]`, `pgvector` (Python package, not just the Postgres
  extension), and `pydantic-settings` to the `.venv` / `requirements.txt` —
  all already named in BRIEF.md's stack table, just not yet installed.

**Verified (against the live Supabase project, via migration/SQL tools):**
- Both migrations applied cleanly (`apply_migration`).
- Inserted two dummy images + 1536-dim vectors (`sin`/`cos` patterns, not
  real embeddings), ran a cosine similarity query (`<=>`) using the HNSW
  index: fox-vector matched itself at similarity `1.0`, the dissimilar
  vector came back at `~-0.0001` — ranking behaves correctly. Dummy rows
  deleted afterward.
- Security advisor: all 8 `rls_disabled_in_public` ERRORs resolved by
  migration 003; remaining findings are informational (RLS-enabled-no-policy,
  expected) and one cosmetic WARN (`vector` extension lives in `public`
  schema) — left as-is.
- `db.py` syntax/imports verified; full live-connection test needs
  `DATABASE_URL` in a local `.env` (not committed — see `.env.example`), which
  the user provisions from the Supabase dashboard.
- `pytest -v` — still 7/7 passing, no regression from Step 1.

**Next:** Step 3 — `vision.py` (forced tool use → `VisionTagOutput`),
`jobs/classify.py` (async, semaphore-limited, tenacity retries, idempotent,
cost-logged to `model_calls`).

---

## Correction — Gemini Flash, not Anthropic, and compliance scaffolding (2026-08-03)

The user shared the actual official capstone brief (a PDF: FlyRank Backend
Track, "AI Image Understanding & Content Matching Engine"). It has a strict
$0 constraint this project's own `BRIEF.md` had missed: **Gemini Flash free
tier** for vision, **Gemini embeddings free tier** (`text-embedding-004`)
for embeddings — no `anthropic` SDK, no paid API of any kind.

**What changed:**
- `BRIEF.md`'s stack table and Flow A pseudocode updated to Gemini Flash /
  Gemini embeddings. Nothing built in Steps 1–2 required rework — `guard.py`
  is provider-agnostic, and the `vector(1536)` placeholder was already
  flagged as pending the real model choice.
- Added the submission-pack files the source brief requires that were
  missing: [`README.md`](README.md), [`LICENSE`](LICENSE) (MIT),
  [`capstone.yaml`](capstone.yaml), [`EVIDENCE.md`](EVIDENCE.md),
  [`BUILDLOG.md`](BUILDLOG.md). Full detail on the AI-usage angle of this
  correction is in `BUILDLOG.md`, not duplicated here — this log stays
  focused on technical decisions.
- `EVIDENCE.md` seeded with proof for what's genuinely done so far (guard
  tests, DB migrations + index confirmation) and explicit `pending: Step N`
  markers for everything else — no boxes checked without pasted proof.

**Next:** Step 3, now against Gemini Flash — `vision.py`
(`google-genai`, `response_schema` JSON mode → `VisionTagOutput`),
`jobs/classify.py` (async, semaphore-limited, tenacity retries, idempotent,
cost-logged to `model_calls`). Blocked on a `GEMINI_API_KEY` from the user
(free, Google AI Studio, no card).

---

## Step 3 — batch vision classification (2026-08-03)

**Scope:** `vision.py` + `jobs/classify.py`, against Gemini Flash. Scope
correction from the original doc: embeddings (`image_vectors`) are Step 4,
not Step 3 — the "Done when" line under the old Step 3 heading mentioned
`image_vectors`, which conflicted with the Follow-up Prompts section
(embeddings explicitly listed under Step 4). Went with the cleaner split:
Step 3 is vision tagging only (`image_tags` + `model_calls`), matching the
same "prove one thing before debugging two at once" principle Step 1 used
for the guard.

**What was built:**
- [`config.py`](config.py) — new. Centralizes `gemini_api_key`,
  `vision_model` (default `"gemini-flash-latest"`, an alias so it doesn't
  need re-pinning as Google rotates versions — confirmed live: currently
  resolves to `gemini-3.6-flash`), `embedding_model` (unused until Step 4),
  and `sim_floor`/`conf_floor` (0.35/0.6, per BRIEF.md's suggested
  starting values — one `conf_floor` used both at ingestion time here and
  at matching time by `guard.guard`, so tagging-time flagging and
  matching-time distrust never drift apart). `db.py` refactored to import
  `Settings` from here instead of defining its own.
- [`vision.py`](vision.py) — `tag_image()` (async, one Gemini call),
  `parse_vision_output()` and `derive_status()` (pure, no network — tested
  offline). Structured output uses
  `response_json_schema=VisionTagOutput.model_json_schema()`, **not**
  `response_schema=VisionTagOutput` — the latter 400'd
  (`Unknown name "additional_properties"`) because `VisionTagOutput`'s
  `extra="forbid"` config schema-serializes into a field Gemini's
  constrained `response_schema` subset rejects; `response_json_schema`
  accepts the raw Pydantic JSON Schema directly and works.
- [`jobs/classify.py`](jobs/classify.py) — `run_classification_job()`:
  fetches images with no `image_tags` row (idempotency), tags them under an
  `asyncio.Semaphore`, retries only 429/5xx via tenacity's `AsyncRetrying`
  (`_is_transient`), logs one `model_calls` row per image (success or
  total failure, with the real attempt count), and writes `image_tags` —
  `invalid_output` rows (validation failure or exhausted retries) skip
  `ImageTagRecord` entirely and go through a raw insert instead, since that
  record type requires a real `subject` and an invalid/failed call has
  none; `Subject.UNKNOWN` (a valid enum member) is what `ImageTagRecord`
  is for when the model *did* answer, just with "none of these."

**Decisions / tradeoffs:**
- DB writes inside the async job use `db.py`'s existing **sync** psycopg
  connections (one per operation), not an async connection pool. Blocks
  the event loop briefly per write; acceptable at ~50 images with
  concurrency 5, would need revisiting for a much larger corpus.
- Per-call cost logging is one `model_calls` row per image representing
  the final outcome (with the correct attempt count), not one row per
  individual retry attempt — failed attempts aren't billed by Gemini, so
  no cost data would be lost, only some retry-level granularity.
- Pricing hardcoded per resolved model version (`gemini-3.6-flash`:
  $1.50/$7.50 per 1M input/output tokens, output price includes thinking
  tokens) with a fallback if the alias resolves elsewhere later — checked
  live against ai.google.dev's pricing page, not from training data (this
  model didn't exist as of this assistant's January 2026 cutoff).

**Verified:**
- Live smoke tests (not committed, temp file deleted after): text-only
  structured output round-trip; then a real photo (fetched via browser
  from Wikimedia Commons for local testing only — not corpus-suitable
  licensing) → correctly tagged `red_fox`, confidence 0.98, full
  `VisionTagOutput` validation passed. Confirmed a live 503 during testing
  retried correctly.
- `pytest -v` — 24/24 passing (7 guard + 10 vision + 7 classify), zero live
  network calls in the suite itself (all Gemini/DB interaction is mocked
  or injected).

**Not yet done:** a real end-to-end run of `run_classification_job()`
against the live Supabase project and an actual image corpus — blocked on
(a) `DATABASE_URL` in `.env`, still outstanding since Step 2, and (b) the
corpus itself (~50 licensed-free images), not gathered yet. `EVIDENCE.md`
reflects this honestly — checkboxes are proven at the unit-test level, not
claimed as a full corpus run.

**Next:** resolve the two blockers above, do a real corpus run, then
Step 4 — `embeddings.py`, `matching.py`, wiring the existing guard to real
candidates.
