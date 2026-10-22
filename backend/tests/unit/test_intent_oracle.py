"""Focused runner checks ordinary requests and rejects corrupted real API bodies.

Author: Imitiyaz and AI Agent
"""

from __future__ import annotations

import copy

from fastapi.testclient import TestClient

from app.main import create_app
from tests.api_fakes import make_bundle
from tools.intent_oracle import findings
from tools.verify_intent import mutation_checks, run_cases


def test_focused_http_runner_and_adversarial_oracle(tmp_path, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "upload_temp_dir", str(tmp_path / "uploads"))
    bundle = make_bundle()
    exchanges = []
    with TestClient(create_app(lambda: bundle.service)) as client:
        samples = run_cases(
            client,
            lambda name, response, issues, payload: exchanges.append(
                (name, response.status_code, issues, payload)
            ),
        )
    assert not any(x[2] for x in exchanges)
    assert sum(name == "grouped_pdf" for name, *_ in exchanges) == 1
    assert all(
        "entity_groups" not in (p or {}) and "group_field" not in (p or {})
        for *_, p in exchanges
    )
    assert all(mutation_checks(samples).values())
    assert len(mutation_checks(samples)) == 10
    assert not bundle.llm.prompts
    for kind, source in [
        ("grouped_pdf", "operations.pdf"),
        ("asha", "hours.xlsx"),
        ("subtotal", "hours.xlsx"),
    ]:
        original = samples[kind]["body"]
        assert findings(kind, original, source) == []
        damaged = copy.deepcopy(original)
        damaged["coverage"]["fields"] = ["Wrong metric"]
        assert findings(kind, damaged, source)
    damaged = copy.deepcopy(samples["grouped_pdf"]["body"])
    damaged["grouped_results"][1]["record_numbers"] = [2, 4]
    assert findings("grouped_pdf", damaged, "operations.pdf")
