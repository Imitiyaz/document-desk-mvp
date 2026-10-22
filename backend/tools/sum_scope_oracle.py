"""Independent reviewed facts for the original extended workbook; no app imports.

Author: Imitiyaz and AI Agent
Project: RAG MVP
Layer: Verification and release tooling
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

# Physical facts reviewed against the original workbook, including merge anchors.
ROWS = [
    ("Merged Region", 2, "North", "45000", "A2"),
    ("Merged Region", 3, "North", "47000", "A2"),
    ("Merged Region", 4, "South", "38000", "A4"),
    ("Merged Region", 5, "South", "39000", "A4"),
    ("Sparse Data", 2, "North", "45000", "A2"),
    ("Sparse Data", 3, "North", "38000", "A3"),
    ("Sparse Data", 4, "East", None, "A4"),
    ("Sparse Data", 5, "West", "41000", "A5"),
    ("Sparse Data", 6, "West", "22000", "A6"),
]


def validate_sequence_answer(
    body: dict[str, Any],
    *,
    scopes: list[str] | None = None,
    entity: str | None = None,
    calculate: bool = False,
) -> list[str]:
    """Check exact source/cell/operand/exclusion sets against independent facts."""
    from tools.presentation_checks import readable_findings

    expected = [
        r
        for r in ROWS
        if (not scopes or r[0] in scopes) and (entity is None or r[2] == entity)
    ]
    findings = []
    records = body.get("records", [])
    source = "sample_sales_extended.xlsx"
    identities = [(r[0], r[1]) for r in expected]
    if [
        (r.get("sheet_or_page"), r.get("row_or_location")) for r in records
    ] != identities:
        findings.append("Wrong source population/order after conversation scope change")
    for number, (record, fact) in enumerate(zip(records, expected, strict=False), 1):
        sheet, row, region, value, anchor = fact
        if (
            record.get("number") != number
            or record.get("source_file") != source
            or record.get("values") != {"Region": region, "Q3 Revenue": value}
        ):
            findings.append("Wrong physical record/value/label")
        if record.get("cell_references") != {"Region": anchor, "Q3 Revenue": f"B{row}"}:
            findings.append("Wrong original cell/merge anchor")
        expected_continuation = {}
        if sheet == "Sparse Data" and row in {3, 6}:
            expected_continuation = {
                "Region": {
                    "value": region,
                    "original_value": None,
                    "original_cell": f"A{row}",
                    "anchor_cell": "A2" if row == 3 else "A5",
                    "anchor_row": 2 if row == 3 else 5,
                    "policy": "region-continuation-v1",
                }
            }
        if record.get("continuation_fields", {}) != expected_continuation:
            findings.append("Original blank or continuation provenance omitted/changed")
    citations = body.get("citations", [])
    if [
        (
            c.get("number"),
            c.get("source_file"),
            c.get("sheet_or_page"),
            c.get("row_or_location"),
        )
        for c in citations
    ] != [(i, source, r[0], r[1]) for i, r in enumerate(expected, 1)]:
        findings.append("Wrong/omitted source references")
    missing: list[dict[str, Any]] = [
        {"number": i, "field": "Q3 Revenue", "cell": f"B{r[1]}"}
        for i, r in enumerate(expected, 1)
        if r[3] is None
    ]
    if body.get("coverage", {}).get("missing_cells") != missing or body.get(
        "coverage", {}
    ).get("matched_records") != len(expected):
        findings.append("Wrong missing-cell/population coverage")
    if body.get("status") != ("incomplete" if missing else "answered") or body.get(
        "coverage", {}
    ).get("complete") != (not missing):
        findings.append("Wrong completeness/status")
    calc = body.get("calculation")
    if not calculate:
        if calc is not None:
            findings.append("Unrequested calculation")
    elif not calc:
        findings.append("Requested available-value SUM was withheld")
    else:
        total = sum((Decimal(r[3]) for r in expected if r[3] is not None), Decimal(0))
        if calc.get("result") != {"Q3 Revenue": str(total)} or calc.get(
            "partial"
        ) != bool(missing):
            findings.append("Wrong subtotal or false completeness")
        wanted_operands = [
            {
                "number": i,
                "values": {"Q3 Revenue": r[3]},
                "source": {
                    "source_file": source,
                    "sheet_or_page": r[0],
                    "row_or_location": r[1],
                },
                "cell_references": {"Q3 Revenue": f"B{r[1]}"},
            }
            for i, r in enumerate(expected, 1)
            if r[3] is not None
        ]
        if calc.get("operands") != wanted_operands:
            findings.append("Wrong/omitted/imputed operand or cell")
        wanted_exclusions = [
            {
                **cell,
                "reason": "missing_value",
                "source": {
                    "source_file": source,
                    "sheet_or_page": expected[cell["number"] - 1][0],
                    "row_or_location": expected[cell["number"] - 1][1],
                },
            }
            for cell in missing
        ]
        if calc.get("excluded_cells") != wanted_exclusions:
            findings.append("Wrong/omitted exclusion or source cell")
    findings.extend(readable_findings(body))
    return sorted(set(findings))
