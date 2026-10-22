# SPDX-License-Identifier: AGPL-3.0-only
"""Splits narrative (non-tabular) text into embeddable chunks.

Uses LangChain's RecursiveCharacterTextSplitter -- a well-tested
paragraph -> sentence -> word -> character fallback algorithm -- rather
than hand-rolling the same thing. Per docs/decisions/technology-stack.md,
LangChain is used here as a single, focused utility function, not as
deep pipeline orchestration -- consistent with "kept thin/modular, not a
black box."

Author: Imitiyaz and AI Agent
Project: RAG MVP
Layer: Chunking
"""

from __future__ import annotations

from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.chunking.models import Chunk
from app.models.cleaned import CleanedText
from app.models.extracted import SourceMetadata

DEFAULT_CHUNK_SIZE = 800
DEFAULT_CHUNK_OVERLAP = 100


def chunk_text_block(
    block: CleanedText,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
) -> list[Chunk]:
    """Splits one CleanedText block into one or more Chunks.

    If the block is already small enough to stay as one chunk, its
    citation metadata is unchanged. If it's split into multiple pieces,
    each piece's metadata gets a part suffix on row_or_location -- same
    convention as row_chunker's wide-row splitting -- so a citation can
    always distinguish "which part of this page" without implying a
    different page.
    """
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=["\n\n", "\n", ". ", " ", ""],
    )
    pieces = splitter.split_text(block.text)

    if len(pieces) <= 1:
        return [Chunk(text=block.text, metadata=block.metadata)]

    chunks = []
    for i, piece in enumerate(pieces, start=1):
        metadata = SourceMetadata(
            source_file=block.metadata.source_file,
            sheet_or_page=block.metadata.sheet_or_page,
            row_or_location=f"{block.metadata.row_or_location}_part{i}",
        )
        chunks.append(Chunk(text=piece, metadata=metadata))
    return chunks
