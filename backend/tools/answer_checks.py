"""Conservative fixture checks, alongside human review of saved answer bodies.

These checks are deliberately stricter than finding a correct total substring.
They are not a general-purpose claim entailment validator.

Author: Imitiyaz and AI Agent
Project: RAG MVP
Layer: Verification and release tooling
"""

from __future__ import annotations

import re
from typing import Any


def check_fixture_answer(case: str, body: dict[str, Any]) -> list[str]:
    """Return review findings for one of the four Stage 10 regression questions."""
    from tools.presentation_checks import readable_findings

    text = re.sub(
        r"(?<=\d),(?=\d)", "", str(body.get("evidence_text") or body.get("answer", ""))
    )
    citations = body.get("citations", [])
    findings: list[str] = readable_findings(body)
    if not citations:
        findings.append("No supporting citations.")
    if body.get("unresolved_citation_numbers"):
        findings.append("Unresolved citation markers.")
    if case == "total":
        offsets = []
        for entity, value, row in [
            ("North", 45000, 2),
            ("South", 38000, 3),
            ("East", 41000, 4),
        ]:
            matches = re.finditer(
                rf"\b{entity}\b(?P<segment>(?:(?!\b(?:North|South|East)\b).){{0,180}})",
                text,
                re.IGNORECASE | re.DOTALL,
            )
            # Ignore introductory name lists. Inspect the first occurrence with
            # a standalone numeric value, retaining wrong-pairing failures.
            match = next(
                (
                    m
                    for m in matches
                    if re.search(r"(?<!\w)\d+(?!\w)", m.group("segment"))
                ),
                None,
            )
            segment = match.group("segment") if match else ""
            first_number = re.search(r"(?<!\w)\d+(?!\w)", segment)
            markers = {int(n) for n in re.findall(r"\[(\d+)\]", segment)}
            if not first_number or int(first_number.group()) != value:
                findings.append(f"{entity} is not explicitly paired with {value}.")
            if not any(
                c.get("number") in markers
                and c.get("sheet_or_page") == "Q3 Sales"
                and c.get("row_or_location") == row
                for c in citations
            ):
                findings.append(f"{entity}'s labelled value lacks its Q3 row citation.")
            if match:
                offsets.append(match.start())
        if len(offsets) != 3 or offsets != sorted(offsets):
            findings.append(
                "Entities are not presented in requested North/South/East order."
            )
        if not re.search(r"(?<!\d)124000(?!\d)", text):
            findings.append("Expected total 124000 is missing.")
    elif case == "merged":
        positions = [text.find(v) for v in ("45000", "47000")]
        if min(positions) < 0 or positions[0] >= positions[1]:
            findings.append(
                "Expected distinct values 45000 then 47000 in source-row order."
            )
        locations = {
            (c.get("sheet_or_page"), c.get("row_or_location")) for c in citations
        }
        if not {("Merged Region", 2), ("Merged Region", 3)} <= locations:
            findings.append("Both Merged Region row citations are required.")
    elif case == "wide":
        if "2027-01-15" not in text:
            findings.append("Expected renewal date 2027-01-15 is missing.")
        if not any(
            c.get("sheet_or_page") == "Wide Row"
            and (
                c.get("row_or_location") == 2
                or str(c.get("row_or_location", "")).startswith("2_part")
            )
            for c in citations
        ):
            findings.append("Expected original Wide Row row 2 fragment citation.")
    elif case == "comparison":
        if not re.search(r"\bNorth\b", text) or not re.search(
            r"(?<!\d)7000(?!\d)", text
        ):
            findings.append("Expected North and increase 7000.")
        north_supported = any(
            c.get("sheet_or_page") == "Q3 Sales" and c.get("row_or_location") == 2
            for c in citations
        )
        if not north_supported or any(
            c.get("sheet_or_page") != "Q3 Sales"
            or c.get("row_or_location") not in {2, 3, 4}
            for c in citations
        ):
            findings.append(
                "Comparison must cite the numeric North Q3 Sales row, not a comment-only row."
            )
    else:
        raise ValueError(f"Unknown fixture check: {case}")
    return findings
