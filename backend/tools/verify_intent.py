"""Replay ordinary API requests and check deliberate response corruptions.

This module supplies test helpers; it does not install releases or modify workspaces.
Author: Imitiyaz and AI Agent
"""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

from tools.intent_oracle import findings

ROOT = Path(__file__).resolve().parents[2]


def run_cases(client: Any, note: Any) -> dict[str, dict]:
    """Exercise fresh and acknowledged chats without hidden planning parameters."""
    docs = {}
    samples: dict[str, dict] = {}
    for source in ["operations.pdf", "hours.xlsx"]:
        reply = client.post(
            "/documents",
            files={
                "file": (
                    source,
                    (ROOT / "backend/tests/fixtures/acceptance" / source).read_bytes(),
                )
            },
        )
        note(
            "upload " + source,
            reply,
            (
                []
                if reply.status_code == 201
                else ["Expected new isolated upload HTTP 201"]
            ),
            None,
        )
        reply.raise_for_status()
        docs[source] = reply.json()
    for source, steps in [
        (
            "operations.pdf",
            [
                ("What is the quantity of Apple in the file ?", "absent_product"),
                ("What Quantity is recorded for BOLT-A?", "lookup_pdf"),
                (
                    "What is the total quantity of the individual products and overall products in the file ?",
                    "clarify_counting",
                ),
                ("Use source records", "grouped_pdf"),
                ("What is the quantity of Apple in the file ?", "absent_product"),
                ("Total Quantity for BOLT-A and Apple?", "clarify_products"),
                (None, "new_chat"),
                ("What is the quantity for Apple?", "absent_product"),
                ('Quantity of "All" in the file?', "absent_all"),
                ("What Quantity is recorded for BOLT-A?", "lookup_pdf"),
            ],
        ),
        (
            "hours.xlsx",
            [
                ("What Hours are recorded for Asha totally ?", "asha"),
                ("Total hours for Zenzee?", "absent_name"),
                ("And Ben?", "ben"),
                ("And Asha?", "asha"),
                ("What is the sum of Hours?", "subtotal"),
                ("What Hours are recorded for Zenzee?", "absent_name"),
                ("Total Hours for Asha and Zenzee?", "clarify_names"),
                ("Total hours for Asha ?", "asha"),
                ("Hours for Asha excluding Ben?", "clarify_qualifier"),
                ("Total Hours for each Name and overall?", "grouped_hours"),
                ("What is the average Hours for Asha?", "clarify_qualifier"),
                (None, "new_chat"),
                ("What Hours are recorded for Asha?", "record_asha"),
                ("And Zenzee?", "absent_name"),
                ("And Ben?", "ben"),
                ("What Hours are recorded in the file?", "record_all"),
            ],
        ),
    ]:
        chat = None
        token = None
        for question, kind in [(None, "new_chat"), *steps]:
            if question is None:
                d = docs[source]
                r = client.post(
                    "/conversations",
                    json={
                        k: d[k]
                        for k in ["source_file", "document_id", "workspace_revision"]
                    },
                )
                r.raise_for_status()
                chat = r.json()["conversation_id"]
                token = None
                continue
            payload = {
                "question": question,
                "source_file": source,
                "conversation_id": chat,
                "context_token": token,
                "document_id": docs[source]["document_id"],
                "workspace_revision": docs[source]["workspace_revision"],
            }
            r = client.post("/query", json=payload)
            body = r.json()
            issues = (
                findings(kind, body, source)
                if r.status_code == 200
                else ["Expected HTTP 200"]
            )
            note(kind, r, issues, payload)
            samples.setdefault(kind, {"body": body, "source": source})
            token = body.get("context_token")
    return samples


def mutation_checks(samples: dict[str, dict]) -> dict[str, bool]:
    """Wrong totals, missing records and broad unknown answers must all fail."""
    result = {}
    for name, kind in [
        ("wrong_group_total", "grouped_pdf"),
        ("missing_product_group", "grouped_pdf"),
        ("wrong_group_source", "grouped_pdf"),
        ("missing_zero_operand", "asha"),
        ("wrong_visible_total", "asha"),
        ("missing_as_zero", "ben"),
        ("wrong_citation", "lookup_pdf"),
        ("drop_missing_exclusion", "subtotal"),
        ("unknown_becomes_all", "absent_product"),
        ("wrong_units", "asha"),
    ]:
        original = samples[kind]
        body = copy.deepcopy(original["body"])
        if name == "wrong_group_total":
            body["grouped_results"][1]["calculation"]["result"]["Quantity"] = "28"
        elif name == "missing_product_group":
            body["grouped_results"].pop()
        elif name == "wrong_group_source":
            body["grouped_results"][1]["calculation"]["operands"][0]["source"][
                "row_or_location"
            ] = "table_1_row_2"
        elif name == "missing_zero_operand":
            body["calculation"]["operands"].pop()
        elif name == "wrong_visible_total":
            body["answer"] = body["answer"].replace("15.75", "16.75")
        elif name == "missing_as_zero":
            body["records"][0]["values"]["Hours"] = "0"
        elif name == "wrong_citation":
            body["citations"][0]["row_or_location"] = "table_1_row_2"
        elif name == "drop_missing_exclusion":
            body["calculation"]["excluded_cells"].clear()
        elif name == "unknown_becomes_all":
            body["records"] = copy.deepcopy(samples["grouped_pdf"]["body"]["records"])
        elif name == "wrong_units":
            body["calculation"]["unit"] = "USD"
        result[name] = bool(findings(kind, body, original["source"]))
    return result
