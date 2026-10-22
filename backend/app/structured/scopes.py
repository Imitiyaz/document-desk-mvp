# SPDX-License-Identifier: AGPL-3.0-only
"""One source-alias contract for selection, replacement and conversation reuse.

Unavailable pages remain constraints, never permission to answer the whole file.
Author: Imitiyaz and AI Agent
"""

from __future__ import annotations

import re

from app.api.schemas import QueryRequest
from app.structured.intent import SUM_WORDS

_PAGE_NAME = re.compile(r"page_(\d+)", re.I)
_PAGE_REF = re.compile(
    r"\bpages?[\s_-]+(\d+(?:(?:\s*,\s*|\s+and\s+)(?:pages?[\s_-]+)?\d+)*)(?!\w)", re.I
)
_PAGE_RANGE = re.compile(
    r"\bpages?[\s_-]+\d+\s*(?:-|to\b|through\b|\.\.)\s*(?:pages?[\s_-]+)?\d+", re.I
)


def _syntax_problem(question: str) -> str | None:
    if re.search(
        r"\bpages?(?:[ _]+-\d+|[ _-]+\d+(?:\.\d+|[A-Za-z]\w*))", question, re.I
    ):
        return "Use positive whole page numbers, for example page 1. No other page or whole-file total was substituted."
    if re.search(
        r"(?:^|\b(?:in|on|from|within|and|instead|now)\s+)(?:the\s+)?pages?[ _-]+[A-Za-z]+",
        question,
        re.I,
    ):
        return "Use a numbered source section, for example page 1; this page wording was not resolved and no whole-file total was calculated."
    if _PAGE_RANGE.search(question):
        return "Page ranges are not supported. Name each page explicitly, for example page 1 and page 3; no range or whole-file total was calculated."
    return None


def _matches(question: str, names: list[str]) -> list[tuple[int, int, list[str]]]:
    """Keep raw spans so aliases cannot be recognized but fail replacement."""
    matches: list[tuple[int, int, list[str]]] = []
    for match in _PAGE_REF.finditer(question):
        selected = []
        for number in re.findall(r"\d+", match[1]):
            canonical = "page_" + (number.lstrip("0") or "0")
            selected.append(
                next(
                    (name for name in names if name.casefold() == canonical), canonical
                )
            )
        matches.append((match.start(), match.end(), selected))
    for name in sorted(names, key=len, reverse=True):
        if _PAGE_NAME.fullmatch(name):
            continue
        tokens = re.findall(r"[^\W_]+", name)
        if not tokens:
            continue
        pattern = (
            r"(?<!\w)"
            + r"[\W_]+".join(re.escape(token) for token in tokens)
            + r"(?!\w)"
        )
        for match in re.finditer(pattern, question, re.I):
            if not any(
                match.start() < end and match.end() > start for start, end, _ in matches
            ):
                matches.append((match.start(), match.end(), [name]))
    return sorted(matches)


def named_scopes(question: str, names: list[str]) -> list[str]:
    """Return canonical requested sections, including unavailable page IDs."""
    return list(
        dict.fromkeys(
            name for _, _, selected in _matches(question, names) for name in selected
        )
    )


def canonical_question(question: str, names: list[str]) -> str:
    for start, end, selected in reversed(_matches(question, names)):
        question = question[:start] + " and ".join(selected) + question[end:]
    return question


def scope_choice(question: str, names: list[str]) -> list[str]:
    """Accept only a source-only follow-up, preserving its acknowledged measure."""
    selected = named_scopes(question, names)
    remainder = question
    for start, end, _ in reversed(_matches(question, names)):
        remainder = remainder[:start] + " " + remainder[end:]
    remainder = re.sub(
        r"\b(?:and|instead|now|same|what about|how about|in|on|from|the|please)\b",
        " ",
        remainder,
        flags=re.I,
    )
    return selected if selected and not remainder.strip(" ?!.,\n") else []


def replace_scope(question: str, names: list[str], selected: list[str]) -> str:
    """Remove all prior alias spans before describing the selected scope."""
    for start, end, _ in reversed(_matches(question, names)):
        question = question[:start] + " " + question[end:]
    question = re.sub(
        r"\b(?:in|from) (?:the )?file\b|\b(?:whole|entire) (?:file|document|workbook)\b|\ball (?:sheets|pages)\b",
        " ",
        question,
        flags=re.I,
    )
    question = " ".join(question.strip(" ?.").split())
    question = re.sub(
        r"\b(?:(?:in|on|from|and)\s*)+$", "", question, flags=re.I
    ).strip()
    return question + " in " + " and ".join(selected)


def document_scopes(document: dict) -> list[str]:
    return list(
        dict.fromkeys(
            row["sheet_or_page"] for row in document["rows"] + document["text_blocks"]
        )
    )


def scope_problem(request: QueryRequest, document: dict) -> str | None:
    """Stop invalid/unavailable/tableless calculations before retrieval or planning."""
    if problem := _syntax_problem(request.question):
        return problem
    selected = (
        [request.sheet_or_page] if request.sheet_or_page else request.source_scopes
    )
    names = document_scopes(document)
    absent = [name for name in selected if name not in names]
    if absent:
        return (
            "Requested source sections are unavailable: "
            + ", ".join(absent)
            + ". Available sections: "
            + ", ".join(names)
            + ". No other pages were substituted."
        )
    if selected and not any(
        row["sheet_or_page"] in selected for row in document["rows"]
    ):
        headers = {field for row in document["rows"] for field in row["values"]}
        wants_sum = request.operation == "sum" or re.search(
            SUM_WORDS, request.question, re.I
        )
        if wants_sum and (
            request.fields
            or any(
                re.search(
                    r"(?<!\w)" + re.escape(field) + r"(?!\w)", request.question, re.I
                )
                for field in headers
            )
        ):
            return "The selected source sections have no extracted table records for this calculation. No values from other pages were used."
    return None


def resolve_question_scope(
    request: QueryRequest,
    document: dict,
    *,
    question: str | None = None,
    whole_document: bool = True,
) -> tuple[QueryRequest, str | None]:
    """Explicit current-question sections outrank stale refinements visibly."""
    names = document_scopes(document)
    text = request.question if question is None else question
    if _syntax_problem(text):
        return request, None
    selected = named_scopes(text, names)
    whole = whole_document and bool(
        re.search(
            r"\b(?:(?:in|from) (?:the )?file|(?:whole|entire) (?:file|document|workbook)|all (?:sheets|pages))\b",
            text,
            re.I,
        )
    )
    if not selected and not whole:
        return request, None
    previous = (
        [request.sheet_or_page] if request.sheet_or_page else request.source_scopes
    )
    notice = None
    if previous and set(previous) != set(selected):
        notice = (
            "Used the source scope named in this question: "
            + (", ".join(selected) or "whole document")
            + ". The previous source refinement was replaced."
        )
    return (
        request.model_copy(
            update={
                "question": canonical_question(request.question, names),
                "sheet_or_page": selected[0] if len(selected) == 1 else None,
                "source_scopes": selected if len(selected) != 1 else [],
            }
        ),
        notice,
    )
