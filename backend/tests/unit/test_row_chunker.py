"""Unit tests for app.chunking.row_chunker.

Author: Imitiyaz and AI Agent
Project: RAG MVP
Layer: Verification and synthetic fixtures
"""

from __future__ import annotations

from app.chunking.row_chunker import (
    chunk_row,
    chunk_rows,
    render_row_as_sentence,
    split_row_into_field_groups,
)
from app.models.cleaned import CleanedRow
from app.models.extracted import SourceMetadata


def _row(data: dict, row_num=2) -> CleanedRow:
    return CleanedRow(
        data=data,
        metadata=SourceMetadata(
            source_file="test.xlsx", sheet_or_page="Q3 Sales", row_or_location=row_num
        ),
    )


def test_render_row_as_sentence_basic() -> None:
    sentence = render_row_as_sentence({"Region": "North", "Revenue": 45000}, "Q3 Sales")
    assert sentence == "In 'Q3 Sales': Region is North; Revenue is 45000."


def test_render_row_as_sentence_preserves_field_order() -> None:
    sentence = render_row_as_sentence({"B": 1, "A": 2}, "Sheet1")
    assert sentence == "In 'Sheet1': B is 1; A is 2."


def test_split_row_into_field_groups_single_group_when_under_limit() -> None:
    data = {"Region": "North", "Revenue": 45000}
    groups = split_row_into_field_groups(data, max_chars=800)
    assert groups == [data]


def test_split_row_into_field_groups_splits_wide_row() -> None:
    data = {f"Col{i}": "x" * 50 for i in range(20)}  # deliberately wide/long
    groups = split_row_into_field_groups(data, max_chars=200)
    assert len(groups) > 1
    # The anchor repeats; all remaining original fields appear exactly once.
    assert all(group["Col0"] == data["Col0"] for group in groups)
    all_keys = [key for group in groups for key in group if key != "Col0"]
    assert sorted(all_keys) == sorted(key for key in data if key != "Col0")


def test_wide_row_retains_identifier_beside_later_value() -> None:
    chunks = chunk_row(
        _row({"Order ID": "ORD-1001", "Notes": "x" * 900, "Renewal Date": "2027-01-15"})
    )
    assert len(chunks) > 1
    date_chunks = [c for c in chunks if "Renewal Date is 2027-01-15" in c.text]
    assert len(date_chunks) == 1
    assert "Order ID is ORD-1001" in date_chunks[0].text
    assert all("Order ID is ORD-1001" in c.text for c in chunks)


def test_empty_row_produces_no_chunks() -> None:
    assert chunk_row(_row({})) == []


def test_split_row_into_field_groups_keeps_oversized_single_field_whole() -> None:
    # A single field's value alone exceeds max_chars -- must not be dropped
    # or truncated, just kept as its own group.
    data = {"Notes": "x" * 500}
    groups = split_row_into_field_groups(data, max_chars=100)
    assert len(groups) == 1
    assert groups[0] == data


def test_chunk_row_produces_one_chunk_for_normal_row() -> None:
    row = _row({"Region": "North", "Revenue": 45000})
    chunks = chunk_row(row)
    assert len(chunks) == 1
    assert chunks[0].metadata == row.metadata
    assert "North" in chunks[0].text


def test_chunk_row_splits_wide_row_into_multiple_chunks_with_part_suffix() -> None:
    data = {f"Col{i}": "x" * 50 for i in range(20)}
    row = _row(data)
    chunks = chunk_row(row, max_chunk_chars=200)
    assert len(chunks) > 1
    for i, chunk in enumerate(chunks, start=1):
        assert chunk.metadata.source_file == "test.xlsx"
        assert chunk.metadata.sheet_or_page == "Q3 Sales"
        assert chunk.metadata.row_or_location == f"2_part{i}"


def test_chunk_rows_produces_one_chunk_per_normal_row() -> None:
    rows = [_row({"Region": "North"}, 2), _row({"Region": "South"}, 3)]
    chunks = chunk_rows(rows)
    assert len(chunks) == 2


def test_chunk_rows_handles_empty_list() -> None:
    assert chunk_rows([]) == []
