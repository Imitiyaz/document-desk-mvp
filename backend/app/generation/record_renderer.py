# SPDX-License-Identifier: AGPL-3.0-only
"""Render selected context records without trusting model-written values or order.

Author: Imitiyaz and AI Agent
Project: RAG MVP
Layer: Generation
"""

from __future__ import annotations

import json
import re
from typing import Any

from app.core.exceptions import InvalidRecordSelectionError
from app.generation.models import GeneratedAnswer
from app.models.extracted import format_citation


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON key")
        result[key] = value
    return result


def _natural_key(value: str | int) -> tuple[tuple[int, int | str], ...]:
    """Numeric runs sort numerically, including PDF table rows and row fragments."""
    return tuple(
        (0, int(part)) if part.isdigit() else (1, part.casefold())
        for part in re.split(r"(\d+)", str(value))
        if part
    )


def render_records(answer: GeneratedAnswer) -> str:
    """Validate selection, then copy source text and sort by trusted source location.

    This validates reference existence, not query relevance or completeness.
    Across files/sheets the policy is natural label order, not workbook tab order.
    Empty selection means a refusal, not proof that the source contains no answer.
    """
    try:
        payload = json.loads(answer.raw_text, object_pairs_hook=_unique_object)
        if not isinstance(payload, dict) or set(payload) != {"record_citations"}:
            raise ValueError("Expected only record_citations")
        numbers = payload["record_citations"]
        if not isinstance(numbers, list):
            raise ValueError("Expected a list")
        if any(type(n) is not int for n in numbers):
            raise ValueError("References must be integers")
        if len(set(numbers)) != len(numbers):
            raise ValueError("Repeated references")
        if any(n not in answer.prompt.citation_map for n in numbers):
            raise ValueError("Unknown reference")
        # Numbering is defined by build_prompt, not by the retrieval backend's rank.
        records = []
        for number in numbers:
            result = answer.prompt.context_used[number - 1]
            if result.metadata != answer.prompt.citation_map[number]:
                raise ValueError("Inconsistent citation map")
            records.append((number, result))
    except (ValueError, TypeError, IndexError, KeyError) as exc:
        raise InvalidRecordSelectionError(
            "Invalid structured record selection"
        ) from exc

    if not records:
        return (
            "I don't have enough information in the provided documents to answer that."
        )
    records.sort(
        key=lambda item: (
            _natural_key(item[1].metadata.source_file),
            _natural_key(item[1].metadata.sheet_or_page),
            _natural_key(item[1].metadata.row_or_location),
            item[0],
        )
    )
    lines = []
    for number, result in records:
        # Literal source brackets must not become model citation markers. Copy all
        # fields: no model-written field/value pairing is used to render a record.
        text = result.text.replace("[", "［").replace("]", "］")
        location = (
            format_citation(result.metadata).replace("[", "［").replace("]", "］")
        )
        lines.append(f"- {text} ({location}; Source: [{number}])")
    return "\n".join(lines)
