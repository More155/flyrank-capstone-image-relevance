# Image Relevance & Auto-Tagging — Build Brief

Handoff document for Claude Code. Contains the project description, the agreed
architecture, the build sequence, and the prompt to start from.

Companion files (already written, treat as given): `vocab.py`, `schemas.py`.

> **Correction (2026-08-03):** this doc originally specified the `anthropic`
> SDK for vision, which is not free. The actual source assignment (FlyRank
> Backend Track capstone, "AI Image Understanding & Content Matching Engine")
> requires a strict $0 stack: **Gemini Flash free tier** for vision,
> **Gemini embeddings free tier** (`text-embedding-004`) for embeddings — no
> credit card, ever. Stack table and Flow A below are corrected. Everything
> already built (Step 1's guard, Step 2's data model) is provider-agnostic
> and unaffected.

---

## 1. What we're building

A service that takes a library of images and a set of blog posts, figures out
what is actually in each image, and matches each post to the right image — so a
post about red foxes gets a red fox photo, not a generic dog, and **never** a wolf.

The interesting part is not the matching. It is the **refusal**: knowing when the
best available candidate is still wrong, rejecting it, and explaining why.

### The core problem

"Red fox" and "gray wolf" sit close together in embedding space — same family,
same wilderness captions, similar visual features. So:

- A **similarity threshold alone** cannot separate them. Any floor either lets
  wolves through or throws out good foxes.
- **String matching on subject alone** breaks the paraphrase requirement
  ("vulpes vulpes" must still match a "red fox" post).

The resolution is to use each signal only where it is strong:

| Question | Mechanism |
|---|---|
| Is anything relevant at all? | Cosine similarity vs a floor |
| Is it the *right* animal? | Canonical subject equality |
| Do synonyms collapse? | Handled upstream, at tag/extraction time |

Two failure modes, two mechanisms. No knife-edge threshold to tune.

---

## 2. Scope

### In scope (definition of done)

1. Vision tagging as **validated structured output**; low confidence flags rather than guesses.
2. **Batch classification job** with retries and per-call cost tracking.
3. **Semantic matching** — embed captions + post text, rank images per post; paraphrase still matches.
4. **Mismatch guard** — rejects a wrong pairing with a reason. Fox/wolf/dog proven.
5. **Data model** — images, tags, embeddings, posts, pairings, cost ledger, correct indexes.
6. **Validated API** + a minimal approve/reject review surface.
7. **Cost tracking** per vision/embedding call.
8. **Tests** — schema-validation path, guard (fox post rejects wolf), top-1 precision eval.
9. **README + diagram.**

### Explicitly out of scope

Do not build these unless asked: auto alt-text, near-duplicate detection,
image-generation fallback, integration as a Capstone 1 node, human-in-the-loop
QA agent. All stretch goals.

### Corpus

~50 images across ~6 animal species (see `vocab.py`). Hand-labeled. The same set
serves as the eval set for the precision number.

---

## 3. Stack

| Concern | Choice | Notes |
|---|---|---|
| Language | Python 3.11+ | |
| Schema + validation | Pydantic v2 | One definition serves vision validation, DB shape, and API |
| Vision | Gemini Flash (`google-genai`, free tier) | Structured output via `response_schema` JSON mode |
| Embeddings | Gemini embeddings (`text-embedding-004`, free tier) | Same model for captions AND posts — non-negotiable |
| DB | Postgres + pgvector (Supabase) | Hand-written SQL migrations, no ORM |
| Driver | `psycopg` 3 | |
| API | FastAPI | Pydantic models reused directly |
| Batch | `asyncio` + `Semaphore` + `tenacity` | 50 images does not need a queue |
| Tests | pytest | |
| Review UI | FastAPI `/docs`, then one Jinja2 page | Keep it to one page |

---

## 4. Architecture

Two runtime flows. Keeping them separate is the whole mental model.

### Flow A — ingestion (offline, batch, slow, expensive)

```
image file
  → vision model (Gemini Flash, response_schema JSON mode)
  → Pydantic validate → VisionTagOutput
  → derive status (ok | low_confidence | unknown_subject | invalid_output)
  → INSERT image_tags
  → embed(caption) → INSERT image_vectors
  → INSERT model_calls (cost) for every call
```

Properties: **idempotent** (skip already-tagged images), **concurrency-limited**
(vision calls are slow / rate-limited), **retrying** on transient errors
(429/5xx via tenacity) but *not* on validation failures — those are recorded as
`invalid_output` and flagged, never retried forever.

### Flow B — matching (online, per request, fast)

```
GET /posts/{id}/images
  → ensure post embedded (once, cached)
  → pgvector top-k over image_vectors
  → build Candidate list
  → guard(post_subject, candidates)
  → MatchResponse { decision, ranked }

POST /pairings/{id}/review  → approve | reject
```

No expensive model calls on the hot path. Milliseconds, not seconds.

### The guard

```python
def guard(post_subject, candidates, sim_floor, conf_floor) -> GuardDecision:
    if not candidates:
        return NO_MATCH(BELOW_SIMILARITY_FLOOR)

    best = candidates[0]

    # 1. no-match detection — is anything relevant at all?
    if best.similarity < sim_floor:
        return NO_MATCH(BELOW_SIMILARITY_FLOOR,
                        f"top candidate {best.similarity:.2f} below {sim_floor}")

    # 2. wrong-match detection — is it the right animal?
    if best.subject != post_subject:
        rescue = first c in candidates
                 where c.subject == post_subject and c.similarity >= sim_floor
        if rescue:
            return SUGGEST(rescue, PROMOTED_OVER_TOP_HIT)
        return NO_MATCH(SUBJECT_MISMATCH,
                        f"best is {best.subject}, post is {post_subject}")

    # 3. trust check
    if best.subject is Subject.UNKNOWN:
        return NO_MATCH(SUBJECT_UNKNOWN)
    if best.tag_confidence < conf_floor:
        return FLAG(best, LOW_TAG_CONFIDENCE)

    return SUGGEST(best, OK)
```

Same function runs when a pairing is **forced** via the API, not only when
ranking — that is what makes the "force the wolf, it still refuses" demo work.

Thresholds live in config, not literals: `SIM_FLOOR` (start ~0.35, tune on the
eval set), `CONF_FLOOR` (start 0.6).

### Data model

```sql
subjects(id text PK, display text, synonyms text[], family text)

images(id uuid PK, source_uri text NOT NULL, storage_url text,
       sha256 text UNIQUE, created_at timestamptz DEFAULT now())

image_tags(image_id uuid PK REFERENCES images(id),
           subject text REFERENCES subjects(id),
           category text, attributes text[], caption text,
           confidence real, status text NOT NULL,
           model text, created_at timestamptz DEFAULT now())

image_vectors(image_id uuid PK REFERENCES images(id),
              embedding vector(N), model text)

posts(id uuid PK, title text, body text,
      subject text REFERENCES subjects(id), subject_confidence real)

post_vectors(post_id uuid PK REFERENCES posts(id),
             embedding vector(N), model text)

pairings(id uuid PK, post_id uuid REFERENCES posts(id),
         image_id uuid REFERENCES images(id),
         similarity real, verdict text, reason text, explanation text,
         status text, note text, created_at timestamptz DEFAULT now())

model_calls(id uuid PK, kind text, model text,
            input_units int, output_units int, cost_usd numeric(10,6),
            ref_id uuid, ok boolean, attempt int,
            created_at timestamptz DEFAULT now())
```

Indexes that matter:

```sql
CREATE INDEX ON image_vectors USING hnsw (embedding vector_cosine_ops);
CREATE INDEX ON post_vectors  USING hnsw (embedding vector_cosine_ops);
CREATE INDEX ON image_tags (subject);
CREATE INDEX ON image_tags (status);
CREATE INDEX ON pairings (post_id, status);
CREATE INDEX ON model_calls (kind, created_at);
```

`subjects` is seeded from `vocab.py` — Python is the source of truth, one
direction only.

---

## 5. Build sequence

Each step is independently verifiable. **Do them in this order.** The reason is
specific: the guard is proven on fabricated data before any model call exists,
so you are never debugging "is my logic wrong" and "is my API call wrong" at the
same moment.

### Step 1 — the guard, on mocks (do this first)

`guard.py` + `tests/test_guard.py`. No DB, no vision, no embeddings — hand-built
`Candidate` objects only.

Must-pass tests:
- fox post + wolf top hit + no fox available → `NO_MATCH` / `SUBJECT_MISMATCH`
- fox post + wolf top hit + fox at rank 3 → `SUGGEST(fox)` / `PROMOTED_OVER_TOP_HIT`
- fox post + fox top hit, high confidence → `SUGGEST` / `OK`
- fox post + fox top hit, confidence 0.3 → `FLAG` / `LOW_TAG_CONFIDENCE`
- all candidates below floor → `NO_MATCH` / `BELOW_SIMILARITY_FLOOR`
- top hit subject `unknown` → not suggested
- empty candidate list → `NO_MATCH`, no crash

**Done when:** the suite is green with zero external calls.

### Step 2 — data model

`migrations/001_init.sql`, `migrations/002_seed_subjects.sql`, plus a small
`db.py`. **Done when:** you can insert a dummy image + vector and run a
similarity query.

### Step 3 — batch classification job

`vision.py` (Gemini Flash `response_schema` → `VisionTagOutput`), `jobs/classify.py`
(async, semaphore-limited, tenacity retries, idempotent, cost-logged).

**Done when:** running it over the corpus fills `image_tags` + `image_vectors`,
every call appears in `model_calls`, and bad outputs land as `invalid_output`
rather than crashing the run.

### Step 4 — embeddings, matching, real guard

`embeddings.py`, `matching.py` (pgvector top-k), post subject extraction into
`posts.subject`. Wire the step-1 guard to real candidates.

**Done when:** `GET /posts/{id}/images` returns a real ranked list, a real wolf
is refused on a real fox post, and a "vulpes vulpes" post still matches the fox.

### Step 5 — API, review, eval, docs

FastAPI app, one Jinja2 review page (post, thumbnail, similarity, verdict,
reason, approve/reject), cost summary endpoint, `eval/run_eval.py` reporting
top-1 precision, README + architecture diagram.

**Done when:** the demo runs end to end and produces a precision number.

---

## 6. Conventions

- Type hints everywhere; Pydantic for anything crossing a boundary.
- No secrets in code — `.env` + `pydantic-settings`.
- Every model call goes through one wrapper that writes to `model_calls`. No
  exceptions; that is how cost tracking stays honest.
- Thresholds and model names in config, never inline literals.
- Log the guard's reason on every decision.

---

## 7. Prompt for Claude Code

Paste this to start. Then work step by step — do not let it build everything at once.

```
I'm building an image relevance & auto-tagging service in Python. Read
BRIEF.md in full before writing any code — it contains the architecture,
data model, build sequence, and scope boundaries we've already agreed on.
Also read vocab.py and schemas.py; treat them as given and import from
them rather than redefining types.

Key context so you don't optimize the wrong thing: the hard part of this
project is the MISMATCH GUARD — correctly refusing a wrong image pairing
(a wolf photo on a red-fox post) and explaining why. Similarity alone
cannot separate foxes from wolves because they are close in embedding
space, so the guard uses a similarity floor for "is anything relevant"
and canonical subject equality for "is it the right animal". Do not
collapse those into one threshold.

Start with STEP 1 ONLY: implement guard.py and tests/test_guard.py using
hand-built Candidate objects. No database, no vision calls, no
embeddings. Cover every case listed under Step 1 in the brief, including
the rescue path and the empty-list case. Thresholds come from config
parameters, not literals.

When the tests pass, stop and show me the results. We'll move to Step 2
together. Ask before adding any dependency or any file the brief does
not mention.
```

### Follow-up prompts

- **Step 2:** "Now Step 2 — migrations and db.py per the brief. Hand-written SQL, no ORM. Seed `subjects` from vocab.py. Include every index listed."
- **Step 3:** "Step 3 — the batch classification job. Forced tool use validated into `VisionTagOutput`. Idempotent, semaphore-limited, tenacity retries on transient errors only. Validation failures store `invalid_output` and keep the run alive. Every call logged to `model_calls`."
- **Step 4:** "Step 4 — embeddings and matching. Same embedding model for captions and posts. pgvector top-k, then feed the existing guard. Don't modify guard.py's logic; only build its inputs."
- **Step 5:** "Step 5 — FastAPI endpoints, one Jinja2 review page, cost summary, and the top-1 precision eval. Keep the UI to a single page."