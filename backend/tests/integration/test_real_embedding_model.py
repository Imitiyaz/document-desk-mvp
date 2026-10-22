"""Tests that load and run the REAL embedding model (BAAI/bge-base-en-v1.5
by default). These require network access on first run (~440MB download
from Hugging Face, cached afterward) and take meaningfully longer than
the rest of the suite.

Excluded from the default `pytest` run via the `embedding_model` marker
(see pytest.ini's `addopts`). Run explicitly with:

    pytest -m embedding_model -v

This mirrors the `llm` marker convention documented in docs/testing.md
for tests that need a real local Ollama instance -- same reasoning:
real-dependency tests are valuable but must never make the default fast
suite slow, flaky, or network-dependent.

Author: Imitiyaz and AI Agent
Project: RAG MVP
Layer: Verification and synthetic fixtures
"""

from __future__ import annotations

import numpy as np
import pytest

from app.embedding.embedder import Embedder

pytestmark = pytest.mark.embedding_model


def test_real_model_produces_correct_dimensionality() -> None:
    embedder = Embedder()
    vectors = embedder.embed_passages(["The sky is blue."])
    assert len(vectors) == 1
    # bge-base-en-v1.5's known embedding dimension
    assert len(vectors[0]) == 768


def test_real_model_query_and_passage_embeddings_differ_for_identical_text() -> None:
    embedder = Embedder()
    text = "revenue grew significantly this quarter"
    query_vector = embedder.embed_query(text)
    passage_vector = embedder.embed_passages([text])[0]
    # Different because the query gets the instruction prefix and the
    # passage does not -- if these were ever equal, the instruction
    # prefixing logic would have silently broken.
    assert query_vector != passage_vector


def test_real_model_ranks_similar_sentences_above_dissimilar_ones() -> None:
    """Sanity check of actual retrieval quality, not just wiring --
    normalized vectors, so dot product == cosine similarity."""
    embedder = Embedder()
    vectors = embedder.embed_passages(
        [
            "The company's revenue increased significantly this quarter.",
            "Sales grew substantially in the third quarter.",
            "The weather today is sunny and warm.",
        ]
    )
    v = np.array(vectors)
    similarity_related = np.dot(v[0], v[1])
    similarity_unrelated = np.dot(v[0], v[2])
    assert similarity_related > similarity_unrelated


def test_real_model_query_retrieves_the_right_passage() -> None:
    """An end-to-end sanity check of the whole point of this stage: does
    a realistic query actually rank the relevant passage above an
    irrelevant one?"""
    embedder = Embedder()
    passages = [
        "In 'Q3 Sales': Region is North; Q3 Revenue is 45000; Q4 Revenue is 52000.",
        "In 'Q3 Sales': Region is South; Q3 Revenue is 38000; Q4 Revenue is 39500.",
    ]
    passage_vectors = np.array(embedder.embed_passages(passages))
    query_vector = np.array(
        embedder.embed_query("What was the North region's Q3 revenue?")
    )

    similarities = passage_vectors @ query_vector
    best_match_index = int(np.argmax(similarities))
    assert best_match_index == 0  # the North row, not the South row
