# Image Relevance & Auto-Tagging

FlyRank Backend Track capstone — "AI Image Understanding & Content Matching
Engine." Understands what's actually in an image library, tags it, and
matches each image to the right blog post: a red-fox post gets the red-fox
photo, never the wolf. The production-critical part isn't finding a match —
it's a **mismatch guard** that refuses a wrong pairing and explains why.

**Status: in progress.** Steps 1–4 of 5 are done (see
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
`GEMINI_API_KEY` in `.env`.

Seed the corpus and run vision tagging for real:

```bash
.venv/bin/python -m scripts.seed_corpus   # idempotent, inserts the 48-image corpus
.venv/bin/python -m jobs.classify         # tags every untagged image
.venv/bin/python -m jobs.embed_images     # embeds every tagged image's caption
.venv/bin/python -m scripts.seed_posts    # seeds 8 sample posts + subject extraction
.venv/bin/python -m scripts.verify_matching  # live proof: ranking, guard rejection, paraphrase, no-match
```

Note: `DATABASE_URL` must point at Supabase's **connection pooler**
(`aws-0-<region>.pooler.supabase.com:6543`, username
`postgres.<project-ref>`), not the direct-connection host — the direct host
is IPv6-only and unreachable from most networks. `.env.example` has the
exact format.

`run:` for the full API is not available yet — see
[`capstone.yaml`](capstone.yaml), filled in as each phase ships.

## Evaluation

Formal top-1 precision script lands in Step 5. The same underlying signal
already exists informally: all 48 tagged images match their corpus label
(100%), and `scripts/verify_matching.py`'s 4 live checks — fox post ranks
fox, a forced real wolf candidate on the fox post is rejected, the
"Vulpes vulpes" paraphrase still matches fox, the no-coverage (elephant)
post gets `no_match` — all pass. See `EVIDENCE.md` for the pasted output.

## Limitations (honest, as of this writing)

- No API/review surface yet — matching only runs via
  `matching.match_images_for_post()` directly or `scripts/verify_matching.py`,
  not over HTTP.
- No formal eval script yet (top-1 precision as a single reported number);
  the informal signal above exists but isn't the Step 5 deliverable.
- The corpus (`corpus.py`) is 48 images, not exactly ~50 — 8 per species
  across the 6 species in `vocab.py`.
- Default vision model is `gemini-3.1-flash-lite`, not the newest
  `gemini-3.6-flash` — the latter's free tier is 20 requests/day, too low
  for a 48-image batch. See BUILDLOG.md.
- Embedding cost tracking (`embeddings.py`) estimates tokens from text
  length (`len(text) // 4`) rather than a real usage field — Gemini's
  `embed_content` doesn't return one in this SDK version. Approximate, not
  exact.

## Docs

- [BRIEF.md](BRIEF.md) — full architecture, data model, and build sequence.
- [IMPLEMENTATION_LOG.md](IMPLEMENTATION_LOG.md) — step-by-step technical
  build record, updated every step.
- [BUILDLOG.md](BUILDLOG.md) — honest AI-usage log: where AI helped, where
  it was wrong, what changed.
- [EVIDENCE.md](EVIDENCE.md) — one pasted proof per definition-of-done
  checkbox.
