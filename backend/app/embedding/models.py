# SPDX-License-Identifier: AGPL-3.0-only
"""The Stage 4 -> Stage 5 contract: a Chunk with its embedding vector
attached.

Author: Imitiyaz and AI Agent
Project: RAG MVP
Layer: Embedding
"""

from __future__ import annotations

from dataclasses import dataclass

from app.models.extracted import SourceMetadata


@dataclass(frozen=True)
class EmbeddedChunk:
    """A Chunk plus the vector Stage 5 (ChromaDB) will index it by.

    `vector` is a plain `list[float]`, not a numpy array -- keeps this
    type trivially serializable (JSON, ChromaDB's API) without every
    caller needing to know about numpy.
    """

    text: str
    metadata: SourceMetadata
    vector: list[float]
