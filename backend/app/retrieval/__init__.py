# SPDX-License-Identifier: AGPL-3.0-only
"""Stage 6: Retriever -- embeds a query and returns ranked, citable
chunks from the vector store.

Author: Imitiyaz and AI Agent
Project: RAG MVP
Layer: Retrieval
"""

from __future__ import annotations

from app.retrieval.models import RetrievalResult
from app.retrieval.retriever import Retriever

__all__ = ["Retriever", "RetrievalResult"]
