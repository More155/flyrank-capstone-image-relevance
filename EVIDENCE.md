# Evidence

One pasted proof per Definition-of-Done checkbox (source brief §6). Filled in
as each checkbox actually becomes true — unchecked boxes are not claimed as
done.

---

## AI processing

- [x] Vision model produces structured output validated against a schema;
      invalid responses are never trusted.

  Live call against Gemini Flash (`gemini-flash-latest` → resolved
  `gemini-3.6-flash`), `response_json_schema=VisionTagOutput.model_json_schema()`,
  real image (a red fox photo), full round trip validated:

  ```
  RAW TEXT: {"subject":"red_fox","category":"mammal","attributes":[...],
  "caption":"A red fox rests peacefully curled up in the bright white
  snow.","confidence":0.98,"reasoning":"..."}
  VALIDATED: subject=<Subject.RED_FOX: 'red_fox'> category=<Category.MAMMAL...>
  ```

  Malformed/out-of-schema output never trusted:
  `tests/test_vision.py::test_malformed_json_never_raises_and_reports_error`,
  `::test_confidence_out_of_range_is_rejected`,
  `::test_unknown_enum_value_is_rejected`,
  `::test_missing_required_field_is_rejected` — all assert
  `parse_vision_output` returns `(None, error)`, never raises, never
  silently accepts.

- [x] Low-confidence classifications are flagged instead of accepted.

  `tests/test_vision.py::test_derive_status_low_confidence` — confidence
  0.3 with `conf_floor=0.6` → `TagStatus.LOW_CONFIDENCE`, not `OK`.

- [x] Images are processed through a batch background job with retries.

  `jobs/classify.py`: `asyncio.Semaphore`-limited concurrency, tenacity
  `AsyncRetrying` on 429/5xx only. Unit-tested:
  `tests/test_classify.py::test_retries_and_succeeds_after_transient_failures`
  (2 injected failures, succeeds on 3rd attempt),
  `::test_gives_up_after_max_attempts_of_transient_failures` (exhausts at 4
  attempts, raises), `::test_does_not_retry_non_transient_errors` (a 400
  fails on the first attempt, no retry).

  **Real end-to-end run**, live Supabase project + a real 48-image corpus
  (`corpus.py`, Unsplash photos, seeded via `scripts/seed_corpus.py`):

  ```
  $ .venv/bin/python -m jobs.classify
  classification job done: {'ok': 48}
  ```

  (Two runs: the first hit `gemini-3.6-flash`'s free-tier quota — 20
  requests/day — after 19 images; switching `vision_model` to
  `gemini-3.1-flash-lite`, which had separate quota, finished the remaining
  29. See BUILDLOG.md.) All 48 images landed `status='ok'`; tagged subject
  matches the corpus's ground-truth label for all 48/48 (100%) — a real
  precision signal, not yet the formal Step 5 eval script, but the same
  underlying check.

  One genuine catch along the way: one "gray wolf" Unsplash search result
  was actually a coyote (bad alt-text on Unsplash's end). The model
  correctly returned `subject=unknown` at confidence 0.95 rather than
  force-fitting it to `gray_wolf` — exactly the flag-don't-guess behavior
  this checkbox is about. Swapped the corpus entry for a verified wolf photo
  since this corpus doubles as eval ground truth (see BUILDLOG.md for the
  full callout).

- [x] Vision and embedding costs are tracked per call *(vision done;
      embeddings pending Step 4)*.

  `vision.tag_image` computes `cost_usd` from `resp.usage_metadata`
  (input/output/thinking tokens) against real Gemini Flash pricing
  (checked 2026-08-03, ai.google.dev/gemini-api/docs/pricing).
  `jobs/classify.py` logs one `model_calls` row per image, success or
  failure, including the 29 quota-exhausted attempts from the
  `gemini-3.6-flash` run (at $0/0 tokens — never billed):

  ```sql
  select count(*), round(sum(cost_usd), 6), sum(input_units), sum(output_units)
  from model_calls;
  -- (78, 0.129250, 64904, 13775)

  select ok, count(*) from model_calls group by ok;
  -- (false, 29), (true, 49)
  ```

  Notional cost at paid-tier rates; actual billing was $0 (free tier).

## Matching system

- [x] Image and post embeddings are stored; posts return ranked image
      suggestions.

  All 48 image captions embedded (`jobs/embed_images.py`) and all 8 seed
  posts embedded on first access (`matching.ensure_post_embedded`), both
  via `gemini-embedding-001` at 768 dims (native output is 3072, over
  pgvector's HNSW index limit of 2000 — see
  `migrations/004_fix_vector_dimension.sql`). Real pgvector top-k query
  (`matching.rank_images_for_post`) against the live DB:

  ```
  $ .venv/bin/python -m scripts.verify_matching
  PASS - fox post ranks fox top and suggests it
  ```

  `'Getting to Know the Red Fox'` (post_subject=red_fox) → top-3:
  `red_fox@0.842, red_fox@0.842, red_fox@0.841` → `verdict=suggest
  reason=ok`.

- [x] Semantic matching works for equivalent concepts — "red fox" matches
      "Vulpes vulpes".

  `'The Secretive World of Vulpes Vulpes'` — the post body never contains
  the word "fox," only the Latin binomial — still ranks real fox images top
  and gets suggested:

  ```
  $ .venv/bin/python -m scripts.verify_matching
  PASS - "Vulpes vulpes" paraphrase post still matches fox
  ```
  top-3: `red_fox@0.797, red_fox@0.796, red_fox@0.793`.

## Safety layer

- [x] The mismatch guard rejects incorrect recommendations — the
      wolf-on-a-fox-post scenario provably fails.

  ```
  tests/test_guard.py::test_wrong_top_hit_with_no_rescue_available_is_no_match

  candidates = [wolf @ similarity 0.82, dog @ similarity 0.60]
  guard(post_subject=RED_FOX, candidates, sim_floor=0.35, conf_floor=0.6)
  → verdict=NO_MATCH, reason=SUBJECT_MISMATCH

  $ .venv/bin/pytest tests/test_guard.py -v
  7 passed in 0.06s
  ```

  **Same case, proven with real data** (source brief's Probe 3 — force the
  wolf as a candidate for the fox post): took a real `gray_wolf` image's
  actual embedding-based similarity to the real "Getting to Know the Red
  Fox" post (0.785 — genuinely close, confirming the brief's premise that
  fox/wolf sit near each other in embedding space) and forced it through
  the unmodified guard:

  ```
  $ .venv/bin/python -m scripts.verify_matching
  PASS - forced wolf candidate on fox post is rejected with a reason
  ```
  `verdict=no_match reason=subject_mismatch explanation="best is gray_wolf,
  post is red_fox"`.

- [x] Rejections include a human-readable explanation.

  From `guard.py`, the SUBJECT_MISMATCH branch:
  ```python
  explanation=f"best is {best.subject.value}, post is {post_subject.value}"
  ```
  Produces e.g. `"best is gray_wolf, post is red_fox"` — asserted in
  `tests/test_guard.py::test_wrong_top_hit_with_no_rescue_available_is_no_match`
  and confirmed live above.

- [x] When no image clears the bar, the system answers "no confident match"
      with reasons.

  ```
  tests/test_guard.py::test_all_candidates_below_similarity_floor_is_no_match

  candidates = [fox @ 0.20, wolf @ 0.10], sim_floor = 0.35
  guard(...) → verdict=NO_MATCH, reason=BELOW_SIMILARITY_FLOOR,
  explanation="top candidate 0.20 below floor 0.35"
  ```

  **Real case** (source brief's Probe 4): the seeded "Majestic African
  Elephant" post — no elephant in the corpus at all, and its subject
  extraction correctly came back `unknown` — gets refused, not guessed:

  ```
  $ .venv/bin/python -m scripts.verify_matching
  PASS - post with no good image gets no_match, not a guess
  ```
  `verdict=no_match reason=subject_mismatch explanation="best is red_fox,
  post is unknown"` (best real candidate was only 0.739 similarity — a
  weak match on top of the subject mismatch).

  **Also observed for free**, not a synthetic test: the "Why Dogs Make
  Great Companions" post's top real candidate was a `gray_wolf` image at
  0.756 similarity — the guard's rescue path fired for real, promoting a
  `domestic_dog` candidate at 0.744 (`reason=promoted_over_top_hit`)
  instead of either accepting the wrong top hit or refusing outright.

## Backend

- [x] Database models for images, tags, embeddings, posts, suggestions,
      approvals/rejections — with the required indexes.

  Migrations `001_init.sql`, `002_seed_subjects.sql`, `003_enable_rls.sql`
  applied to a live Supabase project (`autotagging`, project ref
  `qfoeblplrgjrcjfutsia`) via `apply_migration`. Confirmed indexes present:

  ```sql
  select indexname, tablename from pg_indexes where schemaname = 'public'
  order by tablename, indexname;

  image_tags_status_idx           | image_tags
  image_tags_subject_idx          | image_tags
  image_vectors_embedding_idx     | image_vectors   (hnsw, vector_cosine_ops)
  model_calls_kind_created_at_idx | model_calls
  pairings_post_id_status_idx     | pairings
  post_vectors_embedding_idx      | post_vectors    (hnsw, vector_cosine_ops)
  ```

  End-to-end proof (dummy row, deleted after): inserted two 1536-dim vectors
  (`sin`/`cos` patterns), ran a cosine similarity query via the HNSW index —
  self-match scored `1.0`, the dissimilar vector scored `~-0.0001`.

- [x] API endpoints validated; the review workflow (approve / reject /
      inspect why) exists.

  `api.py` — FastAPI app: `GET /posts`, `GET /images`, `GET
  /posts/{id}/images` (ranks + persists a pairing; `force_image_id` query
  param forces a specific candidate through the guard), `POST
  /pairings/{id}/review`, `GET /pairings`, `GET /costs/summary`, plus a
  server-rendered `GET /review` page (Jinja2, no JS) with three form
  actions (`/review/suggest`, `/review/force`, `/review/act`).

  Validated input → clean 4xx, live-checked:
  ```
  $ curl -o /dev/null -w "%{http_code}\n" localhost:8000/posts/00000000-0000-0000-0000-000000000000/images
  404
  $ curl -o /dev/null -w "%{http_code}\n" localhost:8000/posts/not-a-uuid/images
  422
  $ curl -X POST localhost:8000/pairings/00000000-.../review -d '{"action":"suggested"}' -w "%{http_code}\n"
  400   # SUGGESTED/REFUSED_BY_GUARD aren't valid review actions
  ```
  Same malformed-UUID case also covered offline:
  `tests/test_api.py` (3 tests, no DB/network — pure FastAPI/Pydantic
  validation) — `pytest -v` → all pass.

  Review workflow exercised live in a browser (`/review`): selected the
  fox post, clicked **Suggest** → row appeared with thumbnail (hotlinked
  from Unsplash), verdict=`suggest`, similarity `0.842`, **Approve**
  button → status flipped to `approved`, buttons disappeared. Separately,
  forced a real `gray_wolf` image onto the fox post via the **Force**
  form → row appeared with verdict=`no_match`, status=`refused_by_guard`,
  **no image shown and no approve/reject buttons** — the guard never
  associates an image with a refusal, so there's nothing to review.

## Quality & documentation

- [x] Automated tests cover schema validation, mismatch rejection, and
      matching accuracy.

  `.venv/bin/pytest -v` → `37 passed` (7 guard + 10 vision + 7 classify + 6
  extraction + 4 pairings + 3 API — schema validation covered for vision
  tagging, post subject extraction, and API input; mismatch rejection
  covered on mocks and live). Matching accuracy: formal top-1 precision
  below, plus the live 48/48 (100%) corpus-label match under "AI
  processing" and 4/4 `scripts/verify_matching.py` checks under "Safety
  layer."

- [x] A small labeled evaluation dataset measures top-1 precision — the
      number is in your README.

  `eval/run_eval.py` — ground truth is hand-labeled in `posts_seed.py`
  (`expected_subject` per post, written by me, not extracted by the
  model — grading the model against its own answer would be circular).
  Live run:

  ```
  $ .venv/bin/python -m eval.run_eval
  Top-1 precision: 100.0% (7/7)

    PASS  'Getting to Know the Red Fox': expected=red_fox got=red_fox
    PASS  'The Secretive World of Vulpes Vulpes': expected=red_fox got=red_fox
    PASS  'Life Among Gray Wolves': expected=gray_wolf got=gray_wolf
    PASS  'Why Dogs Make Great Companions': expected=domestic_dog got=domestic_dog
    PASS  'The Charming Red Panda': expected=red_panda got=red_panda
    PASS  'Nighttime Visitors: Understanding Raccoons': expected=raccoon got=raccoon
    PASS  'Domestic Cats: Independent by Nature': expected=domestic_cat got=domestic_cat

    PASS  'The Majestic African Elephant' (no corpus coverage): correctly refused (no_match)
  ```
  The elephant post (no corpus coverage) is excluded from the precision
  denominator on purpose — there's no correct image to measure against —
  and reported as a separate guard-behavior check instead.

- [x] README with architecture explanation and diagram; submission-pack
      files present.

  README.md updated with the real eval number, run/seed instructions, and
  an honest limitations section. All five required files present:
  `README.md`, `capstone.yaml`, `EVIDENCE.md`, `BUILDLOG.md`,
  `.env.example`.
