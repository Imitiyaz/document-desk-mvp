# SPDX-License-Identifier: AGPL-3.0-only
"""FastAPI entrypoint: import is cheap; real models are loaded in lifespan.

Author: Imitiyaz and AI Agent
Project: RAG MVP
Layer: Main
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.concurrency import run_in_threadpool

from app.api.errors import register_error_handlers
from app.api.middleware import RequestBodyLimitMiddleware
from app.api.routes import router
from app.api.service import PipelineService, create_pipeline_service
from app.core.config import settings
from app.core.logging_config import configure_logging


def create_app(
    service_factory: Callable[[], PipelineService] = create_pipeline_service,
) -> FastAPI:
    """Construct an app with replaceable resources for isolated HTTP tests."""

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        """Own startup/shutdown resources without loading models at module import."""
        configure_logging()
        service = await run_in_threadpool(service_factory)
        application.state.pipeline_service = service
        try:
            yield
        finally:
            application.state.pipeline_service = None
            await run_in_threadpool(service.close)

    application = FastAPI(title="Tabular RAG MVP", version="0.3.8", lifespan=lifespan)
    register_error_handlers(application)
    # Allow 1 MiB for multipart boundaries and small form headers above the
    # per-file limit. Count actual bytes even without Content-Length.
    application.add_middleware(
        RequestBodyLimitMiddleware, max_bytes=settings.max_upload_bytes + 1024 * 1024
    )
    application.add_middleware(
        CORSMiddleware,
        allow_origins=[
            s.strip() for s in settings.cors_allowed_origins.split(",") if s.strip()
        ],
        allow_methods=["GET", "POST", "DELETE"],
        allow_headers=["Content-Type", "X-Workspace-Revision"],
    )
    application.include_router(router)
    return application


app = create_app()
