"""Project settings.

Values can be changed with environment variables that start with CREATOROPS_
(for example CREATOROPS_OLLAMA_MODEL=llama3.1:8b) or in a .env file.
"""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT_DIR / "data"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="CREATOROPS_", env_file=ROOT_DIR / ".env", extra="ignore"
    )

    seed: int = 42

    # files
    data_dir: Path = DATA_DIR
    manifest_path: Path = DATA_DIR / "manifest.csv"
    db_path: Path = DATA_DIR / "creatorops.sqlite"

    # vector store: "local" (no docker needed) or "server" (docker compose)
    qdrant_mode: str = "local"
    qdrant_path: Path = DATA_DIR / "qdrant"
    qdrant_url: str = "http://localhost:6333"
    collection_name: str = "chunks"

    # retrieval
    embedding_model: str = "BAAI/bge-base-en-v1.5"
    reranker_model: str = "BAAI/bge-reranker-v2-m3"
    top_k: int = 10

    # llm: "ollama" or "fake" (fake is used in tests and CI)
    llm_provider: str = "ollama"
    ollama_url: str = "http://localhost:11434"
    ollama_model: str = "qwen3:8b"
    temperature: float = 0.0

    # sql tool limits
    sql_max_rows: int = 200
    sql_timeout_s: float = 5.0


settings = Settings()
