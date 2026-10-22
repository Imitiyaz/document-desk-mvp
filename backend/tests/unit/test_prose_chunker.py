"""Unit tests for app.chunking.prose_chunker.

Author: Imitiyaz and AI Agent
Project: RAG MVP
Layer: Verification and synthetic fixtures
"""

from __future__ import annotations

from app.chunking.prose_chunker import chunk_text_block
from app.models.cleaned import CleanedText
from app.models.extracted import SourceMetadata


def _text_block(text: str) -> CleanedText:
    return CleanedText(
        text=text,
        metadata=SourceMetadata(
            source_file="test.pdf",
            sheet_or_page="page_1",
            row_or_location="full_page_text",
        ),
    )


def test_chunk_text_block_returns_single_chunk_for_short_text() -> None:
    block = _text_block("A short paragraph that fits in one chunk easily.")
    chunks = chunk_text_block(block)
    assert len(chunks) == 1
    assert chunks[0].text == block.text
    assert chunks[0].metadata == block.metadata  # unchanged, no part suffix


def test_chunk_text_block_splits_long_text_into_multiple_pieces() -> None:
    long_text = " ".join(f"Sentence number {i} in a long document." for i in range(200))
    block = _text_block(long_text)
    chunks = chunk_text_block(block, chunk_size=200, chunk_overlap=20)
    assert len(chunks) > 1


def test_chunk_text_block_multi_piece_chunks_get_part_suffix_metadata() -> None:
    long_text = " ".join(f"Sentence number {i} in a long document." for i in range(200))
    block = _text_block(long_text)
    chunks = chunk_text_block(block, chunk_size=200, chunk_overlap=20)
    for i, chunk in enumerate(chunks, start=1):
        assert chunk.metadata.source_file == "test.pdf"
        assert chunk.metadata.sheet_or_page == "page_1"
        assert chunk.metadata.row_or_location == f"full_page_text_part{i}"


def test_chunk_text_block_pieces_stay_within_chunk_size_budget() -> None:
    long_text = " ".join(f"Sentence number {i} in a long document." for i in range(200))
    block = _text_block(long_text)
    chunks = chunk_text_block(block, chunk_size=200, chunk_overlap=20)
    # Allow a little slack since the splitter respects word/sentence
    # boundaries rather than cutting exactly at chunk_size.
    for chunk in chunks:
        assert len(chunk.text) <= 250


def test_chunk_text_block_handles_empty_text() -> None:
    block = _text_block("")
    chunks = chunk_text_block(block)
    assert len(chunks) == 1
    assert chunks[0].text == ""
