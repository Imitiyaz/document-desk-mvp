# SPDX-License-Identifier: AGPL-3.0-only
"""Calculate available-value sums without inventing missing operands.

Missing source values produce explicit exclusions and an incomplete subtotal.
Invalid numbers, incompatible units and ambiguous shared merge anchors block
calculation instead of being silently skipped. Display pagination never selects
the population used for arithmetic.

Author: Imitiyaz and AI Agent
Project: RAG MVP
Layer: Structured
"""

from __future__ import annotations

from decimal import Context, Decimal
from typing import Any

from app.api.schemas import QueryRequest, QueryResponse
from app.structured.cross_scope import repeated_cells, source_unit


def sum_available(
    response: QueryResponse,
    request: QueryRequest,
    rows: list[dict],
    fields: list[str],
    *,
    combined_label: str | None = None,
) -> QueryResponse:
    """Attach an exact SUM and source-linked exclusions to an existing response.


    Args:
        response: Evidence/citation response to enrich; the object is mutated.
        request: Includes the user's selected physical-record counting basis.
        rows: Complete accepted population, not a display page or top-k subset.
        fields: Requested measure columns.
        combined_label: Optional label for a compatible combined measure.

    Returns:
        The same response with operands/result, or an explicit calculation refusal.

    Only missing cells are excluded. Invalid values, mixed units, shared numeric merge
    anchors and additive percentage ambiguity remain reasons to withhold a result.
    """
    from app.structured.engine import display, number

    # A local Decimal context avoids ambient precision changes and binary-float arithmetic.
    arithmetic = Context(prec=80)
    totals: dict[str, Decimal] = {}
    operands: list[dict[str, Any]] = []
    exclusions: list[dict[str, Any]] = []
    units = set()
    for index, row in enumerate(rows, 1):
        values = {}
        for field in fields:
            if field not in row["values"]:
                continue
            value = row["values"][field]
            # Missing is unknown, not zero; retain the excluded original cell for the subtotal warning.
            if value is None:
                exclusions.append(
                    {
                        "number": index,
                        "field": field,
                        "cell": row.get("cell_origins", {}).get(field),
                        "reason": (
                            "formula_cache_missing"
                            if row.get("formula_fields", {}).get(field)
                            == "cache_missing"
                            else "missing_value"
                        ),
                        "source": {
                            "source_file": response.records[index - 1].source_file,
                            "sheet_or_page": row["sheet_or_page"],
                            "row_or_location": row["row_or_location"],
                        },
                    }
                )
                continue
            parsed = number(value)
            if parsed is None:
                response.status = "clarification_required"
                response.answer = (
                    "Calculation withheld: a present value is not a supported numeric format; it was not silently excluded.\n"
                    + response.answer
                )
                return response
            units.add(source_unit(row, parsed[1]))
            values[field] = display(parsed[0])
            totals[field] = arithmetic.add(totals.get(field, Decimal(0)), parsed[0])
        if values:
            operands.append({"number": index, "values": values})
    missing = [{k: e[k] for k in ("number", "field", "cell")} for e in exclusions]
    response.coverage.update(missing_cells=missing, complete=not missing)
    if not operands:
        response.status = "incomplete"
        response.coverage["calculation_complete"] = False
        response.answer = (
            "No numeric values are available for the requested SUM; no zero or subtotal was invented.\n"
            + response.answer
        )
        return response
    if None in units or len(units) != 1:
        response.status = "clarification_required"
        response.answer = (
            "Calculation withheld: contributing units/currencies are mixed, missing or inconsistent. No conversion was inferred.\n"
            + response.answer
        )
        return response
    # A numeric merge anchor shared by label rows needs an allocation decision, not duplicate counting.
    if repeated_cells(rows, fields):
        response.status = "clarification_required"
        response.answer = (
            "Calculation withheld: a numeric merge anchor is shared by multiple rows; clarify allocation.\n"
            + response.answer
        )
        return response
    if units == {"%"} and sum(len(o["values"]) for o in operands) > 1:
        response.status = "clarification_required"
        response.answer = (
            "Calculation withheld: percentages/rates are not automatically additive; clarify the business rule and weights.\n"
            + response.answer
        )
        return response
    result = (
        {combined_label: display(sum_exact(list(totals.values())))}
        if combined_label
        else {f: display(v) for f, v in totals.items()}
    )
    # The number can be exact for available operands while the requested total remains incomplete.
    partial = bool(exclusions)
    response.status = "incomplete" if partial else "answered"
    response.coverage.update(
        calculation_complete=not partial,
        calculation_included_records=len(operands),
        calculation_excluded_cells=len(exclusions),
    )
    response.calculation = {
        "operation": "sum",
        "fields": fields,
        "unit": next(iter(units)),
        "rounding": "Exact decimal operands; no rounding",
        "result": result,
        "operands": operands,
        "partial": partial,
        "excluded_cells": exclusions,
        "matched_records": len(rows),
        "included_records": len(operands),
        "population_basis": request.aggregation_basis,
    }
    response.answer += (
        "\n"
        + ("Subtotals: " if partial else "Totals: ")
        + "; ".join(f"{f} = {v}" for f, v in result.items())
    )
    if partial:
        response.warnings.append(
            f"Available-value subtotal: {len(operands)} of {len(rows)} source records contribute; {len(exclusions)} requested source cells are missing and excluded. Missing values were not replaced with zero."
        )
    return response


def sum_exact(values: list[Decimal]) -> Decimal:
    """Combine already validated period totals without the ambient Decimal context."""
    arithmetic = Context(prec=80)
    result = Decimal(0)
    for value in values:
        result = arithmetic.add(result, value)
    return result
