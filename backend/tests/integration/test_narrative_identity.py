"""Wrong-subject regressions use real generation wrappers and independent facts.
Author: Imitiyaz and AI Agent
"""

from __future__ import annotations

import json

import pytest

from app.api.schemas import QueryRequest
from app.generation.entity_guard import requested_anchors, subject_passage
from app.generation.grounded import narrative_answer
from tests.api_fakes import make_bundle


def document(text: str) -> dict:
    return {
        "rows": [],
        "text_blocks": [
            {
                "sheet_or_page": "page_4",
                "row_or_location": "full_page_text",
                "text": text,
            }
        ],
    }


@pytest.mark.parametrize(
    "name",
    [
        "Rose",
        "rose",
        "Aster",
        "aster",
        "Juniper",
        "Juniper-42",
        "Zenzee",
        '"Blue Harbour"',
    ],
)
def test_unknown_named_subject_never_returns_another_projects_facts(name):
    bundle = make_bundle()
    try:
        bundle.llm.text = json.dumps(
            {
                "claims": [
                    {"source": 1, "quote": "Orchid production launch is not approved."}
                ]
            }
        )
        response = narrative_answer(
            QueryRequest(
                question=f"Is {name} production launch approved and when is the next review?"
            ),
            "operations.pdf",
            document(
                "Orchid production launch is not approved. The next review is scheduled for 2026-11-03."
            ),
            [],
            bundle.service._llm,
        )
        assert response.status == "no_evidence"
        assert not response.citations and response.context_count == 0
        assert "2026-11-03" not in response.answer and "Orchid" not in response.answer
        assert not bundle.llm.prompts
    finally:
        bundle.service.close()


@pytest.mark.parametrize("name", ["Orchid", "Aster", "Juniper", "Larch", "Maple"])
def test_matching_subject_preserves_negation_date_and_page(name):
    bundle = make_bundle()
    try:
        fact = f"{name} production launch is not approved."
        date = "The next review is scheduled for 2026-11-03."
        bundle.llm.text = json.dumps(
            {"claims": [{"source": 1, "quote": fact}, {"source": 1, "quote": date}]}
        )
        response = narrative_answer(
            QueryRequest(
                question=f"Is {name} production launch approved and when is the next review?"
            ),
            "operations.pdf",
            document(fact + " " + date),
            [],
            bundle.service._llm,
        )
        assert response.status == "answered"
        assert fact in response.answer and date in response.answer
        assert [(c.sheet_or_page, c.row_or_location) for c in response.citations] == [
            ("page_4", "full_page_text")
        ]
    finally:
        bundle.service.close()


def test_mixed_project_page_does_not_leak_other_subject_or_date():
    bundle = make_bundle()
    try:
        text = "Orchid production launch is not approved. The next review is scheduled for 2026-11-03. Rose production launch is approved. The next review is scheduled for 2026-12-08."
        bundle.llm.text = json.dumps(
            {
                "claims": [
                    {"source": 1, "quote": "Orchid production launch is not approved."}
                ]
            }
        )
        response = narrative_answer(
            QueryRequest(
                question="Is Rose production launch approved and when is the next review?"
            ),
            "operations.pdf",
            document(text),
            [],
            bundle.service._llm,
        )
        assert response.status == "evidence_only"
        assert "Orchid" not in response.answer and "2026-11-03" not in response.answer
        assert (
            "Rose production launch is approved." in response.answer
            and "2026-12-08" in response.answer
        )
    finally:
        bundle.service.close()


def test_empty_model_selection_abstains_instead_of_claiming_answered():
    bundle = make_bundle()
    try:
        bundle.llm.text = '{"claims":[]}'
        response = narrative_answer(
            QueryRequest(question="Summarize the document"),
            "x.pdf",
            document("The shipment is delayed."),
            [],
            bundle.service._llm,
        )
        assert response.status == "no_evidence" and not response.citations
    finally:
        bundle.service.close()


def test_literal_names_have_word_boundaries_and_no_invented_aliases():
    anchors = requested_anchors("Is Rose production launch approved?")
    assert not subject_passage("Rosemary production launch is approved.", anchors)
    assert not subject_passage("Project R production launch is approved.", anchors)
    assert subject_passage("Rose production launch is approved.", anchors)


@pytest.mark.parametrize(
    "question",
    [
        "Is Rose production launch approved and when is the next review?",
        "Is rose production launch approved and when is the next review?",
    ],
)
def test_unknown_subject_through_actual_upload_and_http_routes(
    question, tmp_path, monkeypatch
):
    from pathlib import Path

    from fastapi.testclient import TestClient

    from app.core.config import settings
    from app.main import create_app

    monkeypatch.setattr(settings, "upload_temp_dir", str(tmp_path / "uploads"))
    bundle = make_bundle()
    fixture = Path(__file__).parents[1] / "fixtures/acceptance/operations.pdf"
    with TestClient(create_app(lambda: bundle.service)) as client:
        uploaded = client.post(
            "/documents",
            files={"file": ("operations.pdf", fixture.read_bytes(), "application/pdf")},
        )
        assert uploaded.status_code == 201
        response = client.post(
            "/query", json={"question": question, "source_file": "operations.pdf"}
        )
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "no_evidence" and body["citations"] == []
        assert "Orchid" not in body["answer"] and "2026-11-03" not in body["answer"]
        assert not bundle.llm.prompts
