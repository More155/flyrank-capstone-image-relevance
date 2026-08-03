# Image Relevance & Auto-Tagging

FlyRank Backend Track capstone — "AI Image Understanding & Content Matching
Engine." Understands what's actually in an image library, tags it, and
matches each image to the right blog post: a red-fox post gets the red-fox
photo, never the wolf. The production-critical part isn't finding a match —
it's a **mismatch guard** that refuses a wrong pairing and explains why.

**Status: in progress.** Steps 1–2 of 5 are done (see
[IMPLEMENTATION_LOG.md](IMPLEMENTATION_LOG.md) for the step-by-step record).
This README will fill in as later steps land — see Limitations below for
exactly what isn't built yet.

## What it does

1. **Ingests & classifies** each image with a vision model (Gemini Flash,
   free tier) → structured tags `{subject, category, attributes, caption,
   confidence}`, validated against a schema. Low confidence is flagged, not
   guessed.
2. **Embeds** image captions and post text into one semantic space (Gemini
   embeddings, free tier), so "red fox" and "Vulpes vulpes" land close
   together even though the words differ.
3. **Ranks** candidate images per post by cosine similarity.
4. **Guards**: separates "is anything relevant at all" (similarity floor)
   from "is it the right animal" (canonical subject equality) — two
   mechanisms, not one blurred threshold. Proven on the fox/wolf/dog case.
5. **Reviews**: a minimal API to approve/reject a suggested pairing and see
   why it was suggested or refused.

## Architecture

```
images ─(batch job)─► vision model (Gemini Flash) ─► {tags, caption, confidence}
                                                        │
                                                        ├─► image_tags
                                                        └─► embed(caption) ─► image_vectors

posts ──────────────────────────────────────────────────► embed(post text) ─► post_vectors

GET /posts/:id/images
  └─► similarity ranking (image_vectors × post_vector)
        └─► mismatch guard (subject equality + similarity floor + confidence)
              ├─► suggested image (ranked, explained)
              └─► "no confident match" + reason
                    └─► review API: approve / reject
```

Two runtime flows, kept separate on purpose: ingestion (Flow A) is offline,
batch, slow, and cost-tracked; matching (Flow B) is online, per-request, and
does no model calls on the hot path. Full design rationale in
[BRIEF.md](BRIEF.md).

## Data model

Postgres + pgvector (hosted on Supabase, free tier). Hand-written SQL
migrations in [`migrations/`](migrations/), no ORM. Schema: `subjects`
(seeded from [`vocab.py`](vocab.py)), `images`, `image_tags`,
`image_vectors`, `posts`, `post_vectors`, `pairings`, `model_calls` (cost
ledger). See [BRIEF.md §4](BRIEF.md) for the full DDL and index list.

## Running it

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/pytest -v
```

Database: copy `.env.example` to `.env` and fill in `DATABASE_URL` from the
Supabase dashboard (Project Settings → Database) for the `autotagging`
project.

Vision/embeddings: requires a free Gemini API key from
[Google AI Studio](https://aistudio.google.com/apikey) (no credit card) —
`GEMINI_API_KEY` in `.env`. *(Wiring lands in Step 3.)*

`run:` / `seed:` commands for the full API are not available yet — see
[`capstone.yaml`](capstone.yaml), which is filled in as each phase ships.

## Evaluation

Top-1 precision on a small labeled eval set — *not measured yet, lands in
Step 5.* Number will be reported here and must match `EVIDENCE.md`.

## Limitations (honest, as of this writing)

- No vision pipeline yet — no images have actually been tagged.
- No embeddings/matching yet — the guard is proven only on hand-built mock
  candidates (`tests/test_guard.py`), not real ranked results.
- No API/review surface yet.
- No image corpus committed yet.
- `vector(1536)` in the migrations is a placeholder dimension; will be
  corrected to match Gemini's embedding output size in Step 4.

## Docs

- [BRIEF.md](BRIEF.md) — full architecture, data model, and build sequence.
- [IMPLEMENTATION_LOG.md](IMPLEMENTATION_LOG.md) — step-by-step technical
  build record, updated every step.
- [BUILDLOG.md](BUILDLOG.md) — honest AI-usage log: where AI helped, where
  it was wrong, what changed.
- [EVIDENCE.md](EVIDENCE.md) — one pasted proof per definition-of-done
  checkbox.
