"""Exact user additions, varied order and request-only clarification state.

Author: Imitiyaz and AI Agent
Project: RAG MVP
Layer: Verification and synthetic fixtures
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from tests.integration.test_grouped_continuation import (
    COMPLETE,
    FOLLOWUP,
    SOURCE,
    World,
    ask,
)
from tests.integration.test_grouped_continuation import (
    world as grouped_world,
)
from tests.integration.test_mvp import workbook
from tools.contributor_oracle import mutations, validate_contributions

DETAILS = ", include contributed region details in the results."


@pytest.fixture(name="world")
def contributor_world(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Iterator[World]:
    """Reuse the real loader/service fixture without importing a shadowed fixture."""
    yield from grouped_world.__wrapped__(tmp_path, monkeypatch)


@pytest.mark.parametrize(
    "question",
    [
        COMPLETE + DETAILS,
        "What was the Q3 revenue in the file ? " + FOLLOWUP + DETAILS,
        (COMPLETE + DETAILS).upper(),
    ],
)
def test_fully_restated_requests_keep_every_group_and_contributor(
    world: World, question: str
) -> None:
    body = ask(world[0], question, aggregation_basis="all_selected_records")
    assert validate_contributions(body) == []
    assert world[1].llm.prompts == []


@pytest.mark.parametrize(
    "prefix",
    [
        [
            "What was the Q3 revenue for north in Merged Region?",
            "Sum these records",
            "and South ?",
        ],
        ["SUM Q3 Revenue for North in the file", "and South ?"],
        ["What was the Q3 revenue in the file ?"],
    ],
)
def test_compound_details_after_different_question_orders(
    world: World, prefix: list[str]
) -> None:
    api, bundle, chat = world
    token = None
    for question in prefix:
        body = ask(
            api,
            question,
            conversation_id=chat,
            context_token=token,
            aggregation_basis="all_selected_records",
        )
        token = body["context_token"]
    body = ask(
        api,
        FOLLOWUP + DETAILS,
        conversation_id=chat,
        context_token=token,
        sheet_or_page="Merged Region",
        aggregation_basis="all_selected_records",
    )
    assert validate_contributions(body) == []
    assert body["coverage"]["resolved_scopes"] == []
    assert bundle.llm.prompts == []


def test_display_only_followup_keeps_group_and_population_request(world: World) -> None:
    api, _, chat = world
    body = ask(
        api,
        COMPLETE,
        conversation_id=chat,
        context_token=None,
        aggregation_basis="all_selected_records",
    )
    for _ in range(2):
        body = ask(
            api,
            "Include contributed region details in the results",
            conversation_id=chat,
            context_token=body["context_token"],
        )
        assert validate_contributions(body) == []


@pytest.mark.parametrize(
    "wording",
    [
        "what clarification you need ?",
        "What clarification do you need?",
        "What do you need me to clarify?",
        "Please explain the clarification",
    ],
)
def test_explaining_population_choice_keeps_request_and_options(
    world: World, wording: str
) -> None:
    api, bundle, chat = world
    first = ask(api, COMPLETE + DETAILS, conversation_id=chat, context_token=None)
    assert first["status"] == "clarification_required"
    for _ in range(2):
        explained = ask(
            api, wording, conversation_id=chat, context_token=first["context_token"]
        )
        assert explained["execution_path"] == "conversation_clarification"
        assert explained["status"] == "clarification_required"
        assert explained["clarification_options"] == first["clarification_options"]
        assert explained["records"] == explained["citations"] == []
        assert "Question awaiting clarification" in explained["answer"]
        assert "Q3" in explained["resolved_question"]
        first = explained
    body = ask(
        api,
        "Use source records",
        conversation_id=chat,
        context_token=first["context_token"],
    )
    assert validate_contributions(body) == []
    assert bundle.llm.prompts == []


def test_unrecognized_clause_is_specific_and_can_be_rephrased_after_explanation(
    world: World,
) -> None:
    api, bundle, chat = world
    first = ask(
        api,
        COMPLETE + " using unicorn accounting",
        conversation_id=chat,
        context_token=None,
        aggregation_basis="all_selected_records",
    )
    assert first["status"] == "clarification_required"
    assert "'unicorn'" in first["answer"] and "Q3 Revenue" in first["answer"]
    explanation = ask(
        api,
        "what clarification you need ?",
        conversation_id=chat,
        context_token=first["context_token"],
    )
    assert "'unicorn'" in explanation["answer"]
    body = ask(
        api,
        FOLLOWUP + DETAILS,
        conversation_id=chat,
        context_token=explanation["context_token"],
        aggregation_basis="all_selected_records",
    )
    assert validate_contributions(body) == []
    assert bundle.llm.prompts == []


def test_no_pending_clarification_does_not_search_workbook_or_other_chat(
    world: World,
) -> None:
    api, bundle, chat = world
    first = ask(api, COMPLETE, conversation_id=chat, context_token=None)
    identity = api.get("/documents").json()[0]
    other = api.post(
        "/conversations",
        json={
            "source_file": SOURCE,
            "document_id": identity["document_id"],
            "workspace_revision": identity["workspace_revision"],
        },
    ).json()["conversation_id"]
    for options in ({}, {"conversation_id": other, "context_token": None}):
        body = ask(api, "what clarification you need ?", **options)
        assert body["status"] == "no_evidence"
        assert body["execution_path"] == "conversation_clarification"
        assert body["records"] == body["citations"] == []
    # An unacknowledged response does not become a context for an explicit null token.
    body = ask(
        api, "what clarification you need ?", conversation_id=chat, context_token=None
    )
    assert body["status"] == "no_evidence"
    body = ask(
        api,
        "what clarification you need ?",
        conversation_id=chat,
        context_token=first["context_token"],
    )
    assert body["status"] == "clarification_required"
    assert bundle.llm.prompts == []


@pytest.mark.parametrize(
    "fault",
    [
        "omitted_east",
        "east_zero",
        "absent_south_zero",
        "wrong_region",
        "wrong_contributor_sum",
        "omitted_contributor_operand",
        "wrong_contributor_cell",
        "wrong_contributor_display",
        "lost_contributor_citation",
    ],
)
def test_contributor_checker_detects_each_corruption(world: World, fault: str) -> None:
    body = ask(world[0], COMPLETE + DETAILS, aggregation_basis="all_selected_records")
    assert validate_contributions(body) == []
    assert validate_contributions(mutations(body)[fault])


def test_actual_zero_negative_and_all_missing_contributions_remain_distinct(
    world: World,
) -> None:
    api, _, _ = world
    data = workbook(
        {
            "Data": [
                ["Region", "Revenue"],
                ["North", 0],
                ["South", -12],
                ["East", None],
                ["West", 12],
            ]
        }
    )
    assert (
        api.post("/documents", files={"file": ("zero.xlsx", data)}).status_code == 201
    )
    body = api.post(
        "/query",
        json={
            "source_file": "zero.xlsx",
            "question": "Sum Revenue for North and South; sum East and West by sheet, include contributed region details",
        },
    ).json()
    groups = {g["label"]: g for g in body["grouped_results"]}
    north = next(
        c for c in groups["North + South"]["contributions"] if c["entity"] == "North"
    )
    assert north["status"] == "answered" and north["calculation"]["result"] == {
        "Revenue": "0"
    }
    east = groups["East + West"]["contributions"][0]
    assert east["status"] == "incomplete" and east["calculation"] is None
    assert east["missing_cells"] == [{"number": 3, "field": "Revenue", "cell": "B4"}]


def test_meta_question_without_pending_choice_preserves_last_answer_context(
    world: World,
) -> None:
    api, bundle, chat = world
    first = ask(
        api,
        "SUM Q3 Revenue for North in Merged Region",
        conversation_id=chat,
        context_token=None,
        aggregation_basis="all_selected_records",
    )
    explanation = ask(
        api,
        "what clarification you need ?",
        conversation_id=chat,
        context_token=first["context_token"],
    )
    assert explanation["status"] == "no_evidence"
    body = ask(
        api,
        "And South?",
        conversation_id=chat,
        context_token=explanation["context_token"],
    )
    assert body["calculation"]["result"] == {"Q3 Revenue": "77000"}
    assert bundle.llm.prompts == []


def test_meta_question_does_not_bypass_unknown_document_validation(
    world: World,
) -> None:
    response = world[0].post(
        "/query",
        json={
            "source_file": "not-indexed.xlsx",
            "question": "what clarification you need ?",
        },
    )
    assert response.status_code == 404


@pytest.mark.parametrize(
    "suffix",
    [
        ", include contributed region details excluding West",
        ", include only Atlantis region details in the results",
    ],
)
def test_display_phrase_never_swallows_extra_filters_or_entities(
    world: World, suffix: str
) -> None:
    body = ask(world[0], COMPLETE + suffix, aggregation_basis="all_selected_records")
    assert body["status"] == "clarification_required"
    assert body["grouped_results"] == [] and body["calculation"] is None


@pytest.mark.parametrize(
    "record_scope, labels, amount",
    [
        ("detail", ["North", "South"], "30"),
        ("summary", ["Total"], "30"),
    ],
)
def test_contributors_use_the_same_confirmed_detail_or_summary_population(
    world: World, record_scope: str, labels: list[str], amount: str
) -> None:
    api, _, _ = world
    data = workbook(
        {"Data": [["Region", "Revenue"], ["North", 10], ["South", 20], ["Total", 30]]}
    )
    assert (
        api.post("/documents", files={"file": ("summary.xlsx", data)}).status_code
        == 201
    )
    response = api.post(
        "/query",
        json={
            "source_file": "summary.xlsx",
            "record_scope": record_scope,
            "question": "Sum Revenue by sheet, include contributed region details in the results",
        },
    )
    assert response.status_code == 200
    body = response.json()
    group = body["grouped_results"][0]
    assert group["calculation"]["result"] == {"Revenue": amount}
    assert [c["entity"] for c in group["contributions"]] == labels
    assert sum(len(c["record_numbers"]) for c in group["contributions"]) == len(
        body["records"]
    )
