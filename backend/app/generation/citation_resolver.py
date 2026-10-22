# SPDX-License-Identifier: AGPL-3.0-only
"""Resolves the `[N]` citation markers in an LLM's answer back to the
real sources they refer to.

Implements the citation half of this project's grounding design:
Stage 7 hands the model a numbered context list and asks it to cite
which number backs each claim; this module is what turns those bare
numbers back into real, human-readable citations after the fact --
using data captured at ingestion time (`AssembledPrompt.citation_map`),
never by re-parsing or trusting the model's own text for anything beyond
which numbers it referenced.

Author: Imitiyaz and AI Agent
Project: RAG MVP
Layer: Generation
"""

from __future__ import annotations

import re

from loguru import logger

from app.generation.models import Answer, GeneratedAnswer, ResolvedCitation
from app.generation.record_renderer import render_records
from app.models.extracted import format_citation

_CITATION_MARKER_PATTERN = re.compile(r"\[(\d+)\]")


def resolve_citations(answer: GeneratedAnswer) -> Answer:
    """Extracts every `[N]` marker from `answer.raw_text`, resolves each
    one against `answer.prompt.citation_map`, and returns a structured
    `Answer`.

    Args:
        answer: A `GeneratedAnswer` from Stage 8's `LLMClient.generate()`.

    Returns:
        An `Answer` with prose unchanged, or validated source records rendered
        in source order (original context marker identities are NOT rewritten --
        see `Answer`'s docstring for why), `citations` deduplicated and
        ordered by first appearance in the text, and
        `unresolved_citation_numbers` for any `[N]` the model wrote that
        doesn't exist in the citation map -- a real, visible signal, not
        something to silently drop.
    """
    text = (
        render_records(answer)
        if answer.prompt.answer_mode == "records"
        else answer.raw_text
    )
    citation_map = answer.prompt.citation_map

    seen_numbers: set[int] = set()
    citations: list[ResolvedCitation] = []
    unresolved: list[int] = []

    for match in _CITATION_MARKER_PATTERN.finditer(text):
        number = int(match.group(1))
        if number in seen_numbers:
            continue
        seen_numbers.add(number)

        metadata = citation_map.get(number)
        if metadata is None:
            unresolved.append(number)
            logger.warning(
                "Answer cites [{}], which does not exist in the assembled prompt's "
                "citation map ({} valid number(s)) -- possible hallucinated source",
                number,
                len(citation_map),
            )
            continue

        citations.append(
            ResolvedCitation(
                number=number,
                metadata=metadata,
                citation_text=format_citation(metadata),
            )
        )

    logger.info(
        "Resolved {} citation(s), {} unresolved, from answer: {!r}",
        len(citations),
        len(unresolved),
        text,
    )

    return Answer(
        text=text,
        citations=citations,
        unresolved_citation_numbers=unresolved,
        model=answer.model,
        latency_seconds=answer.latency_seconds,
    )
