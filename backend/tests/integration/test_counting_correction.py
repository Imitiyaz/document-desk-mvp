"""Normal UI payloads, acknowledged repair chains and counting-approval boundaries.

Author: Imitiyaz and AI Agent
Project: RAG MVP
Layer: Verification and synthetic fixtures
"""

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from app.api.schemas import QueryRequest
from app.conversation import counting_population
from tests.integration.test_contributor_clarification import DETAILS
from tests.integration.test_grouped_continuation import (
    COMPLETE,
    FOLLOWUP,
    SOURCE,
    World,
)
from tests.integration.test_grouped_continuation import world as grouped_world
from tools.contributor_oracle import validate_contributions

UNKNOWN = "Sum Q3 Revenue for East and West; Sum North and South from the file and each sheet using unicorn accounting"
NOTICE = "Retained your confirmed source-record counting choice"


@pytest.fixture(name="world")
def correction_world(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Iterator[World]:
    """Use the actual API/parsers and injected vector/model backends."""
    yield from grouped_world.__wrapped__(tmp_path, monkeypatch)


def sequence(world: World) -> tuple[Any, str]:
    """Send the UI's exact default payload and confirm only by the real choice."""
    api, _, chat = world
    identity = api.get("/documents").json()[0]
    token = None

    def turn(question: str, **options: Any) -> dict[str, Any]:
        nonlocal token
        response = api.post(
            "/query",
            json={
                "source_file": SOURCE,
                "question": question,
                "operation": "auto",
                "conversation_id": chat,
                "context_token": token,
                "document_id": identity["document_id"],
                "workspace_revision": identity["workspace_revision"],
                **options,
            },
        )
        assert response.status_code == 200, response.text
        body = response.json()
        token = body["context_token"]
        return body

    turn("What was the Q3 revenue in the file ?")
    assert turn(FOLLOWUP + DETAILS)["status"] == "clarification_required"
    turn("what clarification you need ?")
    confirmed = turn("Use source records", aggregation_basis="all_selected_records")
    assert validate_contributions(confirmed) == []
    return turn, token


@pytest.mark.parametrize("rephrased", [FOLLOWUP + DETAILS, COMPLETE + DETAILS])
@pytest.mark.parametrize("explanations", [0, 1, 3])
def test_ui_repair_retains_counting_choice_without_hidden_options(
    world: World, rephrased: str, explanations: int
) -> None:
    turn, _ = sequence(world)
    assert turn(UNKNOWN)["status"] == "clarification_required"
    for _ in range(explanations):
        body = turn("what clarification you need ?")
        assert body["execution_path"] == "conversation_clarification"
        assert "'unicorn'" in body["answer"]
        assert body["records"] == body["citations"] == []
    body = turn(rephrased)
    assert validate_contributions(body) == []
    assert any(NOTICE in warning for warning in body["warnings"])
    assert world[1].llm.prompts == []


@pytest.mark.parametrize(
    "options",
    [
        {"aggregation_basis": "auto"},
        {"entity_groups": [["North", "East"], ["South", "West"]]},
        {"record_scope": "detail"},
        {"filters": {"Region": "North"}},
        {"context_token": None},
    ],
)
def test_changed_or_unacknowledged_population_does_not_reuse_approval(
    world: World, options: dict[str, Any]
) -> None:
    turn, _ = sequence(world)
    turn(UNKNOWN)
    body = turn(COMPLETE + DETAILS, **options)
    assert not any(NOTICE in warning for warning in body["warnings"])
    assert not body["grouped_results"]


def test_changed_source_does_not_borrow_the_whole_file_counting_choice(
    world: World,
) -> None:
    turn, _ = sequence(world)
    turn(UNKNOWN)
    body = turn(
        "Sum Q3 Revenue for North and South in Merged Region, include contributed region details in the results"
    )
    assert not any(NOTICE in warning for warning in body["warnings"])
    assert body["coverage"]["resolved_scopes"] == ["Merged Region"]
    for group in body["grouped_results"]:
        if group["calculation"]:
            assert group["calculation"]["population_basis"] == "auto"


def test_fresh_question_without_pending_repair_requests_confirmation_again(
    world: World,
) -> None:
    turn, _ = sequence(world)
    body = turn(COMPLETE + DETAILS)
    assert body["status"] == "clarification_required"
    assert any(
        c.get("aggregation_basis") == "all_selected_records"
        for c in body["clarification_options"]
    )


@pytest.mark.parametrize(
    "changed",
    [
        {"source_file": "other.xlsx"},
        {"document_id": "other-version"},
        {"workspace_revision": 1},
        {"fields": ["Q4 Revenue"]},
        {"group_field": "Customer"},
        {"entity_groups": [["North", "West"]]},
        {"source_scopes": ["Merged Region"]},
        {"sheet_or_page": "Sparse Data"},
        {"filters": {"Region": "North"}},
        {"record_scope": "summary"},
        {"breakdown": "source"},
        {"operation": "maximum"},
    ],
)
def test_counting_proof_is_bound_to_every_population_dimension(
    changed: dict[str, Any],
) -> None:
    original = QueryRequest(
        source_file=SOURCE,
        question=COMPLETE,
        operation="sum",
        fields=["Q3 Revenue"],
        group_field="Region",
        entity_groups=[["North", "South"]],
        breakdown="file_and_source",
        workspace_revision=0,
    )
    assert counting_population(original) is not None
    assert counting_population(
        original.model_copy(update=changed)
    ) != counting_population(original)


def test_explicit_basis_reset_during_repair_clears_the_old_approval(
    world: World,
) -> None:
    turn, _ = sequence(world)
    turn(UNKNOWN, aggregation_basis="auto")
    turn("what clarification you need ?")
    body = turn(FOLLOWUP + DETAILS)
    assert body["status"] == "clarification_required"
    assert not any(NOTICE in w for w in body["warnings"])
