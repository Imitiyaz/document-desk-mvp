"""Integration test: Stage 1 loaders -> Stage 2 cleaning -> Stage 3
chunking -> Stage 4 embedding -> Stage 5 vector store, end-to-end
against real fixture files. Uses a FakeBackend for the embedder and a
FakeCollection for the vector store (both already established patterns
from their respective unit test suites) -- this test verifies the full
pipeline's wiring is correct, not the real ML libraries themselves
(those are covered by their own marked, real-dependency tests).

Author: Imitiyaz and AI Agent
Project: RAG MVP
Layer: Verification and synthetic fixtures
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

from app.chunking import chunk_document
from app.cleaning import clean_document
from app.embedding import Embedder
from app.loaders.xlsx_loader import XlsxLoader
from app.vectorstore import VectorStore
from tests.unit.test_vectorstore import FakeCollection


class _FakeEmbeddingBackend:
    """Deterministic fake -- same shape as Stage 4's FakeBackend."""

    def get_sentence_embedding_dimension(self) -> int:
        return 4

    def encode(self, texts, normalize_embeddings: bool = True):  # noqa: ANN001
        # Deterministic, distinct vectors per unique text (hash-based, not
        # semantically meaningful -- this test checks wiring, not retrieval
        # quality). Normalized to unit length, matching the real contract
        # (Stage 4 always normalizes) -- without this, a self-query isn't
        # actually guaranteed to retrieve itself first, since raw dot
        # product can favor a larger-magnitude vector over an
        # identical-direction one.
        def _unit_vector(text: str) -> np.ndarray:
            vec = np.array([((hash(text) >> (8 * i)) % 100) / 100.0 for i in range(4)])
            norm = np.linalg.norm(vec)
            return vec / norm if norm > 0 else vec

        if isinstance(texts, str):
            return _unit_vector(texts)
        return np.array([_unit_vector(t) for t in texts])


def test_full_pipeline_from_real_file_to_vector_store(sample_sales_xlsx: Path) -> None:
    document = XlsxLoader().load(sample_sales_xlsx)
    cleaned = clean_document(document)
    chunks = chunk_document(cleaned)

    embedder = Embedder(model_name="fake-model", backend=_FakeEmbeddingBackend())
    embedded_chunks = embedder.embed_chunks(chunks)

    store = VectorStore(collection=FakeCollection())
    stored_count = store.upsert_chunks(embedded_chunks)

    assert stored_count == len(chunks) == 6
    assert store.count() == 6

    # Query using one of the actual stored vectors -- should retrieve itself first
    query_vector = embedded_chunks[0].vector
    results = store.query(query_vector=query_vector, top_k=1)
    assert results[0].text == embedded_chunks[0].text
    assert results[0].metadata.source_file == "sample_sales.xlsx"
