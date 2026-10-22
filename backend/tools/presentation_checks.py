"""Independent display-contract checks; never import the application renderer.

Author: Imitiyaz and AI Agent
Project: RAG MVP
Layer: Verification and release tooling
"""

from __future__ import annotations

import re
from decimal import Decimal
from typing import Any

UNIT_KEYS = {"currency", "currencycode", "unit", "units", "unitofmeasure"}
LITERAL_KEYS = {
    "region",
    "entity",
    "customer",
    "product",
    "name",
    "account",
    "id",
    "orderid",
    "order",
    "accountid",
    "customerid",
    "productid",
    "recordid",
    "transactionid",
    "year",
    "quarter",
    "month",
    "date",
    "period",
}


def clean(value: object) -> str:
    """Keep source-authored square brackets visibly literal."""
    return str(value).replace("[", "［").replace("]", "］")


def literal_field(field: str) -> bool:
    """Identifiers and calendar labels are not numeric measures."""
    words = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", field).replace("_", " ").casefold()
    return re.sub(r"[^a-z]", "", words) in LITERAL_KEYS or bool(
        re.search(r"\b(id|code|identifier|reference|year)\b", words)
    )


def shown(value: str | None, field: str = "") -> str:
    """Independent exact grouping expectation; no arithmetic or rounding."""
    if value is None:
        return "Missing in source"
    if not literal_field(field) and re.fullmatch(
        r"[+-]?(?:0|[1-9]\d*)(?:\.\d+)?", value
    ):
        return ("+" if value.startswith("+") else "") + format(Decimal(value), ",f")
    return clean(value)


def label(record: dict, fields: list[str]) -> str:
    """Expected labels from independently checked records, not text elsewhere."""
    names = [
        f
        for f in record["values"]
        if f not in fields and re.sub(r"[^a-z]", "", f.casefold()) not in UNIT_KEYS
    ]
    return (
        "; ".join(
            (
                clean(record["values"][f])
                if record["values"][f] is not None
                else f"{clean(f)} not recorded"
            )
            for f in names
        )
        if names
        else f"Record {record['number']}"
    )


def readable_findings(body: dict[str, Any]) -> list[str]:
    """Verify readable values/sources and exact plain-text serialization.

    Legacy internal table-engine specimens have no evidence_text; API specimens
    must retain evidence_text and typed readable items, checked by HTTP tests.
    """
    if body.get("evidence_text") is None:
        return []
    findings = []
    items = body.get("answer_items", [])
    if not items:
        return ["Readable answer items missing"]
    fields = body.get("coverage", {}).get("fields", [])
    citations = {c["number"] for c in body.get("citations", [])}
    lines = []
    scope = None
    for item in items:
        numbers = item.get("citation_numbers", [])
        if len(set(numbers)) != len(numbers) or not set(numbers) <= citations:
            findings.append("Readable statement has wrong source references")
        if item.get("kind") == "record" and item.get("scope") != scope:
            scope = item.get("scope")
            lines.append("\n" + clean(scope or "Source records"))
        refs = " ".join(f"[{n}]" for n in numbers[:3])
        if len(numbers) > 3:
            refs += f" (+{len(numbers)-3} source records in evidence)"
        lines.append(
            ("- " if item.get("kind") == "record" else "")
            + item["text"]
            + (" " + refs if refs else "")
        )
    if body.get("answer") != "\n".join(lines).strip():
        findings.append("Readable answer text disagrees with displayed statements")
    records = body.get("records", [])
    if body.get("grouped_results"):
        # Each nested population has its own exact oracle; serialize/cite checks above still apply.
        return sorted(set(findings))
    calculation = body.get("calculation")
    if not calculation:
        actual = [i for i in items if i.get("kind") == "record"]
        if [i.get("record_number") for i in actual] != [r["number"] for r in records]:
            findings.append("Readable answer omits/adds/reorders a displayed record")
        for item, record in zip(actual, records, strict=False):
            units = {
                v
                for f, v in record["values"].items()
                if re.sub(r"[^a-z]", "", f.casefold()) in UNIT_KEYS and v
            }
            unit = next(iter(units)) if len(units) == 1 else ""
            values = []
            for f in fields:
                if f not in record["values"]:
                    continue
                v = record["values"][f]
                value = shown(v, f)
                if (
                    unit
                    and not literal_field(f)
                    and v is not None
                    and re.fullmatch(r"[+-]?(?:0|[1-9]\d*)(?:\.\d+)?", v)
                ):
                    value += " " + clean(unit)
                values.append(f"{clean(f)}: {value}")
            expected = label(record, fields) + " — " + "; ".join(values)
            if (
                item.get("text") != expected
                or item.get("scope") != record["sheet_or_page"]
                or item.get("citation_numbers") != [record["number"]]
            ):
                findings.append(
                    "Readable record has a wrong label/value/source association"
                )
        if any(i.get("kind") == "calculation" for i in items):
            findings.append("Readable answer invents an unrequested calculation")
    else:
        result = calculation["result"]
        operation = calculation["operation"]
        suffix = " " + clean(calculation["unit"]) if calculation.get("unit") else ""
        calc_items = [i for i in items if i.get("kind") == "calculation"]
        if len(calc_items) != len(result):
            findings.append("Readable calculated results omitted/added")
        if operation == "sum":
            operands = calculation.get("operands", [])
            exclusions = calculation.get("excluded_cells", [])
            missing = body.get("coverage", {}).get("missing_cells", [])
            if bool(missing) != bool(calculation.get("partial", False)):
                findings.append(
                    "Subtotal completeness disagrees with missing source cells"
                )
            if {
                (x.get("number"), x.get("field"), x.get("cell")) for x in exclusions
            } != {
                (x.get("number"), x.get("field"), x.get("cell")) for x in missing
            } or len(
                exclusions
            ) != len(
                missing
            ):
                findings.append("Missing/extra/wrong subtotal exclusions")
            pairs = [(o["number"], f) for o in operands for f in o["values"]]
            if len(pairs) != len(set(pairs)) or set(pairs) & {
                (x["number"], x["field"]) for x in exclusions
            }:
                findings.append(
                    "A source cell was counted twice or a missing cell was imputed"
                )
            if calculation.get("partial") and (
                body.get("status") != "incomplete"
                or body.get("coverage", {}).get("complete") is not False
            ):
                findings.append("Partial subtotal presented as a complete answer")
            references_by_number = {c["number"]: c for c in body.get("citations", [])}
            for cell in exclusions:
                source = cell.get("source", {})
                reference = references_by_number.get(cell["number"], {})
                if cell.get("reason") not in {
                    "missing_value",
                    "formula_cache_missing",
                } or any(
                    source.get(k) != reference.get(k)
                    for k in ["source_file", "sheet_or_page", "row_or_location"]
                ):
                    findings.append("Subtotal exclusion has a wrong reason/source")
            for field, value in result.items():
                selected = [
                    Decimal(v)
                    for o in operands
                    for f, v in o["values"].items()
                    if f == field or field not in calculation["fields"]
                ]
                from decimal import localcontext

                with localcontext() as context:
                    context.prec = 80
                    if not selected or sum(selected, Decimal(0)) != Decimal(value):
                        findings.append(
                            "Subtotal/total is inconsistent with contributing operands"
                        )
        by_number = {str(r["number"]): r for r in records}
        for item, (field, value) in zip(calc_items, result.items(), strict=False):
            if operation in {"sum", "minimum", "maximum"}:
                prefix = {"sum": "Total", "minimum": "Minimum", "maximum": "Maximum"}[
                    operation
                ]
                if operation == "sum" and calculation.get("partial"):
                    prefix = "Available-value subtotal"
                expected = f"{prefix} {clean(field)}: {shown(value)}{suffix}."
                numbers = [
                    o["number"]
                    for o in calculation.get("operands", [])
                    if (
                        operation == "sum"
                        and (field not in calculation["fields"] or field in o["values"])
                    )
                    or (
                        operation != "sum"
                        and Decimal(o["values"][field]) == Decimal(value)
                    )
                ]
                if item.get("citation_numbers") != numbers:
                    findings.append(
                        "Readable result has wrong operand/winner references"
                    )
            else:
                who = (
                    label(by_number[field], calculation["fields"])
                    if len(calculation["fields"]) == 2 and field in by_number
                    else clean(field)
                )
                measure = (
                    "percentage growth" if operation == "growth_percent" else "increase"
                )
                expected = f"{who} — {measure}: {shown(value)}{suffix}."
            if item.get("text") != expected:
                findings.append("Readable calculated value/source association is wrong")
    return sorted(set(findings))
