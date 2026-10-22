# SPDX-License-Identifier: AGPL-3.0-only
"""Normalize source cells without guessing missing values.

Only actual vertical merge anchors captured by the Excel loader permit a
blank field to inherit a value. Ordinary spreadsheet/PDF blanks stay missing.
The removed string-column heuristic and its failures are retained in the
chunking ADR and Stage 10 quality evidence.

Author: Imitiyaz and AI Agent
Project: RAG MVP
Layer: Cleaning
"""

from __future__ import annotations

import datetime as _datetime
from typing import Any

from app.cleaning.cell_semantics import semantic_cell
from app.cleaning.text_cleaning import clean_text
from app.models.extracted import ExtractedRow


def _normalize_numeric_value(value: Any) -> Any:
    """Converts a whole-number float to int (e.g. 45000.0 -> 45000).

    Addresses a genuine pandas quirk, not a hypothetical one: a numeric
    Excel column containing even one blank/NaN cell gets upcast to
    float64 for the ENTIRE column, since pandas cannot represent NaN in
    an int64 column. An otherwise-integer column like "Q3 Revenue" then
    has every value extracted as a float, purely as a side effect of one
    unrelated blank cell -- not a real change in the data's precision.
    Only whole-number floats are converted; a genuine decimal (45.5)
    is left untouched, since collapsing that would be a real data change,
    not a formatting fix.
    """
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return value


def _normalize_date_value(value: Any) -> Any:
    """Renders a date-only Excel value as a plain date string (e.g.
    "2026-01-15") instead of a full datetime string with a spurious
    "00:00:00" appended.

    Preserve date-only meaning when a reader supplies a midnight timestamp.
    Root cause: pandas reads an Excel date-only cell as a
    `pandas.Timestamp` (a `datetime.datetime` subclass) with its
    time-of-day defaulted to midnight -- that midnight component isn't
    real information, it's an artifact of the column being date-only,
    the same way `45000.0`'s trailing `.0` wasn't a real decimal. A
    genuine datetime WITH a non-midnight time component is left
    completely untouched -- that time-of-day is real data, not a
    formatting artifact, and destroying it would be a real data change,
    not a cleanup.
    """
    if isinstance(value, _datetime.datetime) and value.time() == _datetime.time.min:
        return value.date().isoformat()
    if isinstance(value, _datetime.time):
        return value.isoformat()
    if isinstance(value, _datetime.timedelta):
        return str(value.total_seconds()) + " s"
    return value


def forward_fill_group(rows: list[ExtractedRow]) -> list[ExtractedRow]:
    """Fill only values explicitly attached to actual vertical Excel merges.

    No value is inferred from the previous row, field type or PDF layout.
    Ordinary blanks and input objects remain unchanged.
    """
    if not rows:
        return rows

    filled_rows = []
    for row in rows:
        data = dict(row.data)
        for column, value in row.merged_values.items():
            if data.get(column) is None:
                data[column] = value
        filled_rows.append(
            ExtractedRow(
                data=data,
                metadata=row.metadata,
                cell_origins=dict(row.cell_origins),
                cell_formats=dict(row.cell_formats),
                formula_fields=set(row.formula_fields),
                merged_values=dict(row.merged_values),
            )
        )

    return filled_rows


def clean_row_data(
    data: dict[str, Any], cell_formats: dict[str, str] | None = None
) -> dict[str, Any]:
    """Drops fields with no value and cleans (whitespace/encoding) string
    values. A string that becomes empty after cleaning is treated as
    absent, same as None -- an empty string carries no more information
    than a missing field, and leaving it in would make downstream chunking
    render a blank value instead of omitting the field.
    """
    cleaned: dict[str, Any] = {}
    for key, value in data.items():
        value = semantic_cell(value, (cell_formats or {}).get(key, "General"))
        if value is None:
            continue
        if isinstance(value, str):
            value = clean_text(value)
            if value == "":
                continue
        else:
            value = _normalize_numeric_value(value)
            value = _normalize_date_value(value)
        cleaned[key] = value
    return cleaned
