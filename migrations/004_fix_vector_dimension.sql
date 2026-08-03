-- 004_fix_vector_dimension.sql
-- 001_init.sql used vector(1536) as a placeholder pending the real
-- embedding model choice. gemini-embedding-001's native output is 3072
-- dims, which exceeds pgvector's HNSW index limit (2000) — using
-- output_dimensionality=768 (Gemini's supported truncation) instead.
-- Cosine distance is scale-invariant, so truncated/non-unit-norm vectors
-- rank identically to normalized ones; no normalization needed.
--
-- Both tables are still empty (embeddings land later in this same step),
-- so this is a plain column-type change, not a backfill.

drop index if exists image_vectors_embedding_idx;
drop index if exists post_vectors_embedding_idx;

alter table image_vectors alter column embedding type vector(768);
alter table post_vectors alter column embedding type vector(768);

create index on image_vectors using hnsw (embedding vector_cosine_ops);
create index on post_vectors using hnsw (embedding vector_cosine_ops);
