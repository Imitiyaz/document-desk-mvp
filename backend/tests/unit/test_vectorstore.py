"""Unit tests for the vector adapter using a functional in-memory collection.

The fake performs nearest-neighbor ranking over supplied normalized vectors.
Separate vectorstore-marked tests exercise real Chroma persistence.
Author: Imitiyaz and AI Agent
"""

from __future__ import annotations

from typing import Any

import pytest

from app.core.exceptions import VectorStoreConnectionError
from app.embedding.models import EmbeddedChunk
from app.models.extracted import SourceMetadata
from app.vectorstore.chroma_client import VectorStore, build_chunk_id


class FakeCollection:
    """A minimal but genuinely-functional VectorCollection test double."""

    def __init__(self) -> None:
        self._ids: list[str] = []
        self._embeddings: list[list[float]] = []
        self._documents: list[str] = []
        self._metadatas: list[dict[str, Any]] = []

    def upsert(self, ids, embeddings, documents, metadatas) -> None:  # noqa: ANN001
        for i, id_ in enumerate(ids):
            if id_ in self._ids:
                idx = self._ids.index(id_)
                self._embeddings[idx] = embeddings[i]
                self._documents[idx] = documents[i]
                self._metadatas[idx] = metadatas[i]
            else:
                self._ids.append(id_)
                self._embeddings.append(embeddings[i])
                self._documents.append(documents[i])
                self._metadatas.append(metadatas[i])

    def query(self, query_embeddings, n_results, where=None):  # noqa: ANN001
        query_vec = query_embeddings[0]
        candidates = list(range(len(self._ids)))
        if where:
            candidates = [
                i
                for i in candidates
                if all(self._metadatas[i].get(k) == v for k, v in where.items())
            ]
        scored = []
        for i in candidates:
            # strict=True deliberately: a dot product between
            # differently-sized vectors is meaningless, not just
            # inconvenient -- this should only ever match a dimension
            # mismatch bug, never a legitimate case to truncate through.
            dot = sum(
                a * b for a, b in zip(self._embeddings[i], query_vec, strict=True)
            )
            distance = 1 - dot  # cosine-style distance on normalized vectors
            scored.append((distance, i))
        scored.sort(key=lambda pair: pair[0])
        top = scored[:n_results]
        return {
            "ids": [[self._ids[i] for _, i in top]],
            "distances": [[d for d, _ in top]],
            "documents": [[self._documents[i] for _, i in top]],
            "metadatas": [[self._metadatas[i] for _, i in top]],
        }

    def count(self) -> int:
        return len(self._ids)

    def get(self, where=None, limit=None, include=None):
        indices = [
            i
            for i, m in enumerate(self._metadatas)
            if where is None or all(m.get(k) == v for k, v in where.items())
        ]
        indices = indices[:limit]
        return {
            "ids": [self._ids[i] for i in indices],
            "metadatas": (
                [self._metadatas[i] for i in indices]
                if include and "metadatas" in include
                else []
            ),
        }

    def delete(self, where) -> None:  # noqa: ANN001
        keep = [
            i
            for i in range(len(self._ids))
            if not all(self._metadatas[i].get(k) == v for k, v in where.items())
        ]
        self._ids = [self._ids[i] for i in keep]
        self._embeddings = [self._embeddings[i] for i in keep]
        self._documents = [self._documents[i] for i in keep]
        self._metadatas = [self._metadatas[i] for i in keep]


def _chunk(
    text: str, vector: list[float], source_file="test.xlsx", sheet="Sheet1", row=2
) -> EmbeddedChunk:
    return EmbeddedChunk(
        text=text,
        metadata=SourceMetadata(
            source_file=source_file, sheet_or_page=sheet, row_or_location=row
        ),
        vector=vector,
    )


def test_build_chunk_id_is_deterministic() -> None:
    metadata = SourceMetadata(
        source_file="a.xlsx", sheet_or_page="Sheet1", row_or_location=2
    )
    assert build_chunk_id(metadata) == build_chunk_id(metadata)


def test_build_chunk_id_differs_for_different_rows() -> None:
    m1 = SourceMetadata(source_file="a.xlsx", sheet_or_page="Sheet1", row_or_location=2)
    m2 = SourceMetadata(source_file="a.xlsx", sheet_or_page="Sheet1", row_or_location=3)
    assert build_chunk_id(m1) != build_chunk_id(m2)


def test_upsert_chunks_stores_and_counts() -> None:
    store = VectorStore(collection=FakeCollection())
    chunks = [
        _chunk("North region", [1.0, 0.0], row=2),
        _chunk("South region", [0.0, 1.0], row=3),
    ]
    stored = store.upsert_chunks(chunks)
    assert stored == 2
    assert store.count() == 2


def test_upsert_chunks_empty_list_is_no_op() -> None:
    store = VectorStore(collection=FakeCollection())
    assert store.upsert_chunks([]) == 0
    assert store.count() == 0


def test_upsert_chunks_is_idempotent_for_same_chunk() -> None:
    store = VectorStore(collection=FakeCollection())
    chunk = _chunk("North region", [1.0, 0.0], row=2)
    store.upsert_chunks([chunk])
    store.upsert_chunks([chunk])  # re-upsert same citation metadata
    assert store.count() == 1  # updated in place, not duplicated


def test_query_returns_closest_match_first() -> None:
    store = VectorStore(collection=FakeCollection())
    store.upsert_chunks(
        [
            _chunk("North region", [1.0, 0.0], row=2),
            _chunk("South region", [0.0, 1.0], row=3),
        ]
    )
    results = store.query(query_vector=[1.0, 0.0], top_k=2)
    assert results[0].text == "North region"
    assert results[0].distance < results[1].distance


def test_query_respects_top_k() -> None:
    store = VectorStore(collection=FakeCollection())
    store.upsert_chunks([_chunk(f"Row {i}", [float(i), 0.0], row=i) for i in range(5)])
    results = store.query(query_vector=[0.0, 0.0], top_k=2)
    assert len(results) == 2


def test_query_filters_by_metadata_where_clause() -> None:
    store = VectorStore(collection=FakeCollection())
    store.upsert_chunks(
        [
            _chunk("From A", [1.0, 0.0], source_file="a.xlsx", row=2),
            _chunk("From B", [1.0, 0.0], source_file="b.xlsx", row=2),
        ]
    )
    results = store.query(
        query_vector=[1.0, 0.0], top_k=5, where={"source_file": "a.xlsx"}
    )
    assert len(results) == 1
    assert results[0].text == "From A"


def test_query_preserves_citation_metadata() -> None:
    store = VectorStore(collection=FakeCollection())
    store.upsert_chunks(
        [
            _chunk(
                "North region", [1.0, 0.0], source_file="report.xlsx", sheet="Q3", row=7
            )
        ]
    )
    results = store.query(query_vector=[1.0, 0.0], top_k=1)
    assert results[0].metadata.source_file == "report.xlsx"
    assert results[0].metadata.sheet_or_page == "Q3"
    assert results[0].metadata.row_or_location == 7


def test_delete_by_source_file_removes_only_matching_records() -> None:
    store = VectorStore(collection=FakeCollection())
    store.upsert_chunks(
        [
            _chunk("From A", [1.0, 0.0], source_file="a.xlsx", row=2),
            _chunk("From B", [1.0, 0.0], source_file="b.xlsx", row=2),
        ]
    )
    store.delete_by_source_file("a.xlsx")
    assert store.count() == 1


def test_vectorstore_wraps_connection_failure_when_no_collection_injected(
    monkeypatch,
) -> None:
    import sys

    # Deterministic regardless of whether chromadb is actually installed --
    # same technique used in Stage 4's equivalent test.
    monkeypatch.setitem(sys.modules, "chromadb", None)
    with pytest.raises(
        VectorStoreConnectionError, match="Failed to connect to the vector store"
    ):
        VectorStore(persist_dir="/tmp/fake_chroma", collection_name="test")


def test_has_source_file_checks_only_matching_metadata() -> None:
    store = VectorStore(collection=FakeCollection())
    assert not store.has_source_file("a.xlsx")
    store.upsert_chunks([_chunk("From A", [1.0, 0.0], source_file="a.xlsx")])
    assert store.has_source_file("a.xlsx")
    assert not store.has_source_file("b.xlsx")
