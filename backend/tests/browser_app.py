"""Browser-only server: actual API/parsers/SQLite; default Chroma, test embeddings.

RAG_TEST_VECTOR_BACKEND=fake explicitly selects protocol fakes for isolated
verification; this mode never establishes native vector-store acceptance.

Never the deployment entrypoint. The browser suite discloses this substitution;
separate marked tests exercise the real BGE model.

Author: Imitiyaz and AI Agent
Project: RAG MVP
Layer: Verification and synthetic fixtures
"""

import os
from pathlib import Path

from app.api.service import PipelineService
from app.core.config import settings
from app.embedding import Embedder
from app.generation import LLMClient
from app.main import create_app
from app.retrieval import Retriever
from app.structured.store import RecordStore
from app.vectorstore import VectorStore
from tests.api_fakes import ScriptedLLM, TinyEncoder


def create_browser_service() -> PipelineService:
    """Use production wrappers and real persistence in an isolated test directory."""
    embedder = Embedder(backend=TinyEncoder())
    mode = os.environ.get("RAG_TEST_VECTOR_BACKEND", "real")
    if mode == "fake":
        from tests.unit.test_vectorstore import FakeCollection

        store = VectorStore(collection=FakeCollection())
    elif mode == "real":
        store = VectorStore(persist_dir=settings.chroma_persist_dir)
    else:
        raise ValueError("Unknown test-only vector backend: " + mode)
    return PipelineService(
        embedder,
        store,
        Retriever(embedder, store),
        LLMClient(backend=ScriptedLLM()),
        RecordStore(str(Path(settings.chroma_persist_dir) / "records.sqlite3")),
    )


app = create_app(create_browser_service)
