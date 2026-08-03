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
