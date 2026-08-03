-- 001_init.sql
-- Core schema per BRIEF.md section 4. Hand-written, no ORM.
--
-- Embedding dimension is a placeholder (1536) until Step 4 picks the actual
-- embedding model — captions and posts must share one model/dimension, so
-- this will be revisited then if the chosen model's dimension differs.

create extension if not exists vector;

create table subjects (
    id       text primary key,
    display  text not null,
    synonyms text[] not null default '{}',
    family   text
);

create table images (
    id          uuid primary key default gen_random_uuid(),
    source_uri  text not null,
    storage_url text,
    sha256      text unique,
    created_at  timestamptz not null default now()
);

create table image_tags (
    image_id    uuid primary key references images(id),
    subject     text references subjects(id),
    category    text,
    attributes  text[],
    caption     text,
    confidence  real,
    status      text not null,
    model       text,
    created_at  timestamptz not null default now()
);

create table image_vectors (
    image_id  uuid primary key references images(id),
    embedding vector(1536),
    model     text
);

create table posts (
    id                 uuid primary key default gen_random_uuid(),
    title              text not null,
    body               text not null,
    subject            text references subjects(id),
    subject_confidence real
);

create table post_vectors (
    post_id   uuid primary key references posts(id),
    embedding vector(1536),
    model     text
);

create table pairings (
    id          uuid primary key default gen_random_uuid(),
    post_id     uuid references posts(id),
    image_id    uuid references images(id),
    similarity  real,
    verdict     text,
    reason      text,
    explanation text,
    status      text,
    note        text,
    created_at  timestamptz not null default now()
);

create table model_calls (
    id           uuid primary key default gen_random_uuid(),
    kind         text not null,
    model        text not null,
    input_units  int not null,
    output_units int not null,
    cost_usd     numeric(10, 6) not null,
    ref_id       uuid,
    ok           boolean not null,
    attempt      int not null default 1,
    created_at   timestamptz not null default now()
);

create index on image_vectors using hnsw (embedding vector_cosine_ops);
create index on post_vectors using hnsw (embedding vector_cosine_ops);
create index on image_tags (subject);
create index on image_tags (status);
create index on pairings (post_id, status);
create index on model_calls (kind, created_at);
