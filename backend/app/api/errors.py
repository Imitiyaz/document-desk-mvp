# SPDX-License-Identifier: AGPL-3.0-only
"""Exception-to-HTTP mapping shared by all routes, without leaking internal paths.

Author: Imitiyaz and AI Agent
Project: RAG MVP
Layer: Api
"""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from loguru import logger
from starlette.exceptions import HTTPException
from starlette.responses import JSONResponse

from app.api.schemas import ErrorResponse, ValidationIssue
from app.core.exceptions import (
    CorruptFileError,
    DocumentAlreadyExistsError,
    DocumentNotFoundError,
    EmbeddingModelLoadError,
    EmptyDocumentError,
    EncryptedDocumentError,
    ExtractionLimitError,
    InvalidFilenameError,
    InvalidRecordSelectionError,
    LegacyExcelFormatError,
    LLMConnectionError,
    LLMGenerationError,
    ReindexRequiredError,
    StaleWorkspaceError,
    UnsupportedFileTypeError,
    UnsupportedLayoutError,
    UploadTooLargeError,
    VectorStoreConnectionError,
    VectorStoreOperationError,
)

_ERRORS: dict[type[Exception], tuple[int, str, str | None]] = {
    StaleWorkspaceError: (409, "stale_workspace", None),
    UnsupportedLayoutError: (422, "unsupported_layout", None),
    ExtractionLimitError: (413, "extraction_limit", None),
    ReindexRequiredError: (409, "reindex_required", None),
    InvalidRecordSelectionError: (
        502,
        "invalid_record_selection",
        "The model returned an invalid record selection. Retry the request.",
    ),
    InvalidFilenameError: (400, "invalid_filename", None),
    DocumentNotFoundError: (404, "document_not_found", None),
    DocumentAlreadyExistsError: (409, "document_exists", None),
    UploadTooLargeError: (413, "upload_too_large", None),
    UnsupportedFileTypeError: (
        415,
        "unsupported_file_type",
        "No loader supports this document type.",
    ),
    LegacyExcelFormatError: (
        415,
        "legacy_excel_format",
        "Re-save the legacy Excel file as .xlsx before uploading.",
    ),
    CorruptFileError: (
        422,
        "corrupt_document",
        "The document could not be parsed. Check that it is a valid, undamaged file.",
    ),
    EncryptedDocumentError: (
        422,
        "encrypted_document",
        "Upload an unencrypted copy of the document.",
    ),
    EmptyDocumentError: (422, "empty_document", None),
    EmbeddingModelLoadError: (
        503,
        "embedding_unavailable",
        "The embedding model is unavailable.",
    ),
    VectorStoreConnectionError: (
        503,
        "index_unavailable",
        "The document index is unavailable.",
    ),
    VectorStoreOperationError: (503, "index_operation_failed", None),
    LLMConnectionError: (
        503,
        "llm_unavailable",
        "Ollama is unavailable or did not respond in time.",
    ),
    LLMGenerationError: (
        502,
        "llm_generation_failed",
        "Ollama rejected the generation request. Check its model configuration.",
    ),
}


async def pipeline_error(request: Request, exc: Exception) -> JSONResponse:
    """Map known pipeline exceptions; log the underlying detail server-side."""
    status, code, message = next(
        _ERRORS[cls] for cls in type(exc).__mro__ if cls in _ERRORS
    )
    logger.warning("{} {}: {}: {}", request.method, request.url.path, code, exc)
    return JSONResponse(
        status_code=status,
        content=ErrorResponse(
            status_code=status, code=code, message=message or str(exc)
        ).model_dump(),
    )


async def validation_error(request: Request, exc: Exception) -> JSONResponse:
    """Describe invalid fields without echoing the original request content."""
    assert isinstance(exc, RequestValidationError)
    details = [
        ValidationIssue(location=list(e["loc"]), message=e["msg"], kind=e["type"])
        for e in exc.errors()
    ]
    return JSONResponse(
        status_code=422,
        content=ErrorResponse(
            status_code=422,
            code="validation_error",
            message="The request did not match the API schema.",
            details=details,
        ).model_dump(),
    )


async def http_error(request: Request, exc: Exception) -> JSONResponse:
    """Normalize routing, middleware and readiness HTTP errors."""
    assert isinstance(exc, HTTPException)
    code = "upload_too_large" if exc.status_code == 413 else "http_error"
    return JSONResponse(
        status_code=exc.status_code,
        headers=exc.headers,
        content=ErrorResponse(
            status_code=exc.status_code, code=code, message=str(exc.detail)
        ).model_dump(),
    )


async def unexpected_error(request: Request, exc: Exception) -> JSONResponse:
    """Keep unexpected failures observable without returning internal details."""
    logger.opt(exception=exc).error(
        "Unexpected failure for {} {}", request.method, request.url.path
    )
    return JSONResponse(
        status_code=500,
        content=ErrorResponse(
            status_code=500,
            code="internal_error",
            message="The request could not be completed. Check the server logs.",
        ).model_dump(),
    )


def register_error_handlers(app: FastAPI) -> None:
    """Install the same error contract for every router."""
    for exception_type in _ERRORS:
        app.add_exception_handler(exception_type, pipeline_error)
    app.add_exception_handler(RequestValidationError, validation_error)
    app.add_exception_handler(HTTPException, http_error)
    app.add_exception_handler(Exception, unexpected_error)
