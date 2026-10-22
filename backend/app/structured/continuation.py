# SPDX-License-Identifier: AGPL-3.0-only
"""Apply the explicitly approved Region-continuation view at read time.

Only adjacent spreadsheet data rows may inherit a Region under this policy.
Raw blank values and both original/anchor coordinates remain available for audit.
Numeric values, PDF labels, gaps and summary boundaries are not forward-filled.
See docs/decisions/region-continuation.md before changing the interpretation.

Author: Imitiyaz and AI Agent
Project: RAG MVP
Layer: Structured
"""

from __future__ import annotations

import re
from copy import deepcopy
from pathlib import Path

POLICY = "region-continuation-v1"


def apply_continuations(document: dict, source: str) -> dict:
    """Return a disclosed continuation view while retaining original source cells.


    Args:
        document: Ledger payload with values, raw_values and physical coordinates.
        source: Filename used to limit the policy to XLSX/XLSM documents.

    Returns:
        A deep-copied spreadsheet view with continuation_fields provenance; other
        formats return the original document without applying this policy.

    An adjacent numeric measure is required before a blank Region can inherit. Any
    row gap or boundary clears the anchor. Requested numeric cells are never filled.
    """
    if Path(source).suffix.casefold() not in {".xlsx", ".xlsm"}:
        return document
    from app.structured.engine import header_name, number

    # Inferred labels must not mutate the canonical raw-cell ledger used by other requests.
    document = deepcopy(document)
    previous: dict[tuple[str, str], tuple[int, str, str, int]] = {}
    for row in document["rows"]:
        location = row["row_or_location"]
        if not isinstance(location, int):
            continue
        for field in row["values"]:
            if header_name(field) != "region":
                continue
            key = row["sheet_or_page"], field
            anchor = previous.get(key)
            # A gap is a boundary, not permission to carry a Region into another table.
            if anchor and location != anchor[0] + 1:
                previous.pop(key, None)
                anchor = None
            value = row["values"][field]
            if value is not None:
                text = str(value).strip()
                if header_name(text) in {
                    "region",
                    "total",
                    "totals",
                    "subtotal",
                    "sub total",
                    "grand total",
                    "all",
                    "all regions",
                }:
                    previous.pop(key, None)
                    continue
                cell = row.get("cell_origins", {}).get(field)
                if cell and number(value) is None:
                    coordinate = re.fullmatch(r"[A-Z]+(\d+)", cell)
                    anchor_row = int(coordinate[1]) if coordinate else location
                    previous[key] = location, text, cell, anchor_row
                else:
                    previous.pop(key, None)
                continue
            # Require a measure-bearing row; headings and blank separators cannot inherit a label.
            has_measure = any(
                number(v) is not None
                for f, v in row["values"].items()
                if f != field and header_name(f) not in {"year", "quarter"}
            )
            cell = row.get("cell_origins", {}).get(field)
            if anchor and cell and has_measure and field not in row["merged_fields"]:
                _, value, origin, anchor_row = anchor
                row["values"][field] = value
                # Keep both coordinates so the UI can distinguish a raw blank from its assumed label.
                row.setdefault("continuation_fields", {})[field] = {
                    "value": value,
                    "original_value": row.get("raw_values", {}).get(field),
                    "original_cell": cell,
                    "anchor_cell": origin,
                    "anchor_row": anchor_row,
                    "policy": POLICY,
                }
                previous[key] = location, value, origin, anchor_row
            else:
                previous.pop(key, None)
    return document
