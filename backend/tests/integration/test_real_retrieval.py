"""Tests that exercise the REAL embedding model AND the REAL ChromaDB
backend together, through Retriever -- the actual end-to-end path a
real question will take once Stage 10's API calls this class. Excluded
from the default `pytest` run (both `embedding_model` and `vectorstore`
are in pytest.ini's default-exclusion `addopts`). Run explicitly with:

    pytest -m "embedding_model and vectorstore" -v

This downloads the real BAAI/bge-base-en-v1.5 model on first run (~440MB,
same as Stage 4's marked test) and requires the real `chromadb` package
installed (same as Stage 5's marked test). No new dependency-weight is
introduced by this stage -- this test only combines two already-real
dependencies through the new Retriever class.

Author: Imitiyaz and AI Agent
Project: RAG MVP
Layer: Verification and synthetic fixtures
"""

from __future__ import annotations

import shutil
import tempfile

import pytest

from app.chunking import chunk_document
from app.cleaning import clean_document
from app.embedding import Embedder
from app.loaders import get_loader_for_file
from app.retrieval import Retriever
from app.vectorstore import VectorStore

pytestmark = [pytest.mark.embedding_model, pytest.mark.vectorstore]


@pytest.fixture
def temp_persist_dir():
    path = tempfile.mkdtemp(prefix="chroma_retrieval_test_")
    yield path
    shutil.rmtree(path, ignore_errors=True)


def test_real_retrieval_ranks_the_relevant_row_first(
    sample_sales_xlsx, temp_persist_dir
) -> None:
    # Full real pipeline: real loader -> real cleaning -> real chunking
    # -> real embedding model -> real ChromaDB.
    document = get_loader_for_file(sample_sales_xlsx).load(sample_sales_xlsx)
    cleaned = clean_document(document)
    chunks = chunk_document(cleaned)

    embedder = Embedder()  # real model, downloads on first run if not cached
    embedded_chunks = embedder.embed_chunks(chunks)

    store = VectorStore(persist_dir=temp_persist_dir, collection_name="retrieval_test")
    store.upsert_chunks(embedded_chunks)

    retriever = Retriever(embedder=embedder, vector_store=store)

    results = retriever.retrieve(
        "What was the Q3 revenue for the North region?", top_k=3
    )

    assert len(results) > 0
    assert results[0].rank == 1
    # The real ranking guarantee this stage exists to provide: the most
    # semantically relevant row is ranked first, not just "a" row.
    assert "North" in results[0].text
    assert results[0].metadata.source_file == "sample_sales.xlsx"
    # Ranks strictly increase and scores are non-increasing down the list.
    assert [r.rank for r in results] == list(range(1, len(results) + 1))
    # strict=False deliberately: this is the standard pairwise-iteration
    # pattern (results vs. results[1:]) -- the two sequences always
    # differ in length by exactly one, by design, not by mistake.
    for earlier, later in zip(results, results[1:], strict=False):
        assert earlier.score >= later.score


def test_real_retrieval_source_file_filter(sample_sales_xlsx, temp_persist_dir) -> None:
    document = get_loader_for_file(sample_sales_xlsx).load(sample_sales_xlsx)
    cleaned = clean_document(document)
    chunks = chunk_document(cleaned)

    embedder = Embedder()
    embedded_chunks = embedder.embed_chunks(chunks)

    store = VectorStore(
        persist_dir=temp_persist_dir, collection_name="retrieval_filter_test"
    )
    store.upsert_chunks(embedded_chunks)

    retriever = Retriever(embedder=embedder, vector_store=store)

    results = retriever.retrieve(
        "What was the revenue?", source_file="a_file_that_was_never_ingested.pdf"
    )

    assert results == []
