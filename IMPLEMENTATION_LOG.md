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

---

## Step 3 continued — real corpus, live end-to-end run (2026-08-03)

**What was built:**
- [`corpus.py`](corpus.py) — the ~50-image corpus manifest, source of truth
  for both DB seeding and (Step 5) eval ground truth. 48 real Unsplash
  photos (8 per species × 6 species in `vocab.py`), gathered by browsing
  Unsplash search results and extracting real CDN photo URLs — not
  guessed, not committed as binary files (`CorpusImage.url` points straight
  at Unsplash's CDN, so `scripts/seed_corpus.py` reproduces the same corpus
  anywhere). Unsplash License: free for any use, no attribution required.
- [`scripts/seed_corpus.py`](scripts/seed_corpus.py) — idempotent (dedupes
  on `sha256`) insert into `images`, reusing `jobs.classify.load_image_bytes`
  rather than duplicating fetch logic.

**Two real infrastructure problems hit and fixed, both needed for any
future live run to work at all, not just this one:**

1. **DATABASE_URL**: Supabase's direct-connection host
   (`db.<ref>.supabase.co`) only has an `AAAA` (IPv6) record — no `A`
   record — and this network can't reach it (`dig` confirmed). Fixed by
   switching to Supabase's transaction-mode pooler
   (`aws-0-us-east-1.pooler.supabase.com:6543`, username
   `postgres.<project-ref>`), which resolves over IPv4. That in turn
   surfaced a second issue: PgBouncer in transaction mode doesn't give
   pooled connections their own prepared-statement namespace, so
   psycopg3's automatic server-side `PREPARE` collided
   (`DuplicatePreparedStatement`) across connections. Fixed in
   [`db.py`](db.py) with `psycopg.connect(..., prepare_threshold=None)`.
2. **SSL on macOS**: the python.org build doesn't use the system CA store,
   so `urllib.request.urlopen()` failed every HTTPS fetch with
   `CERTIFICATE_VERIFY_FAILED`. Fixed by building an SSL context from
   `certifi.where()` and passing it explicitly
   (`jobs/classify.py`'s `load_image_bytes`, now the one place both the
   classify job and `seed_corpus.py` fetch bytes from).

**Also hit, and it changed the default model:** `gemini-flash-latest`
(→ `gemini-3.6-flash`) has a **20-requests/day** free-tier quota — far too
low for a 48-image batch even at concurrency 5. Quota is per-model, not
per-account, so switching `vision_model` to `gemini-3.1-flash-lite`
(cheaper too: $0.25/$1.50 per 1M tokens vs. $1.50/$7.50) picked up separate,
sufficient quota and finished the run. `config.py` and `vision.py`'s
pricing table updated accordingly. Full narrative in BUILDLOG.md, including
why this changed `_classify_one`'s failure handling (see next paragraph).

**A design correction that came directly from hitting the quota wall:**
the original Step 3 code wrote an `image_tags` row with
`status=invalid_output` for *any* failure to get a model response,
including exhausted-retry transient failures — which, combined with
idempotency ("skip images already in `image_tags`"), permanently branded
29 images invalid the moment quota ran out, even though nothing was wrong
with them. Changed `_classify_one` so `invalid_output` is written only for
a genuine model response that failed schema validation — that is what the
status name actually means. A total API failure (quota, network, a
non-transient error) now logs the failed `model_calls` row for cost/audit
visibility but writes no `image_tags` row at all, leaving the image
legitimately pending for the next run. Manually deleted the 29 bad rows
from the earlier run before re-running with the corrected code and model.

**One more real catch, not a bug:** one of the 8 "gray wolf" corpus photos
turned out to be a coyote (Unsplash's alt-text was wrong). The model
correctly returned `subject=unknown` at 0.95 confidence instead of forcing
it to `gray_wolf` — a live demonstration of the exact behavior Step 3 is
supposed to produce. Since `corpus.py` doubles as eval ground truth for
Step 5, a mislabeled entry would have quietly deflated a future precision
number for the wrong reason, so it was swapped for a verified wolf photo
rather than left in.

**Verified (final state, live Supabase project):**
```
$ .venv/bin/python -m jobs.classify
classification job done: {'ok': 48}
```
- `image_tags`: 48/48 `status='ok'`.
- Tagged subject matches `corpus.py`'s ground-truth label for 48/48 images
  (100%) — not the formal Step 5 eval script, but the same check.
- `model_calls`: 78 rows (29 failed attempts from the quota-exhausted
  `gemini-3.6-flash` run, at $0/0 tokens, + 49 successful), notional cost
  $0.129250 at paid-tier rates — actual billing $0 (free tier).
- `pytest -v` — still 24/24, no regressions from any of the above fixes.

**Next:** Step 4 — `embeddings.py`, `matching.py`, wiring the existing
guard to real candidates. `vector(1536)` placeholder needs correcting to
whatever `gemini-embedding-001` actually outputs before that lands.

---

## Step 4 — embeddings, matching, real guard (2026-08-03)

**Scope:** `embeddings.py`, `matching.py`, post subject extraction, wiring
`guard.guard()` (untouched) to real ranked candidates. Per the source
brief's Step 4 instruction: don't modify `guard.py`'s logic, only build its
inputs — confirmed true here; `guard.py` has zero changes since Step 1.

**What was built:**
- [`embeddings.py`](embeddings.py) — `embed_text()`, async, one Gemini
  call. `gemini-embedding-001` at `output_dimensionality=768` (native
  output is 3072, which exceeds pgvector's HNSW index limit of 2000 — see
  the dimension fix below), `task_type=SEMANTIC_SIMILARITY` since captions
  and posts are compared symmetrically, not query→document.
- [`migrations/004_fix_vector_dimension.sql`](migrations/004_fix_vector_dimension.sql)
  — corrects the `vector(1536)` placeholder from Step 2 to `vector(768)`
  on both `image_vectors` and `post_vectors` (drop HNSW index, alter
  column type, recreate index — safe, both tables were still empty).
  Applied live.
- [`extraction.py`](extraction.py) — `extract_subject()`, same
  structured-output pattern as `vision.py` (`response_json_schema` against
  `SubjectExtraction`), applied to post title+body instead of pixels, per
  `schemas.py`'s own docstring ("Same idea, applied to post text instead
  of pixels"). Reuses `settings.vision_model` — no separate model needed
  for a plain text-in/JSON-out call.
- [`matching.py`](matching.py) — `ensure_post_embedded()` (lazy, cached —
  no-ops if `post_vectors` already has a row, matching Flow B's "ensure
  post embedded (once, cached)"), `rank_images_for_post()` (pgvector
  top-k via `<=>`, returns `Candidate` objects already sorted by
  similarity descending — the guard's `candidates[0] = best` assumption),
  `match_images_for_post()` (the full pipeline: embed → rank → `guard()`).
- [`corpus.py`](corpus.py) doubles as eval ground truth (already true from
  Step 3); [`posts_seed.py`](posts_seed.py) — 8 sample posts: one per
  species, a paraphrase case ("Vulpes vulpes," no literal "fox" anywhere in
  the text), and a deliberate no-coverage case (elephant — not in
  `vocab.py` at all), matching the source brief's demo script (§13).
- [`scripts/seed_posts.py`](scripts/seed_posts.py) — idempotent (on
  title), extracts + stores `posts.subject`/`subject_confidence`, logs
  `model_calls` (`CallKind.EXTRACT_SUBJECT`).
- [`jobs/embed_images.py`](jobs/embed_images.py) — batch-embeds every
  `image_tags` row without an `image_vectors` row yet. Same idempotency
  pattern as `jobs/classify.py`.
- [`scripts/verify_matching.py`](scripts/verify_matching.py) — a live
  (not pytest) script reproducing the source brief's acceptance probes
  2-4 against the real DB: fox post ranks fox top, a forced real wolf
  candidate on the fox post gets rejected, the paraphrase post still
  matches, the elephant post gets `no_match`. Kept out of the pytest suite
  deliberately — pytest never touches the network or live DB in this
  project; this script is the live counterpart.
- [`tests/test_extraction.py`](tests/test_extraction.py) — 6 tests
  mirroring `test_vision.py`'s schema-validation coverage for
  `extraction.parse_extraction_output`.

**Decisions / a couple of real corrections along the way:**
- `embed_content`'s response has no `usage_metadata` at all in this SDK
  version (verified live — `resp.metadata` is `None`), unlike
  `generate_content`. First draft of `embeddings.py` guessed at a
  `billable_character_count` field that doesn't exist; caught by actually
  printing the response object before trusting the guess. Now estimates
  input tokens from `len(text) // 4` (Gemini's own documented rule of
  thumb) instead.
- Moved the `generate_content` pricing table from a private constant in
  `vision.py` into `config.py` as `GENERATE_CONTENT_PRICING_USD` /
  `FALLBACK_GENERATE_CONTENT_PRICING_USD` — `extraction.py` needs the same
  table (same model family), and reaching into another module's
  underscore-prefixed "private" constant via `from vision import
  _PRICING_PER_TOKEN_USD` (the first draft did this) is exactly the kind
  of thing that constant naming convention exists to prevent.
- `top_k=10` default for `rank_images_for_post` — generous enough that a
  same-species rescue candidate is very likely to be within the fetched
  window at this corpus size (48 images, ~8/species), without fetching
  the entire table on every request.

**Verified (live, against the real DB and the real 48-image corpus):**
- All 48 images embedded (`jobs/embed_images.py`): `{'ok': 48, 'failed': 0}`.
- All 8 posts seeded with extracted subjects, including the paraphrase
  case (→ `red_fox`) and the elephant case (→ `unknown`).
- `scripts/verify_matching.py` — all 4 checks pass: fox post ranks fox top
  and suggests it; a forced real wolf candidate (0.785 similarity — a
  genuinely close call, confirming the brief's fox/wolf premise) on the
  fox post is rejected with `SUBJECT_MISMATCH`; the "Vulpes vulpes" post
  still matches fox; the elephant post gets `NO_MATCH`.
- Not scripted, but observed for free while eyeballing all 8 posts: the
  dog post's real top hit was a wolf image (0.756) — the guard's
  **rescue path fired for real**, promoting a dog candidate at 0.744
  (`PROMOTED_OVER_TOP_HIT`), the exact mechanism Step 1 proved on mocks,
  now proven on live embeddings too.
- `pytest -v` — 30/30 (24 previous + 6 new extraction tests), zero
  network/DB calls in the suite itself.

**Next:** Step 5 — FastAPI endpoints (`GET /posts/{id}/images`,
`POST /pairings/{id}/review`), the one-page Jinja2 review UI, a cost
summary endpoint, and `eval/run_eval.py` for the formal top-1 precision
number (the informal version — 48/48 tagging-accuracy and 4/4 matching
checks — already exists above).

---

## Step 5 — API, review UI, cost summary, eval (2026-08-03)

**Scope:** FastAPI app, one Jinja2 review page, cost summary endpoint,
`eval/run_eval.py`. This is the last of the 5 build steps — the core
capstone is now complete end to end.

**What was built:**
- [`pairings.py`](pairings.py) — `create_pairing()` (runs the guard,
  natural-ranked or forced, persists the result), `review_pairing()`
  (validates the action is `approved`/`rejected` — `suggested` and
  `refused_by_guard` are system-only outcomes, never a human review
  action), `list_pairings_for_review()`.
- [`matching.py`](matching.py) — added `match_forced_image()` and the
  `_get_post_subject`/`_get_post_embedding`/`_candidate_for_image` helpers
  it and `match_images_for_post()` now share (refactor, no behavior
  change to the existing functions). The forced path builds a `Candidate`
  from that image's *real* similarity to the post — not a fabricated one
  — so "force the wolf, it still refuses" is an honest demo.
- [`api.py`](api.py) — FastAPI app: `GET /posts`, `GET /images`, `GET
  /posts/{id}/images` (accepts `force_image_id`), `POST
  /pairings/{id}/review`, `GET /pairings`, `GET /costs/summary`, plus
  `GET /review` (the page) and three form-only routes
  (`/review/suggest`, `/review/force`, `/review/act`) using
  POST/redirect/GET — no JavaScript anywhere.
- [`templates/review.html`](templates/review.html) — the one page: get a
  suggestion, force a specific image (the demo path), a pairings table
  with hotlinked Unsplash thumbnails, approve/reject where applicable.
- [`posts_seed.py`](posts_seed.py) — added `expected_subject: Subject` to
  `SeedPost`, hand-labeled ground truth for the eval (distinct from
  `posts.subject`, which is the model's own extraction — grading the
  model against its own answer would be circular).
- [`eval/run_eval.py`](eval/run_eval.py) — top-1 precision per the source
  brief's glossary definition, over the 7 posts with real corpus
  coverage; the 8th (elephant, no coverage) is excluded from the
  denominator and checked separately as a refuse-don't-guess case.
- [`tests/test_pairings.py`](tests/test_pairings.py),
  [`tests/test_api.py`](tests/test_api.py) — pure/offline tests (status
  mapping, malformed-UUID → 422). DB-dependent API behavior (404s, the
  full review workflow) verified live instead, consistent with how this
  project has handled DB-touching code since Step 2 — see EVIDENCE.md.

**One real bug, caught immediately by testing in a browser (not just
`pytest`):** `templates.TemplateResponse("review.html", {"request":
request, ...})` — the pattern from most tutorials and this assistant's
training data — raised `TypeError: unhashable type: 'dict'` on first
load. Starlette changed the calling convention: `request` is now a
positional argument, not a context-dict key
(`TemplateResponse(request, "name.html", context)`). Fixed in `api.py`'s
`review_page`. Full account in BUILDLOG.md.

**Decisions:**
- Dual surface on purpose: a JSON API for programmatic use, plus
  form-only HTML routes for the review page, rather than making the page
  call the JSON API via JavaScript. Keeps the page usable with zero JS,
  per the brief's "keep the UI to a single page" instruction, and keeps
  the JSON API's request/response shapes clean (`ReviewAction`'s `action`
  is a `PairingStatus`, not a string that happens to work in a form post).
- `GET /posts/{id}/images` both computes *and persists* a pairing on every
  call — matches Flow B's pseudocode (ranking always produces a decision
  worth recording) and means the review page's data is never stale
  relative to what the guard would say right now.
- Cost tracking is real, not a placeholder: `GET /costs/summary`
  aggregates `model_calls` by `kind`/`model` with live counts and dollar
  totals — checked live, not just unit-tested.

**Verified (live, browser + curl + the real DB):**
- Full review workflow in a real browser: selected the fox post, clicked
  Suggest → thumbnail + verdict=`suggest` + similarity `0.842` appeared →
  clicked Approve → status flipped to `approved`, action buttons
  disappeared. Forced a real `gray_wolf` image onto the fox post via the
  Force form → verdict=`no_match`, status=`refused_by_guard`, no image
  shown, no approve/reject buttons (nothing to review for a refusal).
- `curl` error-handling checks: 404 (missing post), 422 (malformed UUID),
  400 (invalid review action), 200 (`/docs` auto-generated).
- `eval/run_eval.py`: **top-1 precision 100% (7/7)**, plus the
  no-coverage post correctly refused.
- `pytest -v` — 37/37 (30 previous + 4 pairings + 3 API), zero network/DB
  calls in the suite itself.

**Not part of this build, flagged not hidden:** while setting up browser
testing, a `.claude/launch.json` was mistakenly created in an unrelated
project directory (`be-01-api`) rather than this one, because the preview
tool requires its config in the *primary* working directory rather than
this project's own. Caught by the user, removed immediately. Doesn't
affect this repo at all — noted here only because BUILDLOG.md's honesty
standard shouldn't stop at this repo's boundary.

**This completes all 5 build steps.** Remaining polish, not blocking:
architecture diagram as an actual image (currently ASCII, which the
brief explicitly allows), and the stretch goals (none attempted, all
explicitly out of scope per BRIEF.md §2 unless asked for).

---

## Post-Step-5 polish (2026-08-03)

**Decisions:** asked the user which stretch goal (if any) to build —
answer: skip stretch goals entirely, core is already done and proven.
Kept scope to the two remaining concrete items.

**What was built:**
- README.md's Architecture section: replaced the ASCII diagram with a
  real Mermaid flowchart (both flows, DB tables as cylinder nodes, the
  guard as a decision node with labeled `suggest`/`no_match` branches).
  GitHub renders Mermaid natively in README.md — no separate image file
  to generate or keep in sync, renders as a crisp vector diagram,
  theme-aware. Chosen over a hand-authored static SVG specifically
  because SVG coordinates can't be visually verified without a render
  step. Verified two ways: pushed and inspected GitHub's own render
  pipeline (the mermaid block loads into a sandboxed
  `viewscreen.githubusercontent.com` iframe with the diagram source
  correctly passed through — confirmed via `javascript_tool`, since
  cross-origin restrictions blocked reading the iframe's rendered SVG
  directly), and rendered the exact same source locally with
  `@mermaid-js/mermaid-cli` (`npx -y @mermaid-js/mermaid-cli`) to a real
  SVG file, then read it to confirm every node, both subgraphs, the `×`
  character, the single-quoted text, and both edge labels came through
  correctly. The local render is the stronger proof — same engine,
  fully inspectable, no cross-origin sandbox in the way.
- Repo rename to the brief's suggested `flyrank-capstone-*` convention:
  **not done by this assistant** — `gh` isn't authenticated on this
  machine (checked again; still true), and renaming a GitHub repo isn't
  achievable through plain `git` without API access. Instructions handed
  to the user instead.
