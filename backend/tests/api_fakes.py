"""Shared lightweight backends; actual parsers, service and HTTP stack remain real.

Author: Imitiyaz and AI Agent
Project: RAG MVP
Layer: Verification and synthetic fixtures
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from app.api.service import PipelineService
from app.embedding import Embedder
from app.generation import LLMClient
from app.retrieval import Retriever
from app.vectorstore import VectorStore
from tests.unit.test_vectorstore import FakeCollection


class TinyEncoder:
    """Small deterministic keyword vectors; these tests do not measure BGE quality."""

    def get_sentence_embedding_dimension(self) -> int:
        return 4

    def encode(self, texts, normalize_embeddings=True):
        single = isinstance(texts, str)
        values = [texts] if single else texts
        vectors = np.array(
            [
                [float(word in text.lower()) for word in ("north", "south", "east")]
                + [0.1]
                for text in values
            ]
        )
        if normalize_embeddings:
            vectors = vectors / np.linalg.norm(vectors, axis=1, keepdims=True)
        return vectors[0] if single else vectors


class ScriptedLLM:
    """Records prompts and returns controlled text, never pretending to reason."""

    def __init__(self) -> None:
        self.text = "45000 (Source: [1])"
        self.error: Exception | None = None
        self.prompts: list[str] = []
        self.close_count = 0

    def generate(self, prompt: str, model: str, temperature: float) -> str:
        self.prompts.append(prompt)
        if self.error:
            raise self.error
        return self.text

    def close(self) -> None:
        self.close_count += 1


@dataclass
class ApiBundle:
    """Expose test backends for assertions while keeping the production service real."""

    service: PipelineService
    collection: FakeCollection
    store: VectorStore
    llm: ScriptedLLM


def make_bundle() -> ApiBundle:
    """Build every pipeline wrapper with tiny injected backends."""
    embedder = Embedder(backend=TinyEncoder())
    collection = FakeCollection()
    store = VectorStore(collection=collection)
    llm = ScriptedLLM()
    service = PipelineService(
        embedder,
        store,
        Retriever(embedder, store),
        LLMClient(backend=llm, model="test-model", max_attempts=1),
    )
    return ApiBundle(service, collection, store, llm)
