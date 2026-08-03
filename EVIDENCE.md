# Evidence

One pasted proof per Definition-of-Done checkbox (source brief §6). Filled in
as each checkbox actually becomes true — unchecked boxes are not claimed as
done.

---

## AI processing

- [ ] Vision model produces structured output validated against a schema;
      invalid responses are never trusted. — *pending: Step 3*
- [ ] Low-confidence classifications are flagged instead of accepted. —
      *pending: Step 3*
- [ ] Images are processed through a batch background job with retries. —
      *pending: Step 3*
- [ ] Vision and embedding costs are tracked per call. — *pending: Step 3
      (vision), Step 4 (embeddings)*

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
