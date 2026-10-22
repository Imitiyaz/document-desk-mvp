"""Focused real-Ollama presentation checks; API runner separately checks retrieval.

Author: Imitiyaz and AI Agent
Project: RAG MVP
Layer: Verification and synthetic fixtures
"""

from __future__ import annotations

from pathlib import Path

import httpx
import pytest

from app.chunking import chunk_document
from app.cleaning import clean_document
from app.core.config import settings
from app.generation import LLMClient, build_prompt, resolve_citations
from app.loaders import get_loader_for_file
from app.retrieval.models import RetrievalResult
from tools.answer_checks import check_fixture_answer


@pytest.mark.ollama
@pytest.mark.parametrize(
    "case,filename,question",
    [
        (
            "total",
            "sample_sales.xlsx",
            "What is the combined Q3 revenue for North, South, and East in the Q3 Sales sheet?",
        ),
        (
            "comparison",
            "sample_sales.xlsx",
            "Among North, South, and East, which region had the largest revenue increase from Q3 to Q4, and how much was the increase?",
        ),
        (
            "merged",
            "sample_sales_extended.xlsx",
            "What Q3 revenue values are recorded for North in the Merged Region sheet? Report each matching record separately with its citation.",
        ),
        (
            "wide",
            "sample_sales_extended.xlsx",
            "What is the renewal date for order ORD-1001 in the Wide Row sheet?",
        ),
    ],
)
def test_real_presentation(
    case: str, filename: str, question: str, fixtures_dir: Path
) -> None:
    try:
        if (
            httpx.get(
                settings.ollama_base_url + "/api/tags", timeout=2, trust_env=False
            ).status_code
            != 200
        ):
            pytest.skip(
                "Ollama is not reachable; real answer quality remains unverified."
            )
    except httpx.HTTPError:
        pytest.skip("Ollama is not reachable; real answer quality remains unverified.")
    file = fixtures_dir / filename
    chunks = chunk_document(clean_document(get_loader_for_file(file).load(file)))
    # Reverse source rows to ensure source-order instructions are not simply
    # copying the context order. Include notes so wrong-sheet citations can fail.
    results = [
        RetrievalResult(c.text, c.metadata, 0.9, i)
        for i, c in enumerate(reversed(chunks), 1)
    ]
    client = LLMClient()
    try:
        answer = resolve_citations(
            client.generate(
                build_prompt(
                    question,
                    results,
                    answer_mode="records" if case == "merged" else "prose",
                )
            )
        )
    finally:
        client.close()
    body = {
        "answer": answer.text,
        "unresolved_citation_numbers": answer.unresolved_citation_numbers,
        "citations": [
            {
                "number": c.number,
                "sheet_or_page": c.metadata.sheet_or_page,
                "row_or_location": c.metadata.row_or_location,
            }
            for c in answer.citations
        ],
    }
    assert check_fixture_answer(case, body) == [], body
