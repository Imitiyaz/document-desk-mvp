"""Unit tests for app.generation.citation_resolver.resolve_citations.

Author: Imitiyaz and AI Agent
Project: RAG MVP
Layer: Verification and synthetic fixtures
"""

from __future__ import annotations

from app.generation.citation_resolver import resolve_citations
from app.generation.models import AssembledPrompt, GeneratedAnswer
from app.models.extracted import SourceMetadata


def make_answer(
    raw_text: str,
    citation_map: dict[int, SourceMetadata] | None = None,
) -> GeneratedAnswer:
    prompt = AssembledPrompt(
        text="SYSTEM:...\nCONTEXT:...\nQUESTION:...\nANSWER:",
        citation_map=citation_map or {},
        context_used=[],
    )
    return GeneratedAnswer(
        raw_text=raw_text, prompt=prompt, model="test-model", latency_seconds=0.1
    )


def meta(row: int = 2) -> SourceMetadata:
    return SourceMetadata(
        source_file="sample_sales.xlsx", sheet_or_page="Q3 Sales", row_or_location=row
    )


def test_resolve_citations_extracts_a_single_marker() -> None:
    answer = make_answer(
        "The revenue was 45000. (Source: [1])", citation_map={1: meta()}
    )

    resolved = resolve_citations(answer)

    assert len(resolved.citations) == 1
    assert resolved.citations[0].number == 1
    assert resolved.citations[0].metadata == meta()


def test_resolve_citations_builds_human_readable_citation_text() -> None:
    answer = make_answer("Answer. [1]", citation_map={1: meta(row=7)})

    resolved = resolve_citations(answer)

    assert resolved.citations[0].citation_text == "sample_sales.xlsx / Q3 Sales / row 7"


def test_resolve_citations_preserves_text_verbatim() -> None:
    raw_text = "The revenue was 45,000. (Source: [1])"
    answer = make_answer(raw_text, citation_map={1: meta()})

    resolved = resolve_citations(answer)

    assert resolved.text == raw_text  # markers NOT rewritten


def test_resolve_citations_handles_multiple_distinct_markers() -> None:
    answer = make_answer(
        "North was [1] and South was [2].",
        citation_map={1: meta(row=2), 2: meta(row=3)},
    )

    resolved = resolve_citations(answer)

    assert [c.number for c in resolved.citations] == [1, 2]


def test_resolve_citations_orders_by_first_appearance_not_number() -> None:
    answer = make_answer(
        "South was [2], mentioned before North [1].",
        citation_map={1: meta(row=2), 2: meta(row=3)},
    )

    resolved = resolve_citations(answer)

    assert [c.number for c in resolved.citations] == [2, 1]


def test_resolve_citations_deduplicates_repeated_markers() -> None:
    answer = make_answer(
        "North was [1]. As noted in [1], North had strong growth.",
        citation_map={1: meta()},
    )

    resolved = resolve_citations(answer)

    assert len(resolved.citations) == 1


def test_resolve_citations_flags_unresolved_citation_number() -> None:
    # The model cited [5], but only 1 context chunk was ever provided --
    # a plausible hallucinated source, must be surfaced, not dropped.
    answer = make_answer("The answer was [5].", citation_map={1: meta()})

    resolved = resolve_citations(answer)

    assert resolved.citations == []
    assert resolved.unresolved_citation_numbers == [5]


def test_resolve_citations_handles_mix_of_resolved_and_unresolved() -> None:
    answer = make_answer("North [1], and something odd [9].", citation_map={1: meta()})

    resolved = resolve_citations(answer)

    assert len(resolved.citations) == 1
    assert resolved.citations[0].number == 1
    assert resolved.unresolved_citation_numbers == [9]


def test_resolve_citations_with_no_markers_returns_empty_citations() -> None:
    # The refusal case: no context was given, no [N] markers expected.
    answer = make_answer(
        "I don't have enough information in the provided documents to answer that.",
        citation_map={},
    )

    resolved = resolve_citations(answer)

    assert resolved.citations == []
    assert resolved.unresolved_citation_numbers == []


def test_resolve_citations_carries_model_and_latency_through() -> None:
    prompt = AssembledPrompt(text="...", citation_map={1: meta()}, context_used=[])
    answer = GeneratedAnswer(
        raw_text="Answer [1]",
        prompt=prompt,
        model="llama3.1:8b-instruct-q4_K_M",
        latency_seconds=2.5,
    )

    resolved = resolve_citations(answer)

    assert resolved.model == "llama3.1:8b-instruct-q4_K_M"
    assert resolved.latency_seconds == 2.5


def test_resolve_citations_does_not_match_non_numeric_brackets() -> None:
    # A stray "[abc]" or "[N]" placeholder-looking text should not be
    # mistaken for a citation marker.
    answer = make_answer(
        "See [abc] for details, and also [1].", citation_map={1: meta()}
    )

    resolved = resolve_citations(answer)

    assert len(resolved.citations) == 1
    assert resolved.citations[0].number == 1
