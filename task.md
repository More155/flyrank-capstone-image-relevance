# Image Relevance & Auto-Tagging

Build a system that looks at a library of images, understands what's actually in each one, tags them, and matches each image to the right blog post — so the article about red foxes gets a red-fox photo, not a generic dog, and never a wolf.

# Objectives
By the end you will be able to:
Turn perception into structure — call a vision model and get validated, structured tags out of an image.
Match by meaning, not filename — embed image descriptions and post text into one semantic space and rank relevance.

Build a mismatch guard — the production-critical part: knowing when the best candidate is still wrong , and refusing it.

Run vision/embeddings as a cost-tracked background job over many items.
Scope note: the Challenge 2 — relevance gate assignment is the decision core of this capstone in one sitting. Do it first; this capstone builds the whole system (ingest → classify → match → guard → review) around it.

# What you'll build
Given a set of images and a set of posts, a service that:
1. Ingests & classifies each image with a vision model → structured tags {subject, category, attributes[], caption, confidence} (runs as a batch job ; vision calls are slow/bulk).

2. Embeds each image's description and each post's text into a shared space.

3. Matches : for a post, ranks the most relevant images, flagging when even the best is weak ("no good image for this post").

4. Guards against mismatches : detects and refuses a bad pairing (the wolf-on-a-fox-post case) using tags and a similarity threshold.

5. Exposes a validated API + a tiny review surface (approve/reject a suggested pairing).

# Definition of done (core)

- Vision tagging as structured output with a validated schema; low confidence → flag, don't guess. (M6)

- Batch classification job with retries + cost tracking (model it on FlyRank's blog-existence batch + image job). (M5)

- Semantic matching : embed captions + post text; rank images per post; a paraphrase ("vulpes vulpes" vs "red fox") still matches. (M8)

- Mismatch guard : a clear rule (tags disagree, or similarity below threshold) that rejects a wrong pairing and explains why. Prove the fox/wolf/dog case. (M8)

- Data model : images, tags, embeddings, posts, suggested/approved pairings, the right indexes. (M2)

- Validated API + a minimal approve/reject surface. (M3)

- Cost tracking per vision/embedding call. (M6)

- Tests : schema-validation path; the mismatch guard (fox post rejects wolf); an eval on a small labeled set (top-1 precision). (M10)

- README + diagram.

# Realistic scope
Gather ~50 images across a few categories (e.g. animal species) — enough to be real, small enough to classify cheaply. Reuse the Challenge 2 eval set as your test seed. The review "UI" can be just endpoints + a one-page table.
Architecture sketch
` [images] ─(job)─► vision model ─► {tags, caption, confidence} ─► image_tags
└─► embed(caption) ───────────────► image_vectors
[posts] ───────► embed(post text) ──────────────────────────────► post_vectors
GET /posts/:id/images ─► rank by similarity ─► mismatch guard (tags + threshold)
─► {suggested | "no good match"} ─► review: approve/reject `

# Milestones
Wk3: design — the tag schema, the matching approach, the data model, your ~50-image corpus.
Wk5: the batch classification job producing structured tags.
Wk7: embeddings + matching + the mismatch guard.
Wk8: review API, cost tracking, the eval + tests, README.

# Stretch
Auto alt-text from the tags (real FlyRank concern). · Near-duplicate detection (perceptual hash / embedding distance). · "Best image" generation fallback when nothing matches (ties to generateImageForContent.ts). · Run it as a node on Capstone 1. · Human-in-the-loop agent QA for low-confidence pairings.

# Built from
A11 (structured vision output) · A12 (cost) · A15 (embeddings/retrieval) · A9 (batch job) · Challenge 2 (the matching/guard core).

# Demo
Show a folder of animal photos getting auto-tagged. Pick the "red fox" post → the fox photo surfaces on top, wolf and dog rank far below, and the guard refuses the wolf even if you force it. Show a post with no good image → "no confident match, here's why." Close with your precision number from the eval set.
