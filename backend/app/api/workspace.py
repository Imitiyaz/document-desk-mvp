# SPDX-License-Identifier: AGPL-3.0-only
"""Coordinate document and chat lifecycle across the source ledger and vectors.

SQLite and Chroma do not share a transaction. Persistent indexing/deleting states
make interrupted operations unavailable and recoverable on startup. The owning
service's process-local lock requires one API worker; this is not a distributed
transaction or a multi-user authorization boundary.

Author: Imitiyaz and AI Agent
Project: RAG MVP
Layer: Api
"""

from __future__ import annotations

import re
from typing import Any, cast

from loguru import logger

from app.api.schemas import QueryRequest, QueryResponse
from app.conversation import ConversationBook
from app.core.config import settings
from app.core.exceptions import StaleWorkspaceError, VectorStoreOperationError
from app.generation.answer_presenter import present_answer
from app.structured.engine import clarify
from app.structured.grouped import grouped_answer, plan_groups
from app.structured.scopes import resolve_question_scope, scope_problem


class WorkspaceOperations:
    """Pipeline mixin; the service owns dependencies and the one operation lock."""

    _records: Any
    _store: Any
    _embedder: Any
    _llm: Any
    _lock: Any
    _execute_query: Any

    def _initialize_workspace(self) -> None:
        """Recover interrupted cleanup before exposing documents as ready."""
        self._conversations = ConversationBook()
        self._revision = self._records.revision()
        # A crash can leave one store ahead of the other; finish source-scoped cleanup first.
        for source in self._records.pending():
            try:
                self._store.delete_by_source_file(source)
                self._records.delete(source)
            except Exception:
                logger.exception("Cleanup remains pending for {}", source)
        dimension = getattr(self._embedder, "dimension", None)
        if isinstance(dimension, int):
            try:
                self._records.bind_embedding(
                    getattr(self._embedder, "model_name", settings.embedding_model),
                    dimension,
                    bool(self._all_sources()),
                )
            except Exception:
                self._records.close()
                self._llm.close()
                raise

    def _all_sources(self) -> list[str]:
        """Include vector-only legacy sources, independent of retrieval ranking."""
        method = getattr(self._store, "list_source_files", None)
        return (
            method() if method else [i["source_file"] for i in self._records.sources()]
        )

    @property
    def received_revision(self) -> int:
        """Nonblocking snapshot taken before a streamed upload body is read."""
        return self._revision

    def _check_revision(self, revision: int | None) -> None:
        """A stale request cannot mutate or display a newer workspace."""
        if revision is not None and revision != self._records.revision():
            raise StaleWorkspaceError(
                "Workspace changed. Refresh documents and start a new chat."
            )

    def workspace(self) -> dict[str, int]:
        """Return persistent generation, including an empty workspace."""
        with self._lock:
            return {"revision": self._records.revision()}

    def catalog(self) -> list[dict]:
        """Legacy/pending sources remain visible for selective cleanup."""
        with self._lock:
            items = self._records.sources()
            known = {s["source_file"] for s in items}
            for source in self._all_sources():
                if source not in known:
                    items.append(
                        {
                            "source_file": source,
                            "ready": False,
                            "state": "reindex_required",
                            "document_id": None,
                            "workspace_revision": self._records.revision(),
                            "sha256": "",
                            "sheets": [],
                            "warnings": [
                                "Legacy vectors require selective remove/re-upload."
                            ],
                        }
                    )
            return sorted(items, key=lambda item: item["source_file"])

    def remove_document(self, source: str, expected_id: str | None = None) -> dict:
        """Tombstone first; partial deletion is unavailable and recoverable."""
        with self._lock:
            identity = self._records.identity(source)
            existed = identity is not None or source in self._all_sources()
            if not existed:
                return {
                    "status": "removed",
                    "existed": False,
                    "workspace_revision": self._revision,
                }
            if (identity and expected_id != identity["document_id"]) or (
                identity is None and expected_id is not None
            ):
                raise StaleWorkspaceError(
                    "Document identity is missing or changed. Refresh before removal."
                )
            self._revision = self._records.bump_revision()
            # Tombstone before the external delete so failed cleanup cannot remain queryable.
            self._records.set_state(source, "deleting")
            self._conversations.remove_source(source)
            try:
                self._store.delete_by_source_file(source)
                self._records.delete(source)
            except Exception as exc:
                logger.exception("Removal pending for {}", source)
                raise VectorStoreOperationError(
                    "Removal is pending. Retry removal or restart to reconcile; this document is unavailable."
                ) from exc
            return {
                "status": "removed",
                "source_file": source,
                "existed": True,
                "workspace_revision": self._revision,
            }

    def reset_workspace(self, revision: int) -> dict:
        """Mark every source unavailable before the first external deletion."""
        with self._lock:
            self._check_revision(revision)
            self._revision = self._records.bump_revision()
            self._conversations.items.clear()
            sources = set(self._all_sources()) | {
                s["source_file"] for s in self._records.sources()
            }
            for source in sources:
                self._records.set_state(source, "deleting")
            failed = []
            for source in sorted(sources):
                try:
                    self._store.delete_by_source_file(source)
                    self._records.delete(source)
                except Exception:
                    logger.exception("Workspace cleanup remains pending for {}", source)
                    failed.append(source)
            if failed:
                raise VectorStoreOperationError(
                    "Workspace reset is incomplete; pending data is unavailable. Refresh and retry reset."
                )
            return {
                "status": "reset",
                "removed_documents": len(sources),
                "workspace_revision": self._revision,
            }

    def start_conversation(self, source: str, document_id: str, revision: int) -> dict:
        """Start a session for one ready document at its current revision."""
        with self._lock:
            self._check_revision(revision)
            identity = self._records.identity(source)
            if (
                not identity
                or identity["document_id"] != document_id
                or self._records.get(source) is None
            ):
                raise StaleWorkspaceError(
                    "Document is unavailable or changed. Refresh the list."
                )
            return {
                "conversation_id": self._conversations.start(source, document_id),
                "document_id": document_id,
            }

    def end_conversation(self, key: str) -> dict:
        """Clear only conversation state; idempotent even after deletion/expiry."""
        with self._lock:
            self._conversations.end(key)
            return {"status": "cleared"}

    def query(self, request: QueryRequest) -> QueryResponse:
        """Resolve an acknowledged request, then answer against current source data.


        Args:
            request: Validated question, optional refinements and acknowledged context.

        Returns:
            A source-backed answer, subtotal, clarification or explicit evidence gap.

        Raises:
            StaleWorkspaceError: Revision, document identity or chat context changed.

        Pending-clarification questions are handled before retrieval. Grouped calculations
        use the complete ledger; pagination affects display only. A previously confirmed
        counting choice can survive repair only for the identical acknowledged population.
        """
        with self._lock:
            self._check_revision(request.workspace_revision)
            identity = self._records.identity(request.source_file or "")
            if identity and identity["state"] != "ready":
                raise StaleWorkspaceError("Document cleanup is pending; retry removal.")
            if request.document_id and (
                not identity or identity["document_id"] != request.document_id
            ):
                raise StaleWorkspaceError(
                    "Document identity changed. Start a new chat."
                )
            document = self._records.get(request.source_file or "")
            resolved = (
                self._conversations.resolve(request, identity, document)
                if request.conversation_id
                else request
            )
            # Questions about our clarification are conversation control, not workbook content.
            pending_reply = (
                self._conversations.clarification_response(request)
                if document is not None
                else None
            )
            scope_notice = None
            if document is not None and pending_reply is None:
                resolved, scope_notice = resolve_question_scope(
                    resolved, document, question=request.question
                )
            scope_failure = (
                scope_problem(resolved, document)
                if document is not None and pending_reply is None
                else None
            )
            grouped = None
            # Resolve groups after explicit source wording, then test retained counting proof.
            if document is not None and pending_reply is None and scope_failure is None:
                resolved, grouped = plan_groups(resolved, document)
                if grouped is None:
                    resumed = self._conversations.resume_counting_choice(
                        resolved, request
                    )
                    if resumed is not None:
                        resolved = resumed
                    grouped = grouped_answer(
                        resolved, request.source_file or "", document
                    )
                    if resumed is not None and grouped is not None:
                        grouped.warnings.append(
                            "Retained your confirmed source-record counting choice for this corrected request."
                        )
            if pending_reply is not None:
                response = pending_reply
            elif scope_failure is not None:
                response = clarify(scope_failure)
            elif grouped is not None:
                response = grouped
            elif re.match(
                r"^(and\b|what about\b|how about\b|instead\b|same\b|now\b)",
                resolved.question,
                re.I,
            ):
                response = clarify(
                    "Please identify the field/entity or ask a complete question; this follow-up could not be resolved safely."
                )
            else:
                response = self._execute_query(resolved)
            if scope_notice:
                response.warnings.append(scope_notice)
            response.coverage["resolved_scopes"] = (
                [resolved.sheet_or_page]
                if resolved.sheet_or_page
                else resolved.source_scopes
            )
            response.conversation_id = request.conversation_id
            response.document_id = identity["document_id"] if identity else None
            response.workspace_revision = self._records.revision()
            response.resolved_question = resolved.question
            if request.conversation_id:
                self._conversations.remember(
                    request.conversation_id, resolved, response, request
                )
            full = {record.number: record for record in response.records}
            if response.calculation:
                for operand in cast(
                    list[dict[str, Any]], response.calculation.get("operands", [])
                ):
                    record = full.get(operand["number"])
                    if record:
                        operand["source"] = {
                            k: getattr(record, k)
                            for k in ["source_file", "sheet_or_page", "row_or_location"]
                        }
                        operand["cell_references"] = {
                            f: record.cell_references[f]
                            for f in operand["values"]
                            if f in record.cell_references
                        }
            if response.records:
                count = len(response.records)
                pages = (count + request.page_size - 1) // request.page_size
                if request.page > pages:
                    response.status = "clarification_required"
                    response.warnings.append("Requested evidence page is out of range.")
                    return response
                response.records = response.records[
                    (request.page - 1)
                    * request.page_size : request.page
                    * request.page_size
                ]
                visible = {record.number for record in response.records}
                visible_lines = []
                for line in response.answer.splitlines():
                    marker = re.search(r"\(Source: \[(\d+)\]\)", line)
                    if (
                        not line.startswith("- ")
                        or marker is None
                        or int(marker[1]) in visible
                    ):
                        visible_lines.append(line)
                response.answer = "\n".join(visible_lines)
                response.coverage.update(
                    page=request.page,
                    total_pages=pages,
                    page_size=request.page_size,
                    returned_records=len(response.records),
                    calculation_uses_all_matches=response.calculation is not None
                    and not response.calculation.get("partial", False),
                )
            present_answer(response, resolved, list(full.values()))
            return response
