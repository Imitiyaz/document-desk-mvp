"""Integration tests: full pipeline (loader -> cleaning -> chunking)
against sample_sales_extended.xlsx -- edge cases the original
sample_sales.xlsx never exercised (real merged cells, wide rows, unicode,
dates, multi-column sparse data). Added after Stage 6's manual smoke test
surfaced a real bug that only became visible against real chunk text; see
docs/pipeline.md's extraction and cleaning policyes #2-#5 and
docs/testing.md for the full rationale behind these fixtures.

Author: Imitiyaz and AI Agent
Project: RAG MVP
Layer: Verification and synthetic fixtures
"""

from __future__ import annotations

from pathlib import Path

from app.chunking import chunk_document
from app.cleaning import clean_document
from app.loaders.xlsx_loader import XlsxLoader


def _chunks_for_sheet(chunks, sheet_name: str):  # noqa: ANN001, ANN201
    return [c for c in chunks if c.metadata.sheet_or_page == sheet_name]


def test_merged_region_cells_are_forward_filled_from_real_openpyxl_merge(
    sample_sales_extended_xlsx: Path,
) -> None:
    # Confirms forward_fill_group()'s documented approximation against a
    # GENUINE openpyxl merge (ws.merge_cells(...)), not just a synthetic
    # blank-string dict -- this specific scenario had never been
    # exercised against a real loaded file before.
    document = XlsxLoader().load(sample_sales_extended_xlsx)
    cleaned = clean_document(document)
    chunks = chunk_document(cleaned)

    merged_chunks = _chunks_for_sheet(chunks, "Merged Region")
    assert len(merged_chunks) == 4
    for chunk in merged_chunks:
        assert "Region is" in chunk.text  # forward-fill succeeded, not dropped


def test_wide_row_triggers_character_budget_splitting_on_real_file(
    sample_sales_extended_xlsx: Path,
) -> None:
    # Confirms row_chunker's wide-row splitting (previously only unit
    # tested against synthetic dicts) actually triggers against a real
    # pandas-extracted row with enough real content to exceed the
    # character budget.
    document = XlsxLoader().load(sample_sales_extended_xlsx)
    cleaned = clean_document(document)
    chunks = chunk_document(cleaned)

    wide_chunks = _chunks_for_sheet(chunks, "Wide Row")
    part_suffixed = [c for c in wide_chunks if "_part" in c.metadata.row_or_location]
    assert len(part_suffixed) > 0, "expected at least one row to split into parts"


def test_unicode_and_currency_values_survive_cleaning(
    sample_sales_extended_xlsx: Path,
) -> None:
    document = XlsxLoader().load(sample_sales_extended_xlsx)
    cleaned = clean_document(document)
    chunks = chunk_document(cleaned)

    unicode_chunks = _chunks_for_sheet(chunks, "Unicode Currency")
    combined = " ".join(c.text for c in unicode_chunks)
    assert "José García" in combined
    assert "€45,000" in combined
    assert "🎉" in combined


def test_date_only_values_render_without_spurious_time_component(
    sample_sales_extended_xlsx: Path,
) -> None:
    document = XlsxLoader().load(sample_sales_extended_xlsx)
    cleaned = clean_document(document)
    chunks = chunk_document(cleaned)

    date_chunks = _chunks_for_sheet(chunks, "Dates")
    for chunk in date_chunks:
        assert "00:00:00" not in chunk.text
    combined = " ".join(c.text for c in date_chunks)
    assert "2026-01-15" in combined


def test_sparse_data_ordinary_blanks_remain_missing(
    sample_sales_extended_xlsx: Path,
) -> None:
    """Regression: unmerged comments and labels must never inherit a prior row."""
    document = XlsxLoader().load(sample_sales_extended_xlsx)
    cleaned = clean_document(document)
    chunks = chunk_document(cleaned)

    sparse_chunks = _chunks_for_sheet(chunks, "Sparse Data")
    # Row 4 (East) had no Comment in the source data at all, but forward
    # fill (correctly, per its documented tradeoff) carries the prior
    # row's "Strong" comment forward since the whole column is all-string.
    row_4 = next(c for c in sparse_chunks if c.metadata.row_or_location == 4)
    assert "Comment is Strong" not in row_4.text
    row_3 = next(c for c in sparse_chunks if c.metadata.row_or_location == 3)
    assert "Region is North" not in row_3.text
