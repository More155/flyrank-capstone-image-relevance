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

- [x] Images are processed through a batch background job with retries
      *(code + unit tests done; full run over a real corpus pending — see
      note below)*.

  `jobs/classify.py`: `asyncio.Semaphore`-limited concurrency, tenacity
  `AsyncRetrying` on 429/5xx only. Verified:
  `tests/test_classify.py::test_retries_and_succeeds_after_transient_failures`
  (2 injected failures, succeeds on 3rd attempt),
  `::test_gives_up_after_max_attempts_of_transient_failures` (exhausts at 4
  attempts, raises), `::test_does_not_retry_non_transient_errors` (a 400
  fails on the first attempt, no retry).

- [x] Vision and embedding costs are tracked per call *(vision done;
      embeddings pending Step 4)*.

  `vision.tag_image` computes `cost_usd` from `resp.usage_metadata`
  (input/output/thinking tokens) against real Gemini Flash pricing
  (checked 2026-08-03, ai.google.dev/gemini-api/docs/pricing).
  `jobs/classify.py` logs one `model_calls` row per image — success or
  failure — via `_log_model_call`.

  **Not yet run end-to-end against the live DB or a real corpus**: needs
  `DATABASE_URL` in `.env` (still outstanding from Step 2) and an actual
  image corpus (not gathered yet). Code paths are exercised by unit tests
  with a fake `tag_fn` and no live DB; a real batch run is the next
  concrete step once those two are in place.

## Matching system

- [ ] Image and post embeddings are stored; posts return ranked image
      suggestions. — *pending: Step 4*
- [ ] Semantic matching works for equivalent concepts — "red fox" matches
      "Vulpes vulpes". — *pending: Step 4*

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

- [x] Rejections include a human-readable explanation.

  From `guard.py`, the SUBJECT_MISMATCH branch:
  ```python
  explanation=f"best is {best.subject.value}, post is {post_subject.value}"
  ```
  Produces e.g. `"best is gray_wolf, post is red_fox"` — asserted in
  `tests/test_guard.py::test_wrong_top_hit_with_no_rescue_available_is_no_match`.

- [x] When no image clears the bar, the system answers "no confident match"
      with reasons.

  ```
  tests/test_guard.py::test_all_candidates_below_similarity_floor_is_no_match

  candidates = [fox @ 0.20, wolf @ 0.10], sim_floor = 0.35
  guard(...) → verdict=NO_MATCH, reason=BELOW_SIMILARITY_FLOOR,
  explanation="top candidate 0.20 below floor 0.35"
  ```

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

- [ ] API endpoints validated; the review workflow (approve / reject /
      inspect why) exists. — *pending: Step 5*

## Quality & documentation

- [x] Automated tests cover schema validation *(partial — guard covered;
      vision-schema tests pending Step 3)*, mismatch rejection, and matching
      accuracy *(matching pending Step 4)*.

  All 7 must-pass guard cases green: `.venv/bin/pytest -v` → `7 passed`.

- [ ] A small labeled evaluation dataset measures top-1 precision — the
      number is in your README. — *pending: Step 5*
- [ ] README with architecture explanation and diagram; submission-pack
      files present. — *README skeleton added 2026-08-03; diagram + final
      content pending later phases.*
