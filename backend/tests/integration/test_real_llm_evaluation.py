"""Opt-in raw Ollama prompt evaluations with hand-built source contexts.

These tests separate model/prompt behavior from retrieval behavior.
Some synthesis cases are expected failures; inspect skips/xfails explicitly.
They do not establish full UI narrative identity/relevance correctness.
See docs/testing.md and docs/limitations.md.
Author: Imitiyaz and AI Agent
"""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from app.core.config import settings
from app.generation import LLMClient, build_prompt, resolve_citations
from app.models.extracted import SourceMetadata
from app.retrieval.models import RetrievalResult

QUESTIONS_PATH = (
    Path(__file__).parent.parent / "fixtures" / "prompt_eval_questions.json"
)

_NORTH_ROW = RetrievalResult(
    text="In 'Q3 Sales': Region is North; Q3 Revenue is 45000; Q4 Revenue is 52000.",
    metadata=SourceMetadata("sample_sales.xlsx", "Q3 Sales", 2),
    score=0.9,
    rank=1,
)
_SOUTH_ROW = RetrievalResult(
    text="In 'Q3 Sales': Region is South; Q3 Revenue is 38000; Q4 Revenue is 39500.",
    metadata=SourceMetadata("sample_sales.xlsx", "Q3 Sales", 3),
    score=0.85,
    rank=2,
)
_EAST_ROW = RetrievalResult(
    text="In 'Q3 Sales': Region is East; Q3 Revenue is 41000; Q4 Revenue is 44000.",
    metadata=SourceMetadata("sample_sales.xlsx", "Q3 Sales", 4),
    score=0.8,
    rank=3,
)
_EAST_ROW_PDF = RetrievalResult(
    text="In 'page_1': Region is East; Q3 Revenue is 41000; Q4 Revenue is 44000.",
    metadata=SourceMetadata("sample_report.pdf", "page_1", "table_1_row_3"),
    score=0.9,
    rank=1,
)

# The exact top-3 context real retrieval produced for this file/question
# in an earlier Stage 9 manual smoke test -- not a synthetic
# approximation. sample_sales_extended.xlsx's "Merged Region" sheet has
# two genuinely distinct North records sharing one merged region cell
# (a deliberate Stage 6 fixture design); the third chunk is the
# already-documented Sparse Data forward-fill artifact, included here
# because it's what real retrieval actually surfaces, not because the
# test requires the model to use it.
_NORTH_MERGED_ROW_3 = RetrievalResult(
    text="In 'Merged Region': Region is North; Q3 Revenue is 47000; Q4 Revenue is 53000.",
    metadata=SourceMetadata("sample_sales_extended.xlsx", "Merged Region", 3),
    score=0.9,
    rank=1,
)
_NORTH_MERGED_ROW_2 = RetrievalResult(
    text="In 'Merged Region': Region is North; Q3 Revenue is 45000; Q4 Revenue is 52000.",
    metadata=SourceMetadata("sample_sales_extended.xlsx", "Merged Region", 2),
    score=0.88,
    rank=2,
)
_NORTH_SPARSE_ROW_3 = RetrievalResult(
    text="In 'Sparse Data': Region is North; Q3 Revenue is 38000; Q4 Revenue is 39500; Comment is Strong.",
    metadata=SourceMetadata("sample_sales_extended.xlsx", "Sparse Data", 3),
    score=0.82,
    rank=3,
)

# Hand-built context per question ID, matching the real fixture data
# each question is actually about. Empty list = deliberately no
# context, for the refusal cases. All three "which region" / "total"
# synthesis questions get the same full three-row context -- they're
# all testing different reasoning operations over the same underlying data.
_CONTEXT_BY_QUESTION_ID: dict[str, list[RetrievalResult]] = {
    "q1_north_q3_revenue": [_NORTH_ROW],
    "q2_south_q4_revenue": [_SOUTH_ROW],
    "q3_east_q3_revenue_pdf": [_EAST_ROW_PDF],
    "q4_highest_growth_region_synthesis": [_NORTH_ROW, _SOUTH_ROW, _EAST_ROW],
    "q7_lowest_q3_revenue_region_synthesis": [_NORTH_ROW, _SOUTH_ROW, _EAST_ROW],
    "q8_total_q3_revenue_sum_synthesis": [_NORTH_ROW, _SOUTH_ROW, _EAST_ROW],
    "q9_smallest_growth_region_synthesis": [_NORTH_ROW, _SOUTH_ROW, _EAST_ROW],
    "q10_north_ambiguous_multiple_values": [
        _NORTH_MERGED_ROW_3,
        _NORTH_MERGED_ROW_2,
        _NORTH_SPARSE_ROW_3,
    ],
    "q5_out_of_scope_general_knowledge": [],
    "q6_out_of_scope_unrelated_business_question": [],
}

_REFUSAL_PHRASE = "i don't have enough information"


def _answer_contains_expected_value(answer_text: str, expected: str) -> bool:
    """True if `expected` appears in `answer_text`, ignoring thousands-
    separator commas on the answer side.

    Regression test for a real evaluation bug: a model answering
    "45,000" instead of "45000" is a formatting choice, not a wrong
    answer -- a naive substring check flagged it as a failure the first
    time this test actually ran against a real model. Stripping commas
    fixes that specific case without masking a genuine digit error (e.g.
    "40,100" when the expected value is "41000" still correctly returns
    False, since stripping commas doesn't change which digits are
    present -- see test_helper_still_catches_genuine_digit_errors below).
    """
    return expected in answer_text.replace(",", "")


def _load_questions() -> list[dict]:
    with open(QUESTIONS_PATH, encoding="utf-8") as f:
        return list(json.load(f)["questions"])


def _ollama_is_reachable() -> bool:
    try:
        response = httpx.get(
            f"{settings.ollama_base_url}/api/tags", timeout=2.0, trust_env=False
        )
        return response.status_code == 200
    except httpx.HTTPError:
        return False


_SYNTHESIS_XFAIL_REASON = (
    "Known raw-model limitation: cross-row comparison/synthesis is not reliable "
    "for this model and context set. See docs/limitations.md."
)

_AMBIGUOUS_XFAIL_REASON = (
    "Known raw-model limitation: distinct records sharing an entity label can "
    "be reduced to one unsupported choice. See docs/limitations.md."
)

_XFAIL_REASON_BY_CATEGORY = {
    "synthesis": _SYNTHESIS_XFAIL_REASON,
    "ambiguous": _AMBIGUOUS_XFAIL_REASON,
}


def _make_question_param(
    question_spec: dict,
) -> pytest.MarkDecorator | pytest.ParameterSet:
    marks = []
    xfail_reason = _XFAIL_REASON_BY_CATEGORY.get(question_spec["category"])
    if xfail_reason is not None:
        marks.append(
            pytest.mark.xfail(
                reason=xfail_reason,
                strict=False,  # an eventual fix shows as XPASS, not an error
            )
        )
    return pytest.param(question_spec, id=question_spec["id"], marks=marks)


@pytest.mark.ollama
@pytest.mark.parametrize(
    "question_spec", [_make_question_param(q) for q in _load_questions()]
)
def test_real_llm_answers_question_correctly(question_spec: dict) -> None:
    if not _ollama_is_reachable():
        pytest.skip(
            f"Ollama not reachable at {settings.ollama_base_url} -- this is an "
            "opt-in raw-model evaluation. Start Ollama and "
            "re-run with `pytest -m ollama -v` to actually exercise it."
        )

    client = LLMClient()
    context = _CONTEXT_BY_QUESTION_ID[question_spec["id"]]
    prompt = build_prompt(question_spec["question"], context)
    answer = client.generate(prompt)
    resolved = resolve_citations(answer)

    print(
        f"\nQ: {question_spec['question']}\nA: {answer.raw_text}\n"
        f"Citations: {[c.citation_text for c in resolved.citations]}\n"
        f"Unresolved: {resolved.unresolved_citation_numbers}\n"
    )

    if question_spec["should_refuse"]:
        assert (
            _REFUSAL_PHRASE in answer.raw_text.lower()
        ), f"expected a refusal, got: {answer.raw_text!r}"
        # No context was ever given for a refusal case (citation_map is
        # empty by construction), so a valid citation is structurally
        # impossible here regardless of what the model writes -- this
        # confirms that invariant holds, not just that the model behaved.
        assert (
            resolved.citations == []
        ), f"refusal answer should never resolve to a real citation, got: {resolved.citations}"
    else:
        if question_spec["category"] == "ambiguous":
            # Correct behavior, per explicit project decision: the model
            # must surface BOTH genuinely distinct values (45000 and
            # 47000), each backed by its own citation -- not silently
            # pick one or substitute a sum whose meaning the fixture
            # does not establish.
            mentions_both_values = _answer_contains_expected_value(
                answer.raw_text, "45000"
            ) and _answer_contains_expected_value(answer.raw_text, "47000")
            assert mentions_both_values, (
                f"expected both 45000 and 47000 separately in the "
                f"answer, got: {answer.raw_text!r}"
            )
            if mentions_both_values:
                # If both values are actually stated, each should be
                # backed by its own citation -- not just claimed.
                assert len(resolved.citations) >= 2, (
                    f"expected at least 2 citations backing the 2 distinct "
                    f"values stated, got: {resolved.citations}"
                )
        elif question_spec.get("expected_answer_contains"):
            expected = question_spec["expected_answer_contains"]
            assert _answer_contains_expected_value(
                answer.raw_text, expected
            ), f"expected {expected!r} in the answer, got: {answer.raw_text!r}"
        else:
            assert answer.raw_text.strip(), "got an empty answer"

        # Every answerable question should cite a real source, and it
        # should be the file the question is actually about -- checks
        # the citation MECHANISM works correctly, independent of whether
        # the answer's content itself was correct.
        expected_source_file = question_spec["expected_source_file"]
        assert resolved.citations, (
            f"expected at least one resolved citation, got none. "
            f"Unresolved numbers: {resolved.unresolved_citation_numbers}"
        )
        assert resolved.citations[0].metadata.source_file == expected_source_file, (
            f"expected first citation from {expected_source_file!r}, "
            f"got {resolved.citations[0].metadata.source_file!r}"
        )
        assert resolved.unresolved_citation_numbers == [], (
            f"model cited a number with no matching source: "
            f"{resolved.unresolved_citation_numbers}"
        )


# --- Regression tests for the comma-formatting fix (no network needed) ---


def test_helper_treats_comma_formatted_number_as_matching() -> None:
    assert _answer_contains_expected_value("The revenue was 45,000 dollars.", "45000")


def test_helper_matches_plain_unformatted_number() -> None:
    assert _answer_contains_expected_value("The revenue was 45000 dollars.", "45000")


def test_helper_still_catches_genuine_digit_errors() -> None:
    # The exact real-world case this regression test exists for: the
    # model answered "40,100" when the correct value was "41000" -- a
    # digit transposition, not a formatting difference. Comma-stripping
    # must NOT paper over this.
    assert not _answer_contains_expected_value(
        "The revenue was 40,100 dollars.", "41000"
    )
