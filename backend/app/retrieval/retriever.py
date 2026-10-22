# SPDX-License-Identifier: AGPL-3.0-only
"""Turns a natural-language question into a ranked list of the most
relevant chunks, ready for Stage 7 (Prompt Engineering) to assemble into
a grounded LLM prompt.

Constructor injection keeps encoder and storage adapters replaceable in tests.
The caller owns the supplied instances; this retriever does not create hidden clients.

Author: Imitiyaz and AI Agent
Project: RAG MVP
Layer: Retrieval
"""

from __future__ import annotations

from typing import Protocol

from loguru import logger

from app.core.config import settings
from app.embedding.embedder import Embedder
from app.retrieval.models import RetrievalResult
from app.vectorstore.chroma_client import VectorStore
from app.vectorstore.models import RetrievedMatch


class QueryEmbedder(Protocol):
    """The minimal interface Retriever needs to turn query text into a
    vector. Implemented by `app.embedding.embedder.Embedder` (used by
    default) and by any lightweight test double.
    """

    def embed_query(self, text: str) -> list[float]:
        """Embed a search query using query-specific instructions, not passage encoding."""
        ...  # noqa: E704


class ChunkSearcher(Protocol):
    """The minimal interface Retriever needs to run a similarity search.
    Implemented by `app.vectorstore.chroma_client.VectorStore` (used by
    default) and by any lightweight test double.
    """

    def query(
        self,
        query_vector: list[float],
        top_k: int = 5,
        where: dict[str, str] | None = None,
    ) -> list[RetrievedMatch]:
        """Return the backend result contract for the requested embedding and scope."""
        ...  # noqa: E704


def _distance_to_score(distance: float) -> float:
    """Converts ChromaDB's cosine distance to a cosine similarity score.

    ChromaDB's collection was created with `{"hnsw:space": "cosine"}`
    (Stage 5), and Stage 4's Embedder always normalizes vectors
    (`normalize_embeddings=True`). For normalized vectors, cosine
    distance is defined as `1 - cosine_similarity`, so this conversion
    is exact -- not an approximation -- as long as both of those upstream
    invariants hold. `score` is bigger-is-better (matches how a human,
    or an LLM prompt, intuitively reads "relevance"); `distance` is
    smaller-is-better (ChromaDB's native convention). Keeping the raw
    `RetrievedMatch.distance` and the derived `RetrievalResult.score` as
    two different field names in two different types (rather than one
    field two stages disagree on the meaning of) is deliberate -- see
    `retrieval/models.py`'s module docstring.
    """
    return 1.0 - distance


class Retriever:
    """Retrieves the most relevant chunks for a natural-language query."""

    def __init__(
        self,
        embedder: QueryEmbedder | None = None,
        vector_store: ChunkSearcher | None = None,
    ) -> None:
        """
        Args:
            embedder: Injected query embedder. If omitted, a real
                `Embedder()` is constructed (downloads/loads the model
                per Stage 4's fail-fast behavior).
            vector_store: Injected similarity searcher. If omitted, a
                real `VectorStore()` is constructed (connects to
                ChromaDB per Stage 5's fail-fast behavior).
        """
        self._embedder: QueryEmbedder = embedder if embedder is not None else Embedder()
        self._vector_store: ChunkSearcher = (
            vector_store if vector_store is not None else VectorStore()
        )

    def retrieve(
        self,
        query: str,
        top_k: int | None = None,
        source_file: str | None = None,
        min_score: float | None = None,
    ) -> list[RetrievalResult]:
        """Returns the top_k most relevant chunks for `query`, ranked by
        similarity score (best first).

        Args:
            query: The user's natural-language question. Must be
                non-empty after stripping whitespace.
            top_k: Maximum number of results to return. Defaults to
                `settings.retrieval_top_k` if omitted.
            source_file: If given, restricts the search to chunks from
                this one source file (e.g. "sample_sales.xlsx") --
                supports "ask a question about just this document."
            min_score: If given, drops any result whose similarity score
                is below this threshold. Omitted by default (no
                filtering) -- Stage 7 hasn't built a real evaluation
                question set yet, so a default cutoff here would be a
                guess, not a measured choice. Callers who already know
                their retrieval quality profile can set one explicitly.

        Returns:
            A list of RetrievalResult, ranked best-first (rank 1 =
            most similar). Empty list if the store has no matches for
            this query (e.g., empty collection, or an over-strict
            min_score/source_file filter) -- this is a valid, expected
            outcome, not an error condition; callers (Stage 7) decide
            how to handle "no relevant context found."

        Raises:
            ValueError: If `query` is empty or whitespace-only. Embedding
                and searching for a blank query is never a meaningful
                operation, and failing loudly here is cheaper than a
                confusing, silently-wrong empty-vector search two layers
                down.
        """
        if not query or not query.strip():
            raise ValueError("query must not be empty or whitespace-only")

        effective_top_k = top_k if top_k is not None else settings.retrieval_top_k
        where = {"source_file": source_file} if source_file is not None else None

        logger.info(
            "Retrieving top {} chunk(s) for query: {!r}{}",
            effective_top_k,
            query,
            f" (filtered to source_file={source_file!r})" if source_file else "",
        )

        query_vector = self._embedder.embed_query(query)
        matches = self._vector_store.query(
            query_vector=query_vector, top_k=effective_top_k, where=where
        )

        results = [
            RetrievalResult(
                text=match.text,
                metadata=match.metadata,
                score=_distance_to_score(match.distance),
                rank=rank,
            )
            for rank, match in enumerate(matches, start=1)
        ]

        if min_score is not None:
            results = [result for result in results if result.score >= min_score]

        logger.info("Retrieved {} result(s) for query: {!r}", len(results), query)
        return results
