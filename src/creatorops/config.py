"""Central, typed configuration.

All settings are read from environment variables prefixed with ``CREATOROPS_``
(or from a ``.env`` file at the project root). See ``.env.example`` for the full list.

Usage::

    from creatorops.config import get_settings

    settings = get_settings()
    settings.db_path
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """Application settings. Defaults target a local, Ollama-only setup."""

    model_config = SettingsConfigDict(
        env_prefix="CREATOROPS_",
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- General -----------------------------------------------------------
    seed: int = 42
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"

    # --- Paths -------------------------------------------------------------
    data_dir: Path = PROJECT_ROOT / "data"
    manifest_path: Path | None = None  # defaults to <data_dir>/manifest.csv
    db_path: Path | None = None  # defaults to <data_dir>/creatorops.sqlite

    # --- Vector store (Qdrant) -----------------------------------------------
    qdrant_mode: Literal["local", "server"] = "local"
    qdrant_path: Path | None = None  # local mode storage, defaults to <data_dir>/qdrant
    qdrant_url: str = "http://localhost:6333"
    qdrant_collection: str = "creatorops_chunks"

    # --- Retrieval -------------------------------------------------------------
    embedding_model: str = "BAAI/bge-base-en-v1.5"
    reranker_model: str = "BAAI/bge-reranker-v2-m3"
    retrieval_top_k: int = Field(default=10, ge=1, le=100)

    # --- LLM ---------------------------------------------------------------
    # "fake" is a deterministic offline provider for tests and CI.
    llm_provider: Literal["ollama", "fake"] = "ollama"
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "qwen3:8b"
    ollama_judge_model: str = "qwen3:14b"
    llm_temperature: float = Field(default=0.0, ge=0.0, le=2.0)
    llm_timeout_s: float = Field(default=120.0, gt=0)

    # --- SQL guardrails ------------------------------------------------------
    sql_row_limit: int = Field(default=200, ge=1, le=10_000)
    sql_timeout_s: float = Field(default=5.0, gt=0)

    # --- Experiment tracking -----------------------------------------------
    mlflow_tracking_uri: str = f"file:{PROJECT_ROOT / 'mlruns'}"

    @model_validator(mode="after")
    def _fill_derived_paths(self) -> Settings:
        if self.manifest_path is None:
            self.manifest_path = self.data_dir / "manifest.csv"
        if self.db_path is None:
            self.db_path = self.data_dir / "creatorops.sqlite"
        if self.qdrant_path is None:
            self.qdrant_path = self.data_dir / "qdrant"
        return self


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the process-wide settings (cached). Call ``get_settings.cache_clear()`` in tests."""
    return Settings()
