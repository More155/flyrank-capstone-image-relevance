-- 003_enable_rls.sql
-- This app talks to Postgres directly via psycopg, never through Supabase's
-- PostgREST/anon-key layer. Enable RLS with no policies on every table so
-- that layer can't read or write anything, even if a publishable key leaks.
-- Direct connections (the app's own role) are unaffected by RLS here.

alter table subjects       enable row level security;
alter table images         enable row level security;
alter table image_tags     enable row level security;
alter table image_vectors  enable row level security;
alter table posts          enable row level security;
alter table post_vectors   enable row level security;
alter table pairings       enable row level security;
alter table model_calls    enable row level security;
