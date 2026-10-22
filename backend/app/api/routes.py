# SPDX-License-Identifier: AGPL-3.0-only
"""HTTP endpoints; expensive synchronous work runs in FastAPI's worker thread pool.

Author: Imitiyaz and AI Agent
Project: RAG MVP
Layer: Api
"""

from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Annotated, Any

from fastapi import APIRouter, Depends, File, Header, Query, Request, UploadFile

from app.api.dependencies import get_pipeline_service
from app.api.schemas import (
    ConversationRequest,
    ErrorResponse,
    HealthResponse,
    IngestionResponse,
    QueryRequest,
    QueryResponse,
)
from app.api.service import PipelineService
from app.api.uploads import save_upload, validate_filename
from app.core.config import settings
from app.loaders import get_loader_for_file, supported_extensions

router = APIRouter()
ServiceDependency = Annotated[PipelineService, Depends(get_pipeline_service)]
_ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    code: {"model": ErrorResponse}
    for code in (400, 404, 409, 413, 415, 422, 500, 502, 503)
}


@router.get("/health", response_model=HealthResponse, tags=["health"])
def health() -> HealthResponse:
    """Process liveness only; does not contact Ollama or prove model quality."""
    return HealthResponse(status="ok")


@router.get(
    "/ready", response_model=HealthResponse, tags=["health"], responses=_ERROR_RESPONSES
)
def ready(service: ServiceDependency) -> HealthResponse:
    """Confirms the embedding/index service was initialized, not Ollama availability."""
    return HealthResponse(status="ready")


@router.post(
    "/documents",
    status_code=201,
    response_model=IngestionResponse,
    tags=["documents"],
    responses=_ERROR_RESPONSES,
)
def ingest_document(
    service: ServiceDependency,
    request: Request,
    file: Annotated[
        UploadFile, File(description="A document handled by the loader registry")
    ],
    workspace_revision: Annotated[
        int | None, Header(alias="X-Workspace-Revision", ge=0)
    ] = None,
) -> IngestionResponse:
    """Wait for indexing; temporary copies are removed on success and failure."""
    filename = validate_filename(file.filename)
    # Registry dispatch, never a second hardcoded format list in the API.
    get_loader_for_file(Path(filename))
    temp_root = Path(settings.upload_temp_dir)
    temp_root.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix="ingest-", dir=temp_root) as directory:
        path = Path(directory) / filename
        size_bytes = save_upload(file.file, path, settings.max_upload_bytes)
        return service.ingest(
            path,
            size_bytes,
            expected_revision=(
                workspace_revision
                if workspace_revision is not None
                else getattr(
                    request.state, "ingestion_revision", service.received_revision
                )
            ),
        )


@router.post(
    "/query", response_model=QueryResponse, tags=["query"], responses=_ERROR_RESPONSES
)
def query_documents(request: QueryRequest, service: ServiceDependency) -> QueryResponse:
    """Answer lookup, aggregation or comparison questions through the existing pipeline."""
    return service.query(request)


@router.get("/documents", tags=["documents"], responses=_ERROR_RESPONSES)
def list_documents(service: ServiceDependency) -> list[dict[str, Any]]:
    """List persistent source identities and schema choices for question scope."""
    return service.documents()


@router.get("/capabilities", tags=["documents"])
def capabilities() -> dict[str, Any]:
    """Expose actual format capabilities and upload budget to clients."""
    return {
        "supported_extensions": supported_extensions(),
        "max_upload_bytes": settings.max_upload_bytes,
    }


@router.get("/workspace", tags=["workspace"])
def workspace_state(service: ServiceDependency) -> dict:
    """Return the persistent workspace generation."""
    return service.workspace()


@router.delete(
    "/documents/{source_file}", tags=["documents"], responses=_ERROR_RESPONSES
)
def remove_document(
    source_file: str, service: ServiceDependency, document_id: str | None = None
) -> dict:
    """Remove one document's ledger and vector entries, with stale-ID protection."""
    return service.remove_document(validate_filename(source_file), document_id)


@router.delete("/workspace", tags=["workspace"], responses=_ERROR_RESPONSES)
def reset_workspace(
    service: ServiceDependency, revision: Annotated[int, Query(ge=0)]
) -> dict:
    """Reset managed data, requiring a current generation."""
    return service.reset_workspace(revision)


@router.post("/conversations", tags=["conversation"], responses=_ERROR_RESPONSES)
def new_conversation(request: ConversationRequest, service: ServiceDependency) -> dict:
    """Start a short-lived session on one ready document version."""
    return service.start_conversation(
        request.source_file, request.document_id, request.workspace_revision
    )


@router.delete("/conversations/{conversation_id}", tags=["conversation"])
def clear_conversation(conversation_id: str, service: ServiceDependency) -> dict:
    """Forget session constraints without deleting indexed sources."""
    return service.end_conversation(conversation_id)
