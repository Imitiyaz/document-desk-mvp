# SPDX-License-Identifier: AGPL-3.0-only
"""Persist and search citation-bearing fragments through an injectable collection.

Chroma is loaded only when a real collection is needed. Deterministic chunk IDs
support repeatable low-level upserts; the service separately rejects duplicate
filename uploads. The vector store ranks fragments and does not establish table
population completeness. See docs/decisions/vector-database-selection.md.

Author: Imitiyaz and AI Agent
Project: RAG MVP
Layer: Vectorstore
"""

from __future__ import annotations

from typing import Any, Protocol

from loguru import logger

from app.core.config import settings
from app.core.exceptions import VectorStoreConnectionError, VectorStoreOperationError
from app.embedding.models import EmbeddedChunk
from app.models.extracted import SourceMetadata
from app.vectorstore.models import RetrievedMatch


class VectorCollection(Protocol):
    """The minimal interface VectorStore needs from a collection.

    Implemented by a real ChromaDB `Collection` object (used by default)
    and by any lightweight test double. A real Chroma collection already
    has exactly these four methods with this shape -- no adapter layer
    needed, just a narrower declared interface.
    """

    def upsert(
        self,
        ids: list[str],
        embeddings: list[list[float]],
        documents: list[str],
        metadatas: list[dict[str, Any]],
    ) -> None:
        """Persist vectors together with deterministic IDs, text and citation metadata."""
        ...  # noqa: E704

    def query(
        self,
        query_embeddings: list[list[float]],
        n_results: int,
        where: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Return the backend result contract for the requested embedding and scope."""
        ...  # noqa: E704

    def count(self) -> int:
        """Return the collection size used to bound backend search requests."""
        ...  # noqa: E704

    def get(
        self,
        where: dict[str, Any] | None = None,
        limit: int | None = None,
        include: list[str] | None = None,
    ) -> dict[str, Any]:
        """Read metadata for matching records independently of similarity ranking."""
        ...  # noqa: E704

    def delete(self, where: dict[str, Any]) -> None:
        """Delete only records matching the explicit backend filter."""
        ...  # noqa: E704


def build_chunk_id(metadata: SourceMetadata) -> str:
    """Builds a deterministic, unique ID from citation metadata, so
    re-ingesting the same document updates its existing records (upsert)
    rather than accumulating duplicates.
    """
    return (
        f"{metadata.source_file}::{metadata.sheet_or_page}::{metadata.row_or_location}"
    )


def _load_default_collection(
    persist_dir: str, collection_name: str
) -> VectorCollection:
    """Lazily imports and connects to ChromaDB. Imported here, not at
    module top-level -- see module docstring for why that matters.
    """
    try:
        import chromadb

        client = chromadb.PersistentClient(path=persist_dir)
        # chromadb's real Collection class has a richer method signature
        # than our minimal VectorCollection Protocol declares (more
        # optional parameters, TypedDict return types like QueryResult/
        # DeleteResult instead of dict[str, Any]) -- mypy's structural
        # Protocol check is stricter here than the real runtime behavior
        # warrants. The real object satisfies everything VectorStore
        # actually calls; verified at runtime by
        # tests/integration/test_real_vectorstore.py.
        return client.get_or_create_collection(  # type: ignore[return-value]
            name=collection_name,
            metadata={
                "hnsw:space": "cosine"
            },  # matches Stage 4's normalized embeddings
        )
    except Exception as exc:
        raise VectorStoreConnectionError(
            f"Failed to connect to the vector store at '{persist_dir}' "
            f"(collection '{collection_name}'). Check that chromadb is "
            f"installed and the persist directory is writable. "
            f"Underlying error: {exc}"
        ) from exc


class VectorStore:
    """Stores and queries embedded chunks via a VectorCollection."""

    def __init__(
        self,
        persist_dir: str | None = None,
        collection_name: str | None = None,
        collection: VectorCollection | None = None,
    ) -> None:
        self.persist_dir = persist_dir or settings.chroma_persist_dir
        self.collection_name = collection_name or settings.chroma_collection_name
        if collection is not None:
            self._collection = collection
        else:
            logger.info(
                "Connecting to vector store: {} (collection: {})",
                self.persist_dir,
                self.collection_name,
            )
            self._collection = _load_default_collection(
                self.persist_dir, self.collection_name
            )

    def upsert_chunks(self, chunks: list[EmbeddedChunk]) -> int:
        """Stores a batch of embedded chunks. Returns the count stored.
        Re-upserting a chunk with the same citation metadata (same
        source_file/sheet_or_page/row_or_location) updates it in place.
        """
        if not chunks:
            return 0

        # Keep IDs, vectors, text and provenance in the same input order for a single backend batch.
        ids = [build_chunk_id(chunk.metadata) for chunk in chunks]
        embeddings = [chunk.vector for chunk in chunks]
        documents = [chunk.text for chunk in chunks]
        metadatas: list[dict[str, Any]] = [
            {
                "source_file": chunk.metadata.source_file,
                "sheet_or_page": chunk.metadata.sheet_or_page,
                "row_or_location": chunk.metadata.row_or_location,
            }
            for chunk in chunks
        ]

        self._collection.upsert(
            ids=ids, embeddings=embeddings, documents=documents, metadatas=metadatas
        )
        logger.info("Upserted {} chunk(s) into '{}'", len(chunks), self.collection_name)
        return len(chunks)

    def query(
        self,
        query_vector: list[float],
        top_k: int = 5,
        where: dict[str, Any] | None = None,
    ) -> list[RetrievedMatch]:
        """Returns the top_k most similar chunks to query_vector,
        optionally restricted by a metadata filter (e.g.
        `{"source_file": "sample_sales.xlsx"}`).
        """
        try:
            results = self._collection.query(
                query_embeddings=[query_vector], n_results=top_k, where=where
            )
        except Exception as exc:
            logger.exception("Vector-store query failed")
            raise VectorStoreOperationError(
                "Unable to query the document index."
            ) from exc

        ids = results["ids"][0] if results["ids"] else []
        distances = results["distances"][0] if results.get("distances") else []
        documents = results["documents"][0] if results.get("documents") else []
        metadatas = results["metadatas"][0] if results.get("metadatas") else []

        matches = []
        for i in range(len(ids)):
            metadata = SourceMetadata(
                source_file=metadatas[i]["source_file"],
                sheet_or_page=metadatas[i]["sheet_or_page"],
                row_or_location=metadatas[i]["row_or_location"],
            )
            matches.append(
                RetrievedMatch(
                    text=documents[i], metadata=metadata, distance=distances[i]
                )
            )
        return matches

    def count(self) -> int:
        """Total number of records currently stored."""
        return self._collection.count()

    def has_source_file(self, source_file: str) -> bool:
        """Checks indexed metadata without loading vectors or embedding a query."""
        result = self._collection.get(
            where={"source_file": source_file}, limit=1, include=[]
        )
        return bool(result["ids"])

    def delete_by_source_file(self, source_file: str) -> None:
        """Removes every record belonging to a given source file --
        useful for re-ingestion without accumulating stale records under
        a changed chunking strategy.
        """
        self._collection.delete(where={"source_file": source_file})
        logger.info("Deleted all records for source file: {}", source_file)

    def list_source_files(self) -> list[str]:
        """Enumerate indexed source metadata without similarity retrieval."""
        try:
            result = self._collection.get(include=["metadatas"])
            return sorted(
                {
                    str(item["source_file"])
                    for item in result.get("metadatas", [])
                    if item
                }
            )
        except Exception as exc:
            raise VectorStoreOperationError(
                "Unable to enumerate indexed sources."
            ) from exc
