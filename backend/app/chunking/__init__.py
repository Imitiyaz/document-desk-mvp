# SPDX-License-Identifier: AGPL-3.0-only
"""Stage 3: Chunking. Public entrypoint is `chunk_document()`.

Author: Imitiyaz and AI Agent
Project: RAG MVP
Layer: Chunking
"""

from __future__ import annotations

from app.chunking.chunker import chunk_document
from app.chunking.models import Chunk

__all__ = ["chunk_document", "Chunk"]
