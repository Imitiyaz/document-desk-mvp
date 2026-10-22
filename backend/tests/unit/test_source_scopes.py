"""Alias recognition and replacement share raw spans. Author: Imitiyaz and AI Agent"""

from __future__ import annotations

import pytest

from app.api.schemas import QueryRequest
from app.structured.scopes import (
    canonical_question,
    named_scopes,
    replace_scope,
    resolve_question_scope,
    scope_choice,
    scope_problem,
)


@pytest.mark.parametrize("alias", ["page 1", "page_1", "page-1", "PAGE 01"])
def test_aliases_share_selection_and_replacement(alias):
    names = ["page_1", "page_3"]
    q = f"Total Quantity in {alias}?"
    assert named_scopes(q, names) == ["page_1"]
    assert canonical_question(q, names) == "Total Quantity in page_1?"
    assert replace_scope(q, names, ["page_3"]) == "Total Quantity in page_3"
    assert scope_choice("And " + alias + "?", names) == ["page_1"]
    assert scope_choice(q, names) == []


def test_multiple_pages_and_unknown_constraint_are_retained():
    names = ["page_1", "page_3"]
    assert named_scopes("pages 1 and 3", names) == names
    assert named_scopes("page 1 and page 99", names) == ["page_1", "page_99"]
    d = {
        "rows": [{"sheet_or_page": "page_1", "values": {"Quantity": "10"}}],
        "text_blocks": [],
    }
    r, _ = resolve_question_scope(
        QueryRequest(question="Total Quantity in page 99?", source_file="x.pdf"), d
    )
    assert r.sheet_or_page == "page_99"
    assert "unavailable" in scope_problem(r, d)


def test_longest_nested_names():
    names = ["Sales", "Q3 Sales", "North / Notes"]
    assert named_scopes("Q3 Sales and North / Notes", names) == [
        "Q3 Sales",
        "North / Notes",
    ]
    assert (
        replace_scope("Total Revenue in Q3 Sales?", names, ["North / Notes"])
        == "Total Revenue in North / Notes"
    )


@pytest.mark.parametrize(
    "q",
    [
        "Total Quantity in page 1.5",
        "Total Quantity in page -1",
        "Total Quantity in page 1a",
        "Total Quantity in page two",
        "Total Quantity in pages 1-3",
    ],
)
def test_invalid_syntax_is_not_converted_into_valid_scope(q):
    d = {
        "rows": [{"sheet_or_page": "page_1", "values": {"Quantity": "10"}}],
        "text_blocks": [],
    }
    r, _ = resolve_question_scope(QueryRequest(question=q, source_file="x.pdf"), d)
    assert r.question == q
    assert scope_problem(r, d)
