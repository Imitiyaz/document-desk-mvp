# SPDX-License-Identifier: AGPL-3.0-only
"""Stage 4: Embedding. Public exports: Embedder, EmbeddedChunk.

Author: Imitiyaz and AI Agent
Project: RAG MVP
Layer: Embedding
"""

from __future__ import annotations

from app.embedding.embedder import Embedder
from app.embedding.models import EmbeddedChunk

__all__ = ["Embedder", "EmbeddedChunk"]
