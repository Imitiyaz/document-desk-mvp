"""Unit tests for app.core.config.

These mainly verify that Settings loads with sensible defaults when no
.env file is present -- important because CI environments and fresh
clones won't have a .env until the developer creates one from
.env.example (see docs/setup.md).

Author: Imitiyaz and AI Agent
Project: RAG MVP
Layer: Verification and synthetic fixtures
"""

from __future__ import annotations

from app.core.config import Settings


def test_settings_have_sensible_defaults() -> None:
    settings = Settings(_env_file=None)  # ignore any real .env for this test

    assert settings.app_env == "development"
    assert settings.log_level == "INFO"
    assert settings.ollama_model == "llama3.1:8b-instruct-q4_K_M"
    assert settings.embedding_model == "BAAI/bge-base-en-v1.5"
    assert settings.retrieval_top_k == 5


def test_settings_can_be_overridden_via_env(monkeypatch) -> None:
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")
    monkeypatch.setenv("RETRIEVAL_TOP_K", "10")

    settings = Settings(_env_file=None)

    assert settings.log_level == "DEBUG"
    assert settings.retrieval_top_k == 10
