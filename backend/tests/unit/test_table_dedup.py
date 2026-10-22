"""Unit tests for app.cleaning.table_dedup.

Author: Imitiyaz and AI Agent
Project: RAG MVP
Layer: Verification and synthetic fixtures
"""

from __future__ import annotations

from app.cleaning.table_dedup import (
    build_table_tokens_by_page,
    remove_table_duplicate_lines,
)
from app.models.extracted import ExtractedRow, SourceMetadata


def _table_row(data: dict, page: str) -> ExtractedRow:
    return ExtractedRow(
        data=data,
        metadata=SourceMetadata(
            source_file="test.pdf", sheet_or_page=page, row_or_location="table_1_row_1"
        ),
    )


def test_build_table_tokens_by_page_collects_tokens_per_page() -> None:
    rows = [
        _table_row({"Region": "North", "Revenue": "45000"}, "page_1"),
        _table_row({"Region": "South", "Revenue": "38000"}, "page_2"),
    ]
    tokens = build_table_tokens_by_page(rows)
    assert "north" in tokens["page_1"]
    assert "45000" in tokens["page_1"]
    assert "south" not in tokens["page_1"]
    assert "south" in tokens["page_2"]


def test_build_table_tokens_by_page_includes_column_header_names() -> None:
    """Regression test for the bug found via Stage 6's manual smoke test:
    header cell text ("Region", "Q3 Revenue") must be tokenized too, not
    just cell values -- otherwise a PDF's rendered table header row is
    never recognized as table-duplicate content. See
    docs/pipeline.md's second extraction and cleaning policy.
    """
    rows = [_table_row({"Region": "North", "Q3 Revenue": "45000"}, "page_1")]
    tokens = build_table_tokens_by_page(rows)
    assert "region" in tokens["page_1"]
    assert "q3" in tokens["page_1"]
    assert "revenue" in tokens["page_1"]


def test_remove_table_duplicate_lines_removes_high_overlap_line() -> None:
    text = "North 45000 52000\nThis is genuine narrative commentary about the report."
    table_tokens = {"north", "45000", "52000"}
    result = remove_table_duplicate_lines(text, table_tokens)
    assert "North 45000 52000" not in result
    assert "genuine narrative commentary" in result


def test_remove_table_duplicate_lines_removes_single_token_line_that_fully_matches() -> (
    None
):
    """Regression test for the bug found via Stage 6's manual smoke test:
    a one-word/one-number line ("North", "45000") that exactly matches a
    table token must now be removed -- it used to be unconditionally kept
    regardless of overlap, which meant a PDF table rendered cell-per-line
    (PyMuPDF's normal behavior) was never deduplicated at all. See
    docs/pipeline.md's second extraction and cleaning policy.
    """
    result = remove_table_duplicate_lines("North", {"north"})
    assert result == ""


def test_remove_table_duplicate_lines_keeps_single_token_line_with_no_overlap() -> None:
    """A single-token line that does NOT match any table token must still
    be kept -- confirms the fix doesn't over-correct into removing every
    short line unconditionally, only ones that actually overlap.
    """
    result = remove_table_duplicate_lines("Overview", {"north", "45000"})
    assert result == "Overview"


def test_remove_table_duplicate_lines_keeps_blank_lines() -> None:
    """A blank line has zero tokens -- overlap is undefined (division by
    zero), not just unreliable, so it must always be kept regardless of
    table_tokens. This is the one case DEFAULT_MIN_LINE_TOKENS still
    guards against after the fix.
    """
    text = "\nSome narrative text.\n"
    result = remove_table_duplicate_lines(text, {"narrative"})
    assert result.startswith("\n")


def test_remove_table_duplicate_lines_strips_a_realistic_pymupdf_table_dump() -> None:
    """End-to-end regression test using the exact shape PyMuPDF produces
    for a real table -- each header and each cell value on its own line
    -- rather than the earlier tests' artificial single combined line.
    This is the scenario that was completely un-deduplicated before the
    fix (see docs/pipeline.md's second Post-Verification
    Fix): confirmed via Stage 6's manual smoke test against the real
    sample_report.pdf fixture, not caught by any prior automated test.
    """
    rows = [
        _table_row(
            {"Region": "North", "Q3 Revenue": "45000", "Q4 Revenue": "52000"}, "page_1"
        ),
        _table_row(
            {"Region": "South", "Q3 Revenue": "38000", "Q4 Revenue": "39500"}, "page_1"
        ),
    ]
    table_tokens = build_table_tokens_by_page(rows)["page_1"]

    raw_text = (
        "Quarterly Regional Sales Report\n"
        "This report summarizes regional sales performance for the third quarter.\n"
        "Region\n"
        "Q3 Revenue\n"
        "Q4 Revenue\n"
        "North\n"
        "45000\n"
        "52000\n"
        "South\n"
        "38000\n"
        "39500"
    )
    result = remove_table_duplicate_lines(raw_text, table_tokens)

    assert "Quarterly Regional Sales Report" in result
    assert "This report summarizes regional sales performance" in result
    for leaked_cell_line in [
        "Region",
        "Q3 Revenue",
        "Q4 Revenue",
        "North",
        "45000",
        "52000",
    ]:
        assert leaked_cell_line not in result.split("\n")


def test_remove_table_duplicate_lines_keeps_low_overlap_lines() -> None:
    text = "The overall regional performance improved substantially this quarter."
    table_tokens = {"north", "45000"}
    result = remove_table_duplicate_lines(text, table_tokens)
    assert "overall regional performance" in result


def test_remove_table_duplicate_lines_no_op_with_empty_token_set() -> None:
    text = "Any narrative text at all."
    assert remove_table_duplicate_lines(text, set()) == text
