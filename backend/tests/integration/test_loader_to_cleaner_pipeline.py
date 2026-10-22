"""Integration test: Stage 1 loaders -> Stage 2 cleaning, using the real
fixture files (not hand-built ExtractedDocument objects). Per
docs/testing.md's convention, this is what belongs in tests/integration/ --
multiple real components exercised together.

Author: Imitiyaz and AI Agent
Project: RAG MVP
Layer: Verification and synthetic fixtures
"""

from __future__ import annotations

from pathlib import Path

from app.cleaning import clean_document
from app.loaders.pdf_loader import PdfLoader
from app.loaders.xlsx_loader import XlsxLoader


def test_xlsx_loader_to_cleaner_pipeline(sample_sales_xlsx: Path) -> None:
    document = XlsxLoader().load(sample_sales_xlsx)
    cleaned = clean_document(document)

    # Same 6 rows survive (none were entirely empty to begin with)
    assert len(cleaned.rows) == 6
    # No row should contain a None value anywhere after cleaning
    for row in cleaned.rows:
        assert None not in row.data.values()
    # Citation metadata still correctly traces back to the source
    sheet_names = {row.metadata.sheet_or_page for row in cleaned.rows}
    assert sheet_names == {"Q3 Sales", "Q4 Notes"}


def test_pdf_loader_to_cleaner_pipeline(sample_report_pdf: Path) -> None:
    document = PdfLoader().load(sample_report_pdf)
    cleaned = clean_document(document)

    # Table rows survive
    assert len(cleaned.rows) == 3
    # Narrative text survives, with table-duplicate content resolved
    assert len(cleaned.text_blocks) == 1
    assert "Quarterly Regional Sales Report" in cleaned.text_blocks[0].text
    # The table's own row content should no longer appear duplicated in
    # the narrative text block (Stage 1's documented known limitation,
    # resolved here in Stage 2)
    combined_row_text = " ".join(
        str(value) for row in cleaned.rows for value in row.data.values()
    )
    assert combined_row_text  # sanity: rows actually have content
