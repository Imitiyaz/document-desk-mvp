"""Independent contributor expectations from the reviewed physical source cells.

Author: Imitiyaz and AI Agent
Project: RAG MVP
Layer: Verification and release tooling
"""

from __future__ import annotations

import copy
from decimal import Decimal
from typing import Any

from tools.grouped_oracle import validate_grouped
from tools.sum_scope_oracle import ROWS


def validate_contributions(body: dict[str, Any]) -> list[str]:
    """Check all contributors, missing values, absent entities and original cells."""
    findings = validate_grouped(body)
    for group in body.get("grouped_results", []):
        scope, label = group["scope"], group["label"]
        population = [
            (i, r)
            for i, r in enumerate(ROWS, 1)
            if scope == "Whole file" or scope == r[0]
        ]
        names = group["entities"] or list(dict.fromkeys(r[2] for _, r in population))
        values = group.get("contributions", [])
        if [v.get("entity") for v in values] != names:
            findings.append("Missing/extra/reordered region contributions")
        for contribution in values:
            entity = contribution.get("entity")
            if entity not in names:
                continue
            facts = [(i, r) for i, r in population if r[2] == entity]
            numbers = [i for i, _ in facts]
            numeric = [(i, r) for i, r in facts if r[3] is not None]
            missing = [
                {"number": i, "field": "Q3 Revenue", "cell": f"B{r[1]}"}
                for i, r in facts
                if r[3] is None
            ]
            expected_status = (
                "no_evidence" if not facts else "incomplete" if missing else "answered"
            )
            if (
                contribution.get("record_numbers") != numbers
                or contribution.get("missing_cells") != missing
                or contribution.get("status") != expected_status
            ):
                findings.append("Contributor membership/missing/absent status is wrong")
            calc = contribution.get("calculation")
            if not numeric:
                if calc is not None:
                    findings.append("Missing or absent region was assigned a number")
            elif not calc:
                findings.append("Required contributor calculation missing")
            else:
                amount = sum((Decimal(str(r[3])) for _, r in numeric), Decimal(0))
                operands = [
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
                    for i, r in numeric
                ]
                if calc.get("result") != {"Q3 Revenue": str(amount)} or calc.get(
                    "partial"
                ) != bool(missing):
                    findings.append("Wrong contributor amount or completeness")
                if calc.get("operands") != operands:
                    findings.append(
                        "Wrong/omitted contributor operands, cells or citations"
                    )
                exclusions = [
                    {
                        **m,
                        "reason": "missing_value",
                        "source": {
                            "source_file": "sample_sales_extended.xlsx",
                            "sheet_or_page": r[0],
                            "row_or_location": r[1],
                        },
                    }
                    for m, (_, r) in zip(
                        missing, [(i, r) for i, r in facts if r[3] is None], strict=True
                    )
                ]
                if calc.get("excluded_cells") != exclusions:
                    findings.append("Contributor exclusions are wrong")
            prefix = f"{scope} · {label} · {entity} — "
            lines = [
                line
                for line in group.get("answer", "").splitlines()
                if line.startswith(prefix)
            ]
            if not lines:
                findings.append("Readable contributor details missing")
            else:
                line = lines[0]
                if (
                    numeric
                    and f"{sum((Decimal(str(r[3])) for _, r in numeric), Decimal(0)):,}"
                    not in line
                ):
                    findings.append("Readable contributor value is wrong")
                if (
                    not numeric
                    and ("no matching" if not facts else "missing in source")
                    not in line
                ):
                    findings.append("Readable missing/absent region distinction lost")
                if any(f"[{i}]" not in line for i in numbers[:3]):
                    findings.append("Readable contributor citation association lost")
    return sorted(set(findings))


def mutations(body: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Reject plausible totals with hidden, mislabeled or invented contributors."""
    result = {}
    for fault in (
        "omitted_east",
        "east_zero",
        "absent_south_zero",
        "wrong_region",
        "wrong_contributor_sum",
        "omitted_contributor_operand",
        "wrong_contributor_cell",
        "wrong_contributor_display",
        "lost_contributor_citation",
    ):
        item = copy.deepcopy(body)
        result[fault] = item
        sparse = next(
            g
            for g in item["grouped_results"]
            if g["scope"] == "Sparse Data" and g["label"] == "East + West"
        )
        overall = item["grouped_results"][0]
        if fault == "omitted_east":
            sparse["contributions"].pop(0)
        elif fault == "east_zero":
            sparse["contributions"][0]["calculation"] = {"result": {"Q3 Revenue": "0"}}
        elif fault == "absent_south_zero":
            group = next(
                g
                for g in item["grouped_results"]
                if g["scope"] == "Sparse Data" and g["label"] == "North + South"
            )
            group["contributions"][1]["calculation"] = {"result": {"Q3 Revenue": "0"}}
        elif fault == "wrong_region":
            sparse["contributions"][1]["entity"] = "East"
        elif fault == "wrong_contributor_sum":
            overall["contributions"][0]["calculation"]["result"][
                "Q3 Revenue"
            ] = "174000"
        elif fault == "omitted_contributor_operand":
            sparse["contributions"][1]["calculation"]["operands"].pop()
        elif fault == "wrong_contributor_cell":
            sparse["contributions"][1]["calculation"]["operands"][0]["cell_references"][
                "Q3 Revenue"
            ] = "B4"
        elif fault == "wrong_contributor_display":
            overall["answer"] = overall["answer"].replace("175,000", "174,000")
        else:
            overall["contributions"][0]["record_numbers"].pop()

    return result
