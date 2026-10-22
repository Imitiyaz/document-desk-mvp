# SPDX-License-Identifier: AGPL-3.0-only
"""The Stage 5 query-result contract: what comes back from a similarity
search against the vector store.

Author: Imitiyaz and AI Agent
Project: RAG MVP
Layer: Vectorstore
"""

from __future__ import annotations

from dataclasses import dataclass

from app.models.extracted import SourceMetadata


@dataclass(frozen=True)
class RetrievedMatch:
    """One result from a vector store query.

    `distance` follows ChromaDB's convention for cosine space: smaller
    is more similar (0 = identical direction). Stage 6 (Retriever) is
    responsible for turning this into whatever ranking/threshold logic
    it needs -- this type just carries the raw result faithfully.
    """

    text: str
    metadata: SourceMetadata
    distance: float
