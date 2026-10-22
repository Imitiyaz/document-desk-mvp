# SPDX-License-Identifier: AGPL-3.0-only
"""Application configuration, loaded from environment variables / .env.

Centralizing config here means no module ever reads `os.environ` directly
-- everything imports `settings` from this module. pydantic-settings
validates types at import time (fails fast with a clear error on a
malformed value) instead of failing confusingly deep inside some
unrelated function later.

Runtime consumers include logging, embedding, Chroma, retrieval, Ollama,
and the API's CORS/upload settings. The source-record SQLite ledger is scoped
to each Chroma directory/collection; sqlite_db_path is retained only for older
environment files and does not select the new ledger. `api_host`/`api_port` are
available configuration values; the documented Uvicorn command sets its
binding explicitly. Start from the repository root so .env and relative
data paths resolve consistently.

Author: Imitiyaz and AI Agent
Project: RAG MVP
Layer: Core
"""

from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Typed application settings, populated from `.env` if present."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "development"
    log_level: str = "INFO"

    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.1:8b-instruct-q4_K_M"

    ollama_context_length: int = Field(default=8192, ge=4096, le=32768)
    ollama_num_predict: int = Field(default=512, ge=64, le=2048)

    embedding_model: str = "BAAI/bge-base-en-v1.5"

    chroma_persist_dir: str = "./data/processed/chroma_db"
    chroma_collection_name: str = "documents"

    sqlite_db_path: str = "./data/processed/metadata.sqlite3"

    retrieval_top_k: int = Field(default=5, ge=1, le=100)

    api_host: str = "0.0.0.0"
    api_port: int = 8000
    cors_allowed_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    max_upload_bytes: int = Field(default=20 * 1024 * 1024, gt=0)
    max_extracted_rows: int = Field(default=25000, gt=0)
    max_xlsx_expanded_bytes: int = Field(default=100 * 1024 * 1024, gt=0)
    max_xlsx_columns: int = Field(default=512, ge=1, le=16384)
    max_pdf_pages: int = Field(default=200, gt=0)
    upload_temp_dir: str = "./data/processed/uploads"


settings = Settings()
