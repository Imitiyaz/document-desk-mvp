# SPDX-License-Identifier: AGPL-3.0-only
"""Compose ingestion and answering behind injectable, application-scoped ports.

The source ledger supplies complete table populations; retrieval supplies ranked
narrative evidence. These paths are deliberately distinct because top-k matches
cannot prove that every operand of a total was found. Service operations share
one process-local lock so queries cannot observe a partially indexed document.

Author: Imitiyaz and AI Agent
Project: RAG MVP
Layer: Api
"""

from __future__ import annotations

import time
from pathlib import Path
from threading import RLock
from typing import Protocol

from loguru import logger

from app.api.schemas import (
    CitationResponse,
    IngestionResponse,
    QueryRequest,
    QueryResponse,
)
from app.api.workspace import WorkspaceOperations
from app.chunking import Chunk, chunk_document
from app.cleaning import clean_document
from app.core.config import settings
from app.core.exceptions import (
    DocumentAlreadyExistsError,
    DocumentNotFoundError,
    EmptyDocumentError,
    ReindexRequiredError,
    VectorStoreOperationError,
)
from app.embedding import EmbeddedChunk, Embedder
from app.generation import LLMClient, build_prompt, resolve_citations
from app.generation.models import AssembledPrompt, GeneratedAnswer
from app.loaders import get_loader_for_file
from app.retrieval import RetrievalResult, Retriever
from app.structured.engine import clarify, table_answer
from app.structured.store import RecordStore
from app.vectorstore import VectorStore

REFUSAL_RESPONSE = (
    "I don't have enough information in the provided documents to answer that."
)


class ChunkEmbedder(Protocol):
    """Only the ingestion embedding capability required by this service."""

    def embed_chunks(self, chunks: list[Chunk]) -> list[EmbeddedChunk]:
        """Return one embedding per citation-bearing chunk in the supplied order."""
        ...


class DocumentStore(Protocol):
    """Minimal document persistence operations; no Chroma-specific types."""

    def has_source_file(self, source_file: str) -> bool:
        """Check filename existence without relying on relevance-ranked search."""
        ...

    def upsert_chunks(self, chunks: list[EmbeddedChunk]) -> int:
        """Persist the supplied chunk batch and report the number stored."""
        ...

    def delete_by_source_file(self, source_file: str) -> None:
        """Delete only fragments belonging to the selected source filename."""
        ...


class QueryRetriever(Protocol):
    """The existing retriever API; future formats use exactly the same flow."""

    def retrieve(
        self,
        query: str,
        top_k: int | None = None,
        source_file: str | None = None,
        min_score: float | None = None,
    ) -> list[RetrievalResult]:
        """Return ranked, citation-bearing fragments under the selected source/score limits."""
        ...


class AnswerGenerator(Protocol):
    """LLM generation and the lifecycle of its client."""

    def generate(self, prompt: AssembledPrompt) -> GeneratedAnswer:
        """Generate using the injected transport; callers validate answer grounding separately."""
        ...

    def close(self) -> None:
        """Release the owned client resources at application shutdown."""
        ...


class PipelineService(WorkspaceOperations):
    """Serialize pipeline operations for the CPU-only, single-process MVP.

    This prevents a query observing a partially indexed upload and two
    same-name uploads racing between the existence check and write. It is a
    process-local guarantee: run one Uvicorn worker. No background jobs or
    cross-process transactions are claimed.
    """

    def __init__(
        self,
        embedder: ChunkEmbedder,
        vector_store: DocumentStore,
        retriever: QueryRetriever,
        llm_client: AnswerGenerator,
        record_store: RecordStore | None = None,
        *,
        structured_answers: bool = True,
    ) -> None:
        self._records = record_store if record_store is not None else RecordStore()
        self._structured_answers = structured_answers
        self._embedder = embedder
        self._store = vector_store
        self._retriever = retriever
        self._llm = llm_client
        # Workspace methods re-enter the same service lock; a non-reentrant lock would deadlock.
        self._lock = RLock()
        self._initialize_workspace()

    def _has_source(self, source_file: str) -> bool:
        try:
            return self._store.has_source_file(source_file)
        except Exception as exc:
            logger.exception("Could not inspect indexed source {}", source_file)
            raise VectorStoreOperationError(
                "Unable to inspect the document index."
            ) from exc

    def ingest(
        self, file_path: Path, size_bytes: int, expected_revision: int | None = None
    ) -> IngestionResponse:
        """Index one new document without exposing a partial write to queries.


        Args:
            file_path: Temporary, validated upload; its basename is the source identity.
            size_bytes: Accepted file size returned to the client.
            expected_revision: Optional generation captured before upload streaming.

        Returns:
            Extracted/stored counts, document identity, revision and loader warnings.

        Raises:
            DocumentAlreadyExistsError: The filename already has ledger or vector data.
            EmptyDocumentError: Parsing produced no usable chunks.
            VectorStoreOperationError: Indexing or compensating cleanup failed.

        The lock serializes this process only. Persistent states make failed cleanup
        recoverable; they do not turn two storage systems into one atomic transaction.
        """
        with self._lock:
            self._check_revision(expected_revision)
            loader = get_loader_for_file(file_path)
            if self._records.identity(file_path.name) or self._has_source(
                file_path.name
            ):
                raise DocumentAlreadyExistsError(
                    "This filename is already indexed. Use a distinct filename; existing data was not changed."
                )
            document = loader.load(file_path)
            chunks = chunk_document(clean_document(document))
            if not chunks:
                raise EmptyDocumentError(
                    "No usable content was extracted. Image-only PDFs require OCR, which is not supported yet."
                )
            embedded = self._embedder.embed_chunks(chunks)
            if len(embedded) != len(chunks):
                raise ValueError(
                    "Embedding output count does not match the chunk count."
                )
            try:
                # Ready is published only after the complete ledger and vector batch both exist.
                self._records.add(document, file_path.read_bytes(), state="indexing")
                stored = self._store.upsert_chunks(embedded)
                if stored != len(chunks):
                    raise ValueError(
                        "Stored chunk count does not match the ingestion batch."
                    )
                self._records.set_state(file_path.name, "ready")
            except Exception as exc:
                # This filename had no prior records. Remove only this new
                # upload's potentially partial write; never delete old sources.
                logger.exception(
                    "Could not index {}; attempting cleanup", file_path.name
                )
                self._records.set_state(file_path.name, "deleting")
                try:
                    self._store.delete_by_source_file(file_path.name)
                    self._records.delete(file_path.name)
                except Exception as cleanup_exc:
                    logger.exception("Index cleanup failed for {}", file_path.name)
                    raise VectorStoreOperationError(
                        "Indexing failed and partial records may remain. The document index needs repair."
                    ) from cleanup_exc
                raise VectorStoreOperationError(
                    "Indexing failed; partial records were removed."
                ) from exc
            return IngestionResponse(
                source_file=file_path.name,
                size_bytes=size_bytes,
                extracted_rows=len(document.rows),
                extracted_text_blocks=len(document.text_blocks),
                chunks_stored=stored,
                document_id=(self._records.identity(file_path.name) or {}).get(
                    "document_id"
                ),
                workspace_revision=self._records.revision(),
                warnings=document.warnings,
            )

    def _execute_query(self, request: QueryRequest) -> QueryResponse:
        """Answer recognized tables from complete source records; otherwise return cited excerpts.

        The legacy generation branch exists for raw-adapter diagnostics only.
        Production defaults never trust unconstrained model-written values.
        """
        started = time.perf_counter()
        with self._lock:
            if request.source_file is not None and not self._has_source(
                request.source_file
            ):
                raise DocumentNotFoundError(
                    "The selected source filename is not indexed."
                )
            search_source = request.source_file
            # Ranked fragments cannot prove a table total; use complete ledger rows for tables.
            if self._structured_answers:
                source = request.source_file
                if source is None:
                    sources = self._records.sources()
                    if not sources:
                        return QueryResponse(
                            status="no_evidence",
                            execution_path="structured",
                            answer=REFUSAL_RESPONSE,
                            citations=[],
                            unresolved_citation_numbers=[],
                            context_count=0,
                            model=None,
                            generation_latency_seconds=0,
                        )
                    if len(sources) != 1:
                        return clarify(
                            "Select one indexed document before asking a question."
                        )
                    source = sources[0]["source_file"]
                search_source = source
                document = self._records.get(source)
                if document is None:
                    raise ReindexRequiredError(
                        "This source uses an older extraction policy. Remove this selected document and re-upload the original; existing payloads and other documents were preserved."
                    )
                structured = table_answer(request, source, document)
                if structured is not None:
                    structured.warnings.extend(document.get("warnings", []))
                    structured.timings_seconds = {
                        "total": time.perf_counter() - started
                    }
                    return structured
            results = self._retriever.retrieve(
                request.question,
                top_k=request.top_k,
                source_file=search_source,
                min_score=request.min_score,
            )
            if self._structured_answers:
                from app.generation.grounded import narrative_answer

                response = narrative_answer(
                    request, search_source or "", document, results, self._llm
                )
                response.timings_seconds = {"total": time.perf_counter() - started}
                return response
            if not results:
                # Empty evidence can be handled deterministically, even if
                # Ollama is down. Nonempty but irrelevant evidence remains a
                # model/retrieval-quality concern for Stage 12.
                return QueryResponse(
                    status="no_evidence",
                    execution_path="source_excerpts",
                    answer=REFUSAL_RESPONSE,
                    citations=[],
                    unresolved_citation_numbers=[],
                    context_count=0,
                    model=None,
                    generation_latency_seconds=0,
                )
            answer = resolve_citations(
                self._llm.generate(
                    build_prompt(
                        request.question, results, answer_mode=request.answer_mode
                    )
                )
            )
            return QueryResponse(
                answer=answer.text,
                citations=[
                    CitationResponse(
                        number=c.number,
                        source_file=c.metadata.source_file,
                        sheet_or_page=c.metadata.sheet_or_page,
                        row_or_location=c.metadata.row_or_location,
                        citation_text=c.citation_text,
                    )
                    for c in answer.citations
                ],
                unresolved_citation_numbers=answer.unresolved_citation_numbers,
                context_count=len(results),
                model=answer.model,
                generation_latency_seconds=answer.latency_seconds,
            )

    def documents(self) -> list[dict]:
        """List ledger-backed documents and exact sheet/field choices."""
        with self._lock:
            return self.catalog()

    def close(self) -> None:
        """Release the LLM client's HTTP resources at application shutdown."""
        self._llm.close()
        self._records.close()


def create_pipeline_service() -> PipelineService:
    """Load real resources once per lifespan; construction never occurs on import."""
    embedder = Embedder()
    store = VectorStore()
    return PipelineService(
        embedder,
        store,
        Retriever(embedder, store),
        LLMClient(max_attempts=1),
        RecordStore(
            str(
                Path(settings.chroma_persist_dir)
                / (settings.chroma_collection_name + "-records.sqlite3")
            )
        ),
    )
