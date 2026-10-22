# SPDX-License-Identifier: AGPL-3.0-only
"""Compose readable table answers from verified records and computed results.

No retrieval, model generation, calculation or source selection happens here.
The complete records/calculation contract remains the evidence authority.

Author: Imitiyaz and AI Agent
Project: RAG MVP
Layer: Generation
"""

from __future__ import annotations

import re
from decimal import Decimal
from typing import Any, cast

from app.api.schemas import AnswerItem, EvidenceRecord, QueryRequest, QueryResponse
from app.structured.cross_scope import IDENTITIES, PERIODS, UNIT_FIELDS
from app.structured.engine import header_name


def safe_text(value: object) -> str:
    """Prevent source-authored bracket text from impersonating citation markers."""
    return str(value).replace("[", "［").replace("]", "］")


def readable_value(value: str | None, *, literal: bool = False) -> str:
    """Group plain numbers without rounding; retain lexical IDs/dates/units."""
    if value is None:
        return "Missing in source"
    if not literal and re.fullmatch(r"[+-]?(?:0|[1-9]\d*)(?:\.\d+)?", value):
        rendered = format(Decimal(value), ",f")
        return ("+" if value.startswith("+") else "") + rendered
    return safe_text(value)


def record_label(record: EvidenceRecord, fields: list[str]) -> str:
    """Keep identity labels attached, including explicitly missing labels."""
    labels = [
        f
        for f in record.values
        if f not in fields and header_name(f) not in UNIT_FIELDS
    ]
    if not labels:
        return "Record " + str(record.number)
    label = "; ".join(
        (
            safe_text(record.values[f])
            if record.values[f] is not None
            else f"{safe_text(f)} not recorded"
        )
        for f in labels
    )
    return label


def record_statement(record: EvidenceRecord, fields: list[str]) -> str:
    """Render each requested field with its original label and saved unit."""
    units = {v for f, v in record.values.items() if header_name(f) in UNIT_FIELDS and v}
    unit = next(iter(units)) if len(units) == 1 else ""
    values = []
    for field in fields:
        if field not in record.values:
            continue
        value = record.values[field]
        literal = header_name(field) in IDENTITIES | PERIODS or bool(
            re.search(r"\b(id|code|identifier|reference|year)\b", header_name(field))
        )
        text = readable_value(value, literal=literal)
        if (
            unit
            and not literal
            and value is not None
            and re.fullmatch(r"[+-]?(?:0|[1-9]\d*)(?:\.\d+)?", value)
        ):
            text += " " + safe_text(unit)
        values.append(f"{safe_text(field)}: {text}")
    return record_label(record, fields) + " — " + "; ".join(values)


def answer_text(items: list[AnswerItem]) -> str:
    """Plain-text API answer; full source sets remain in the typed item/evidence."""
    lines = []
    previous_scope = None
    for item in items:
        if item.kind == "record" and item.scope != previous_scope:
            lines.append("\n" + safe_text(item.scope or "Source records"))
            previous_scope = item.scope
        markers = " ".join(f"[{n}]" for n in item.citation_numbers[:3])
        if len(item.citation_numbers) > 3:
            markers += f" (+{len(item.citation_numbers)-3} source records in evidence)"
        prefix = "- " if item.kind == "record" else ""
        lines.append(prefix + item.text + (" " + markers if markers else ""))
    return "\n".join(lines).strip()


def calculation_items(
    response: QueryResponse, request: QueryRequest, records: list[EvidenceRecord]
) -> list[AnswerItem]:
    """Explain validated results and winners; never recompute source arithmetic."""
    calculation = cast(dict[str, Any], response.calculation)
    operation = calculation["operation"]
    result = cast(dict[str, str], calculation["result"])
    fields = cast(list[str], calculation["fields"])
    unit = str(calculation.get("unit", ""))
    by_number = {str(r.number): r for r in records}
    operands = cast(list[dict[str, Any]], calculation.get("operands", []))
    all_numbers = [int(o["number"]) for o in operands]
    suffix = " " + safe_text(unit) if unit else ""
    items = []
    if operation in {"sum", "minimum", "maximum"}:
        for field, value in result.items():
            numbers = (
                [int(o["number"]) for o in operands if field in o["values"]]
                if field in fields
                else all_numbers
            )
            if operation in {"minimum", "maximum"}:
                numbers = [
                    int(o["number"])
                    for o in operands
                    if Decimal(o["values"][field]) == Decimal(value)
                ]
            title = {"sum": "Total", "minimum": "Minimum", "maximum": "Maximum"}[
                operation
            ]
            if operation == "sum" and calculation.get("partial"):
                title = "Available-value subtotal"
            text = f"{title} {safe_text(field)}: {readable_value(value)}{suffix}."
            items.append(
                AnswerItem(kind="calculation", text=text, citation_numbers=numbers)
            )
            if operation != "sum":
                names = [record_label(by_number[str(n)], fields) for n in numbers]
                items.append(
                    AnswerItem(
                        kind="paragraph",
                        text="Recorded by " + ", ".join(names) + ".",
                        citation_numbers=numbers,
                    )
                )
    else:
        # Winners are selected from the already-computed results, not raw inputs.
        smallest = bool(
            re.search(r"\b(smallest|lowest|least|minimum)\b", request.question, re.I)
        )
        best = (min if smallest else max)(Decimal(v) for v in result.values())
        winners = [key for key, value in result.items() if Decimal(value) == best]
        mapping = {}
        for key in result:
            if key in by_number and len(fields) == 2:
                record = by_number[key]
                label, numbers = record_label(record, fields), [record.number]
            else:
                label = safe_text(key)
                numbers = [r.number for r in records if key in r.values.values()]
            mapping[key] = (label, numbers)
        labels = [mapping[key][0] for key in winners]
        direction = "Smallest" if smallest else "Largest"
        measure = "percentage growth" if operation == "growth_percent" else "increase"
        winner_text = ", ".join(labels) + (" (tie)" if len(labels) > 1 else "")
        items.append(
            AnswerItem(
                kind="paragraph",
                text=f"{direction} {measure}: {winner_text}.",
                citation_numbers=list(
                    dict.fromkeys(n for key in winners for n in mapping[key][1])
                ),
            )
        )
        for key, value in result.items():
            label, numbers = mapping[key]
            items.append(
                AnswerItem(
                    kind="calculation",
                    text=f"{label} — {measure}: {readable_value(value)}{suffix}.",
                    citation_numbers=numbers,
                )
            )
    if calculation.get("partial"):
        excluded = cast(list[dict[str, Any]], calculation.get("excluded_cells", []))
        items.append(
            AnswerItem(
                kind="notice",
                text=f"Included source records: {len(operands)} of {len(records)}. Missing source cells excluded: {len(excluded)}. This is a subtotal, not a complete total; missing values were not replaced with zero.",
            )
        )
        for cell in excluded:
            record = by_number[str(cell["number"])]
            reason = (
                "formula cache missing"
                if cell["reason"] == "formula_cache_missing"
                else "missing in source"
            )
            items.append(
                AnswerItem(
                    kind="notice",
                    text=f"Excluded {safe_text(record.sheet_or_page)} / {safe_text(cell.get('cell') or record.row_or_location)} — {safe_text(cell['field'])}: {reason}.",
                    citation_numbers=[record.number],
                )
            )
    else:
        items.append(
            AnswerItem(
                kind="notice",
                text=f"Based on all {len(operands)} matching source records. The calculation evidence contains every operand.",
            )
        )
    if calculation.get("population_basis") == "all_selected_records":
        items.append(
            AnswerItem(
                kind="notice",
                text="Counting every selected physical source record, as confirmed; repeated values on different sheets remain separate records.",
            )
        )
    return items


def present_answer(
    response: QueryResponse, request: QueryRequest, records: list[EvidenceRecord]
) -> None:
    """Replace the source dump with a readable answer after evidence pagination."""
    if not response.execution_path.startswith("structured") or not records:
        return
    response.evidence_text = response.answer
    fields = cast(list[str], response.coverage.get("fields", []))
    if not fields:
        return
    if response.grouped_results:
        return
    if response.calculation:
        items = calculation_items(response, request, records)
    else:
        items = []
        # Keep refusal/incompleteness explanations visible above any breakdown.
        notices = [
            line
            for line in response.answer.splitlines()
            if line and not line.startswith("- ")
        ]
        items.extend(AnswerItem(kind="notice", text=line) for line in notices)
        if len(records) > 1:
            labels = [record_label(r, fields) for r in records]
            subject = (
                labels[0]
                if len(set(labels)) == 1 and not labels[0].startswith("Record ")
                else None
            )
            metric = " and ".join(safe_text(f) for f in fields)
            count, scopes = len(records), len({r.sheet_or_page for r in records})
            text = (
                f"{subject} has {count} recorded {metric} values"
                if subject
                else f"I found {count} {metric} records"
            )
            if scopes > 1:
                text += f" across {scopes} source sections"
            items.append(AnswerItem(kind="paragraph", text=text + "."))
            if subject:
                items.append(
                    AnswerItem(
                        kind="notice",
                        text="These are separate source records; no single value was selected.",
                    )
                )
        if response.status == "incomplete" and not notices:
            items.append(
                AnswerItem(
                    kind="notice",
                    text="Some requested values are missing in the source. A complete figure is not available.",
                )
            )
        if any(
            v is None
            for r in records
            for f, v in r.values.items()
            if f not in fields and header_name(f) not in UNIT_FIELDS
        ):
            items.append(
                AnswerItem(
                    kind="notice",
                    text="Some records have no recorded label; those amounts have not been assigned to another region or entity.",
                )
            )
        if len(response.records) < len(records):
            items.append(
                AnswerItem(
                    kind="notice",
                    text=f"Showing {len(response.records)} of {len(records)} records on evidence page {response.coverage.get('page', 1)}. Other records remain available on the other evidence pages.",
                )
            )
        items.extend(
            AnswerItem(
                kind="record",
                text=record_statement(r, fields),
                citation_numbers=[r.number],
                record_number=r.number,
                scope=r.sheet_or_page,
            )
            for r in response.records
        )
    continued = [r for r in records if r.continuation_fields]
    if continued:
        items.append(
            AnswerItem(
                kind="notice",
                text="Region continuation rule applied to "
                + str(len(continued))
                + " source record(s). Original blank cells and their label anchors are retained in evidence; no missing revenue was filled.",
                citation_numbers=[r.number for r in continued],
            )
        )
    response.answer_items = items
    response.answer = answer_text(items)
