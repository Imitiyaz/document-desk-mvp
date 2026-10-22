"""Integration test: Stage 1 loaders -> ... -> Stage 7 prompt assembly ->
Stage 8 LLM generation, end-to-end against a real fixture file. Uses fake
backends throughout (established pattern from Stage 5/6/7's own test
suites), so this runs with no real ML model, no real ChromaDB, and no
real Ollama instance required.

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
from app.generation import LLMClient, build_prompt
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
    """A canned LLM backend -- exercises real wiring through LLMClient
    without needing a real Ollama instance."""

    def generate(self, prompt: str, model: str, temperature: float) -> str:
        assert (
            "SYSTEM:" in prompt
        )  # confirms the real assembled prompt reached the backend
        return "The North region's Q3 revenue was 45000. (Source: [1])"


def test_full_pipeline_from_real_file_through_generation(
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
    answer = llm_client.generate(prompt)

    assert "45000" in answer.raw_text
    assert answer.prompt.citation_map == prompt.citation_map
    assert answer.model == "fake-model"
