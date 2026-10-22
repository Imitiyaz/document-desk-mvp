"""User-reported compound sequence: independent cells, groups and derived labels.

Author: Imitiyaz and AI Agent
Project: RAG MVP
Layer: Verification and synthetic fixtures
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from tests.api_fakes import ApiBundle, make_bundle
from tests.integration.test_mvp import workbook

World = tuple[TestClient, ApiBundle, str]

SOURCE = "sample_sales_extended.xlsx"
FOLLOWUP = "and sum of East and West ? and Sum of North and South ? from the file and from the individual sheets"
COMPLETE = "What is the sum of Q3 revenue for East and West, North and South from the file and from the individual sheets in the file."
# These are independently reviewed expected contributions, not app-generated facts.
EXPECTED = {
    ("Whole file", "Overall"): ("315000", 8, True),
    ("Whole file", "East + West"): ("63000", 2, True),
    ("Whole file", "North + South"): ("252000", 6, False),
    ("Merged Region", "Overall"): ("169000", 4, False),
    ("Merged Region", "East + West"): (None, 0, None),
    ("Merged Region", "North + South"): ("169000", 4, False),
    ("Sparse Data", "Overall"): ("146000", 4, True),
    ("Sparse Data", "East + West"): ("63000", 2, True),
    ("Sparse Data", "North + South"): ("83000", 2, True),
}


@pytest.fixture
def world(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[World]:
    from app.core.config import settings

    monkeypatch.setattr(settings, "upload_temp_dir", str(tmp_path / "uploads"))
    bundle = make_bundle()
    with TestClient(create_app(lambda: bundle.service)) as api:
        path = Path(__file__).parents[1] / "fixtures" / SOURCE
        assert (
            api.post(
                "/documents", files={"file": (SOURCE, path.read_bytes())}
            ).status_code
            == 201
        )
        item = api.get("/documents").json()[0]
        chat = api.post(
            "/conversations",
            json={
                "source_file": SOURCE,
                "document_id": item["document_id"],
                "workspace_revision": item["workspace_revision"],
            },
        ).json()["conversation_id"]
        yield api, bundle, chat


def ask(api: TestClient, question: str, **options: Any) -> dict[str, Any]:
    response = api.post(
        "/query", json={"source_file": SOURCE, "question": question, **options}
    )
    assert response.status_code == 200, response.text
    return response.json()


def assert_groups(body: dict[str, Any]) -> None:
    from tools.grouped_oracle import validate_grouped

    assert validate_grouped(body) == []
    groups = {(g["scope"], g["label"]): g for g in body["grouped_results"]}
    assert set(groups) == set(EXPECTED)
    by_number = {r["number"]: r for r in body["records"]}
    assert len(by_number) == len(body["citations"]) == 9
    assert body["status"] == "incomplete" and body["coverage"]["complete"] is False
    for key, (amount, count, partial) in EXPECTED.items():
        group = groups[key]
        calc = group["calculation"]
        if amount is None:
            assert group["status"] == "no_evidence" and calc is None
            assert group["missing_entities"] == ["East", "West"]
            continue
        assert calc["result"] == {"Q3 Revenue": amount}
        assert calc["partial"] is partial
        assert len(calc["operands"]) == count
        assert sum(
            (Decimal(o["values"]["Q3 Revenue"]) for o in calc["operands"]), Decimal(0)
        ) == Decimal(amount)
        physical = []
        for o in calc["operands"]:
            r = by_number[o["number"]]
            assert o["source"]["sheet_or_page"] == r["sheet_or_page"]
            assert o["source"]["row_or_location"] == r["row_or_location"]
            assert o["cell_references"] == {
                "Q3 Revenue": r["cell_references"]["Q3 Revenue"]
            }
            assert o["values"]["Q3 Revenue"] == r["values"]["Q3 Revenue"]
            physical.append(
                (o["source"]["sheet_or_page"], o["cell_references"]["Q3 Revenue"])
            )
        assert len(set(physical)) == len(physical)
    assert groups[("Sparse Data", "North + South")]["missing_entities"] == ["South"]
    assert "315,000" in body["answer"] and "255,000" not in body["answer"]


@pytest.mark.parametrize(
    "fault",
    [
        "wrong_sum",
        "omitted_group",
        "wrong_membership",
        "omitted_operand",
        "wrong_cell",
        "missing_exclusion",
        "false_completeness",
        "lost_continuation",
        "wrong_anchor",
        "wrong_display",
        "invented_zero",
    ],
)
def test_grouped_oracle_rejects_each_independent_corruption(
    world: World, fault: str
) -> None:
    from tools.grouped_oracle import mutations, validate_grouped

    body = ask(world[0], COMPLETE, aggregation_basis="all_selected_records")
    assert validate_grouped(body) == []
    assert validate_grouped(mutations(body)[fault]), fault


def test_exact_compound_followup_after_the_complete_manual_sequence(
    world: World,
) -> None:
    api, bundle, chat = world
    token = None
    for q in [
        "What is the SUM of Q3 revenue in the file ?",
        "Use source records",
        "What was the Q3 revenue for north in Merged Region?",
        "Sum these records",
        "and South ?",
    ]:
        body = ask(api, q, conversation_id=chat, context_token=token)
        token = body["context_token"]
    body = ask(
        api,
        FOLLOWUP,
        conversation_id=chat,
        context_token=token,
        sheet_or_page="Merged Region",
    )
    assert body["coverage"]["fields"] == ["Q3 Revenue"]
    assert body["coverage"]["resolved_scopes"] == []
    assert_groups(body)
    assert bundle.llm.prompts == []


@pytest.mark.parametrize(
    "question",
    [
        COMPLETE,
        COMPLETE.upper(),
        "Sum Q3 Revenue for East and West; sum North and South from the file and each sheet?",
    ],
)
def test_complete_grouped_questions_keep_the_plan_through_population_confirmation(
    world: World, question: str
) -> None:
    api, _, chat = world
    first = ask(api, question, conversation_id=chat, context_token=None)
    assert first["status"] == "clarification_required"
    body = ask(
        api,
        "Use source records",
        conversation_id=chat,
        context_token=first["context_token"],
    )
    assert_groups(body)


def test_by_sheet_only_does_not_demand_cross_sheet_population_confirmation(
    world: World,
) -> None:
    api, _, _ = world
    body = ask(api, "SUM Q3 Revenue for North and South by sheet")
    assert body["grouped_results"]
    assert {g["scope"] for g in body["grouped_results"]} == {
        "Merged Region",
        "Sparse Data",
    }


@pytest.mark.parametrize(
    "question",
    [
        "Sum Q3 Revenue for East and Atlantis from the file and each sheet",
        "Sum Q2 Revenue for East and West from the file and each sheet",
        "Average Q3 Revenue for East and West from the file and each sheet",
        "Sum Q3 Revenue for East and West excluding North from the file and each sheet",
    ],
)
def test_unknown_entities_periods_operations_and_conditions_do_not_become_partial_answers(
    world: World, question: str
) -> None:
    body = ask(world[0], question, aggregation_basis="all_selected_records")
    assert body["status"] == "clarification_required"
    assert not body["grouped_results"] and body["calculation"] is None


def test_new_chat_does_not_inherit_another_chats_measure(world: World) -> None:
    api, _, _ = world
    body = ask(api, FOLLOWUP)
    assert body["status"] == "clarification_required" and not body["grouped_results"]


def test_single_entity_followup_after_grouped_answer_replaces_old_groups(
    world: World,
) -> None:
    api, _, chat = world
    first = ask(
        api,
        COMPLETE,
        conversation_id=chat,
        context_token=None,
        aggregation_basis="all_selected_records",
    )
    body = ask(
        api, "And South?", conversation_id=chat, context_token=first["context_token"]
    )
    assert {g["label"] for g in body["grouped_results"]} == {"Overall", "South"}
    south = next(
        g
        for g in body["grouped_results"]
        if g["scope"] == "Whole file" and g["label"] == "South"
    )
    assert south["calculation"]["result"] == {"Q3 Revenue": "77000"}
    absent = next(
        g
        for g in body["grouped_results"]
        if g["scope"] == "Sparse Data" and g["label"] == "South"
    )
    assert absent["status"] == "no_evidence" and absent["calculation"] is None


def test_explicit_new_period_replaces_previous_metric_in_grouped_followup(
    world: World,
) -> None:
    api, _, chat = world
    first = ask(
        api,
        COMPLETE,
        conversation_id=chat,
        context_token=None,
        aggregation_basis="all_selected_records",
    )
    body = ask(
        api,
        "And sum Q4 Revenue for North and South by sheet?",
        conversation_id=chat,
        context_token=first["context_token"],
    )
    assert body["coverage"]["fields"] == ["Q4 Revenue"]
    assert {g["scope"] for g in body["grouped_results"]} == {
        "Merged Region",
        "Sparse Data",
    }
    assert all(
        "Q3 Revenue" not in g["calculation"]["result"]
        for g in body["grouped_results"]
        if g["calculation"]
    )


def test_continuation_overlay_preserves_raw_cells_and_stored_payload(
    world: World,
) -> None:
    _, bundle, _ = world
    store = bundle.service._records
    before = store.connection.execute(
        "SELECT payload FROM documents WHERE source=?", (SOURCE,)
    ).fetchone()[0]
    document = store.get(SOURCE)
    for row_number, region, anchor in [(3, "North", "A2"), (6, "West", "A5")]:
        row = next(
            r
            for r in document["rows"]
            if r["sheet_or_page"] == "Sparse Data"
            and r["row_or_location"] == row_number
        )
        assert row["raw_values"]["Region"] is None
        assert row["values"]["Region"] == region
        assert row["cell_origins"]["Region"] == f"A{row_number}"
        assert row["continuation_fields"]["Region"]["anchor_cell"] == anchor
    assert (
        store.connection.execute(
            "SELECT payload FROM documents WHERE source=?", (SOURCE,)
        ).fetchone()[0]
        == before
    )
    raw_row = next(
        r
        for r in json.loads(before)["rows"]
        if r["sheet_or_page"] == "Sparse Data" and r["row_or_location"] == 3
    )
    assert raw_row["values"]["Region"] is None and "continuation_fields" not in raw_row


@pytest.mark.parametrize(
    "barrier",
    [[], [None, None], ["Region", "Revenue"], ["Total", 15], [None, "Note only"]],
)
def test_continuation_never_crosses_blank_header_summary_or_note_boundaries(
    world: World, barrier: list[Any]
) -> None:
    api, _, _ = world
    data = workbook(
        {"Data": [["Region", "Revenue"], ["North", 10], barrier, [None, 20]]}
    )
    assert (
        api.post("/documents", files={"file": ("boundary.xlsx", data)}).status_code
        == 201
    )
    body = api.post(
        "/query", json={"source_file": "boundary.xlsx", "question": "Revenue"}
    ).json()
    assert body["records"][-1]["values"]["Region"] is None
    assert body["records"][-1]["continuation_fields"] == {}
