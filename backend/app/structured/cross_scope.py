# SPDX-License-Identifier: AGPL-3.0-only
"""Explicit compatibility checks for unions and one-key, two-period comparisons.

Author: Imitiyaz and AI Agent
Project: RAG MVP
Layer: Structured
"""

from __future__ import annotations

import re
from decimal import Context, Decimal
from typing import Any

from app.api.schemas import (
    CitationResponse,
    EvidenceRecord,
    QueryRequest,
    QueryResponse,
)
from app.models.extracted import SourceMetadata, format_citation

IDENTITIES = {
    "region",
    "entity",
    "order id",
    "order",
    "customer",
    "customer id",
    "product",
    "product id",
    "id",
    "name",
    "account",
    "account id",
    "record id",
    "transaction id",
}
PERIODS = {"year", "quarter", "month", "date", "period"}
UNIT_FIELDS = {"currency", "currency code", "unit", "units", "unit of measure"}


def period_range(text: str) -> tuple[int | None, int, int] | None:
    """Recognize explicit calendar periods; fiscal/unknown periods stay unknown."""
    lowered = text.casefold()
    if re.search(r"\b(fiscal|fy\d*)\b", lowered):
        return None
    years = set(re.findall(r"\b20\d{2}\b", lowered))
    quarters = set(re.findall(r"\bq([1-4])\b", lowered))
    if len(years) > 1 or len(quarters) > 1:
        return None
    year = int(next(iter(years))) if years else None
    if quarters:
        month = (int(next(iter(quarters))) - 1) * 3 + 1
        return year, month, month + 2
    months = [
        "january",
        "february",
        "march",
        "april",
        "may",
        "june",
        "july",
        "august",
        "september",
        "october",
        "november",
        "december",
    ]
    found = {
        i
        for i, m in enumerate(months, 1)
        if re.search(r"\b(?:" + m + "|" + m[:3] + r")\b", lowered)
    }
    if len(found) == 1:
        month = next(iter(found))
        return year, month, month
    return (year, 1, 12) if years and not found else None


def measure_name(field: str) -> str:
    """Remove period/direction labels when comparing the same measure."""
    from app.structured.engine import header_name

    return " ".join(
        w
        for w in header_name(field).split()
        if not re.fullmatch(
            r"q[1-4]|20\d{2}|before|after|current|previous|prior|next|baseline", w
        )
    )


def source_unit(row: dict, unit: str) -> str | None:
    """Use declared currency/units only when the numeric format agrees."""
    from app.structured.engine import header_name

    keys = [k for k in row["values"] if header_name(k) in UNIT_FIELDS]
    declared = {
        str(row["values"][k]).strip() for k in keys if row["values"][k] is not None
    }
    if keys and (len(declared) != 1 or any(row["values"][k] is None for k in keys)):
        return None
    if not declared:
        return unit
    wanted = next(iter(declared))
    symbols = {
        "USD": "$",
        "SGD": "$",
        "AUD": "$",
        "CAD": "$",
        "EUR": "€",
        "GBP": "£",
        "JPY": "¥",
        "CNY": "¥",
    }
    return wanted if not unit or unit == wanted or symbols.get(wanted) == unit else None


def repeated_cells(rows: list[dict], fields: list[str]) -> bool:
    """Never count a shared numeric merge anchor once per label row."""
    seen = set()
    for row in rows:
        for field in fields:
            cell = row.get("cell_origins", {}).get(field)
            if field not in row["values"] or not cell:
                continue
            # Identity is the physical cell, not equality of the amount stored there.
            key = (row["sheet_or_page"], cell)
            if key in seen:
                return True
            seen.add(key)
    return False


def union_issue(
    rows: list[dict], fields: list[str], request: QueryRequest
) -> str | None:
    """Require an unambiguous population; equal numeric values never deduplicate."""
    from app.structured.engine import header_name

    scopes = {r["sheet_or_page"] for r in rows}
    if len(scopes) < 2:
        return None
    roles = {
        bool(re.search(r"\b(summary|overview|total|totals|annual)\b", s, re.I))
        for s in scopes
    }
    if len(roles) > 1:
        return "Choose summary or detail sources; combining both could double-count the same business population."
    if any(any(f not in row["values"] for f in fields) for row in rows):
        return "Selected sources do not share the same measures. Specify the intended measures and periods."
    # Explicit physical-record counting resolves overlap; it does not fill missing measures.
    if request.aggregation_basis == "all_selected_records":
        return None
    keys = [k for k in rows[0]["values"] if header_name(k) in IDENTITIES]
    seen: dict[tuple, list[tuple[str, Any]]] = {}
    for row in rows:
        if not keys or any(row["values"].get(k) is None for k in keys):
            return "Record keys are missing. Choose a source, or confirm Use source records to count each selected physical record separately."
        key = tuple(str(row["values"][k]) for k in keys)
        periods = [
            str(v)
            for k, v in row["values"].items()
            if header_name(k) in PERIODS and v is not None
        ]
        period = period_range(
            row.get("_period", row["sheet_or_page"]) + " " + " ".join(periods)
        )
        for scope, previous in seen.get(key, []):
            overlap = (
                period is None
                or previous is None
                or (
                    (
                        period[0] is None
                        or previous[0] is None
                        or period[0] == previous[0]
                    )
                    and max(period[1], previous[1]) <= min(period[2], previous[2])
                )
            )
            if scope != row["sheet_or_page"] and overlap:
                return "The same keys have overlapping or unknown periods. Choose sources, or confirm Use source records if every physical record should be counted separately."
        seen.setdefault(key, []).append((row["sheet_or_page"], period))
    return None


def render(source: str, rows: list[dict], fields: list[str]) -> QueryResponse:
    """Render original physical records; comparisons never fabricate a merged row."""
    from app.structured.engine import header_name

    records = []
    citations = []
    lines = []
    for i, row in enumerate(rows, 1):
        chosen = [
            k
            for k in row["values"]
            if header_name(k) in IDENTITIES | PERIODS | UNIT_FIELDS
        ] + [f for f in fields if f in row["values"]]
        chosen = list(dict.fromkeys(chosen))
        metadata = SourceMetadata(source, row["sheet_or_page"], row["row_or_location"])
        values = {
            f: None if row["values"].get(f) is None else str(row["values"][f])
            for f in chosen
        }
        record = EvidenceRecord(
            number=i,
            source_file=source,
            sheet_or_page=metadata.sheet_or_page,
            row_or_location=metadata.row_or_location,
            values=values,
            cell_references={
                f: row["cell_origins"][f] for f in chosen if f in row["cell_origins"]
            },
            merged_fields=[f for f in row["merged_fields"] if f in chosen],
            cell_formats={
                f: v for f, v in row.get("cell_formats", {}).items() if f in chosen
            },
            formula_fields={
                f: v for f, v in row.get("formula_fields", {}).items() if f in chosen
            },
        )
        records.append(record)
        citations.append(
            CitationResponse(
                number=i,
                source_file=source,
                sheet_or_page=metadata.sheet_or_page,
                row_or_location=metadata.row_or_location,
                citation_text=format_citation(metadata),
            )
        )
        text = (
            "; ".join(
                f"{f}: {v if v is not None else 'Missing in source'}"
                for f, v in values.items()
            )
            .replace("[", "［")
            .replace("]", "］")
        )
        lines.append(f"- {format_citation(metadata)} — {text} (Source: [{i}])")
    return QueryResponse(
        answer="\n".join(lines),
        records=records,
        citations=citations,
        unresolved_citation_numbers=[],
        context_count=len(records),
        model=None,
        generation_latency_seconds=0,
        execution_path="structured",
        coverage={
            "method": "all_indexed_rows",
            "matched_records": len(rows),
            "returned_records": len(rows),
            "fields": fields,
            "complete": True,
        },
    )


def compare_sources(
    request: QueryRequest,
    source: str,
    rows: list[dict],
    fields: list[str],
    operation: str,
) -> QueryResponse | None:
    """One common key and exactly two ordered sources; missing competitors withhold winners."""
    from app.structured.engine import clarify, display, header_name, number

    if operation not in {"increase", "growth_percent"}:
        return None
    if len(fields) == 2 and all(
        all(f in row["values"] for f in fields) for row in rows
    ):
        return None
    scopes = list(dict.fromkeys(row["sheet_or_page"] for row in rows))
    if len(scopes) != 2 or len(fields) not in {1, 2}:
        return clarify(
            "A comparison requires two explicit periods and one common record key."
        )
    explicit = all(s.casefold() in request.question.casefold() for s in scopes)
    if explicit:
        scopes.sort(key=lambda s: request.question.casefold().find(s.casefold()))
    else:
        periods = [
            period_range(
                s
                + " "
                + " ".join(
                    f
                    for f in fields
                    if any(
                        f in row["values"] for row in rows if row["sheet_or_page"] == s
                    )
                )
            )
            for s in scopes
        ]
        if any(p is None for p in periods) or periods[0] == periods[1]:
            return clarify(
                "Specify which source/period is the baseline and which is the target."
            )
        scopes.sort(key=lambda s: period_range(s) or (0, 0, 0))
    keys = [
        k
        for k in rows[0]["values"]
        if header_name(k) in IDENTITIES and all(k in row["values"] for row in rows)
    ]
    if len(keys) != 1 or repeated_cells(rows, fields):
        return clarify(
            "Comparison keys or shared numeric cells are ambiguous; clarify the record allocation."
        )
    response = render(source, rows, fields)
    response.execution_path = "structured_comparison"
    groups: dict[str, dict[int, tuple[int, dict]]] = {}
    for i, row in enumerate(rows, 1):
        entity = row["values"].get(keys[0])
        side = scopes.index(row["sheet_or_page"])
        if entity is None or side in groups.setdefault(str(entity), {}):
            return clarify(
                "Missing/duplicate comparison keys create an ambiguous join. Choose a more specific scope."
            )
        groups[str(entity)][side] = (i, row)
    units = set()
    operands = []
    result = {}
    arithmetic = Context(prec=80)
    for entity, pair in groups.items():
        if set(pair) != {0, 1}:
            response.status = "incomplete"
            response.coverage["complete"] = False
            response.answer = (
                "Comparison withheld: a requested competitor/period is missing.\n"
                + response.answer
            )
            return response
        values = []
        for side in [0, 1]:
            i, row = pair[side]
            available = [f for f in fields if f in row["values"]]
            if len(available) != 1:
                return clarify("Choose one same measure in each comparison period.")
            field = available[0]
            parsed = number(row["values"][field])
            if parsed is None:
                response.status = "incomplete"
                response.coverage["complete"] = False
                response.answer = (
                    "Comparison withheld: a requested value is missing or nonnumeric.\n"
                    + response.answer
                )
                return response
            unit = source_unit(row, parsed[1])
            units.add(unit)
            values.append(parsed[0])
            operands.append({"number": i, "values": {field: display(parsed[0])}})
        if None in units or len(units) != 1:
            response.status = "clarification_required"
            response.answer = (
                "Comparison withheld: mixed or missing units/currencies; no conversion inferred.\n"
                + response.answer
            )
            return response
        if operation == "growth_percent" and values[0] == 0:
            response.status = "incomplete"
            response.coverage["complete"] = False
            response.answer = (
                "Percentage growth is undefined for a zero baseline.\n"
                + response.answer
            )
            return response
        value = arithmetic.subtract(values[1], values[0])
        if operation == "growth_percent":
            value = arithmetic.multiply(
                arithmetic.divide(value, values[0]), Decimal(100)
            )
        result[entity] = value
    best = (
        min
        if re.search(r"\b(lowest|smallest|least|minimum)\b", request.question, re.I)
        else max
    )(result.values())
    rendered = {
        k: (
            display(arithmetic.quantize(v, Decimal("0.01")))
            if operation == "growth_percent"
            else display(v)
        )
        for k, v in result.items()
    }
    response.calculation = {
        "operation": operation,
        "result": rendered,
        "unit": "%" if operation == "growth_percent" else next(iter(units)),
        "fields": fields,
        "operands": operands,
        "winners": [k for k, v in result.items() if v == best],
        "rounding": (
            "Percentage rounded to 2 decimal places; ranking uses unrounded values."
            if operation == "growth_percent"
            else "Exact decimal operands; no rounding"
        ),
    }
    response.answer += "\nChanges: " + "; ".join(
        f"{key} = {value}" for key, value in rendered.items()
    )
    return response


def combine_fields(
    request: QueryRequest, source: str, rows: list[dict], fields: list[str]
) -> QueryResponse | None:
    """Combine compatible period columns while preserving original physical rows."""
    from app.structured.engine import clarify

    if len(fields) < 2:
        return None
    combined = bool(
        re.search(
            r"\b(combined|combine|together|overall|both)\b", request.question, re.I
        )
    )
    layouts = any(any(f not in row["values"] for f in fields) for row in rows)
    if not combined and not layouts:
        return None
    if len({measure_name(f) for f in fields}) != 1:
        return clarify(
            "Different measures cannot be combined into one total. Request separate measures."
        )
    expanded = []
    for row in rows:
        for f in fields:
            if f in row["values"]:
                expanded.append(
                    {
                        **row,
                        "sheet_or_page": row["sheet_or_page"] + " " + f,
                        "_period": f if period_range(f) else row["sheet_or_page"],
                        "values": {
                            **{
                                k: v
                                for k, v in row["values"].items()
                                if k not in fields
                            },
                            "Measure": row["values"][f],
                        },
                    }
                )
    issue = union_issue(expanded, ["Measure"], request)
    if issue:
        return clarify(
            issue,
            available_scopes=list(dict.fromkeys(r["sheet_or_page"] for r in rows)),
        )
    response = render(source, rows, fields)
    if repeated_cells(rows, fields):
        return clarify(
            "A merged numeric cell is shared by records; clarify allocation before calculating."
        )
    from app.structured.aggregation import sum_available

    return sum_available(
        response,
        request,
        rows,
        fields,
        combined_label=(
            "Combined " + measure_name(fields[0]).title() if combined else None
        ),
    )
