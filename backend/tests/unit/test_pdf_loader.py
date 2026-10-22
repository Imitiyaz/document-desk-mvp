"""Unit tests for PdfLoader.

Author: Imitiyaz and AI Agent
Project: RAG MVP
Layer: Verification and synthetic fixtures
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.core.exceptions import CorruptFileError
from app.loaders.pdf_loader import PdfLoader


def test_pdf_loader_supports_pdf_extension() -> None:
    loader = PdfLoader()
    assert loader.supports(Path("anything.pdf")) is True
    assert loader.supports(Path("anything.xlsx")) is False


def test_pdf_loader_extracts_table_rows(sample_report_pdf: Path) -> None:
    loader = PdfLoader()
    document = loader.load(sample_report_pdf)

    # sample_report.pdf has one table with 3 data rows (North/South/East).
    assert len(document.rows) == 3
    regions = {row.data.get("Region") for row in document.rows}
    assert regions == {"North", "South", "East"}


def test_pdf_loader_table_row_citation_metadata(sample_report_pdf: Path) -> None:
    loader = PdfLoader()
    document = loader.load(sample_report_pdf)

    for row in document.rows:
        assert row.metadata.source_file == "sample_report.pdf"
        assert row.metadata.sheet_or_page == "page_1"
        assert row.metadata.row_or_location.startswith("table_1_row_")


def test_pdf_loader_extracts_narrative_text(sample_report_pdf: Path) -> None:
    loader = PdfLoader()
    document = loader.load(sample_report_pdf)

    assert len(document.text_blocks) >= 1
    combined_text = " ".join(block.text for block in document.text_blocks)
    assert "Quarterly Regional Sales Report" in combined_text
    assert "North region" in combined_text


def test_pdf_loader_narrative_text_citation_metadata(sample_report_pdf: Path) -> None:
    loader = PdfLoader()
    document = loader.load(sample_report_pdf)

    for block in document.text_blocks:
        assert block.metadata.source_file == "sample_report.pdf"
        assert block.metadata.sheet_or_page == "page_1"
        assert block.metadata.row_or_location == "full_page_text"


def test_pdf_loader_raises_corrupt_file_error_for_garbage_content(
    tmp_path: Path,
) -> None:
    fake_pdf = tmp_path / "corrupt.pdf"
    fake_pdf.write_bytes(b"this is not a real pdf file at all")

    loader = PdfLoader()
    with pytest.raises(CorruptFileError):
        loader.load(fake_pdf)


def test_pdf_loader_detects_borderless_table(sample_report_extended_pdf: Path) -> None:
    # Regression test for a real bug found via Stage 6's fixture-coverage
    # review: pdfplumber's default "lines" table-detection strategy
    # finds nothing at all on a table with no visible grid lines, so
    # that page's data was being lost entirely as structured rows. See
    # docs/pipeline.md's extraction and cleaning policy.
    loader = PdfLoader()
    document = loader.load(sample_report_extended_pdf)

    page_2_rows = [r for r in document.rows if r.metadata.sheet_or_page == "page_2"]
    assert len(page_2_rows) == 3
    regions = {row.data.get("Region") for row in page_2_rows}
    assert regions == {"North", "South", "East"}


def test_pdf_loader_borderless_fallback_does_not_hallucinate_table_from_prose(
    sample_report_extended_pdf: Path,
) -> None:
    # The borderless-table fallback (text-alignment based, more
    # permissive than the default line-based detection) is prone to
    # treating a wrapped paragraph of ordinary narrative text as a
    # spurious single-column "table" -- confirmed via direct testing
    # against pdfplumber before this fix was written. page_1 is
    # narrative-only, no table at all, and must produce zero rows.
    loader = PdfLoader()
    document = loader.load(sample_report_extended_pdf)

    page_1_rows = [r for r in document.rows if r.metadata.sheet_or_page == "page_1"]
    assert page_1_rows == []


def test_pdf_loader_still_detects_normal_bordered_table(
    sample_report_extended_pdf: Path,
) -> None:
    # Confirms the borderless-table fallback doesn't change behavior for
    # the already-working case -- a normal, gridded table is still
    # detected by the default strategy, without ever reaching the
    # fallback.
    loader = PdfLoader()
    document = loader.load(sample_report_extended_pdf)

    page_3_rows = [r for r in document.rows if r.metadata.sheet_or_page == "page_3"]
    assert len(page_3_rows) == 3
    regions = {row.data.get("Region") for row in page_3_rows}
    assert regions == {"North", "South", "East"}
