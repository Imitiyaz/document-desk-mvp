"""Retriever ranking, score, filter and validation contracts.

Inject encoder/searcher protocols without loading model or vector runtimes.
Separate marked integration tests exercise real BGE and Chroma.
Author: Imitiyaz and AI Agent
"""

from __future__ import annotations

import pytest

from app.models.extracted import SourceMetadata
from app.retrieval.retriever import Retriever
from app.vectorstore.models import RetrievedMatch


class FakeEmbedder:
    """A QueryEmbedder test double. Returns a fixed vector regardless of
    input text (unit tests here care about Retriever's own logic --
    score conversion, ranking, filtering -- not real embedding quality;
    that's what the marked real-model integration test is for).
    """

    def __init__(self) -> None:
        self.calls: list[str] = []

    def embed_query(self, text: str) -> list[float]:
        self.calls.append(text)
        return [0.1, 0.2, 0.3]


class FakeSearcher:
    """A ChunkSearcher test double. Returns a pre-configured, fixed list
    of RetrievedMatch and records the arguments it was called with, so
    tests can assert Retriever passed top_k/where through correctly.
    """

    def __init__(self, matches: list[RetrievedMatch]) -> None:
        self._matches = matches
        self.last_query_vector: list[float] | None = None
        self.last_top_k: int | None = None
        self.last_where: dict[str, str] | None = None

    def query(
        self,
        query_vector: list[float],
        top_k: int = 5,
        where: dict[str, str] | None = None,
    ) -> list[RetrievedMatch]:
        self.last_query_vector = query_vector
        self.last_top_k = top_k
        self.last_where = where
        return self._matches[:top_k]


def make_match(text: str, distance: float, row: int = 1) -> RetrievedMatch:
    return RetrievedMatch(
        text=text,
        metadata=SourceMetadata(
            source_file="sample_sales.xlsx",
            sheet_or_page="Q3 Sales",
            row_or_location=row,
        ),
        distance=distance,
    )


def test_retrieve_converts_distance_to_similarity_score() -> None:
    searcher = FakeSearcher([make_match("North region text", distance=0.2)])
    retriever = Retriever(embedder=FakeEmbedder(), vector_store=searcher)

    results = retriever.retrieve("What was North region revenue?")

    assert len(results) == 1
    assert results[0].score == pytest.approx(0.8)


def test_retrieve_assigns_1_indexed_rank_in_returned_order() -> None:
    searcher = FakeSearcher(
        [
            make_match("best match", distance=0.1, row=1),
            make_match("second match", distance=0.4, row=2),
            make_match("third match", distance=0.6, row=3),
        ]
    )
    retriever = Retriever(embedder=FakeEmbedder(), vector_store=searcher)

    results = retriever.retrieve("some question")

    assert [r.rank for r in results] == [1, 2, 3]
    assert [r.text for r in results] == ["best match", "second match", "third match"]


def test_retrieve_carries_citation_metadata_through_unchanged() -> None:
    searcher = FakeSearcher([make_match("North region text", distance=0.2, row=7)])
    retriever = Retriever(embedder=FakeEmbedder(), vector_store=searcher)

    results = retriever.retrieve("some question")

    assert results[0].metadata.source_file == "sample_sales.xlsx"
    assert results[0].metadata.sheet_or_page == "Q3 Sales"
    assert results[0].metadata.row_or_location == 7


def test_retrieve_uses_settings_default_top_k_when_not_provided() -> None:
    from app.core.config import settings

    searcher = FakeSearcher([make_match("a", distance=0.1)])
    retriever = Retriever(embedder=FakeEmbedder(), vector_store=searcher)

    retriever.retrieve("some question")

    assert searcher.last_top_k == settings.retrieval_top_k


def test_retrieve_passes_explicit_top_k_through() -> None:
    searcher = FakeSearcher([make_match("a", distance=0.1)])
    retriever = Retriever(embedder=FakeEmbedder(), vector_store=searcher)

    retriever.retrieve("some question", top_k=2)

    assert searcher.last_top_k == 2


def test_retrieve_with_source_file_builds_metadata_filter() -> None:
    searcher = FakeSearcher([make_match("a", distance=0.1)])
    retriever = Retriever(embedder=FakeEmbedder(), vector_store=searcher)

    retriever.retrieve("some question", source_file="sample_sales.xlsx")

    assert searcher.last_where == {"source_file": "sample_sales.xlsx"}


def test_retrieve_without_source_file_passes_no_filter() -> None:
    searcher = FakeSearcher([make_match("a", distance=0.1)])
    retriever = Retriever(embedder=FakeEmbedder(), vector_store=searcher)

    retriever.retrieve("some question")

    assert searcher.last_where is None


def test_retrieve_embeds_query_via_embed_query_not_embed_passages() -> None:
    embedder = FakeEmbedder()
    searcher = FakeSearcher([make_match("a", distance=0.1)])
    retriever = Retriever(embedder=embedder, vector_store=searcher)

    retriever.retrieve("What was North region revenue?")

    assert embedder.calls == ["What was North region revenue?"]
    assert searcher.last_query_vector == [0.1, 0.2, 0.3]


def test_retrieve_applies_min_score_filter() -> None:
    searcher = FakeSearcher(
        [
            make_match("strong match", distance=0.1),  # score 0.9
            make_match("weak match", distance=0.85),  # score 0.15
        ]
    )
    retriever = Retriever(embedder=FakeEmbedder(), vector_store=searcher)

    results = retriever.retrieve("some question", min_score=0.5)

    assert len(results) == 1
    assert results[0].text == "strong match"


def test_retrieve_without_min_score_returns_everything_the_store_returns() -> None:
    searcher = FakeSearcher(
        [
            make_match("strong match", distance=0.1),
            make_match("weak match", distance=0.85),
        ]
    )
    retriever = Retriever(embedder=FakeEmbedder(), vector_store=searcher)

    results = retriever.retrieve("some question")

    assert len(results) == 2


def test_retrieve_returns_empty_list_when_store_has_no_matches() -> None:
    searcher = FakeSearcher([])
    retriever = Retriever(embedder=FakeEmbedder(), vector_store=searcher)

    results = retriever.retrieve("some question")

    assert results == []


@pytest.mark.parametrize("blank_query", ["", "   ", "\n\t"])
def test_retrieve_raises_value_error_on_blank_query(blank_query: str) -> None:
    retriever = Retriever(embedder=FakeEmbedder(), vector_store=FakeSearcher([]))

    with pytest.raises(ValueError, match="query must not be empty"):
        retriever.retrieve(blank_query)


def test_retrieve_does_not_call_embedder_or_searcher_on_blank_query() -> None:
    embedder = FakeEmbedder()
    searcher = FakeSearcher([])
    retriever = Retriever(embedder=embedder, vector_store=searcher)

    with pytest.raises(ValueError):
        retriever.retrieve("")

    assert embedder.calls == []
    assert searcher.last_query_vector is None
