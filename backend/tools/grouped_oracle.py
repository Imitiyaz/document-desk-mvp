"""Reviewed sample-workbook grouped facts; no application planner/calculator imports.

Author: Imitiyaz and AI Agent
Project: RAG MVP
Layer: Verification and release tooling
"""

from __future__ import annotations

import copy
from decimal import Decimal
from typing import Any

from tools.sum_scope_oracle import ROWS, validate_sequence_answer

EXPECTED = {
    ("Whole file", "Overall"): ("315000", None),
    ("Whole file", "East + West"): ("63000", ["East", "West"]),
    ("Whole file", "North + South"): ("252000", ["North", "South"]),
    ("Merged Region", "Overall"): ("169000", None),
    ("Merged Region", "East + West"): (None, ["East", "West"]),
    ("Merged Region", "North + South"): ("169000", ["North", "South"]),
    ("Sparse Data", "Overall"): ("146000", None),
    ("Sparse Data", "East + West"): ("63000", ["East", "West"]),
    ("Sparse Data", "North + South"): ("83000", ["North", "South"]),
}


def validate_grouped(body: dict[str, Any]) -> list[str]:
    """Compare every group to literal source cells, including all exclusions."""
    findings = validate_sequence_answer(body)
    actual = body.get("grouped_results", [])
    keys = [(g.get("scope"), g.get("label")) for g in actual]
    if len(keys) != len(set(keys)) or set(keys) != set(EXPECTED):
        findings.append("Missing/extra/flattened grouped populations")
    for group in actual:
        key = group.get("scope"), group.get("label")
        if key not in EXPECTED:
            continue
        amount, entities = EXPECTED[key]
        facts = [
            (i, r)
            for i, r in enumerate(ROWS, 1)
            if (key[0] == "Whole file" or r[0] == key[0])
            and (entities is None or r[2] in entities)
        ]
        missing_entities = [
            v for v in entities or [] if not any(r[2] == v for _, r in facts)
        ]
        numbers = [i for i, _ in facts]
        if (
            group.get("record_numbers") != numbers
            or group.get("missing_entities") != missing_entities
        ):
            findings.append("Wrong group membership or absent-entity status")
        calc = group.get("calculation")
        if amount is None:
            if calc is not None or group.get("status") != "no_evidence":
                findings.append("Absent source population was turned into a number")
            continue
        if not calc:
            findings.append("Required grouped calculation missing")
            continue
        excluded = [(i, r) for i, r in facts if r[3] is None]
        partial = bool(excluded or missing_entities)
        if (
            calc.get("result") != {"Q3 Revenue": amount}
            or calc.get("partial") != partial
        ):
            findings.append("Wrong group total or false completeness")
        if group.get("status") != ("incomplete" if partial else "answered"):
            findings.append("Wrong grouped answer status")
        expected_operands = [
            {
                "number": i,
                "values": {"Q3 Revenue": r[3]},
                "source": {
                    "source_file": "sample_sales_extended.xlsx",
                    "sheet_or_page": r[0],
                    "row_or_location": r[1],
                },
                "cell_references": {"Q3 Revenue": f"B{r[1]}"},
            }
            for i, r in facts
            if r[3] is not None
        ]
        if calc.get("operands") != expected_operands:
            findings.append(
                "Grouped operands/cells omitted, duplicated or assigned to wrong entities"
            )
        expected_excluded = [
            {
                "number": i,
                "field": "Q3 Revenue",
                "cell": f"B{r[1]}",
                "reason": "missing_value",
                "source": {
                    "source_file": "sample_sales_extended.xlsx",
                    "sheet_or_page": r[0],
                    "row_or_location": r[1],
                },
            }
            for i, r in excluded
        ]
        if calc.get("excluded_cells") != expected_excluded:
            findings.append("Wrong grouped missing-cell exclusions")
        computed = sum(
            (Decimal(o["values"]["Q3 Revenue"]) for o in calc.get("operands", [])),
            Decimal(0),
        )
        if computed != Decimal(amount):
            findings.append("Grouped arithmetic disagrees with physical operands")
        if f"{int(amount):,}" not in group.get("answer", "") or not group.get(
            "answer", ""
        ).startswith(f"{key[0]} · {key[1]}:"):
            findings.append("Readable group result disagrees with group identity/value")
    if "315,000" not in body.get(
        "answer", ""
    ) or "Region continuation rule applied" not in body.get("answer", ""):
        findings.append("Overall subtotal or continuation explanation missing")
    return sorted(set(findings))


def mutations(body: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Demonstrate that plausible but wrong grouped answers cannot pass."""
    changed = {}
    for fault in [
        "wrong_sum",
        "omitted_group",
        "wrong_membership",
        "omitted_operand",
        "wrong_cell",
        "missing_exclusion",
        "false_completeness",
        "lost_continuation",
        "wrong_anchor",
        "wrong_display",
        "invented_zero",
    ]:
        item = copy.deepcopy(body)
        changed[fault] = item
        first = item["grouped_results"][0]
        if fault == "wrong_sum":
            first["calculation"]["result"]["Q3 Revenue"] = "255000"
        elif fault == "omitted_group":
            item["grouped_results"].pop()
        elif fault == "wrong_membership":
            first["record_numbers"].pop()
        elif fault == "omitted_operand":
            first["calculation"]["operands"].pop()
        elif fault == "wrong_cell":
            first["calculation"]["operands"][0]["cell_references"]["Q3 Revenue"] = "B3"
        elif fault == "missing_exclusion":
            first["calculation"]["excluded_cells"] = []
        elif fault == "false_completeness":
            first["calculation"]["partial"] = False
        elif fault == "lost_continuation":
            item["records"][5]["continuation_fields"] = {}
        elif fault == "wrong_anchor":
            item["records"][5]["continuation_fields"]["Region"]["anchor_cell"] = "A5"
        elif fault == "wrong_display":
            first["answer"] = "Whole file · Overall: 255,000."
        else:
            item["grouped_results"][4]["calculation"] = {"result": {"Q3 Revenue": "0"}}
    return changed
