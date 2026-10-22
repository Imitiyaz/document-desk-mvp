"""Integration test: Stage 1 loaders -> Stage 2 cleaning -> Stage 3
chunking -> Stage 4 embedding -> Stage 5 vector store -> Stage 6 retriever
-> Stage 7 prompt assembly, end-to-end against a real fixture file.

Uses the real Embedder and VectorStore classes with fake backends
injected (established pattern from Stage 5/6's own test suites), so this
runs with neither sentence_transformers nor chromadb installed.

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
from app.generation import build_prompt
from app.loaders.xlsx_loader import XlsxLoader
from app.retrieval import Retriever
from app.vectorstore import VectorStore
from tests.unit.test_vectorstore import FakeCollection


class _FakeEmbeddingBackend:
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


def test_full_pipeline_from_real_file_through_prompt_assembly(
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
        "What was the revenue?", top_k=3, source_file="sample_sales.xlsx"
    )

    prompt = build_prompt("What was the revenue?", results)

    assert "SYSTEM:" in prompt.text
    assert "What was the revenue?" in prompt.text
    assert len(prompt.citation_map) == len(results)
    for index, result in enumerate(results, start=1):
        assert prompt.citation_map[index] == result.metadata
    assert prompt.context_used == results


def test_full_pipeline_with_source_file_filter_excluding_everything_gives_no_context(
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
        "some question", source_file="a_file_that_was_never_ingested.pdf"
    )

    prompt = build_prompt("some question", results)

    assert "No relevant context was found" in prompt.text
    assert prompt.citation_map == {}
