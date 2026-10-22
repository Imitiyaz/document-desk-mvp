# SPDX-License-Identifier: AGPL-3.0-only
"""Centralized logging configuration using loguru.

Call `configure_logging()` once, at process startup (application entrypoint
or the top of a test session) -- not from every module independently.
This is what satisfies the project's "meaningful, structured logging"
standard: every module just does `from loguru import logger` and logs,
and this file controls format/level/destination in exactly one place.

Author: Imitiyaz and AI Agent
Project: RAG MVP
Layer: Core
"""

from __future__ import annotations

import sys

from loguru import logger

from app.core.config import settings

_configured = False


def configure_logging() -> None:
    """Configure loguru's sink with the project's log level and format.

    Idempotent -- safe to call multiple times (e.g., once per test module)
    without producing duplicate log lines.
    """
    global _configured
    if _configured:
        return

    logger.remove()  # remove loguru's default handler first, to avoid duplicates
    logger.add(
        sys.stderr,
        level=settings.log_level,
        format=(
            "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
            "<level>{level: <8}</level> | "
            "<cyan>{name}</cyan>:<cyan>{function}</cyan> - <level>{message}</level>"
        ),
    )
    _configured = True
