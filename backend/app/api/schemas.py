# SPDX-License-Identifier: AGPL-3.0-only
"""Pydantic HTTP schemas, separate from the pipeline's dataclass contracts.

Author: Imitiyaz and AI Agent
Project: RAG MVP
Layer: Api
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.api.uploads import validate_filename


class QueryRequest(BaseModel):
    """One question, optionally scoped to an exact indexed source filename."""

    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    conversation_id: str | None = Field(default=None, max_length=80)
    context_token: str | None = Field(default=None, max_length=80)
    document_id: str | None = Field(default=None, max_length=80)
    workspace_revision: int | None = Field(default=None, ge=0, strict=True)
    source_scopes: list[str] = Field(default_factory=list, max_length=200)
    record_scope: Literal["auto", "detail", "summary"] = "auto"
    aggregation_basis: Literal["auto", "all_selected_records"] = "auto"
    group_field: str | None = Field(default=None, max_length=255)
    entity_groups: list[list[str]] = Field(default_factory=list, max_length=8)
    breakdown: Literal["none", "source", "file_and_source"] = "none"
    page: int = Field(default=1, ge=1, strict=True)
    page_size: int = Field(default=50, ge=1, le=200, strict=True)
    answer_mode: Literal["prose", "records"] = Field(
        default="prose",
        description="Records mode copies selected source records in source-location order; prose generates a narrative answer.",
    )
    sheet_or_page: str | None = Field(default=None, min_length=1, max_length=255)
    fields: list[str] = Field(default_factory=list, max_length=20)
    filters: dict[str, str] = Field(default_factory=dict, max_length=20)
    operation: Literal[
        "auto", "lookup", "sum", "minimum", "maximum", "increase", "growth_percent"
    ] = "auto"
    question: str = Field(min_length=1, max_length=4000)
    source_file: str | None = Field(default=None, min_length=1, max_length=255)
    top_k: int | None = Field(default=None, ge=1, le=100, strict=True)
    min_score: float | None = Field(default=None, ge=-1, le=1, strict=True)

    @field_validator("question")
    @classmethod
    def require_nonblank_question(cls, value: str) -> str:
        """Check whitespace without changing the original question."""
        if not value.strip():
            raise ValueError("question must contain non-whitespace text")
        return value

    @field_validator("entity_groups")
    @classmethod
    def bound_groups(cls, groups: list[list[str]]) -> list[list[str]]:
        """Keep explicit group requests bounded and preserve requested group order."""
        if any(
            not g or len(g) > 20 or any(not v.strip() or len(v) > 255 for v in g)
            for g in groups
        ):
            raise ValueError(
                "Each group needs 1–20 nonblank labels of at most 255 characters"
            )
        return [list(dict.fromkeys(v.strip() for v in g)) for g in groups]

    @field_validator("source_file")
    @classmethod
    def require_portable_source(cls, value: str | None) -> str | None:
        """Use the same source identity convention as upload and citations."""
        return validate_filename(value) if value is not None else None


class CitationResponse(BaseModel):
    """A resolved context marker and its original location."""

    number: int
    source_file: str
    sheet_or_page: str
    row_or_location: str | int
    citation_text: str


class EvidenceRecord(BaseModel):
    """One original source row; identical values retain separate identities."""

    number: int
    source_file: str
    sheet_or_page: str
    row_or_location: str | int
    values: dict[str, str | None]
    cell_references: dict[str, str] = Field(default_factory=dict)
    merged_fields: list[str] = Field(default_factory=list)
    cell_formats: dict[str, str] = Field(default_factory=dict)
    formula_fields: dict[str, str] = Field(default_factory=dict)
    continuation_fields: dict[str, dict[str, str | int | None]] = Field(
        default_factory=dict
    )


class AnswerItem(BaseModel):
    """A readable statement with explicit source associations, never HTML."""

    kind: Literal["paragraph", "record", "calculation", "notice"]
    text: str
    citation_numbers: list[int] = Field(default_factory=list)
    record_number: int | None = None
    scope: str | None = None


class EntityContribution(BaseModel):
    """One requested identity, including missing amounts or absent source records."""

    entity: str | None
    status: Literal["answered", "incomplete", "no_evidence", "clarification_required"]
    record_numbers: list[int]
    calculation: dict[str, object] | None = None
    missing_cells: list[dict[str, str | int | None]] = Field(default_factory=list)


class GroupedResult(BaseModel):
    """One separately scoped result; its numbers refer to shared source evidence."""

    label: str
    scope: str
    entities: list[str]
    status: Literal["answered", "incomplete", "no_evidence", "clarification_required"]
    answer: str
    record_numbers: list[int]
    missing_entities: list[str] = Field(default_factory=list)
    calculation: dict[str, object] | None = None
    contributions: list[EntityContribution] = Field(default_factory=list)


class QueryResponse(BaseModel):
    """Answer plus traceability; resolved citations do not certify correctness."""

    conversation_id: str | None = None
    context_token: str | None = None
    document_id: str | None = None
    workspace_revision: int | None = None
    resolved_question: str | None = None
    clarification_options: list[dict[str, str]] = Field(default_factory=list)
    status: Literal[
        "answered",
        "clarification_required",
        "incomplete",
        "evidence_only",
        "no_evidence",
    ] = "answered"
    execution_path: str = "legacy_generation"
    records: list[EvidenceRecord] = Field(default_factory=list)
    coverage: dict[str, object] = Field(default_factory=dict)
    calculation: dict[str, object] | None = None
    grouped_results: list[GroupedResult] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    timings_seconds: dict[str, float] = Field(default_factory=dict)
    answer: str
    answer_items: list[AnswerItem] = Field(default_factory=list)
    evidence_text: str | None = None
    citations: list[CitationResponse]
    unresolved_citation_numbers: list[int]
    context_count: int
    model: str | None
    generation_latency_seconds: float


class IngestionResponse(BaseModel):
    """Returned only after all chunks have been written successfully."""

    source_file: str
    size_bytes: int
    extracted_rows: int
    extracted_text_blocks: int
    chunks_stored: int
    document_id: str | None = None
    workspace_revision: int = 0
    warnings: list[str] = Field(default_factory=list)


class HealthResponse(BaseModel):
    """Process liveness or pipeline initialization, not model-answer quality."""

    status: Literal["ok", "ready"]


class ValidationIssue(BaseModel):
    """A safe validation detail without echoing uploaded/request content."""

    location: list[str | int]
    message: str
    kind: str


class ErrorResponse(BaseModel):
    """Stable error shape for clients; internal tracebacks stay in server logs."""

    status_code: int = Field(ge=400, le=599)
    code: str
    message: str
    details: list[ValidationIssue] = Field(default_factory=list)


class ConversationRequest(BaseModel):
    """Open one session on an immutable document identity."""

    model_config = ConfigDict(extra="forbid")
    source_file: str = Field(min_length=1, max_length=255)
    document_id: str = Field(min_length=1, max_length=80)
    workspace_revision: int = Field(ge=0, strict=True)
