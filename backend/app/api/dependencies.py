# SPDX-License-Identifier: AGPL-3.0-only
"""FastAPI dependency access to resources constructed by application lifespan.

Author: Imitiyaz and AI Agent
Project: RAG MVP
Layer: Api
"""

from __future__ import annotations

from fastapi import HTTPException, Request

from app.api.service import PipelineService


def get_pipeline_service(request: Request) -> PipelineService:
    """Return the initialized service, or an explicit unavailable response."""
    service = getattr(request.app.state, "pipeline_service", None)
    if not isinstance(service, PipelineService):
        raise HTTPException(status_code=503, detail="The pipeline is not initialized.")
    return service
