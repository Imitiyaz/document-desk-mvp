"""Structured selection cannot override source values, source order or citations.

Author: Imitiyaz and AI Agent
Project: RAG MVP
Layer: Verification and synthetic fixtures
"""

import pytest

from app.core.exceptions import InvalidRecordSelectionError
from app.generation import build_prompt, resolve_citations
from app.generation.models import GeneratedAnswer
from app.models.extracted import SourceMetadata
from app.retrieval.models import RetrievalResult


def _answer(raw: str, locations=(3, 2), texts=None) -> GeneratedAnswer:
    if texts is None:
        texts = [
            "Region is North; Q3 Revenue is 47000",
            "Region is North; Q3 Revenue is 45000",
        ]
    results = [
        RetrievalResult(text, SourceMetadata("data.xlsx", "Merged Region", row), 0.9, i)
        for i, (row, text) in enumerate(zip(locations, texts, strict=True), 1)
    ]
    return GeneratedAnswer(
        raw,
        build_prompt("Each matching record", results, answer_mode="records"),
        "fake",
        1.0,
    )


def test_reverse_selection_is_rendered_in_source_order_with_original_markers() -> None:
    answer = resolve_citations(_answer('{"record_citations": [1, 2]}'))
    assert answer.text.index("45000") < answer.text.index("47000")
    assert [c.number for c in answer.citations] == [2, 1]
    assert [c.metadata.row_or_location for c in answer.citations] == [2, 3]
    assert answer.unresolved_citation_numbers == []


@pytest.mark.parametrize(
    "raw",
    [
        "47000 [1] and 45000 [2]",
        '```json\n{"record_citations":[1]}\n```',
        '{"record_citations":[99]}',
        '{"record_citations":[0]}',
        '{"record_citations":[-1]}',
        '{"record_citations":[true]}',
        '{"record_citations":[1.0]}',
        '{"record_citations":["1"]}',
        '{"record_citations":[1,1]}',
        '{"record_citations":null}',
        '{"record_citations":[],"answer":"99999"}',
        '{"record_citations":[],"record_citations":[1]}',
        "[]",
    ],
)
def test_invalid_selection_fails_without_falling_back_to_prose(raw: str) -> None:
    with pytest.raises(InvalidRecordSelectionError):
        resolve_citations(_answer(raw))


def test_empty_selection_is_explicit_refusal() -> None:
    answer = resolve_citations(_answer('{"record_citations": []}'))
    assert answer.citations == []
    assert answer.text.startswith("I don't have enough information")


@pytest.mark.parametrize(
    "locations", [(10, 2), ("table_1_row_10", "table_1_row_2"), ("2_part10", "2_part2")]
)
def test_location_numbers_are_sorted_numerically(locations) -> None:
    answer = resolve_citations(_answer('{"record_citations": [1, 2]}', locations))
    assert [c.number for c in answer.citations] == [2, 1]


def test_source_brackets_do_not_create_spurious_citations() -> None:
    answer = resolve_citations(
        _answer('{"record_citations": [1]}', texts=["Note [99]", "Other"])
    )
    assert answer.unresolved_citation_numbers == []
    assert [c.number for c in answer.citations] == [1]
    assert "［99］" in answer.text
