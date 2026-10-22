"""HTTP ingestion/query with real persisted ChromaDB and real parsers, no ML download.

Author: Imitiyaz and AI Agent
Project: RAG MVP
Layer: Verification and synthetic fixtures
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.api.service import PipelineService
from app.core.config import settings
from app.embedding import Embedder
from app.generation import LLMClient
from app.main import create_app
from app.retrieval import Retriever
from app.structured.store import RecordStore
from app.vectorstore import VectorStore
from tests.api_fakes import ScriptedLLM, TinyEncoder

pytestmark = pytest.mark.vectorstore


def test_api_source_identity_survives_real_index_reopen(
    tmp_path, monkeypatch, sample_sales_xlsx
) -> None:
    monkeypatch.setattr(settings, "upload_temp_dir", str(tmp_path / "uploads"))
    embedder = Embedder(backend=TinyEncoder())

    def service():
        store = VectorStore(
            persist_dir=str(tmp_path / "chroma"), collection_name="api_test"
        )
        return PipelineService(
            embedder,
            store,
            Retriever(embedder, store),
            LLMClient(backend=ScriptedLLM(), model="test-model"),
            RecordStore(str(tmp_path / "chroma" / "records.sqlite3")),
        )

    with TestClient(create_app(service)) as client:
        response = client.post(
            "/documents",
            files={"file": (sample_sales_xlsx.name, sample_sales_xlsx.read_bytes())},
        )
        assert response.status_code == 201, response.text
    # A fresh application must detect earlier ingestion through stored metadata,
    # not a transient in-memory filename registry.
    with TestClient(create_app(service)) as client:
        duplicate = client.post(
            "/documents",
            files={"file": (sample_sales_xlsx.name, sample_sales_xlsx.read_bytes())},
        )
        assert duplicate.status_code == 409
        response = client.post(
            "/query",
            json={
                "question": "North Q3 revenue",
                "source_file": sample_sales_xlsx.name,
                "top_k": 1,
            },
        )
        assert response.status_code == 200, response.text
        citation = response.json()["citations"][0]
        assert citation["source_file"] == sample_sales_xlsx.name
        assert citation["row_or_location"] == 2
        assert list((tmp_path / "uploads").iterdir()) == []
