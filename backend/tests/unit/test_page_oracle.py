"""Actual UI payload replay and independent mutations. Author: Imitiyaz and AI Agent"""

from pathlib import Path

from fastapi.testclient import TestClient

from app.main import create_app
from tests.api_fakes import make_bundle
from tools.page_checks import page_mutations, run_page_cases


def test_page_oracle_rejects_corrupted_responses(tmp_path, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "upload_temp_dir", str(tmp_path / "uploads"))
    bundle = make_bundle()
    exchanges = []
    with TestClient(create_app(lambda: bundle.service)) as client:
        f = Path(__file__).resolve().parents[1] / "fixtures/acceptance/operations.pdf"
        assert (
            client.post(
                "/documents", files={"file": ("operations.pdf", f.read_bytes())}
            ).status_code
            == 201
        )
        samples = run_page_cases(
            client, lambda n, r, i, p: exchanges.append((n, r.status_code, i, p))
        )
    assert len(exchanges) == 15
    assert not [(n, i) for n, _, i, _ in exchanges if i]
    assert all(s == 200 for _, s, _, _ in exchanges)
    assert all(
        "aggregation_basis" not in p
        and "sheet_or_page" not in p
        and "group_field" not in p
        for *_, p in exchanges
    )
    assert all(page_mutations(samples).values())
    assert len(page_mutations(samples)) == 8
    assert not bundle.llm.prompts
