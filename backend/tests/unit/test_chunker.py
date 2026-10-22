"""Unit tests for app.chunking.chunker.chunk_document -- the Stage 3
orchestrator.

Author: Imitiyaz and AI Agent
Project: RAG MVP
Layer: Verification and synthetic fixtures
"""

from __future__ import annotations

from app.chunking.chunker import chunk_document
from app.models.cleaned import CleanedDocument, CleanedRow, CleanedText
from app.models.extracted import SourceMetadata


def _row(data: dict) -> CleanedRow:
    return CleanedRow(
        data=data,
        metadata=SourceMetadata(
            source_file="test.xlsx", sheet_or_page="Sheet1", row_or_location=2
        ),
    )


def _text(text: str) -> CleanedText:
    return CleanedText(
        text=text,
        metadata=SourceMetadata(
            source_file="test.pdf",
            sheet_or_page="page_1",
            row_or_location="full_page_text",
        ),
    )


def test_chunk_document_combines_row_and_text_chunks() -> None:
    document = CleanedDocument(
        source_file="test.xlsx",
        rows=[_row({"Region": "North"})],
        text_blocks=[_text("Some narrative content here.")],
    )
    chunks = chunk_document(document)
    assert len(chunks) == 2


def test_chunk_document_handles_empty_document() -> None:
    document = CleanedDocument(source_file="empty.xlsx")
    chunks = chunk_document(document)
    assert chunks == []


def test_chunk_document_rows_only() -> None:
    document = CleanedDocument(
        source_file="test.xlsx",
        rows=[_row({"Region": "North"}), _row({"Region": "South"})],
    )
    chunks = chunk_document(document)
    assert len(chunks) == 2


def test_chunk_document_text_only() -> None:
    document = CleanedDocument(
        source_file="test.pdf",
        text_blocks=[_text("Narrative content.")],
    )
    chunks = chunk_document(document)
    assert len(chunks) == 1
