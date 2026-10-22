"""Independent raw-XLSX oracle; does not import application parsing/calculation code.

Author: Imitiyaz and AI Agent
Project: RAG MVP
Layer: Verification and release tooling
"""

from __future__ import annotations

import copy
import re
import xml.etree.ElementTree as ET
from collections import Counter
from decimal import Decimal
from pathlib import Path
from typing import Any
from zipfile import ZipFile


def raw_rows(path: Path) -> list[tuple]:
    """Read the synthetic fixtures' cells directly from OOXML."""
    ns = {"s": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    rows = []
    with ZipFile(path) as z:
        sheets = ET.fromstring(z.read("xl/workbook.xml")).findall(
            "s:sheets/s:sheet", ns
        )
        for index, sheet in enumerate(sheets, 1):
            headers = {}
            for row in ET.fromstring(z.read(f"xl/worksheets/sheet{index}.xml")).findall(
                "s:sheetData/s:row", ns
            ):
                values = {}
                cells = {}
                for cell in row.findall("s:c", ns):
                    address = cell.attrib["r"]
                    column = re.sub(r"\d", "", address)
                    value = cell.find("s:v", ns)
                    text = (
                        "".join(t.text or "" for t in cell.findall(".//s:t", ns))
                        if cell.attrib.get("t") == "inlineStr"
                        else (value.text if value is not None else None)
                    )
                    if row.attrib["r"] == "1":
                        headers[column] = text
                    elif column in headers:
                        values[headers[column]] = text
                        cells[headers[column]] = address
                if row.attrib["r"] != "1":
                    rows.append(
                        (sheet.attrib["name"], int(row.attrib["r"]), values, cells)
                    )
    return rows


def validate(
    body: dict[str, Any],
    expected: list[tuple],
    *,
    source: str,
    fields: list[str],
    result: dict | None = None,
    unit: str = "",
    page: int = 1,
    page_size: int = 50,
) -> list[str]:
    """Check exact record/operand sets, source values, cells, citations and display."""
    from tools.presentation_checks import readable_findings

    findings = []
    records = body.get("records", [])
    shown = expected[(page - 1) * page_size : page * page_size]

    def key(r: dict) -> tuple:
        return (r.get("source_file"), r.get("sheet_or_page"), r.get("row_or_location"))

    expected_keys = [(source, s, row) for s, row, _, _ in expected]
    if [key(r) for r in records] != [(source, s, row) for s, row, _, _ in shown]:
        findings.append("Wrong/omitted/extra source records")
    wanted = {(source, s, row): (values, cells) for s, row, values, cells in expected}
    cites = body.get("citations", [])
    if Counter(key(c) for c in cites) != Counter(expected_keys):
        findings.append("Wrong/incomplete source citations")
    by_number = {c.get("number"): key(c) for c in cites}
    for record in records:
        identity = key(record)
        if identity not in wanted:
            continue
        values, cells = wanted[identity]
        if by_number.get(record.get("number")) != identity:
            findings.append("Wrong citation association")
        if any(
            f not in values or values[f] != v
            for f, v in record.get("values", {}).items()
        ):
            findings.append("Wrong label/value association")
        if any(
            record.get("values", {}).get(f) != values[f]
            or record.get("cell_references", {}).get(f) != cells[f]
            for f in fields
            if f in values
        ):
            findings.append("Wrong requested value/cell")
        line = next(
            (
                line
                for line in (
                    body.get("evidence_text") or body.get("answer", "")
                ).splitlines()
                if line.startswith(f"- {source} / {identity[1]} / row {identity[2]} —")
                and line.endswith(f"(Source: [{record['number']}])")
            ),
            None,
        )
        if line is None or any(
            f"{f}: {v if v is not None else 'Missing in source'}" not in line
            for f, v in record.get("values", {}).items()
        ):
            findings.append("Wrong displayed source/value association")
    calc = body.get("calculation")
    if (calc.get("result") if calc else None) != result:
        findings.append("Wrong/unrequested result")
    if result is not None and calc:
        if calc.get("unit") != unit:
            findings.append("Wrong unit")
        wanted_operands = Counter(
            (
                (source, s, row),
                tuple((f, str(Decimal(values[f]))) for f in fields if f in values),
            )
            for s, row, values, _ in expected
        )
        actual_operands = []
        for operand in calc.get("operands", []):
            identity = key(operand.get("source", {}))
            values = operand.get("values", {})
            actual_operands.append(
                (identity, tuple((f, values[f]) for f in fields if f in values))
            )
            if by_number.get(operand.get("number")) != identity:
                findings.append("Wrong operand/source association")
            if identity in wanted:
                _, cells = wanted[identity]
                if any(
                    operand.get("cell_references", {}).get(f) != cells[f]
                    for f in values
                    if f in cells
                ):
                    findings.append("Wrong operand cell")
        if Counter(actual_operands) != wanted_operands:
            findings.append("Missing/extra/changed operands")
        if calc.get("operation") == "sum" and any(
            f"{field} = {value}"
            not in (body.get("evidence_text") or body.get("answer", ""))
            for field, value in result.items()
        ):
            findings.append("Wrong displayed calculation")
    if body.get("coverage", {}).get("matched_records") != len(expected):
        findings.append("Wrong source coverage")
    if (
        body.get("status") != "answered"
        or body.get("coverage", {}).get("complete") is not True
    ):
        findings.append("Wrong completeness/status")
    if body.get("unresolved_citation_numbers"):
        findings.append("Unresolved citations")
    findings.extend(readable_findings(body))
    return sorted(set(findings))


def mutations(body: dict) -> dict[str, dict]:
    """Corrupt independent dimensions so a falsely green checker is detectable."""
    changed = {}

    def variant(name: str) -> dict:
        item = copy.deepcopy(body)
        changed[name] = item
        return item

    item = variant("wrong_sum")
    item["calculation"]["result"]["Revenue"] = "99999"
    variant("omitted_record")["records"].pop()
    item = variant("extra_record")
    item["records"].append(copy.deepcopy(item["records"][0]))
    variant("wrong_label")["records"][0]["values"]["Region"] = "South"
    variant("wrong_cell")["records"][0]["cell_references"]["Revenue"] = "Z99"
    variant("wrong_sheet")["citations"][0]["sheet_or_page"] = "Other"
    variant("omitted_operand")["calculation"]["operands"].pop()
    variant("wrong_operand")["calculation"]["operands"][0]["values"]["Revenue"] = "1"
    variant("wrong_operand_cell")["calculation"]["operands"][0]["cell_references"][
        "Revenue"
    ] = "B99"
    variant("false_completeness")["coverage"]["complete"] = False
    wrong = variant("wrong_display")
    if body.get("evidence_text") is not None:
        wrong["answer"] = body["answer"].replace("97,000", "97,001")
        for item in wrong["answer_items"]:
            item["text"] = item["text"].replace("97,000", "97,001")
    else:
        wrong["answer"] = body["answer"].replace("Revenue: 45000", "Revenue: 4500")
    return changed
