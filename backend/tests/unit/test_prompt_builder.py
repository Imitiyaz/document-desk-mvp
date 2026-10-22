"""Unit tests for app.generation.prompt_builder.build_prompt.

Several tests assert on literal substrings of the system instructions
deliberately -- these encode docs/testing.md's non-negotiable prompt
requirements (grounding, explicit refusal phrase, citation instruction).
If the template's wording ever changes, these tests forcing a conscious
update are the point, not an inconvenience to work around.

Author: Imitiyaz and AI Agent
Project: RAG MVP
Layer: Verification and synthetic fixtures
"""

from __future__ import annotations

import pytest

from app.generation.models import AssembledPrompt
from app.generation.prompt_builder import RECOMMENDED_TEMPERATURE, build_prompt
from app.models.extracted import SourceMetadata
from app.retrieval.models import RetrievalResult


def make_result(
    text: str, rank: int, row: int = 1, source_file: str = "sample_sales.xlsx"
) -> RetrievalResult:
    return RetrievalResult(
        text=text,
        metadata=SourceMetadata(
            source_file=source_file, sheet_or_page="Q3 Sales", row_or_location=row
        ),
        score=0.9 - (rank * 0.05),
        rank=rank,
    )


def test_build_prompt_returns_assembled_prompt() -> None:
    result = build_prompt(
        "What was Q3 revenue?", [make_result("North Q3 revenue is 45000.", 1)]
    )
    assert isinstance(result, AssembledPrompt)


def test_build_prompt_contains_all_four_sections_in_order() -> None:
    prompt = build_prompt(
        "What was Q3 revenue?", [make_result("North Q3 revenue is 45000.", 1)]
    )
    text = prompt.text
    assert (
        text.index("SYSTEM:")
        < text.index("CONTEXT:")
        < text.index("QUESTION:")
        < text.index("ANSWER:")
    )


def test_build_prompt_inserts_question_verbatim() -> None:
    question = "What was the Q3 revenue for the North region specifically?"
    prompt = build_prompt(question, [make_result("some text", 1)])
    assert question in prompt.text


def test_build_prompt_numbers_context_chunks_starting_at_one() -> None:
    results = [
        make_result("first chunk", 1, row=1),
        make_result("second chunk", 2, row=2),
    ]
    prompt = build_prompt("a question", results)
    assert "[1] first chunk" in prompt.text
    assert "[2] second chunk" in prompt.text


def test_build_prompt_citation_map_matches_numbered_context() -> None:
    results = [make_result("first", 1, row=5), make_result("second", 2, row=9)]
    prompt = build_prompt("a question", results)
    assert prompt.citation_map[1].row_or_location == 5
    assert prompt.citation_map[2].row_or_location == 9


def test_build_prompt_context_used_matches_input_order() -> None:
    results = [
        make_result("first", 1),
        make_result("second", 2),
        make_result("third", 3),
    ]
    prompt = build_prompt("a question", results)
    assert prompt.context_used == results


def test_build_prompt_includes_human_readable_citation_per_chunk() -> None:
    prompt = build_prompt(
        "a question",
        [make_result("some text", 1, row=7, source_file="sample_report.pdf")],
    )
    assert "sample_report.pdf / Q3 Sales / row 7" in prompt.text


def test_build_prompt_with_no_results_gives_explicit_no_context_marker() -> None:
    prompt = build_prompt("a question with no relevant documents", [])
    assert "No relevant context was found" in prompt.text
    assert prompt.citation_map == {}
    assert prompt.context_used == []


def test_build_prompt_system_instructions_require_context_only_grounding() -> None:
    prompt = build_prompt("a question", [make_result("text", 1)])
    assert "ONLY the context" in prompt.text


def test_build_prompt_system_instructions_require_explicit_refusal_phrase() -> None:
    prompt = build_prompt("a question", [make_result("text", 1)])
    assert (
        "I don't have enough information in the provided documents to answer that."
        in prompt.text
    )


def test_build_prompt_system_instructions_require_citation_format() -> None:
    prompt = build_prompt("a question", [make_result("text", 1)])
    assert (
        "(Source: [2])" in prompt.text
        or "note which numbered context chunk" in prompt.text
    )


def test_build_prompt_system_instructions_forbid_outside_knowledge() -> None:
    prompt = build_prompt("a question", [make_result("text", 1)])
    assert "outside knowledge" in prompt.text


@pytest.mark.parametrize("blank_question", ["", "   ", "\n\t"])
def test_build_prompt_raises_value_error_on_blank_question(blank_question: str) -> None:
    with pytest.raises(ValueError, match="question must not be empty"):
        build_prompt(blank_question, [make_result("text", 1)])


def test_build_prompt_raises_on_blank_question_even_with_no_results() -> None:
    with pytest.raises(ValueError):
        build_prompt("", [])


def test_recommended_temperature_is_low_for_deterministic_factual_qa() -> None:
    # Low, not zero -- documented as a recommendation for Stage 8, not a
    # hard requirement; Stage 8's own evaluation may tune this further.
    assert 0.0 <= RECOMMENDED_TEMPERATURE <= 0.3


def test_prompt_keeps_ranked_evidence_but_requires_labelled_source_order_answers() -> (
    None
):
    results = [
        make_result("Region is South; Q3 Revenue is 38000", 1, row=3),
        make_result("Region is North; Q3 Revenue is 45000", 2, row=2),
    ]
    prompt = build_prompt("Total for North and South?", results)
    assert prompt.context_used == results
    assert prompt.citation_map[1].row_or_location == 3
    assert prompt.citation_map[2].row_or_location == 2
    assert "Label every entity-value pair explicitly" in prompt.text
    assert "order requested by the question" in prompt.text
    assert "source page/row order, not retrieval rank" in prompt.text
    assert "citation must contain the specific value or fact claimed" in prompt.text
    assert "report each separately" in prompt.text
