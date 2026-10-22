# SPDX-License-Identifier: AGPL-3.0-only
"""Bound request bodies before multipart parsing can spool an unlimited upload.

Author: Imitiyaz and AI Agent
Project: RAG MVP
Layer: Api
"""

from __future__ import annotations

from starlette.exceptions import HTTPException
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send


class RequestBodyLimitMiddleware:
    """Cap declared and streamed bytes; file size is checked separately by the route."""

    def __init__(self, app: ASGIApp, max_bytes: int) -> None:
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        if scope.get("method") == "POST" and scope.get("path") == "/documents":
            service = getattr(
                getattr(scope.get("app"), "state", None), "pipeline_service", None
            )
            if service is not None:
                scope.setdefault("state", {})[
                    "ingestion_revision"
                ] = service.received_revision
        headers = dict(scope.get("headers", []))
        try:
            declared = int(headers.get(b"content-length", b"0"))
        except ValueError:
            declared = 0  # streamed count still enforces the budget
        if declared > self.max_bytes:
            response = JSONResponse(
                status_code=413,
                content={
                    "status_code": 413,
                    "code": "upload_too_large",
                    "message": "Request body exceeds the upload budget.",
                    "details": [],
                },
            )
            await response(scope, receive, send)
            return
        # Headers are only an early rejection; the stream remains the authoritative byte count.
        total = 0

        async def limited_receive() -> Message:
            """Enforce actual streamed bytes even when Content-Length is absent or false."""
            nonlocal total
            message = await receive()
            if message["type"] == "http.request":
                total += len(message.get("body", b""))
                if total > self.max_bytes:
                    raise HTTPException(
                        status_code=413,
                        detail="Request body exceeds the upload budget.",
                    )
            return message

        await self.app(scope, limited_receive, send)
