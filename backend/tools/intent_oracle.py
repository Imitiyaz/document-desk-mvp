"""Independent physical-record expectations for the user-reported intent fixes.

No application parser/planner/calculator is imported. Expected amounts and cell
locations come from the unchanged acceptance workbooks and four-page PDF.
Author: Imitiyaz and AI Agent
"""

from __future__ import annotations

from collections import Counter
from decimal import Decimal
from typing import Any

from tools.presentation_checks import readable_findings

PDF = [
    ("page_1", "table_1_row_1", "BOLT-A", "10"),
    ("page_1", "table_1_row_2", "NUT-B", "6"),
    ("page_3", "table_1_row_1", "BOLT-A", "4"),
    ("page_3", "table_1_row_2", "NUT-B", "8"),
]
HOURS = [
    ("Work log", 2, "Asha", "7.5"),
    ("Work log", 3, "Asha", "8.25"),
    ("Work log", 4, "Ben", None),
    ("Work log", 5, "Asha", "0"),
]


def findings(kind: str, body: dict[str, Any], source: str) -> list[str]:
    """Validate exact scope, identity/value/cell/citation and displayed result."""
    issues = readable_findings(body)
    if not body.get("execution_path", "").startswith("structured"):
        issues.append("Wrong answer path")
    records = body.get("records", [])
    citations = body.get("citations", [])
    if body.get("model") is not None or body.get("unresolved_citation_numbers"):
        issues.append("Unexpected model use or unresolved citations")
    if kind.startswith("absent_"):
        entity, field = {
            "absent_product": ("Apple", "Product"),
            "absent_all": ("All", "Product"),
            "absent_name": ("Zenzee", "Name"),
        }[kind]
        if (
            body.get("status") != "no_evidence"
            or records
            or citations
            or body.get("calculation")
            or body.get("grouped_results")
        ):
            issues.append(
                "Absent entity broadened to records, zero or another population"
            )
        if any(
            word not in body.get("answer", "")
            for word in [entity, field, source, "No matching"]
        ):
            issues.append("Missing actionable absent-entity explanation")
        if body.get("coverage", {}).get("matched_records") != 0:
            issues.append("Wrong absent-entity coverage")
        return issues
    if kind.startswith("clarify"):
        if (
            body.get("status") != "clarification_required"
            or records
            or body.get("calculation")
        ):
            issues.append("Unsupported/mixed request silently calculated a subset")
        if kind == "clarify_counting" and not any(
            c.get("label") == "Use source records"
            for c in body.get("clarification_options", [])
        ):
            issues.append("Physical-record confirmation option missing")
        for name in {
            "clarify_products": ["Apple", "BOLT-A"],
            "clarify_names": ["Asha", "Zenzee"],
        }.get(kind, []):
            if name not in body.get("answer", ""):
                issues.append("Clarification lost a requested entity")
        return issues
    pdf = kind.endswith("pdf")
    field, identity, unit = (
        ("Quantity", "Product", "pcs") if pdf else ("Hours", "Name", "hours")
    )
    wanted = PDF if pdf else HOURS
    if kind == "lookup_pdf":
        wanted = [r for r in PDF if r[2] == "BOLT-A"]
    if kind in {"asha", "record_asha"}:
        wanted = [r for r in HOURS if r[2] == "Asha"]
    if kind == "ben":
        wanted = [HOURS[2]]
    partial = kind in {"ben", "subtotal", "record_all", "grouped_hours"}
    if body.get("status") != ("incomplete" if partial else "answered"):
        issues.append("Wrong missing/complete status")
    if [
        (
            r.get("sheet_or_page"),
            r.get("row_or_location"),
            r.get("values", {}).get(identity),
            r.get("values", {}).get(field),
        )
        for r in records
    ] != wanted:
        issues.append("Wrong, omitted or duplicated identity/source/value records")
    expected_locations = Counter((source, r[0], r[1]) for r in wanted)
    if (
        Counter(
            (c.get("source_file"), c.get("sheet_or_page"), c.get("row_or_location"))
            for c in citations
        )
        != expected_locations
    ):
        issues.append("Wrong complete citation set")
    by_number = {
        c.get("number"): (
            c.get("source_file"),
            c.get("sheet_or_page"),
            c.get("row_or_location"),
        )
        for c in citations
    }
    for record in records:
        location = (source, record.get("sheet_or_page"), record.get("row_or_location"))
        if (
            record.get("source_file") != source
            or by_number.get(record.get("number")) != location
            or record.get("values", {}).get("Unit") != unit
        ):
            issues.append("Wrong record/citation/unit association")
        if not pdf:
            row = record["row_or_location"]
            if record.get("cell_references") != {
                "Name": f"A{row}",
                "Hours": f"B{row}",
                "Unit": f"C{row}",
            }:
                issues.append("Original hours cells differ")
    if body.get("coverage", {}).get("matched_records") != len(wanted) or body.get(
        "coverage", {}
    ).get("fields") != [field]:
        issues.append("Wrong requested metric or record coverage")
    numeric = [r for r in wanted if r[3] is not None]

    def check_calc(
        calc: dict | None, expected: list[tuple], total: str, is_partial: bool
    ) -> None:
        if not calc:
            issues.append("Requested sum absent")
            return
        if (
            calc.get("result") != {field: total}
            or calc.get("unit") != unit
            or calc.get("partial") != is_partial
        ):
            issues.append("Wrong sum/unit/completeness")
        if calc.get("included_records") != len(expected) or (
            not is_partial and calc.get("excluded_cells")
        ):
            issues.append("Wrong included/excluded operand counts")
        operands = calc.get("operands", [])
        actual = [
            (
                o.get("source", {}).get("sheet_or_page"),
                o.get("source", {}).get("row_or_location"),
                o.get("values", {}).get(field),
            )
            for o in operands
        ]
        if Counter(actual) != Counter((r[0], r[1], r[3]) for r in expected):
            issues.append("Omitted/duplicate/changed operands, including zero")
        for o in operands:
            loc = (
                source,
                o.get("source", {}).get("sheet_or_page"),
                o.get("source", {}).get("row_or_location"),
            )
            if (
                o.get("source", {}).get("source_file") != source
                or by_number.get(o.get("number")) != loc
            ):
                issues.append("Operand citation points to another source")
            if not pdf and o.get("cell_references", {}).get(field) != f"B{loc[2]}":
                issues.append("Operand cell differs")
        try:
            if sum(
                (Decimal(o["values"][field]) for o in operands), Decimal(0)
            ) != Decimal(total):
                issues.append("Operand arithmetic differs from independent total")
        except (KeyError, TypeError, ValueError):
            issues.append("Invalid operand value")

    if kind in {"grouped_pdf", "grouped_hours"}:
        groups = body.get("grouped_results", [])
        expected_groups: list[tuple[str, str | None, list[tuple], bool]] = (
            [
                ("Overall", "28", PDF, False),
                ("BOLT-A", "14", [PDF[0], PDF[2]], False),
                ("NUT-B", "14", [PDF[1], PDF[3]], False),
            ]
            if pdf
            else [
                ("Overall", "15.75", numeric, True),
                ("Asha", "15.75", numeric, False),
                ("Ben", None, [], True),
            ]
        )
        if [(g.get("scope"), g.get("label")) for g in groups] != [
            ("Whole file", v[0]) for v in expected_groups
        ]:
            issues.append(
                "Requested per-identity and overall breakdown missing or changed"
            )
        for g, (_, total, rows, is_partial) in zip(
            groups, expected_groups, strict=False
        ):
            if g.get("status") != ("incomplete" if is_partial else "answered"):
                issues.append("Group missing-data status differs")
            group_rows = (
                wanted
                if g.get("label") == "Overall"
                else [r for r in wanted if r[2] == g.get("label")]
            )
            expected_numbers = [
                r["number"]
                for r in records
                if (r["sheet_or_page"], r["row_or_location"])
                in {(v[0], v[1]) for v in group_rows}
            ]
            if g.get("record_numbers") != expected_numbers:
                issues.append("Wrong grouped source-reference links")
            if total is not None:
                check_calc(g.get("calculation"), rows, total, is_partial)
            elif g.get("calculation") is not None:
                issues.append("Missing Ben hours replaced with a number")
    elif kind in {"asha", "subtotal"}:
        check_calc(body.get("calculation"), numeric, "15.75", kind == "subtotal")
        if kind == "subtotal":
            excluded = body.get("calculation", {}).get("excluded_cells", [])
            if (
                len(excluded) != 1
                or excluded[0].get("cell") != "B4"
                or excluded[0].get("source", {}).get("row_or_location") != 4
                or "subtotal" not in body.get("answer", "").lower()
            ):
                issues.append(
                    "Missing Ben source exclusion or visible subtotal warning"
                )
    elif body.get("calculation") is not None:
        issues.append("Unrequested calculation")
    return sorted(set(issues))
