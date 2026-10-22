# SPDX-License-Identifier: AGPL-3.0-only
"""The Stage 3 -> Stage 4 contract: a single, uniform Chunk type.

Unlike Extracted/Cleaned (which split into Row vs Text depending on
source), chunking produces one uniform shape regardless of whether a
chunk originated from a table row or narrative text -- Stage 4
(Embedding) treats every chunk identically, embedding `.text` and
carrying `.metadata` through to the vector store untouched.

Author: Imitiyaz and AI Agent
Project: RAG MVP
Layer: Chunking
"""

from __future__ import annotations

from dataclasses import dataclass

from app.models.extracted import SourceMetadata


@dataclass(frozen=True)
class Chunk:
    """One embeddable unit of text, with the citation metadata it traces
    back to. Immutable (frozen) -- a chunk's identity is its exact text
    plus its source; nothing downstream should ever need to mutate one.
    """

    text: str
    metadata: SourceMetadata
