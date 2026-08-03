"""Central settings — model names and thresholds live here, never as inline
literals in the modules that use them.
"""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str | None = None
    gemini_api_key: str
    vision_model: str = "gemini-3.1-flash-lite"
    embedding_model: str = "gemini-embedding-001"
    # gemini-embedding-001's native output is 3072 dims, over pgvector's
    # HNSW index limit (2000). 768 is a supported truncation (see
    # migrations/004_fix_vector_dimension.sql) — must match the `vector(N)`
    # column width exactly.
    embedding_dimensions: int = 768

    # Same conf_floor value used at ingestion (vision.derive_status) and at
    # matching time (guard.guard) — one signal, one threshold, no drift
    # between when a tag gets flagged and when the guard distrusts it.
    sim_floor: float = 0.35
    conf_floor: float = 0.6


settings = Settings()

# $ per token, keyed by the model version Gemini reports back (a requested
# model name can resolve to a different version, e.g. via an alias).
# Shared by vision.py and extraction.py — both call generate_content
# against settings.vision_model. Source: ai.google.dev/gemini-api/docs/
# pricing, checked 2026-08-03. Output price already includes thinking
# tokens.
GENERATE_CONTENT_PRICING_USD: dict[str, dict[str, float]] = {
    "gemini-3.1-flash-lite": {"input": 0.25e-6, "output": 1.50e-6},
    "gemini-3.5-flash-lite": {"input": 0.30e-6, "output": 2.50e-6},
    "gemini-3.6-flash": {"input": 1.50e-6, "output": 7.50e-6},
}
FALLBACK_GENERATE_CONTENT_PRICING_USD = GENERATE_CONTENT_PRICING_USD["gemini-3.1-flash-lite"]
