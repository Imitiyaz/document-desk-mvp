"""Opt-in tests of real Chroma persistence using supplied test vectors.

These cases do not download an embedding model or establish BGE quality.
Run explicitly with pytest -m vectorstore.
Author: Imitiyaz and AI Agent
"""

from __future__ import annotations

import shutil
import tempfile

import pytest

from app.embedding.models import EmbeddedChunk
from app.models.extracted import SourceMetadata
from app.vectorstore import VectorStore

pytestmark = pytest.mark.vectorstore


@pytest.fixture
def temp_persist_dir():
    path = tempfile.mkdtemp(prefix="chroma_test_")
    yield path
    shutil.rmtree(path, ignore_errors=True)


def test_real_chromadb_stores_and_queries(temp_persist_dir: str) -> None:
    store = VectorStore(persist_dir=temp_persist_dir, collection_name="test_collection")

    chunks = [
        EmbeddedChunk(
            text="North region revenue grew.",
            metadata=SourceMetadata(
                source_file="sales.xlsx", sheet_or_page="Q3", row_or_location=2
            ),
            vector=[1.0, 0.0, 0.0],
        ),
        EmbeddedChunk(
            text="South region revenue declined.",
            metadata=SourceMetadata(
                source_file="sales.xlsx", sheet_or_page="Q3", row_or_location=3
            ),
            vector=[0.0, 1.0, 0.0],
        ),
    ]

    stored = store.upsert_chunks(chunks)
    assert stored == 2
    assert store.count() == 2

    results = store.query(query_vector=[1.0, 0.0, 0.0], top_k=1)
    assert len(results) == 1
    assert results[0].text == "North region revenue grew."
    assert results[0].metadata.source_file == "sales.xlsx"


def test_real_chromadb_persists_across_client_instances(temp_persist_dir: str) -> None:
    store1 = VectorStore(persist_dir=temp_persist_dir, collection_name="persist_test")
    store1.upsert_chunks(
        [
            EmbeddedChunk(
                text="Persisted chunk",
                metadata=SourceMetadata(
                    source_file="a.xlsx", sheet_or_page="S1", row_or_location=1
                ),
                vector=[0.5, 0.5, 0.0],
            )
        ]
    )

    # A fresh VectorStore instance pointed at the same directory should see the same data
    store2 = VectorStore(persist_dir=temp_persist_dir, collection_name="persist_test")
    assert store2.count() == 1


def test_real_chromadb_metadata_filter_works(temp_persist_dir: str) -> None:
    store = VectorStore(persist_dir=temp_persist_dir, collection_name="filter_test")
    store.upsert_chunks(
        [
            EmbeddedChunk(
                text="From file A",
                metadata=SourceMetadata(
                    source_file="a.xlsx", sheet_or_page="S1", row_or_location=1
                ),
                vector=[1.0, 0.0, 0.0],
            ),
            EmbeddedChunk(
                text="From file B",
                metadata=SourceMetadata(
                    source_file="b.xlsx", sheet_or_page="S1", row_or_location=1
                ),
                vector=[1.0, 0.0, 0.0],
            ),
        ]
    )

    results = store.query(
        query_vector=[1.0, 0.0, 0.0], top_k=5, where={"source_file": "a.xlsx"}
    )
    assert len(results) == 1
    assert results[0].text == "From file A"


def test_real_chromadb_source_existence_and_deletion(temp_persist_dir: str) -> None:
    store = VectorStore(persist_dir=temp_persist_dir, collection_name="existence_test")
    assert not store.has_source_file("a.xlsx")
    store.upsert_chunks(
        [
            EmbeddedChunk(
                text="Stored row",
                metadata=SourceMetadata("a.xlsx", "Sheet1", 2),
                vector=[1.0, 0.0],
            )
        ]
    )
    assert store.has_source_file("a.xlsx")
    assert not store.has_source_file("b.xlsx")
    store.delete_by_source_file("a.xlsx")
    assert not store.has_source_file("a.xlsx")
