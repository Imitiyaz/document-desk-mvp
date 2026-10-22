"""Unit tests for app.cleaning.row_cleaning.

Author: Imitiyaz and AI Agent
Project: RAG MVP
Layer: Verification and synthetic fixtures
"""

from __future__ import annotations

import datetime as _datetime

from app.cleaning.row_cleaning import clean_row_data, forward_fill_group
from app.models.extracted import ExtractedRow, SourceMetadata


def _row(data: dict, row_num: int) -> ExtractedRow:
    return ExtractedRow(
        data=data,
        metadata=SourceMetadata(
            source_file="test.xlsx", sheet_or_page="Sheet1", row_or_location=row_num
        ),
    )


def test_clean_row_data_drops_none_values() -> None:
    result = clean_row_data({"Region": "North", "Notes": None})
    assert result == {"Region": "North"}


def test_clean_row_data_cleans_string_values() -> None:
    result = clean_row_data({"Region": "  North  Region  "})
    assert result == {"Region": "North Region"}


def test_clean_row_data_drops_strings_that_become_empty_after_cleaning() -> None:
    result = clean_row_data({"Region": "North", "Notes": "   "})
    assert result == {"Region": "North"}


def test_clean_row_data_passes_through_non_string_values_unchanged() -> None:
    result = clean_row_data({"Region": "North", "Revenue": 45000, "Active": True})
    assert result == {"Region": "North", "Revenue": 45000, "Active": True}


def test_clean_row_data_normalizes_whole_number_float_to_int() -> None:
    # Reproduces the exact pandas quirk found in Stage 3's manual smoke
    # test: a numeric column with one blank cell gets upcast to float64
    # for the whole column, so 45000 gets extracted as 45000.0.
    result = clean_row_data({"Revenue": 45000.0})
    assert result["Revenue"] == 45000
    assert isinstance(result["Revenue"], int)


def test_clean_row_data_preserves_genuine_decimal_values() -> None:
    result = clean_row_data({"Price": 45.5})
    assert result["Price"] == 45.5
    assert isinstance(result["Price"], float)


def test_clean_row_data_renders_no_trailing_zero_for_whole_number_float() -> None:
    # Strict enough to actually catch the original bug -- a looser
    # substring check like "45000" in str(result) would pass even with
    # "45000.0" present, which is exactly how the original bug slipped
    # through testing until a manual smoke test surfaced it.
    result = clean_row_data({"Revenue": 45000.0})
    assert str(result["Revenue"]) == "45000"


def test_forward_fill_group_preserves_unmerged_string_blanks() -> None:
    rows = [
        _row({"Region": "North", "Product": "Widgets"}, 2),
        _row({"Region": None, "Product": "Gadgets"}, 3),
        _row({"Region": None, "Product": "Gizmos"}, 4),
    ]
    filled = forward_fill_group(rows)
    assert [r.data["Region"] for r in filled] == ["North", None, None]


def test_forward_fill_group_does_not_fill_numeric_columns() -> None:
    rows = [
        _row({"Region": "North", "Revenue": 45000}, 2),
        _row({"Region": None, "Revenue": None}, 3),
    ]
    filled = forward_fill_group(rows)
    # Region (all-string column) fills forward; Revenue (numeric) does not
    assert filled[1].data["Region"] is None
    assert filled[1].data["Revenue"] is None


def test_forward_fill_group_does_not_fill_before_first_value_seen() -> None:
    rows = [
        _row({"Region": None}, 2),
        _row({"Region": "South"}, 3),
    ]
    filled = forward_fill_group(rows)
    assert filled[0].data["Region"] is None
    assert filled[1].data["Region"] == "South"


def test_forward_fill_group_does_not_mutate_input_rows() -> None:
    rows = [
        _row({"Region": "North"}, 2),
        _row({"Region": None}, 3),
    ]
    forward_fill_group(rows)
    assert rows[1].data["Region"] is None  # original untouched


def test_forward_fill_group_handles_empty_list() -> None:
    assert forward_fill_group([]) == []


def test_forward_fill_group_leaves_mixed_type_column_unfilled() -> None:
    # A column with both strings and numbers present is not "all string",
    # so it's left alone -- avoids fabricating a value in an ambiguous column.
    rows = [
        _row({"Value": "N/A"}, 2),
        _row({"Value": 100}, 3),
        _row({"Value": None}, 4),
    ]
    filled = forward_fill_group(rows)
    assert filled[2].data["Value"] is None


def test_clean_row_data_normalizes_date_only_value_to_plain_date_string() -> None:
    # Regression test for the bug found via Stage 6's fixture-coverage
    # review: pandas reads a date-only Excel cell as a datetime with the
    # time-of-day defaulted to midnight, which rendered as a spurious
    # "2026-01-15 00:00:00" in chunk text instead of "2026-01-15". See
    # docs/pipeline.md's third extraction and cleaning policy.
    result = clean_row_data({"Order Date": _datetime.datetime(2026, 1, 15, 0, 0, 0)})
    assert result["Order Date"] == "2026-01-15"


def test_clean_row_data_preserves_genuine_datetime_with_real_time_component() -> None:
    # A non-midnight time is real information, not a formatting
    # artifact -- must be left completely untouched, same principle as
    # genuine decimals being preserved in the numeric-normalization test
    # above.
    value = _datetime.datetime(2026, 1, 15, 14, 30, 0)
    result = clean_row_data({"Logged At": value})
    assert result["Logged At"] == value


def test_clean_row_data_renders_no_trailing_time_for_date_only_value() -> None:
    # Strict check, same spirit as the "no trailing zero" float test --
    # a loose substring check like "2026-01-15" in str(result) would
    # pass even with "2026-01-15 00:00:00" present.
    result = clean_row_data({"Order Date": _datetime.datetime(2026, 1, 15)})
    assert str(result["Order Date"]) == "2026-01-15"


def test_actual_merge_metadata_is_the_only_permission_to_fill() -> None:
    row = _row({"Region": None, "Comment": None}, 3)
    row.merged_values = {"Region": "North"}
    row.cell_origins = {"Region": "A2", "Comment": "B3"}
    result = forward_fill_group([row])[0]
    assert result.data == {"Region": "North", "Comment": None}
    assert result.cell_origins["Region"] == "A2"
    assert row.data["Region"] is None
