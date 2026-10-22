"""Unit tests for XlsxLoader.

Naming convention (per docs/testing.md): test_<unit>_<behavior>.

Author: Imitiyaz and AI Agent
Project: RAG MVP
Layer: Verification and synthetic fixtures
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.core.exceptions import CorruptFileError, LegacyExcelFormatError
from app.loaders.xlsx_loader import XlsxLoader


def test_xlsx_loader_supports_xlsx_extension() -> None:
    loader = XlsxLoader()
    assert loader.supports(Path("anything.xlsx")) is True
    assert loader.supports(Path("anything.xlsm")) is True
    assert loader.supports(Path("anything.pdf")) is False


def test_xlsx_loader_supports_legacy_xls_for_routing_only() -> None:
    # .xls is "supported" for routing purposes (so it reaches this loader
    # and gets a specific error), even though it can't actually be loaded.
    loader = XlsxLoader()
    assert loader.supports(Path("old_file.xls")) is True


def test_xlsx_loader_extracts_all_rows_from_all_sheets(sample_sales_xlsx: Path) -> None:
    loader = XlsxLoader()
    document = loader.load(sample_sales_xlsx)

    # sample_sales.xlsx has 4 rows in "Q3 Sales" + 2 rows in "Q4 Notes"
    # + 0 rows in "Empty Sheet" = 6 total rows.
    assert len(document.rows) == 6
    assert document.source_file == "sample_sales.xlsx"


def test_xlsx_loader_retains_correct_sheet_names(sample_sales_xlsx: Path) -> None:
    loader = XlsxLoader()
    document = loader.load(sample_sales_xlsx)

    sheet_names = {row.metadata.sheet_or_page for row in document.rows}
    assert sheet_names == {"Q3 Sales", "Q4 Notes"}
    # "Empty Sheet" contributes no rows, so it should not appear here.


def test_xlsx_loader_computes_correct_excel_row_numbers(
    sample_sales_xlsx: Path,
) -> None:
    loader = XlsxLoader()
    document = loader.load(sample_sales_xlsx)

    q3_rows = [r for r in document.rows if r.metadata.sheet_or_page == "Q3 Sales"]
    row_numbers = sorted(r.metadata.row_or_location for r in q3_rows)
    # Header is row 1 in Excel, so first data row is row 2.
    assert row_numbers == [2, 3, 4, 5]


def test_xlsx_loader_converts_nan_to_none(sample_sales_xlsx: Path) -> None:
    loader = XlsxLoader()
    document = loader.load(sample_sales_xlsx)

    # The "West" row in Q3 Sales has a deliberately blank Q3 Revenue cell.
    west_row = next(
        r
        for r in document.rows
        if r.metadata.sheet_or_page == "Q3 Sales" and r.data.get("Region") == "West"
    )
    assert west_row.data["Q3 Revenue"] is None  # not NaN, not "nan" string -- None


def test_xlsx_loader_row_data_preserves_column_values(sample_sales_xlsx: Path) -> None:
    loader = XlsxLoader()
    document = loader.load(sample_sales_xlsx)

    north_row = next(
        r
        for r in document.rows
        if r.metadata.sheet_or_page == "Q3 Sales" and r.data.get("Region") == "North"
    )
    assert north_row.data["Q3 Revenue"] == 45000
    assert north_row.data["Q4 Revenue"] == 52000


def test_xlsx_loader_raises_legacy_format_error_for_xls(tmp_path: Path) -> None:
    fake_xls = tmp_path / "old_file.xls"
    fake_xls.write_bytes(b"not a real xls file, content doesn't matter for this test")

    loader = XlsxLoader()
    with pytest.raises(LegacyExcelFormatError, match="legacy .xls format"):
        loader.load(fake_xls)


def test_xlsx_loader_raises_corrupt_file_error_for_garbage_content(
    tmp_path: Path,
) -> None:
    fake_xlsx = tmp_path / "corrupt.xlsx"
    fake_xlsx.write_bytes(b"this is not a real xlsx file at all")

    loader = XlsxLoader()
    with pytest.raises(CorruptFileError):
        loader.load(fake_xlsx)
