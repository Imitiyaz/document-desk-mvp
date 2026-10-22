"""Real HTTP, real fixture parsing, actual pipeline wrappers; ML/DB backends injected.

Author: Imitiyaz and AI Agent
Project: RAG MVP
Layer: Verification and synthetic fixtures
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from io import BytesIO
from pathlib import Path

import fitz
import pytest
from fastapi.testclient import TestClient

from app.api.schemas import QueryRequest
from app.api.service import REFUSAL_RESPONSE
from app.core.config import settings
from app.core.exceptions import (
    DocumentAlreadyExistsError,
    EncryptedDocumentError,
    LLMConnectionError,
    LLMGenerationError,
    VectorStoreOperationError,
)
from app.main import create_app
from tests.api_fakes import ApiBundle, make_bundle


@pytest.fixture
def bundle(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[ApiBundle]:
    """Require every test owner to release its ledger, even without API startup."""
    monkeypatch.setattr(settings, "upload_temp_dir", str(tmp_path / "uploads"))
    value = make_bundle()
    try:
        yield value
    finally:
        try:
            with pytest.raises(sqlite3.ProgrammingError, match="closed database"):
                value.service._records.connection.execute("SELECT 1")
            assert value.llm.close_count == 1
        finally:
            # Also release resources when this regression assertion fails.
            if value.llm.close_count == 0:
                value.service.close()
            else:
                value.service._records.close()


@pytest.fixture
def client(bundle):
    with TestClient(
        create_app(lambda: bundle.service), raise_server_exceptions=False
    ) as value:
        yield value


def _upload(client, path: Path, name: str | None = None):
    return client.post(
        "/documents",
        files={
            "file": (name or path.name, path.read_bytes(), "application/octet-stream")
        },
    )


@pytest.mark.parametrize(
    "filename",
    [
        "sample_sales.xlsx",
        "sample_sales_extended.xlsx",
        "sample_report.pdf",
        "sample_report_extended.pdf",
    ],
)
def test_ingests_actual_fixtures_and_cleans_temporary_files(
    client, bundle, fixtures_dir, filename
) -> None:
    response = _upload(client, fixtures_dir / filename)
    assert response.status_code == 201, response.text
    data = response.json()
    assert data["source_file"] == filename
    assert data["size_bytes"] == (fixtures_dir / filename).stat().st_size
    assert data["chunks_stored"] == bundle.store.count() > 0
    assert bundle.llm.prompts == []
    assert data["extracted_rows"] > 0
    assert list(Path(settings.upload_temp_dir).iterdir()) == []
    assert all(m["source_file"] == filename for m in bundle.collection._metadatas)


def test_upload_query_preserves_excel_citations(
    client, bundle, sample_sales_xlsx
) -> None:
    assert _upload(client, sample_sales_xlsx).status_code == 201
    response = client.post(
        "/query",
        json={
            "question": "What was North Q3 revenue?",
            "source_file": sample_sales_xlsx.name,
            "top_k": 1,
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["records"][0]["values"]["Q3 Revenue"] == "45000"
    assert data["execution_path"] == "structured"
    assert data["model"] is None
    assert data["context_count"] == 1
    assert data["citations"][0]["source_file"] == sample_sales_xlsx.name
    assert data["citations"][0]["sheet_or_page"] == "Q3 Sales"
    assert data["citations"][0]["row_or_location"] == 2
    assert data["unresolved_citation_numbers"] == []
    assert bundle.llm.prompts == []


def test_pdf_query_preserves_string_location(client, sample_report_pdf) -> None:
    assert _upload(client, sample_report_pdf).status_code == 201
    response = client.post(
        "/query",
        json={
            "question": "North Q3 revenue",
            "source_file": sample_report_pdf.name,
            "top_k": 1,
        },
    )
    assert response.status_code == 200
    citation = response.json()["citations"][0]
    assert citation["sheet_or_page"] == "page_1"
    assert citation["row_or_location"] == "table_1_row_1"


@pytest.mark.parametrize(
    "question", ["What was total Q3 revenue?", "Which region had the strongest growth?"]
)
def test_accepts_aggregation_and_comparison_questions(
    client, bundle, sample_sales_xlsx, question
) -> None:
    _upload(client, sample_sales_xlsx)
    bundle.llm.text = "Controlled test answer (Source: [1]) (Source: [2]) (Source: [3])"
    response = client.post(
        "/query",
        json={"question": question, "source_file": sample_sales_xlsx.name, "top_k": 3},
    )
    assert response.status_code == 200
    # The available subtotal must not pretend the blank West value is zero.
    if "total" in question:
        assert response.json()["status"] == "incomplete"
        assert response.json()["calculation"]["result"] == {"Q3 Revenue": "124000"}
        assert response.json()["calculation"]["partial"] is True
        assert len(response.json()["calculation"]["operands"]) == 3
        assert response.json()["coverage"]["missing_cells"]
    else:
        assert response.json()["status"] in {"clarification_required", "evidence_only"}
    assert bundle.llm.prompts == []


def test_source_filter_prevents_cross_document_results(
    client, bundle, sample_sales_xlsx
) -> None:
    _upload(client, sample_sales_xlsx, "first.xlsx")
    _upload(client, sample_sales_xlsx, "second.xlsx")
    response = client.post(
        "/query",
        json={"question": "North revenue", "source_file": "second.xlsx", "top_k": 3},
    )
    assert response.status_code == 200
    assert all(c["source_file"] == "second.xlsx" for c in response.json()["citations"])
    assert bundle.llm.prompts == []


def test_duplicate_upload_never_changes_existing_index(
    client, bundle, sample_sales_xlsx
) -> None:
    _upload(client, sample_sales_xlsx)
    before = list(bundle.collection._documents)
    response = _upload(client, sample_sales_xlsx)
    assert response.status_code == 409
    assert response.json()["code"] == "document_exists"
    assert response.json()["status_code"] == response.status_code
    assert bundle.collection._documents == before
    assert list(Path(settings.upload_temp_dir).iterdir()) == []


@pytest.mark.parametrize(
    "name,status,code",
    [
        ("test.txt", 415, "unsupported_file_type"),
        ("test.xls", 415, "legacy_excel_format"),
        ("broken.pdf", 422, "corrupt_document"),
        ("broken.xlsx", 422, "corrupt_document"),
        ("../bad.pdf", 400, "invalid_filename"),
        ("NUL.xlsx", 400, "invalid_filename"),
    ],
)
def test_upload_errors_have_stable_shapes(client, bundle, name, status, code) -> None:
    response = client.post("/documents", files={"file": (name, b"invalid file")})
    assert response.status_code == status, response.text
    assert response.json()["code"] == code
    assert response.json()["status_code"] == response.status_code
    assert bundle.llm.prompts == []
    assert bundle.store.count() == 0
    assert (
        not Path(settings.upload_temp_dir).exists()
        or list(Path(settings.upload_temp_dir).iterdir()) == []
    )
    assert settings.upload_temp_dir not in response.text


def test_empty_upload_rejected(client) -> None:
    response = client.post("/documents", files={"file": ("empty.pdf", b"")})
    assert response.status_code == 422
    assert response.json()["code"] == "empty_document"


def test_image_only_or_blank_pdf_has_no_usable_content(client, bundle) -> None:
    with fitz.open() as document:
        document.new_page()
        content = document.tobytes()
    response = client.post("/documents", files={"file": ("blank.pdf", content)})
    assert response.status_code == 422
    assert response.json()["code"] == "empty_document"
    assert bundle.store.count() == 0


def test_encrypted_loader_error_maps_to_422(
    client, bundle, monkeypatch, sample_report_pdf
) -> None:
    from app.loaders.pdf_loader import PdfLoader

    def reject(self, file_path):
        raise EncryptedDocumentError("protected")

    monkeypatch.setattr(PdfLoader, "load", reject)
    response = _upload(client, sample_report_pdf)
    assert response.status_code == 422
    assert response.json()["code"] == "encrypted_document"


def test_file_limit_checked_and_partial_upload_removed(bundle, monkeypatch) -> None:
    monkeypatch.setattr(settings, "max_upload_bytes", 4)
    with TestClient(create_app(lambda: bundle.service)) as client:
        response = client.post(
            "/documents", files={"file": ("a.pdf", BytesIO(b"12345"))}
        )
    assert response.status_code == 413
    assert response.json()["code"] == "upload_too_large"
    assert response.json()["status_code"] == response.status_code
    assert bundle.llm.prompts == []
    assert list(Path(settings.upload_temp_dir).iterdir()) == []


def test_declared_body_limit_rejects_before_parsing(bundle, monkeypatch) -> None:
    monkeypatch.setattr(settings, "max_upload_bytes", 4)
    with TestClient(create_app(lambda: bundle.service)) as client:
        response = client.post(
            "/documents", content=b"", headers={"Content-Length": str(1024 * 1024 + 5)}
        )
    assert response.status_code == 413
    assert not Path(settings.upload_temp_dir).exists()
    assert response.json()["status_code"] == 413
    assert bundle.llm.prompts == []


def test_streamed_body_limit_works_without_content_length(bundle, monkeypatch) -> None:
    monkeypatch.setattr(settings, "max_upload_bytes", 4)
    with TestClient(create_app(lambda: bundle.service)) as client:
        response = client.post(
            "/query",
            content=iter([b"x" * (1024 * 1024 + 5)]),
            headers={"Content-Type": "application/json"},
        )
    assert response.status_code == 413, response.text
    assert response.json()["code"] == "upload_too_large"


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"question": ""},
        {"question": " \n "},
        {"question": "x", "top_k": 0},
        {"question": "x", "top_k": 101},
        {"question": "x", "top_k": True},
        {"question": "x", "top_k": 1.5},
        {"question": "x", "min_score": 2},
        {"question": "x", "source_file": "../a.pdf"},
        {"question": "x", "unknown": True},
    ],
)
def test_invalid_query_does_not_reach_pipeline(client, bundle, body) -> None:
    response = client.post("/query", json=body)
    assert response.status_code == 422
    assert response.json()["code"] == "validation_error"
    assert response.json()["status_code"] == 422
    assert response.json()["details"]
    assert bundle.llm.prompts == []


def test_unknown_source_is_distinct_from_empty_retrieval(client, bundle) -> None:
    response = client.post(
        "/query", json={"question": "North revenue", "source_file": "unknown.xlsx"}
    )
    assert response.status_code == 404
    assert response.json()["code"] == "document_not_found"
    assert response.json()["status_code"] == 404
    assert bundle.llm.prompts == []


def test_empty_index_refuses_without_calling_llm(client, bundle) -> None:
    bundle.llm.error = LLMConnectionError("down")
    response = client.post("/query", json={"question": "What was the revenue?"})
    assert response.status_code == 200
    assert response.json()["answer"] == REFUSAL_RESPONSE
    assert response.json()["model"] is None
    assert response.json()["context_count"] == 0
    assert response.json()["citations"] == []
    assert bundle.llm.prompts == []


def test_min_score_can_return_no_context(client, bundle, sample_sales_xlsx) -> None:
    _upload(client, sample_sales_xlsx)
    response = client.post(
        "/query",
        json={
            "question": "North South East",
            "source_file": sample_sales_xlsx.name,
            "min_score": 0.99,
        },
    )
    assert response.status_code == 200
    assert response.json()["context_count"] == 0
    assert bundle.llm.prompts == []


@pytest.mark.parametrize(
    "error,status,code",
    [
        (LLMConnectionError("down"), 503, "llm_unavailable"),
        (LLMGenerationError("model missing"), 502, "llm_generation_failed"),
        (RuntimeError("secret internal path"), 500, "internal_error"),
    ],
)
def test_generation_errors_remain_distinct(
    client, bundle, sample_sales_xlsx, error, status, code
) -> None:
    _upload(client, sample_sales_xlsx)
    bundle.llm.error = error
    bundle.service._structured_answers = (
        False  # isolated historical adapter/error contract
    )
    response = client.post("/query", json={"question": "North revenue"})
    assert response.status_code == status
    assert response.json()["code"] == code
    assert "secret internal path" not in response.text
    assert response.json()["status_code"] == status


def test_real_fixture_wide_date_fragment_retains_order_identity(
    client, bundle, sample_sales_extended_xlsx
):
    assert _upload(client, sample_sales_extended_xlsx).status_code == 201
    date_fragments = [
        t for t in bundle.collection._documents if "Renewal Date is 2027-01-15" in t
    ]
    assert len(date_fragments) == 1
    assert "Order ID is ORD-1001" in date_fragments[0]
    assert bundle.llm.prompts == []


def test_unresolved_citations_are_returned_visibly(
    client, bundle, sample_sales_xlsx
) -> None:
    _upload(client, sample_sales_xlsx)
    bundle.service._structured_answers = False  # raw-model citation diagnostic
    bundle.llm.text = "45000 (Source: [1]) [999] [999]"
    response = client.post("/query", json={"question": "North revenue", "top_k": 1})
    assert response.status_code == 200
    assert response.json()["unresolved_citation_numbers"] == [999]
    assert len(response.json()["citations"]) == 1


def test_one_service_per_lifespan_and_close_on_exit(bundle) -> None:
    calls = []

    def factory():
        calls.append(True)
        return bundle.service

    app = create_app(factory)
    assert calls == []
    with TestClient(app) as client:
        assert client.get("/health").json() == {"status": "ok"}
        assert client.get("/ready").json() == {"status": "ready"}
        assert client.get("/openapi.json").status_code == 200
        assert len(calls) == 1
        assert bundle.llm.close_count == 0
    assert bundle.llm.close_count == 1
    assert app.state.pipeline_service is None


def test_readiness_is_unavailable_without_lifespan(bundle: ApiBundle) -> None:
    try:
        # closing() releases HTTP resources without entering the app lifespan.
        with closing(TestClient(create_app(lambda: bundle.service))) as client:
            assert client.get("/health").status_code == 200
            assert client.get("/ready").status_code == 503
    finally:
        bundle.service.close()


def test_cors_includes_errors(client) -> None:
    response = client.post(
        "/query", json={}, headers={"Origin": "http://localhost:5173"}
    )
    assert response.status_code == 422
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"


def test_partial_index_failure_rolls_back_only_new_source(
    bundle: ApiBundle, monkeypatch: pytest.MonkeyPatch, sample_sales_xlsx: Path
) -> None:
    try:
        bundle.service.ingest(sample_sales_xlsx, sample_sales_xlsx.stat().st_size)
        before = list(bundle.collection._documents)
        original = bundle.collection.upsert

        def fail(ids, embeddings, documents, metadatas):
            original(ids[:1], embeddings[:1], documents[:1], metadatas[:1])
            raise RuntimeError("write interrupted")

        monkeypatch.setattr(bundle.collection, "upsert", fail)
        # Same fixture under another name represents a separate document.
        from tempfile import TemporaryDirectory

        with TemporaryDirectory() as directory:
            renamed = Path(directory) / "new.xlsx"
            renamed.write_bytes(sample_sales_xlsx.read_bytes())
            with pytest.raises(
                VectorStoreOperationError, match="partial records were removed"
            ):
                bundle.service.ingest(renamed, renamed.stat().st_size)
        assert bundle.collection._documents == before
        assert not bundle.store.has_source_file("new.xlsx")
    finally:
        bundle.service.close()


def test_index_inspection_failure_is_503(client, bundle, monkeypatch) -> None:
    def fail(**kwargs):
        raise RuntimeError("database problem")

    monkeypatch.setattr(bundle.collection, "get", fail)
    response = client.post("/query", json={"question": "x", "source_file": "a.xlsx"})
    assert response.status_code == 503
    assert response.json()["code"] == "index_operation_failed"


def test_simultaneous_duplicate_ingestions_have_one_winner(
    bundle: ApiBundle, sample_sales_xlsx: Path
) -> None:
    try:

        def ingest():
            try:
                bundle.service.ingest(
                    sample_sales_xlsx, sample_sales_xlsx.stat().st_size
                )
                return "stored"
            except DocumentAlreadyExistsError:
                return "duplicate"

        with ThreadPoolExecutor(max_workers=2) as pool:
            outcomes = list(pool.map(lambda _: ingest(), range(2)))
        assert sorted(outcomes) == ["duplicate", "stored"]
    finally:
        bundle.service.close()


def test_query_question_is_preserved_verbatim() -> None:
    assert QueryRequest(question="  North revenue?\n").question == "  North revenue?\n"


def test_store_query_failure_maps_to_503(
    client, bundle, monkeypatch, sample_sales_xlsx
) -> None:
    def fail(**kwargs):
        raise RuntimeError("index read failed")

    _upload(client, sample_sales_xlsx)
    monkeypatch.setattr(bundle.collection, "query", fail)
    response = client.post("/query", json={"question": "Summarize the document"})
    assert response.status_code == 503
    assert response.json()["code"] == "index_operation_failed"


def test_new_loader_registration_requires_no_api_format_change(
    client, monkeypatch
) -> None:
    from app.loaders import _REGISTERED_LOADERS
    from app.loaders.base import BaseLoader
    from app.models.extracted import ExtractedDocument, ExtractedRow, SourceMetadata

    class FutureLoader(BaseLoader):
        supported_extensions = frozenset({".future"})

        def supports(self, file_path: Path) -> bool:
            return file_path.suffix == ".future"

        def load(self, file_path: Path) -> ExtractedDocument:
            return ExtractedDocument(
                source_file=file_path.name,
                rows=[
                    ExtractedRow(
                        {"Value": file_path.read_text()},
                        SourceMetadata(file_path.name, "record", 1),
                    )
                ],
            )

    monkeypatch.setattr(
        "app.loaders._REGISTERED_LOADERS", [*_REGISTERED_LOADERS, FutureLoader()]
    )
    response = client.post(
        "/documents", files={"file": ("sample.future", b"North revenue")}
    )
    assert response.status_code == 201
    assert response.json()["source_file"] == "sample.future"
    assert ".future" in client.get("/capabilities").json()["supported_extensions"]


def test_cleanup_failure_is_explicit(
    client, bundle, monkeypatch, sample_sales_xlsx
) -> None:
    def fail(*args, **kwargs):
        raise RuntimeError("storage unavailable")

    monkeypatch.setattr(bundle.collection, "upsert", fail)
    monkeypatch.setattr(bundle.collection, "delete", fail)
    response = _upload(client, sample_sales_xlsx)
    assert response.status_code == 503
    assert "index needs repair" in response.json()["message"]
    assert list(Path(settings.upload_temp_dir).iterdir()) == []


def test_record_mode_uses_selected_source_rows_and_not_model_values(
    client, bundle, fixtures_dir
) -> None:
    assert (
        _upload(client, fixtures_dir / "sample_sales_extended.xlsx").status_code == 201
    )
    question = (
        "What Q3 revenue values are recorded for North in the Merged Region sheet?"
    )
    results = bundle.service._retriever.retrieve(
        question, source_file="sample_sales_extended.xlsx", top_k=100
    )
    numbers = [
        i
        for i, r in enumerate(results, 1)
        if r.metadata.sheet_or_page == "Merged Region"
        and r.metadata.row_or_location in {2, 3}
    ]
    import json

    bundle.llm.text = json.dumps({"record_citations": list(reversed(numbers))})
    response = client.post(
        "/query",
        json={
            "question": question,
            "source_file": "sample_sales_extended.xlsx",
            "top_k": 100,
            "answer_mode": "records",
        },
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["answer"].index("45,000") < data["answer"].index("47,000")
    assert [c["row_or_location"] for c in data["citations"]] == [2, 3]
    assert data["unresolved_citation_numbers"] == []


def test_record_mode_invalid_model_output_returns_explicit_502(
    client, bundle, sample_sales_xlsx
) -> None:
    _upload(client, sample_sales_xlsx)
    bundle.service._structured_answers = (
        False  # historical record-selection validation only
    )
    bundle.llm.text = '{"record_citations": [999]}'
    response = client.post(
        "/query",
        json={
            "question": "Each matching North record",
            "answer_mode": "records",
        },
    )
    assert response.status_code == 502
    assert response.json()["status_code"] == 502
    assert response.json()["code"] == "invalid_record_selection"


def test_unknown_answer_mode_is_rejected_without_generation(client, bundle) -> None:
    response = client.post("/query", json={"question": "North", "answer_mode": "guess"})
    assert response.status_code == 422
    assert bundle.llm.prompts == []


def test_capabilities_reflect_registered_loaders_and_actual_upload_budget(
    client, monkeypatch
) -> None:
    from app.core.config import settings

    monkeypatch.setattr(settings, "max_upload_bytes", 12345)
    response = client.get("/capabilities")
    assert response.status_code == 200
    assert response.json() == {
        "supported_extensions": [".pdf", ".xlsm", ".xlsx"],
        "max_upload_bytes": 12345,
    }
