"""Optional smoke test: sends a real assembled prompt to a real, locally
running Ollama instance and prints the raw response for manual
inspection.

This is explicitly NOT a Stage 7 completion requirement -- per this
project's scope decision, Stage 7 is prompt assembly only, and the real
Ollama client wrapper (retries, error handling) is Stage 8's named
deliverable. This test exists purely as an early, optional look at how
the assembled prompt behaves against the real model, using a plain
`httpx` call rather than pulling in the `ollama` package before its
designated stage. Marked `ollama`, excluded from the default run;
skips itself gracefully (not a failure) if Ollama isn't reachable.

Run explicitly with:
    pytest -m ollama -v

Author: Imitiyaz and AI Agent
Project: RAG MVP
Layer: Verification and synthetic fixtures
"""

from __future__ import annotations

import httpx
import pytest

from app.core.config import settings
from app.generation import RECOMMENDED_TEMPERATURE, build_prompt
from app.models.extracted import SourceMetadata
from app.retrieval.models import RetrievalResult

pytestmark = pytest.mark.ollama


def _ollama_is_reachable() -> bool:
    try:
        response = httpx.get(
            f"{settings.ollama_base_url}/api/tags", timeout=2.0, trust_env=False
        )
        return response.status_code == 200
    except httpx.HTTPError:
        return False


def test_real_ollama_answers_using_the_assembled_prompt() -> None:
    if not _ollama_is_reachable():
        pytest.skip(
            f"Ollama not reachable at {settings.ollama_base_url} -- this is an "
            "optional smoke test, not a Stage 7 requirement. Start Ollama and "
            "re-run with `pytest -m ollama -v` to actually exercise it."
        )

    # Hand-built context, standing in for a real Retriever result -- this
    # test's job is "does the real model behave sensibly given OUR
    # prompt shape," not "does retrieval work" (that's Stage 6's job,
    # already verified).
    results = [
        RetrievalResult(
            text="In 'Q3 Sales': Region is North; Q3 Revenue is 45000; Q4 Revenue is 52000.",
            metadata=SourceMetadata(
                source_file="sample_sales.xlsx",
                sheet_or_page="Q3 Sales",
                row_or_location=2,
            ),
            score=0.85,
            rank=1,
        )
    ]
    prompt = build_prompt("What was the Q3 revenue for the North region?", results)

    response = httpx.post(
        f"{settings.ollama_base_url}/api/generate",
        json={
            "model": settings.ollama_model,
            "prompt": prompt.text,
            "stream": False,
            "options": {"temperature": RECOMMENDED_TEMPERATURE},
        },
        timeout=60.0,
    )
    response.raise_for_status()
    answer = response.json()["response"]

    print(f"\n--- Real Ollama response ---\n{answer}\n--- end response ---\n")

    # Deliberately loose assertions -- this is a smoke test for "did
    # something sensible come back," not a strict answer-quality
    # evaluation. Real evaluation against the full question set is
    # Stage 8's job, once the LLM client wrapper exists.
    assert answer.strip()
    assert "45000" in answer or "45,000" in answer
