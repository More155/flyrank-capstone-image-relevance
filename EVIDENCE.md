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
