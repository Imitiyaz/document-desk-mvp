"""Unit tests for app.cleaning.cleaner.clean_document -- the Stage 2
orchestrator. Uses hand-built ExtractedDocument fixtures to test
orchestration logic in isolation from the real loaders (that's what the
integration test in tests/integration/test_loader_to_cleaner_pipeline.py
covers).

Author: Imitiyaz and AI Agent
Project: RAG MVP
Layer: Verification and synthetic fixtures
"""

from __future__ import annotations

from app.cleaning.cleaner import clean_document
from app.models.extracted import (
    ExtractedDocument,
    ExtractedRow,
    ExtractedText,
    SourceMetadata,
)


def _row(data: dict, sheet: str, row_num) -> ExtractedRow:
    return ExtractedRow(
        data=data,
        metadata=SourceMetadata(
            source_file="test.xlsx", sheet_or_page=sheet, row_or_location=row_num
        ),
    )


def _text(text: str, page: str) -> ExtractedText:
    return ExtractedText(
        text=text,
        metadata=SourceMetadata(
            source_file="test.pdf", sheet_or_page=page, row_or_location="full_page_text"
        ),
    )


def test_clean_document_preserves_unmerged_blank_and_cleans_rows() -> None:
    document = ExtractedDocument(
        source_file="test.xlsx",
        rows=[
            _row({"Region": "North", "Revenue": 45000}, "Sheet1", 2),
            _row({"Region": None, "Revenue": 52000}, "Sheet1", 3),
        ],
    )
    result = clean_document(document)
    assert len(result.rows) == 2
    assert "Region" not in result.rows[1].data  # ordinary blank, not a merged cell
    assert result.rows[1].data["Revenue"] == 52000


def test_clean_document_drops_rows_that_become_entirely_empty() -> None:
    document = ExtractedDocument(
        source_file="test.xlsx",
        rows=[
            # First row in the group: nothing above it to forward-fill from,
            # so it genuinely stays empty and gets dropped.
            _row({"Region": None, "Notes": "   "}, "Sheet1", 2),
            _row({"Region": "North"}, "Sheet1", 3),
        ],
    )
    result = clean_document(document)
    assert len(result.rows) == 1
    assert result.rows[0].data["Region"] == "North"


def test_clean_document_preserves_row_citation_metadata() -> None:
    document = ExtractedDocument(
        source_file="test.xlsx",
        rows=[_row({"Region": "North"}, "Sheet1", 2)],
    )
    result = clean_document(document)
    assert result.rows[0].metadata.source_file == "test.xlsx"
    assert result.rows[0].metadata.sheet_or_page == "Sheet1"
    assert result.rows[0].metadata.row_or_location == 2


def test_clean_document_strips_repeated_headers_from_text_blocks() -> None:
    document = ExtractedDocument(
        source_file="test.pdf",
        text_blocks=[
            _text("Confidential Report\nPage one real content here.", "page_1"),
            _text("Confidential Report\nPage two real content here.", "page_2"),
            _text("Confidential Report\nPage three real content here.", "page_3"),
        ],
    )
    result = clean_document(document)
    for block in result.text_blocks:
        assert "Confidential Report" not in block.text
    assert "Page one real content here" in result.text_blocks[0].text


def test_clean_document_removes_table_duplicate_lines_from_text_blocks() -> None:
    document = ExtractedDocument(
        source_file="test.pdf",
        rows=[_row({"Region": "North", "Revenue": "45000"}, "page_1", "table_1_row_1")],
        text_blocks=[
            _text(
                "North 45000\nThis is genuine narrative commentary about performance.",
                "page_1",
            )
        ],
    )
    result = clean_document(document)
    assert len(result.text_blocks) == 1
    assert "North 45000" not in result.text_blocks[0].text
    assert "genuine narrative commentary" in result.text_blocks[0].text


def test_clean_document_drops_text_blocks_that_become_entirely_empty() -> None:
    document = ExtractedDocument(
        source_file="test.pdf",
        text_blocks=[_text("   \n\n   ", "page_1")],
    )
    result = clean_document(document)
    assert result.text_blocks == []


def test_clean_document_handles_empty_input_document() -> None:
    document = ExtractedDocument(source_file="empty.xlsx")
    result = clean_document(document)
    assert result.is_empty() is True
    assert result.source_file == "empty.xlsx"


def test_clean_document_preserves_source_file_name() -> None:
    document = ExtractedDocument(source_file="my_report.xlsx")
    result = clean_document(document)
    assert result.source_file == "my_report.xlsx"
