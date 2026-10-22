# SPDX-License-Identifier: AGPL-3.0-only
"""Stage 3 orchestrator: `chunk_document()` composes row-aware table
chunking and recursive prose chunking into the one uniform list[Chunk]
that Stage 4 (Embedding) consumes.

Author: Imitiyaz and AI Agent
Project: RAG MVP
Layer: Chunking
"""

from __future__ import annotations

from loguru import logger

from app.chunking.models import Chunk
from app.chunking.prose_chunker import chunk_text_block
from app.chunking.row_chunker import chunk_rows
from app.models.cleaned import CleanedDocument


def chunk_document(document: CleanedDocument) -> list[Chunk]:
    """Chunks a CleanedDocument (Stage 2 output) into Stage 4's input."""
    chunks: list[Chunk] = chunk_rows(document.rows)

    for block in document.text_blocks:
        chunks.extend(chunk_text_block(block))

    logger.info(
        "{}: produced {} chunk(s) from {} row(s) and {} text block(s)",
        document.source_file,
        len(chunks),
        len(document.rows),
        len(document.text_blocks),
    )

    if not chunks:
        logger.warning(
            "{}: produced zero chunks -- check whether cleaning was too "
            "aggressive or the source document had no real content",
            document.source_file,
        )

    return chunks
