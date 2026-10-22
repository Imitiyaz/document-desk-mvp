"""Integration test: Stage 1 loaders -> ... -> Stage 8 generation ->
Stage 9 citation resolution, end-to-end against a real fixture file.
Fake backends throughout (established pattern from Stage 5/6/7/8's own
test suites), so this runs with no real ML model, no real ChromaDB, and
no real Ollama instance required.

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
from app.generation import LLMClient, build_prompt, resolve_citations
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


class _FakeLLMBackend:
    def generate(self, prompt: str, model: str, temperature: float) -> str:
        assert "SYSTEM:" in prompt
        return "The North region's Q3 revenue was 45000. (Source: [1])"


def test_full_pipeline_from_real_file_through_citation_resolution(
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
    question = "What was the Q3 revenue for the North region?"
    results = retriever.retrieve(question, top_k=3, source_file="sample_sales.xlsx")

    prompt = build_prompt(question, results)
    llm_client = LLMClient(backend=_FakeLLMBackend(), model="fake-model")
    generated = llm_client.generate(prompt)

    resolved = resolve_citations(generated)

    assert "45000" in resolved.text
    assert len(resolved.citations) == 1
    assert resolved.citations[0].metadata.source_file == "sample_sales.xlsx"
    assert resolved.unresolved_citation_numbers == []
    assert resolved.model == "fake-model"


def test_full_pipeline_refusal_answer_resolves_to_no_citations(
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
    # A source_file filter that matches nothing -> empty context -> the
    # required refusal path, with no citation_map entries at all.
    results = retriever.retrieve("some question", source_file="never_ingested.pdf")
    prompt = build_prompt("some question", results)

    class _RefusalBackend:
        def generate(self, prompt: str, model: str, temperature: float) -> str:
            return "I don't have enough information in the provided documents to answer that."

    llm_client = LLMClient(backend=_RefusalBackend(), model="fake-model")
    generated = llm_client.generate(prompt)

    resolved = resolve_citations(generated)

    assert resolved.citations == []
    assert resolved.unresolved_citation_numbers == []
