"""Database access — a thin psycopg3 wrapper. No ORM.

Connects with whatever role owns the Postgres connection string; RLS
(migrations/003_enable_rls.sql) only affects Supabase's PostgREST/anon-key
path, not this direct connection.
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

import psycopg
from pgvector.psycopg import register_vector
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str


settings = Settings()


@contextmanager
def get_connection() -> Iterator[psycopg.Connection]:
    with psycopg.connect(settings.database_url) as conn:
        register_vector(conn)
        yield conn
