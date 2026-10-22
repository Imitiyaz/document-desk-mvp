"""User-reported wording/population regressions with ordinary UI request shapes.

Author: Imitiyaz and AI Agent
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from tests.api_fakes import make_bundle
from tests.integration.test_mvp import workbook

ROOT = Path(__file__).resolve().parents[3]
FIXTURES = ROOT / "backend/tests/fixtures/acceptance"


@pytest.fixture
def world(tmp_path, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "upload_temp_dir", str(tmp_path / "uploads"))
    bundle = make_bundle()
    with TestClient(create_app(lambda: bundle.service)) as client:
        docs = {}
        for name in ["hours.xlsx", "operations.pdf", "shipments.xlsx"]:
            response = client.post(
                "/documents", files={"file": (name, (FIXTURES / name).read_bytes())}
            )
            assert response.status_code == 201
            docs[name] = response.json()
        yield client, bundle, docs


def ask(world, source, question, **options):
    client, _, _ = world
    response = client.post(
        "/query", json={"source_file": source, "question": question, **options}
    )
    assert response.status_code == 200, response.text
    return response.json()


@pytest.mark.parametrize(
    "question",
    [
        "What is the quantity of Apple in the file ?",
        "What is the quantity for Apple?",
        "Apple Quantity?",
        "What is Apple Quantity?",
        'Quantity of "Apple" in the file?',
        "Total Quantity for Apple?",
    ],
)
def test_absent_product_is_never_all_products(world, question):
    body = ask(world, "operations.pdf", question)
    assert body["status"] == "no_evidence"
    assert "Apple" in body["answer"] and "Product" in body["answer"]
    assert body["records"] == body["citations"] == []
    assert body["calculation"] is None
    assert body["coverage"]["matched_records"] == 0
    assert not world[1].llm.prompts


@pytest.mark.parametrize(
    "question",
    [
        "What Hours are recorded for Zenzee?",
        "Total hours for Zenzee?",
        "Hours of Zenzee?",
        "Zenzee Hours?",
    ],
)
def test_absent_name_has_specific_no_match_message(world, question):
    body = ask(world, "hours.xlsx", question)
    assert body["status"] == "no_evidence"
    assert (
        "Zenzee" in body["answer"]
        and "Name" in body["answer"]
        and "hours.xlsx" in body["answer"]
    )
    assert not body["records"] and not body["citations"] and body["calculation"] is None


@pytest.mark.parametrize(
    "question",
    [
        "What Hours are recorded for Asha totally ?",
        "Total hours for Asha ?",
        "Sum Hours for Asha",
        "What are the combined Hours for Asha?",
        "Hours for Asha altogether?",
    ],
)
def test_equivalent_totals_include_zero_and_exact_cells(world, question):
    body = ask(world, "hours.xlsx", question)
    assert body["status"] == "answered"
    calc = body["calculation"]
    assert calc["result"] == {"Hours": "15.75"}
    assert [
        (o["values"]["Hours"], o["cell_references"]["Hours"]) for o in calc["operands"]
    ] == [("7.5", "B2"), ("8.25", "B3"), ("0", "B5")]
    assert [c["row_or_location"] for c in body["citations"]] == [2, 3, 5]
    assert body["model"] is None


@pytest.mark.parametrize(
    "question",
    [
        "What Quantity is recorded for BOLT-A and Apple?",
        "What is the Quantity of Apple and BOLT-A?",
        "Total Quantity for BOLT-A and Apple?",
    ],
)
def test_mixed_entities_never_silently_calculate_known_subset(world, question):
    body = ask(world, "operations.pdf", question)
    assert body["status"] == "clarification_required"
    assert "Apple" in body["answer"] and "BOLT-A" in body["answer"]
    assert body["calculation"] is None and not body["records"]


@pytest.mark.parametrize(
    "question",
    [
        "Hours for Asha last month?",
        "Hours for Asha excluding Ben?",
        "Hours for Asha before November?",
        "Hours for Asha not approved?",
        "What is the average Hours for Asha?",
    ],
)
def test_unsupported_qualifiers_are_not_discarded(world, question):
    body = ask(world, "hours.xlsx", question)
    assert body["status"] == "clarification_required"
    assert body["calculation"] is None


def conversation(world, source):
    client, _, docs = world
    doc = docs[source]
    reply = client.post(
        "/conversations",
        json={k: doc[k] for k in ["source_file", "document_id", "workspace_revision"]},
    ).json()
    return {
        k: ({**reply, "workspace_revision": doc["workspace_revision"]})[k]
        for k in ["conversation_id", "document_id", "workspace_revision"]
    }


def test_actual_confirmation_sequence_preserves_each_product_and_overall(world):
    chat = conversation(world, "operations.pdf")
    first = ask(
        world,
        "operations.pdf",
        "What is the total quantity of the individual products and overall products in the file ?",
        **chat,
    )
    assert first["status"] == "clarification_required"
    assert any(
        c.get("label") == "Use source records" for c in first["clarification_options"]
    )
    second = ask(
        world,
        "operations.pdf",
        "Use source records",
        context_token=first["context_token"],
        **chat,
    )
    assert second["status"] == "answered"
    groups = second["grouped_results"]
    assert [(g["scope"], g["label"], g["calculation"]["result"]) for g in groups] == [
        ("Whole file", "Overall", {"Quantity": "28"}),
        ("Whole file", "BOLT-A", {"Quantity": "14"}),
        ("Whole file", "NUT-B", {"Quantity": "14"}),
    ]
    assert [
        [
            (
                o["source"]["sheet_or_page"],
                o["source"]["row_or_location"],
                o["values"]["Quantity"],
            )
            for o in g["calculation"]["operands"]
        ]
        for g in groups
    ] == [
        [
            ("page_1", "table_1_row_1", "10"),
            ("page_1", "table_1_row_2", "6"),
            ("page_3", "table_1_row_1", "4"),
            ("page_3", "table_1_row_2", "8"),
        ],
        [("page_1", "table_1_row_1", "10"), ("page_3", "table_1_row_1", "4")],
        [("page_1", "table_1_row_2", "6"), ("page_3", "table_1_row_2", "8")],
    ]
    assert len(second["citations"]) == 4
    assert all(c["source_file"] == "operations.pdf" for c in second["citations"])
    # A full new question in the same chat cannot retain the old group population.
    absent = ask(
        world,
        "operations.pdf",
        "What is the quantity of Apple in the file ?",
        context_token=second["context_token"],
        **chat,
    )
    assert absent["status"] == "no_evidence" and not absent["records"]


def test_known_missing_and_unknown_followups_are_distinct(world):
    chat = conversation(world, "hours.xlsx")
    token = None
    for question, status, value in [
        ("Total Hours for Asha?", "answered", "15.75"),
        ("And Zenzee?", "no_evidence", None),
        ("And Ben?", "incomplete", None),
        ("And Asha?", "answered", "15.75"),
    ]:
        b = ask(world, "hours.xlsx", question, context_token=token, **chat)
        assert b["status"] == status, (question, b)
        assert (
            b["calculation"]["result"]["Hours"] if b["calculation"] else None
        ) == value
        token = b["context_token"]
    assert not world[1].llm.prompts


@pytest.mark.parametrize(
    "question",
    [
        "Total Quantity by Product and overall?",
        "Total Quantity for each product and overall?",
        "Total Quantity per Product?",
    ],
)
def test_schema_derived_breakdown_aliases(world, question):
    chat = conversation(world, "operations.pdf")
    first = ask(world, "operations.pdf", question, **chat)
    second = ask(
        world,
        "operations.pdf",
        "Use source records",
        context_token=first["context_token"],
        **chat,
    )
    labels = [g["label"] for g in second["grouped_results"]]
    assert labels == (
        ["Overall", "BOLT-A", "NUT-B"] if "overall" in question else ["BOLT-A", "NUT-B"]
    )


def test_name_breakdown_preserves_missing_and_zero(world):
    b = ask(world, "hours.xlsx", "Total Hours for each Name and overall?")
    assert b["status"] == "incomplete"
    assert [
        (
            g["label"],
            g["status"],
            g["calculation"]["result"] if g["calculation"] else None,
        )
        for g in b["grouped_results"]
    ] == [
        ("Overall", "incomplete", {"Hours": "15.75"}),
        ("Asha", "answered", {"Hours": "15.75"}),
        ("Ben", "incomplete", None),
    ]


def test_multiword_quoted_entity_and_ambiguous_identity(world):
    client, _, _ = world
    data = workbook(
        {"Table": [["Product", "Quantity", "Unit"], ["Apple in Bloom", 4, "pcs"]]}
    )
    assert (
        client.post("/documents", files={"file": ("quoted.xlsx", data)}).status_code
        == 201
    )
    b = ask(world, "quoted.xlsx", 'Quantity of "Apple in Bloom"?')
    assert b["status"] == "answered" and b["records"][0]["values"]["Quantity"] == "4"
    data = workbook(
        {
            "Table": [
                ["Product", "Customer", "Quantity", "Unit"],
                ["BOLT-A", "Asha", 4, "pcs"],
            ]
        }
    )
    assert (
        client.post("/documents", files={"file": ("ambiguous.xlsx", data)}).status_code
        == 201
    )
    b = ask(world, "ambiguous.xlsx", "Quantity for Apple?")
    assert (
        b["status"] == "clarification_required"
        and "Product" in b["answer"]
        and "Customer" in b["answer"]
    )
    assert not b["records"]


def test_per_product_record_question_does_not_invent_a_sum(world):
    b = ask(world, "operations.pdf", "What Quantity is recorded for each Product?")
    assert b["status"] == "answered" and b["calculation"] is None
    assert len(b["records"]) == 4 and not b["grouped_results"]


def test_aggregation_word_inside_literal_name_is_not_an_operation(world):
    client, _, _ = world
    data = workbook(
        {
            "Table": [
                ["Name", "Hours", "Unit"],
                ["Totally", 2, "hours"],
                ["Sum", 3, "hours"],
            ]
        }
    )
    assert (
        client.post("/documents", files={"file": ("literal.xlsx", data)}).status_code
        == 201
    )
    b = ask(world, "literal.xlsx", "What Hours are recorded for Totally?")
    assert b["status"] == "answered" and b["calculation"] is None
    b = ask(world, "literal.xlsx", "Sum Hours for Sum?")
    assert b["calculation"]["result"] == {"Hours": "3"}


@pytest.mark.parametrize(
    "name", ["The", "All", "Total", "Name", "Totally", "Pineapple"]
)
def test_quoted_unknown_names_never_disappear_as_grammar(world, name):
    b = ask(world, "operations.pdf", f'Quantity of "{name}" in the file?')
    assert b["status"] == "no_evidence" and name in b["answer"] and not b["records"]


def test_named_product_breakdown_does_not_add_other_product_groups(world):
    b = ask(world, "shipments.xlsx", "Total Quantity by Product for BOLT-A?")
    assert [(g["label"], g["calculation"]["result"]) for g in b["grouped_results"]] == [
        ("BOLT-A", {"Quantity": "24"})
    ]


def test_unlabelled_amount_remains_in_overall_without_becoming_a_named_product(world):
    client, _, _ = world
    data = workbook(
        {
            "Table": [
                ["Product", "Quantity", "Unit"],
                ["BOLT-A", 10, "pcs"],
                [None, 5, "pcs"],
                ["NUT-B", 2, "pcs"],
            ]
        }
    )
    assert (
        client.post("/documents", files={"file": ("unlabelled.xlsx", data)}).status_code
        == 201
    )
    b = ask(world, "unlabelled.xlsx", "Total Quantity for each Product and overall?")
    assert [(g["label"], g["calculation"]["result"]) for g in b["grouped_results"]] == [
        ("Overall", {"Quantity": "17"}),
        ("BOLT-A", {"Quantity": "10"}),
        ("NUT-B", {"Quantity": "2"}),
    ]
    assert any(
        c["entity"] is None and c["calculation"]["result"] == {"Quantity": "5"}
        for c in b["grouped_results"][0]["contributions"]
    )
    assert "Product not recorded" in b["answer"]
    b = ask(world, "unlabelled.xlsx", "Total Quantity for each Product?")
    assert b["status"] == "clarification_required" and b["calculation"] is None
