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
