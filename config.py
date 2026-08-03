"""Central settings — model names and thresholds live here, never as inline
literals in the modules that use them.
"""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str | None = None
    gemini_api_key: str
    vision_model: str = "gemini-flash-latest"
    embedding_model: str = "gemini-embedding-001"

    # Same conf_floor value used at ingestion (vision.derive_status) and at
    # matching time (guard.guard) — one signal, one threshold, no drift
    # between when a tag gets flagged and when the guard distrusts it.
    sim_floor: float = 0.35
    conf_floor: float = 0.6


settings = Settings()
