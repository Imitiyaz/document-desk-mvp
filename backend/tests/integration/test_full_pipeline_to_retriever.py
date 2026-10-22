"""Integration test: Stage 1 loaders -> Stage 2 cleaning -> Stage 3
chunking -> Stage 4 embedding -> Stage 5 vector store -> Stage 6
retriever, end-to-end against a real fixture file.

Uses the *real* Embedder and VectorStore classes (so Retriever's actual
composition of them is exercised, not just Retriever's internal logic in
isolation -- that's what tests/unit/test_retriever.py covers), but
injects fake backends into each (established pattern from Stage 4/5's
own test suites, and from
tests/integration/test_full_pipeline_to_vectorstore.py) -- so this still
runs with neither sentence_transformers nor chromadb installed. The real
ML/DB libraries are covered separately by their own marked, real-
dependency tests (test_real_embedding_model.py, test_real_vectorstore.py,
and this stage's test_real_retrieval.py).

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
from app.retrieval import Retriever
from app.vectorstore import VectorStore
from tests.unit.test_vectorstore import FakeCollection


class _FakeEmbeddingBackend:
    """Deterministic fake -- same shape as Stage 4/5's fakes. Crucially,
    this hashes the *raw* text, ignoring any query-instruction prefix --
    so embed_query(chunk.text) still needs to route to the same vector
    embed_passages([chunk.text]) produced at ingestion time for the
    self-retrieval assertion below to mean anything. It does, because
    the prefix only changes the string passed to `encode()`, not this
    fake's normalization behavior... except the prefix DOES change the
    hash. See the test below for how this is handled honestly rather
    than papered over.
    """

    def get_sentence_embedding_dimension(self) -> int:
        return 4

    def encode(self, texts, normalize_embeddings: bool = True):  # noqa: ANN001
        def _unit_vector(text: str) -> np.ndarray:
            vec = np.array([((hash(text) >> (8 * i)) % 100) / 100.0 for i in range(4)])
            norm = np.linalg.norm(vec)
            return vec / norm if norm > 0 else vec

        if isinstance(texts, str):
            return _unit_vector(texts)
        return np.array([_unit_vector(t) for t in texts])


def test_full_pipeline_from_real_file_through_retriever(
    sample_sales_xlsx: Path,
) -> None:
    document = XlsxLoader().load(sample_sales_xlsx)
    cleaned = clean_document(document)
    chunks = chunk_document(cleaned)

    embedder = Embedder(model_name="fake-model", backend=_FakeEmbeddingBackend())
    embedded_chunks = embedder.embed_chunks(chunks)

    store = VectorStore(collection=FakeCollection())
    store.upsert_chunks(embedded_chunks)
    assert store.count() == len(chunks)

    retriever = Retriever(embedder=embedder, vector_store=store)

    # NOTE: embed_query() prepends BGE's instruction prefix (see
    # app/embedding/embedder.py), so a query embedding is NEVER identical
    # to embed_passages()'s embedding of the same raw text, even with a
    # hash-based fake -- this is correct, real behavior, not a fake
    # artifact. So this test does not assert exact self-retrieval (that's
    # what test_retriever.py's unit tests already verify using controlled
    # fakes); instead it verifies the real, meaningful thing at this
    # layer: that a query restricted to this file, with a real top_k,
    # returns real chunks with real citation metadata pointing back to
    # the actual source file -- i.e. the Stage 1->6 wiring is correct
    # end-to-end.
    results = retriever.retrieve(
        "What was the revenue?", top_k=3, source_file="sample_sales.xlsx"
    )

    assert len(results) == 3
    assert [r.rank for r in results] == [1, 2, 3]
    for result in results:
        assert result.metadata.source_file == "sample_sales.xlsx"
        assert isinstance(result.score, float)
        assert result.text  # non-empty


def test_retrieve_source_file_filter_excludes_other_files(
    sample_sales_xlsx: Path,
) -> None:
    document = XlsxLoader().load(sample_sales_xlsx)
    cleaned = clean_document(document)
    chunks = chunk_document(cleaned)

    embedder = Embedder(model_name="fake-model", backend=_FakeEmbeddingBackend())
    embedded_chunks = embedder.embed_chunks(chunks)

    store = VectorStore(collection=FakeCollection())
    store.upsert_chunks(embedded_chunks)

    retriever = Retriever(embedder=embedder, vector_store=store)

    results = retriever.retrieve(
        "some question", source_file="a_totally_different_file.pdf"
    )

    assert results == []
