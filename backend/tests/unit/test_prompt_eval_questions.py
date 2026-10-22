"""Schema and consistency checks for the synthetic raw-model question set.

These checks validate reference-data structure without calling an LLM.
Author: Imitiyaz and AI Agent
"""

from __future__ import annotations

import json
from pathlib import Path

QUESTIONS_PATH = (
    Path(__file__).parent.parent / "fixtures" / "prompt_eval_questions.json"
)


def _load_questions() -> list[dict]:
    with open(QUESTIONS_PATH, encoding="utf-8") as f:
        data = json.load(f)
    return data["questions"]


def test_question_set_file_exists_and_parses() -> None:
    questions = _load_questions()
    assert len(questions) > 0


def test_every_question_has_required_fields() -> None:
    required_fields = {"id", "category", "question", "should_refuse"}
    for question in _load_questions():
        assert required_fields.issubset(question.keys()), question["id"]


def test_every_question_has_a_valid_category() -> None:
    valid_categories = {"lookup", "synthesis", "refusal", "ambiguous"}
    for question in _load_questions():
        assert question["category"] in valid_categories, question["id"]


def test_category_is_consistent_with_should_refuse() -> None:
    for question in _load_questions():
        if question["category"] == "refusal":
            assert question["should_refuse"] is True, question["id"]
        else:
            assert question["should_refuse"] is False, question["id"]


def test_at_least_one_synthesis_question_exists() -> None:
    # Stage 8's real evaluation confirmed cross-row synthesis is
    # unreliable with the current model -- this set must keep at least
    # one synthesis question so that limitation stays tracked, not
    # silently dropped from the eval set over time.
    questions = _load_questions()
    assert any(q["category"] == "synthesis" for q in questions)


def test_at_least_one_ambiguous_question_exists() -> None:
    # Stage 9's real evaluation confirmed the model silently picks one
    # value when multiple context chunks share an entity label but
    # disagree on the requested field -- this set must keep at least one
    # ambiguous-category question so that limitation stays tracked too.
    questions = _load_questions()
    assert any(q["category"] == "ambiguous" for q in questions)


def test_question_ids_are_unique() -> None:
    ids = [q["id"] for q in _load_questions()]
    assert len(ids) == len(set(ids))


def test_at_least_one_refusal_case_and_one_answerable_case_exist() -> None:
    # The set must exercise both required behaviors from
    # docs/testing.md: answering from context, and refusing when context
    # doesn't cover the question. A set with only one or the other isn't
    # actually testing the grounding requirement.
    questions = _load_questions()
    assert any(q["should_refuse"] for q in questions)
    assert any(not q["should_refuse"] for q in questions)


def test_refusal_questions_have_no_expected_source_file() -> None:
    for question in _load_questions():
        if question["should_refuse"]:
            assert question.get("expected_source_file") is None, question["id"]


def test_answerable_questions_declare_an_expected_source_file() -> None:
    for question in _load_questions():
        if not question["should_refuse"]:
            assert question.get("expected_source_file") is not None, question["id"]
