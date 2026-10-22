"""User-facing answer regressions against immutable original/source fixtures.

Author: Imitiyaz and AI Agent
Project: RAG MVP
Layer: Verification and synthetic fixtures
"""

from __future__ import annotations

import copy
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.generation.answer_presenter import answer_text
from app.main import create_app
from tests.api_fakes import make_bundle
from tools.presentation_checks import readable_findings


@pytest.fixture
def api(tmp_path, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "upload_temp_dir", str(tmp_path / "uploads"))
    bundle = make_bundle()
    with TestClient(create_app(lambda: bundle.service)) as client:
        for filename in [
            "sample_sales_extended.xlsx",
            "sample_sales.xlsx",
            "mvp/quarters.xlsx",
            "mvp/large.xlsx",
        ]:
            path = Path(__file__).parents[1] / "fixtures" / filename
            assert (
                client.post(
                    "/documents", files={"file": (path.name, path.read_bytes())}
                ).status_code
                == 201
            )
        yield client


def ask(api, question, source="sample_sales_extended.xlsx", **options):
    response = api.post(
        "/query", json={"question": question, "source_file": source, **options}
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert readable_findings(body) == []
    return body


@pytest.mark.parametrize(
    "question", ["What was the Q3 revenue?", "What was the Q3 revenue in the file ?"]
)
def test_both_user_broad_questions_return_readable_values_not_a_source_dump(
    api, question
):
    body = ask(api, question)
    assert body["answer"].startswith(
        "I found 9 Q3 Revenue records across 2 source sections."
    )
    assert "sample_sales_extended.xlsx" not in body["answer"]
    assert "/ row " not in body["answer"]
    assert body["status"] == "incomplete" and body["calculation"] is None
    items = [i for i in body["answer_items"] if i["kind"] == "record"]
    assert [i["text"] for i in items] == [
        "North — Q3 Revenue: 45,000",
        "North — Q3 Revenue: 47,000",
        "South — Q3 Revenue: 38,000",
        "South — Q3 Revenue: 39,000",
        "North — Q3 Revenue: 45,000",
        "North — Q3 Revenue: 38,000",
        "East — Q3 Revenue: Missing in source",
        "West — Q3 Revenue: 41,000",
        "West — Q3 Revenue: 22,000",
    ]
    assert [i["citation_numbers"] for i in items] == [[i] for i in range(1, 10)]
    assert [i["scope"] for i in items] == ["Merged Region"] * 4 + ["Sparse Data"] * 5
    assert body["coverage"]["missing_cells"] == [
        {"number": 7, "field": "Q3 Revenue", "cell": "B4"}
    ]
    assert "Total" not in body["answer"]
    assert body["evidence_text"].count("- sample_sales_extended.xlsx /") == 9


def test_north_answer_keeps_four_records_with_visible_continuation_notice(api):
    body = ask(api, "What was the Q3 revenue for north")
    assert body["answer"].startswith(
        "North has 4 recorded Q3 Revenue values across 2 source sections."
    )
    assert "no single value was selected" in body["answer"]
    assert "Region continuation rule applied" in body["answer"]
    items = [i for i in body["answer_items"] if i["kind"] == "record"]
    assert [i["text"] for i in items] == [
        "North — Q3 Revenue: 45,000",
        "North — Q3 Revenue: 47,000",
        "North — Q3 Revenue: 45,000",
        "North — Q3 Revenue: 38,000",
    ]
    assert [
        (r["sheet_or_page"], r["row_or_location"], r["cell_references"]["Q3 Revenue"])
        for r in body["records"]
    ] == [
        ("Merged Region", 2, "B2"),
        ("Merged Region", 3, "B3"),
        ("Sparse Data", 2, "B2"),
        ("Sparse Data", 3, "B3"),
    ]


@pytest.mark.parametrize(
    "question,source,expected,count",
    [
        (
            "Combined Q3 revenue for North, South, and East in Q3 Sales",
            "sample_sales.xlsx",
            "Total Q3 Revenue: 124,000.",
            3,
        ),
        (
            "Combined Revenue for North in Q3 Sales and Q4 Sales",
            "quarters.xlsx",
            "Total Revenue: 97,000 USD.",
            2,
        ),
        (
            "Combined Revenue for South in Q3 Sales and Q4 Sales",
            "quarters.xlsx",
            "Total Revenue: 78,000 USD.",
            2,
        ),
    ],
)
def test_totals_are_the_leading_answer_and_keep_every_operand(
    api, question, source, expected, count
):
    body = ask(api, question, source, top_k=1)
    assert body["answer"].startswith(expected)
    assert body["answer_items"][0]["citation_numbers"] == list(range(1, count + 1))
    assert len(body["calculation"]["operands"]) == count
    assert not any(i["kind"] == "record" for i in body["answer_items"])


def test_640_operand_answer_is_concise_and_identical_across_display_pages(api):
    first = ask(api, "Total Revenue", "large.xlsx", top_k=1)
    second = ask(api, "Total Revenue", "large.xlsx", top_k=1, page=2)
    assert first["answer"] == second["answer"]
    assert first["answer"].startswith("Total Revenue: 205,120.")
    assert len(first["answer"]) < 350
    assert first["answer_items"][0]["citation_numbers"] == list(range(1, 641))
    assert first["calculation"] == second["calculation"]
    assert second["records"][0]["cell_references"]["Revenue"] == "B52"
    assert second["coverage"]["returned_records"] == 50


def test_off_page_maximum_is_answered_and_cited_even_when_not_in_the_display_page(api):
    body = ask(api, "Maximum Revenue", "large.xlsx", top_k=1)
    assert body["answer"].startswith("Maximum Revenue: 640. [640]")
    assert "ORD-0640" in body["answer"]
    assert body["answer_items"][0]["citation_numbers"] == [640]
    assert 640 not in [r["number"] for r in body["records"]]
    assert len(body["calculation"]["operands"]) == 640


@pytest.mark.parametrize(
    "word,label,value", [("largest", "North", "7,000"), ("smallest", "South", "1,500")]
)
def test_comparison_leads_with_the_correct_winner_and_its_values(
    api, word, label, value
):
    body = ask(
        api,
        f"Among North, South, and East, which region had the {word} revenue increase from Q3 to Q4?",
        "sample_sales.xlsx",
    )
    assert body["answer"].startswith(f"{word.title()} increase: {label}.")
    assert f"{label} — increase: {value}." in body["answer"]
    assert {c["sheet_or_page"] for c in body["citations"]} == {"Q3 Sales"}


def test_wide_row_date_is_a_direct_answer_with_original_cell_reference(api):
    body = ask(api, "What is the renewal date for order ORD-1001 in Wide Row?")
    assert body["answer"] == "Wide Row\n- ORD-1001 — Renewal Date: 2027-01-15 [1]"
    assert body["records"][0]["cell_references"]["Renewal Date"] == "P2"


@pytest.mark.parametrize(
    "fault",
    ["amount", "label", "citation", "scope", "omitted_record", "invented_total"],
)
def test_checker_rejects_coherent_readable_corruptions_while_raw_evidence_stays_correct(
    api, fault
):
    from app.api.schemas import AnswerItem

    body = ask(api, "What was the Q3 revenue for North?")
    item = next(i for i in body["answer_items"] if i["kind"] == "record")
    if fault == "amount":
        item["text"] = item["text"].replace("45,000", "4,500")
    elif fault == "label":
        item["text"] = item["text"].replace("North", "South")
    elif fault == "citation":
        item["citation_numbers"] = [2]
    elif fault == "scope":
        item["scope"] = "Wrong sheet"
    elif fault == "omitted_record":
        body["answer_items"].remove(item)
    else:
        body["answer_items"].insert(
            0,
            {
                "kind": "calculation",
                "text": "Total Q3 Revenue: 315,000.",
                "citation_numbers": [1],
            },
        )
    body["answer"] = answer_text([AnswerItem(**i) for i in body["answer_items"]])
    assert readable_findings(body), fault


def test_checker_rejects_coherent_wrong_human_total_even_with_correct_calculation(api):
    from app.api.schemas import AnswerItem

    body = ask(
        api, "Combined Revenue for North in Q3 Sales and Q4 Sales", "quarters.xlsx"
    )
    wrong = copy.deepcopy(body)
    wrong["answer_items"][0]["text"] = "Total Revenue: 97,001 USD."
    wrong["answer"] = answer_text([AnswerItem(**i) for i in wrong["answer_items"]])
    assert readable_findings(wrong)
    assert wrong["calculation"]["result"] == {"Revenue": "97000"}
