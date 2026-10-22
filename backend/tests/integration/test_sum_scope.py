"""User-reported SUM/scope sequence, with exact source sets and exclusion facts.

Author: Imitiyaz and AI Agent
Project: RAG MVP
Layer: Verification and synthetic fixtures
"""

from __future__ import annotations

import copy
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from tests.api_fakes import make_bundle
from tests.integration.test_mvp import workbook
from tools.presentation_checks import readable_findings


@pytest.fixture
def client(tmp_path, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "upload_temp_dir", str(tmp_path / "uploads"))
    bundle = make_bundle()
    with TestClient(create_app(lambda: bundle.service)) as api:
        path = Path(__file__).parents[1] / "fixtures/sample_sales_extended.xlsx"
        uploaded = api.post(
            "/documents", files={"file": (path.name, path.read_bytes())}
        )
        assert uploaded.status_code == 201
        yield api, bundle


def ask(api, question, **options):
    response = api.post(
        "/query",
        json={
            "source_file": "sample_sales_extended.xlsx",
            "question": question,
            **options,
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert readable_findings(body) == []
    return body


def session(api):
    source = api.get("/documents").json()[0]
    return api.post(
        "/conversations",
        json={
            "source_file": source["source_file"],
            "document_id": source["document_id"],
            "workspace_revision": source["workspace_revision"],
        },
    ).json()["conversation_id"]


def test_exact_user_sequence_confirms_all_records_then_changes_sheet_without_new_chat(
    client,
):
    api, bundle = client
    chat = session(api)
    first = ask(
        api,
        "What is the SUM of Q3 revenue in the file ?",
        conversation_id=chat,
        context_token=None,
    )
    assert first["status"] == "clarification_required"
    chosen = ask(
        api,
        "Use source records",
        conversation_id=chat,
        context_token=first["context_token"],
    )
    assert chosen["status"] == "incomplete"
    assert chosen["calculation"]["result"] == {"Q3 Revenue": "315000"}
    assert chosen["calculation"]["partial"] is True
    assert [o["number"] for o in chosen["calculation"]["operands"]] == [
        1,
        2,
        3,
        4,
        5,
        6,
        8,
        9,
    ]
    assert chosen["calculation"]["excluded_cells"] == [
        {
            "number": 7,
            "field": "Q3 Revenue",
            "cell": "B4",
            "reason": "missing_value",
            "source": {
                "source_file": "sample_sales_extended.xlsx",
                "sheet_or_page": "Sparse Data",
                "row_or_location": 4,
            },
        }
    ]
    assert len(chosen["records"]) == len(chosen["citations"]) == 9
    assert chosen["coverage"]["complete"] is False
    assert chosen["coverage"]["calculation_uses_all_matches"] is False
    assert chosen["answer"].startswith("Available-value subtotal Q3 Revenue: 315,000.")
    assert "not replaced with zero" in chosen["answer"]
    # Reproduce the old UI's stale refinement, not merely an isolated new question.
    merged = ask(
        api,
        "What was the Q3 revenue for north in Merged Region?",
        conversation_id=chat,
        context_token=chosen["context_token"],
        sheet_or_page="Sparse Data",
    )
    assert [r["values"]["Q3 Revenue"] for r in merged["records"]] == ["45000", "47000"]
    assert {r["sheet_or_page"] for r in merged["records"]} == {"Merged Region"}
    assert merged["coverage"]["resolved_scopes"] == ["Merged Region"]
    assert any("previous source refinement" in w for w in merged["warnings"])
    assert bundle.llm.prompts == []


def test_sparse_clarification_then_explicit_scope_followup_and_fresh_whole_file_question(
    client,
):
    api, _ = client
    chat = session(api)
    first = ask(
        api,
        "What is the SUM of Q3 revenue in the file ?",
        conversation_id=chat,
        context_token=None,
    )
    sparse = ask(
        api, "Sparse Data", conversation_id=chat, context_token=first["context_token"]
    )
    assert sparse["calculation"]["result"] == {"Q3 Revenue": "146000"}
    assert [o["number"] for o in sparse["calculation"]["operands"]] == [1, 2, 4, 5]
    assert sparse["calculation"]["excluded_cells"][0]["cell"] == "B4"
    assert sparse["coverage"]["resolved_scopes"] == ["Sparse Data"]
    merged = ask(
        api,
        "And Merged Region?",
        conversation_id=chat,
        context_token=sparse["context_token"],
    )
    assert merged["calculation"]["result"] == {"Q3 Revenue": "169000"}
    assert "Sparse Data" not in merged["resolved_question"]
    north = ask(
        api,
        "What was the Q3 revenue for North in Merged Region?",
        conversation_id=chat,
        context_token=merged["context_token"],
    )
    assert [r["values"]["Q3 Revenue"] for r in north["records"]] == ["45000", "47000"]
    south = ask(
        api, "And South?", conversation_id=chat, context_token=north["context_token"]
    )
    assert [r["values"]["Q3 Revenue"] for r in south["records"]] == ["38000", "39000"]
    broad = ask(
        api,
        "What was the Q3 revenue in the file ?",
        conversation_id=chat,
        context_token=south["context_token"],
        sheet_or_page="Merged Region",
    )
    assert len(broad["records"]) == 9 and broad["calculation"] is None
    assert broad["coverage"]["resolved_scopes"] == []


@pytest.mark.parametrize(
    "options",
    [{}, {"sheet_or_page": "Sparse Data"}, {"source_scopes": ["Sparse Data"]}],
)
def test_explicit_source_in_question_overrides_conflicting_request_constraints(
    client, options
):
    api, _ = client
    body = ask(api, "What was the Q3 revenue for north in Merged Region?", **options)
    assert [
        (r["sheet_or_page"], r["row_or_location"], r["values"]["Q3 Revenue"])
        for r in body["records"]
    ] == [("Merged Region", 2, "45000"), ("Merged Region", 3, "47000")]


@pytest.mark.parametrize(
    "question,scope,total",
    [
        ("SUM Q3 revenue for North in Merged Region", None, "92000"),
        ("SUM Q3 revenue for North", "Merged Region", "92000"),
        ("SUM Q3 revenue for North in the file", None, "175000"),
    ],
)
def test_explicit_north_sums_keep_record_basis_and_source_scope(
    client, question, scope, total
):
    api, _ = client
    body = ask(
        api,
        question,
        aggregation_basis="all_selected_records",
        **({"sheet_or_page": scope} if scope else {}),
    )
    assert body["calculation"]["result"] == {"Q3 Revenue": total}
    assert body["calculation"]["partial"] is False


@pytest.mark.parametrize(
    "values,result,status,excluded",
    [
        ([None, 0, -2, 2.25], "0.25", "incomplete", 1),
        ([None, None], None, "incomplete", 0),
        ([None, "N/A", 2], None, "clarification_required", 0),
        ([None, "USD 10", "EUR 20"], None, "clarification_required", 0),
        ([None, "10%", "20%"], None, "clarification_required", 0),
    ],
)
def test_missing_zero_negative_invalid_currency_and_rate_values_are_distinct(
    client, values, result, status, excluded
):
    api, _ = client
    data = workbook(
        {"Data": [["Key", "Amount"]] + [[str(i), v] for i, v in enumerate(values)]}
    )
    assert (
        api.post("/documents", files={"file": ("edges.xlsx", data)}).status_code == 201
    )
    response = api.post(
        "/query", json={"source_file": "edges.xlsx", "question": "SUM Amount"}
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == status
    if result is None:
        assert body["calculation"] is None
    else:
        assert body["calculation"]["result"] == {"Amount": result}
        assert len(body["calculation"]["excluded_cells"]) == excluded
        assert [o["values"]["Amount"] for o in body["calculation"]["operands"]] == [
            "0",
            "-2",
            "2.25",
        ]


def test_partial_calculation_keeps_off_page_exclusions_and_all_included_operands(
    client,
):
    api, _ = client
    rows = [["Key", "Amount"]] + [
        [str(i), None if i == 55 else i] for i in range(1, 101)
    ]
    assert (
        api.post(
            "/documents", files={"file": ("paged.xlsx", workbook({"Data": rows}))}
        ).status_code
        == 201
    )
    bodies = [
        api.post(
            "/query",
            json={"source_file": "paged.xlsx", "question": "SUM Amount", "page": page},
        ).json()
        for page in [1, 2]
    ]
    assert all(b["calculation"]["result"] == {"Amount": "4995"} for b in bodies)
    assert bodies[0]["calculation"] == bodies[1]["calculation"]
    assert len(bodies[0]["calculation"]["operands"]) == 99
    assert bodies[0]["calculation"]["excluded_cells"][0]["cell"] == "B56"
    assert 55 not in [r["number"] for r in bodies[0]["records"]]


@pytest.mark.parametrize(
    "fault",
    [
        "complete",
        "missing_exclusion",
        "zero_operand",
        "wrong_total",
        "wrong_exclusion_cell",
    ],
)
def test_partial_checker_rejects_invented_completeness_exclusions_or_operands(
    client, fault
):
    api, _ = client
    body = ask(api, "SUM Q3 revenue in Sparse Data")
    wrong = copy.deepcopy(body)
    if fault == "complete":
        wrong["calculation"]["partial"] = False
    elif fault == "missing_exclusion":
        wrong["calculation"]["excluded_cells"] = []
    elif fault == "zero_operand":
        wrong["calculation"]["operands"].append(
            {"number": 3, "values": {"Q3 Revenue": "0"}}
        )
    elif fault == "wrong_total":
        wrong["calculation"]["result"]["Q3 Revenue"] = "140100"
    else:
        wrong["calculation"]["excluded_cells"][0]["cell"] = "B9"
    assert readable_findings(wrong), fault
    from tools.sum_scope_oracle import validate_sequence_answer

    assert validate_sequence_answer(
        wrong, scopes=["Sparse Data"], calculate=True
    ), fault


def test_sum_these_records_uses_the_last_received_lookup_population(client):
    api, _ = client
    chat = session(api)
    north = ask(
        api,
        "What was the Q3 revenue for North?",
        conversation_id=chat,
        context_token=None,
    )
    body = ask(
        api,
        "Sum these records",
        conversation_id=chat,
        context_token=north["context_token"],
    )
    assert body["calculation"]["result"] == {"Q3 Revenue": "175000"}
    assert [o["values"]["Q3 Revenue"] for o in body["calculation"]["operands"]] == [
        "45000",
        "47000",
        "45000",
        "38000",
    ]
    sparse = ask(
        api, "Sparse Data", conversation_id=chat, context_token=body["context_token"]
    )
    assert sparse["calculation"]["result"] == {"Q3 Revenue": "83000"}
    assert {r["sheet_or_page"] for r in sparse["records"]} == {"Sparse Data"}


def test_combined_period_columns_with_a_missing_value_keep_known_cells_and_no_zero(
    client,
):
    api, _ = client
    rows = [
        ["Region", "Q3 Revenue", "Q4 Revenue"],
        ["North", 10, None],
        ["South", 20, 30],
    ]
    assert (
        api.post(
            "/documents", files={"file": ("periods.xlsx", workbook({"Data": rows}))}
        ).status_code
        == 201
    )
    response = api.post(
        "/query",
        json={
            "source_file": "periods.xlsx",
            "question": "Combined Q3 Revenue and Q4 Revenue",
            "aggregation_basis": "all_selected_records",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["calculation"]["result"] == {"Combined Revenue": "60"}
    assert body["calculation"]["operands"] == [
        {
            "number": 1,
            "values": {"Q3 Revenue": "10"},
            "source": {
                "source_file": "periods.xlsx",
                "sheet_or_page": "Data",
                "row_or_location": 2,
            },
            "cell_references": {"Q3 Revenue": "B2"},
        },
        {
            "number": 2,
            "values": {"Q3 Revenue": "20", "Q4 Revenue": "30"},
            "source": {
                "source_file": "periods.xlsx",
                "sheet_or_page": "Data",
                "row_or_location": 3,
            },
            "cell_references": {"Q3 Revenue": "B3", "Q4 Revenue": "C3"},
        },
    ]
    assert body["calculation"]["excluded_cells"][0]["cell"] == "C2"
    assert body["status"] == "incomplete"
    assert readable_findings(body) == []
