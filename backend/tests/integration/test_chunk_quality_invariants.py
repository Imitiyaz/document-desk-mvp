"""Generic 'chunk quality invariant' test: a property every chunk's
rendered text should satisfy, regardless of which fixture produced it.

This exists because every real bug found so far in this pipeline
(docs/pipeline.md's extraction and cleaning policyes) shares a
pattern: the existing automated tests checked structural properties
(counts, substrings) but nothing ever asserted "does this rendered text
actually look clean" -- a human had to eyeball printed output to catch
any of them. This test checks the SHAPE of that problem generically,
across every fixture, rather than re-verifying one specific past
instance of it. It doesn't need to know what a "table value" is, or
require a table to have been successfully detected as structured rows
at all -- which is exactly why it would have caught the borderless-table
symptom (extraction and cleaning policy) even before that bug was understood.

Author: Imitiyaz and AI Agent
Project: RAG MVP
Layer: Verification and synthetic fixtures
"""

from __future__ import annotations

from pathlib import Path

from app.chunking import Chunk, chunk_document
from app.cleaning import clean_document
from app.loaders import get_loader_for_file

ALL_FIXTURES = [
    "sample_sales.xlsx",
    "sample_report.pdf",
    "sample_sales_extended.xlsx",
    "sample_report_extended.pdf",
]

MAX_CONSECUTIVE_BARE_LINES = 2
BARE_LINE_MAX_LENGTH = 15


def _is_bare_line(line: str) -> bool:
    """A raw, un-rendered table fragment reads as a short line with no
    spaces (a single cell's worth of content: "North", "45000", "12%").
    Genuine narrative prose in these fixtures is never this short and
    word-count-of-one at the same time.
    """
    return len(line) < BARE_LINE_MAX_LENGTH and " " not in line


def _longest_consecutive_bare_run(text: str) -> int:
    longest = 0
    current = 0
    for line in text.split("\n"):
        stripped = line.strip()
        if not stripped:
            continue
        current = current + 1 if _is_bare_line(stripped) else 0
        longest = max(longest, current)
    return longest


def _chunks_for_fixture(fixtures_dir: Path, filename: str) -> list[Chunk]:
    file_path = fixtures_dir / filename
    document = get_loader_for_file(file_path).load(file_path)
    cleaned = clean_document(document)
    return chunk_document(cleaned)


def test_no_chunk_has_a_long_run_of_bare_short_lines(fixtures_dir: Path) -> None:
    for filename in ALL_FIXTURES:
        for chunk in _chunks_for_fixture(fixtures_dir, filename):
            worst_run = _longest_consecutive_bare_run(chunk.text)
            assert worst_run <= MAX_CONSECUTIVE_BARE_LINES, (
                f"{filename} {chunk.metadata.sheet_or_page}/"
                f"{chunk.metadata.row_or_location}: chunk text has "
                f"{worst_run} consecutive bare short lines -- looks like "
                f"a leaked raw table dump, not rendered prose:\n{chunk.text}"
            )


def test_longest_consecutive_bare_run_helper_detects_a_synthetic_leak() -> None:
    """Confirms the detection helper itself actually works, using a
    synthetic reproduction of the exact shape extraction and cleaning policy #2
    found in real PyMuPDF output -- independent of whether any current
    fixture happens to still trigger it.
    """
    leaked_text = (
        "Quarterly Regional Sales Report\n"
        "This report summarizes regional sales performance.\n"
        "Region\nQ3 Revenue\nQ4 Revenue\nNorth\n45000\n52000"
    )
    assert _longest_consecutive_bare_run(leaked_text) > MAX_CONSECUTIVE_BARE_LINES


def test_longest_consecutive_bare_run_helper_allows_clean_prose() -> None:
    clean_text = (
        "Quarterly Regional Sales Report\n"
        "This report summarizes regional sales performance for the third "
        "quarter, driven primarily by strong performance in the North region."
    )
    assert _longest_consecutive_bare_run(clean_text) == 0
