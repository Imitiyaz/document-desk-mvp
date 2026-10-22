"""Independent source-population oracle; no application planner imports.

Author: Imitiyaz and AI Agent
"""

from __future__ import annotations

import copy
import re
from decimal import Decimal
from typing import Any

FACTS = {
    "one": [
        ("page_1", "table_1_row_1", "BOLT-A", "10"),
        ("page_1", "table_1_row_2", "NUT-B", "6"),
    ],
    "three": [
        ("page_3", "table_1_row_1", "BOLT-A", "4"),
        ("page_3", "table_1_row_2", "NUT-B", "8"),
    ],
}


def page_findings(kind: str, body: dict[str, Any]) -> list[str]:
    issues = []
    if (
        not body.get("execution_path", "").startswith("structured")
        or body.get("model") is not None
    ):
        issues.append("Unexpected narrative/model path")
    if kind in {"invalid", "counting"}:
        if (
            body.get("status") != "clarification_required"
            or body.get("records")
            or body.get("citations")
            or body.get("calculation")
        ):
            issues.append(
                "Unavailable or unconfirmed scope calculated another population"
            )
        if kind == "counting" and not any(
            o.get("label") == "Use source records"
            for o in body.get("clarification_options", [])
        ):
            issues.append("Missing counting choice")
        return issues
    expected = (
        FACTS["one"]
        if kind == "one"
        else FACTS["three"] if kind == "three" else FACTS["one"] + FACTS["three"]
    )
    records = body.get("records", [])
    calc = body.get("calculation") or {}
    operands = calc.get("operands", [])
    citations = body.get("citations", [])
    if body.get("status") != "answered":
        issues.append("Wrong answered status")
    if sorted(
        (
            r["sheet_or_page"],
            r["row_or_location"],
            r["values"].get("Product"),
            r["values"].get("Quantity"),
        )
        for r in records
    ) != sorted(expected):
        issues.append("Wrong or incomplete source population")
    total = sum((Decimal(v) for *_, v in expected), Decimal("0"))
    if calc.get("result") != {"Quantity": str(total)} or calc.get("unit") != "pcs":
        issues.append("Incorrect total or unit")
    if sorted(
        (
            o.get("source", {}).get("sheet_or_page", ""),
            o.get("source", {}).get("row_or_location", ""),
            o["values"].get("Quantity"),
        )
        for o in operands
    ) != sorted((s, r, v) for s, r, _, v in expected):
        issues.append("Wrong or omitted operands")
    if sum((Decimal(o["values"]["Quantity"]) for o in operands), Decimal("0")) != total:
        issues.append("Operand arithmetic mismatch")
    if sorted((c["sheet_or_page"], c["row_or_location"]) for c in citations) != sorted(
        (s, r) for s, r, _, _ in expected
    ):
        issues.append("Wrong citation population")
    lookup = {r["number"]: (r["sheet_or_page"], r["row_or_location"]) for r in records}
    if any(
        lookup.get(c["number"]) != (c["sheet_or_page"], c["row_or_location"])
        or c["source_file"] != "operations.pdf"
        for c in citations
    ):
        issues.append("Citation associated with another source")
    scopes = {s for s, _, _, _ in expected}
    if kind != "file":
        if set(body.get("coverage", {}).get("resolved_scopes", [])) != scopes:
            issues.append("Effective scope lost")
        if set(re.findall(r"page_(\d+)", body.get("resolved_question", ""))) != {
            s.split("_")[1] for s in scopes
        }:
            issues.append("Contradictory effective question")
    if not re.search(r"\b" + str(total) + r"\s+pcs\b", body.get("answer", "")):
        issues.append("Incorrect readable answer")
    if body.get("coverage", {}).get("matched_records") != len(expected):
        issues.append("Incorrect coverage count")
    return issues


def run_page_cases(client: Any, note: Any) -> dict[str, dict]:
    doc = next(
        d
        for d in client.get("/documents").json()
        if d["source_file"] == "operations.pdf"
    )
    samples: dict[str, dict] = {}
    for steps in [
        [
            ("Total Quantity for NUT-B and BOLT-A in page 1?", "one"),
            ("Use source records", "one"),
            ("page_3", "three"),
            ("And page 1?", "one"),
            ("page 99", "invalid"),
            ("page 3", "three"),
            ("Total Quantity for NUT-B and BOLT-A in the file?", "counting"),
            ("Use source records", "file"),
            ("page_1", "one"),
        ],
        [
            ("Total Quantity for BOLT-A and NUT-B on page-3?", "three"),
            ("Total Quantity for NUT-B and BOLT-A in page_1?", "one"),
            ("Total Quantity in page 2?", "invalid"),
            ("Total Quantity in page 1.5?", "invalid"),
            ("Total Quantity in pages 1-3?", "invalid"),
            ("Total Quantity in page 99?", "invalid"),
        ],
    ]:
        c = client.post(
            "/conversations",
            json={
                k: doc[k] for k in ["source_file", "document_id", "workspace_revision"]
            },
        )
        c.raise_for_status()
        chat = c.json()["conversation_id"]
        token = None
        for question, kind in steps:
            payload = {
                "source_file": "operations.pdf",
                "question": question,
                "conversation_id": chat,
                "document_id": doc["document_id"],
                "workspace_revision": doc["workspace_revision"],
                "context_token": token,
            }
            r = client.post("/query", json=payload)
            issues = (
                page_findings(kind, r.json())
                if r.status_code == 200
                else ["Expected HTTP 200"]
            )
            note("page_" + kind, r, issues, payload)
            samples.setdefault(kind, r.json())
            token = r.json().get("context_token")
    return samples


def page_mutations(samples: dict[str, dict]) -> dict[str, bool]:
    results = {}
    for name in [
        "wrong_total",
        "wrong_page",
        "missing_operand",
        "wrong_citation",
        "lost_scope",
        "contradictory_question",
        "wrong_unit",
        "unavailable_becomes_total",
    ]:
        kind = "invalid" if name == "unavailable_becomes_total" else "one"
        b = copy.deepcopy(samples[kind])
        if name == "wrong_total":
            b["calculation"]["result"]["Quantity"] = "28"
        elif name == "wrong_page":
            b["records"][0]["sheet_or_page"] = "page_3"
        elif name == "missing_operand":
            b["calculation"]["operands"].pop()
        elif name == "wrong_citation":
            b["citations"][0]["row_or_location"] = "table_1_row_999"
        elif name == "lost_scope":
            b["coverage"]["resolved_scopes"] = []
        elif name == "contradictory_question":
            b["resolved_question"] += " in page_3"
        elif name == "wrong_unit":
            b["calculation"]["unit"] = "hours"
        else:
            b = copy.deepcopy(samples["one"])
        results[name] = bool(page_findings(kind, b))
    return results
