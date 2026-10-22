# SPDX-License-Identifier: AGPL-3.0-only
"""Stage 2: Cleaning. Public entrypoint is `clean_document()`.

Author: Imitiyaz and AI Agent
Project: RAG MVP
Layer: Cleaning
"""

from __future__ import annotations

from app.cleaning.cleaner import clean_document

__all__ = ["clean_document"]
