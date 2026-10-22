"""Unit tests for app.core.logging_config.

Mainly verifies idempotency (calling configure_logging() multiple times
doesn't add duplicate handlers) since that's the one behavior this
module needs to get right.

Author: Imitiyaz and AI Agent
Project: RAG MVP
Layer: Verification and synthetic fixtures
"""

from __future__ import annotations

from loguru import logger

import app.core.logging_config as logging_config_module
from app.core.logging_config import configure_logging


def test_configure_logging_is_idempotent() -> None:
    # Reset module-level state so this test is independent of test order.
    logging_config_module._configured = False
    logger.remove()

    configure_logging()
    handler_count_after_first_call = len(logger._core.handlers)  # type: ignore[attr-defined]

    configure_logging()  # calling again should not add a second handler
    handler_count_after_second_call = len(logger._core.handlers)  # type: ignore[attr-defined]

    assert handler_count_after_first_call == handler_count_after_second_call
    assert handler_count_after_first_call >= 1
