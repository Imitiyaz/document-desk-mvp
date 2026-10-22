"""Unit tests for app.cleaning.header_footer.

Author: Imitiyaz and AI Agent
Project: RAG MVP
Layer: Verification and synthetic fixtures
"""

from __future__ import annotations

from app.cleaning.header_footer import detect_repeated_lines, strip_repeated_lines
from app.models.extracted import ExtractedText, SourceMetadata


def _text_block(text: str, page: int) -> ExtractedText:
    return ExtractedText(
        text=text,
        metadata=SourceMetadata(
            source_file="test.pdf",
            sheet_or_page=f"page_{page}",
            row_or_location="full_page_text",
        ),
    )


def test_detect_repeated_lines_finds_line_on_every_page() -> None:
    blocks = [
        _text_block("Confidential\nPage content one", 1),
        _text_block("Confidential\nPage content two", 2),
        _text_block("Confidential\nPage content three", 3),
    ]
    repeated = detect_repeated_lines(blocks)
    assert "Confidential" in repeated
    assert "Page content one" not in repeated


def test_detect_repeated_lines_requires_minimum_page_count() -> None:
    # Only 2 pages -- below the default min_pages=3, so nothing is flagged
    # even though "Confidential" appears on both.
    blocks = [
        _text_block("Confidential\nContent A", 1),
        _text_block("Confidential\nContent B", 2),
    ]
    repeated = detect_repeated_lines(blocks)
    assert repeated == set()


def test_detect_repeated_lines_respects_frequency_threshold() -> None:
    blocks = [
        _text_block("Header\nContent A", 1),
        _text_block("Header\nContent B", 2),
        _text_block("Content C only", 3),  # no "Header" here
        _text_block("Content D only", 4),
    ]
    # "Header" appears on 2/4 pages = 50%, below the default 60% threshold
    repeated = detect_repeated_lines(blocks, min_pages=3, frequency_threshold=0.6)
    assert "Header" not in repeated


def test_detect_repeated_lines_ignores_blank_lines() -> None:
    blocks = [
        _text_block("\n\nContent A", 1),
        _text_block("\n\nContent B", 2),
        _text_block("\n\nContent C", 3),
    ]
    repeated = detect_repeated_lines(blocks)
    assert repeated == set()  # blank lines never counted as "repeated content"


def test_strip_repeated_lines_removes_matching_lines() -> None:
    text = "Confidential\nReal content here\nConfidential"
    result = strip_repeated_lines(text, {"Confidential"})
    assert result == "Real content here"


def test_strip_repeated_lines_no_op_when_no_repeated_lines_given() -> None:
    text = "Some content"
    assert strip_repeated_lines(text, set()) == text


def test_detect_repeated_lines_recognizes_page_numbered_footer() -> None:
    # Regression test for a real bug found via Stage 6's fixture-coverage
    # review: a footer like "Page 1"/"Page 2"/"Page 3" never matched
    # itself exactly across pages, so it was never recognized as a
    # repeated footer at all. See docs/pipeline.md's
    # fourth extraction and cleaning policy.
    blocks = [
        _text_block("Report\nContent A\nAcme Corp - Page 1", 1),
        _text_block("Report\nContent B\nAcme Corp - Page 2", 2),
        _text_block("Report\nContent C\nAcme Corp - Page 3", 3),
    ]
    repeated = detect_repeated_lines(blocks)
    assert "Acme Corp - Page 1" in repeated
    assert "Acme Corp - Page 2" in repeated
    assert "Acme Corp - Page 3" in repeated
    assert "Content A" not in repeated


def test_detect_repeated_lines_ignores_coincidental_repetition_in_page_body() -> None:
    # Regression test for a real false-positive bug found via Stage 6's
    # fixture-coverage review: two DIFFERENT tables on different pages
    # that coincidentally share a cell value ("North") were being
    # treated as document-wide header/footer noise and silently
    # deleted, even though "North" was genuine, page-specific table
    # data, not a running header. See docs/pipeline.md's
    # fifth extraction and cleaning policy. Real headers/footers live at a
    # page's top/bottom edge; "North" here is deep in the page body
    # (position 10 of 12 lines), well outside the default edge zone.
    body_padding = "\n".join(f"Body line {i}" for i in range(1, 6))
    tail_padding = "\n".join(f"Tail line {i}" for i in range(1, 6))
    blocks = [
        _text_block(
            f"Report Title\n{body_padding}\nNorth\n{tail_padding}\nEnd of page", 1
        ),
        _text_block(
            f"Different Title\n{body_padding}\nNorth\n{tail_padding}\nEnd of page", 2
        ),
        _text_block(
            f"Another Title\n{body_padding}\nNorth\n{tail_padding}\nEnd of page", 3
        ),
    ]
    repeated = detect_repeated_lines(blocks)
    assert "North" not in repeated
    # "End of page" IS within the edge zone (last line) and IS genuinely
    # repeated across all 3 pages -- confirms the zone restriction isn't
    # over-broad, only content outside the zone is excluded.
    assert "End of page" in repeated


def test_detect_repeated_lines_still_finds_header_within_edge_zone() -> None:
    # Confirms the edge-zone restriction doesn't accidentally break the
    # original, already-working case -- a real header positioned at the
    # very top of the page (well within the default edge zone) is still
    # detected normally.
    blocks = [
        _text_block("Confidential\nPage content one", 1),
        _text_block("Confidential\nPage content two", 2),
        _text_block("Confidential\nPage content three", 3),
    ]
    repeated = detect_repeated_lines(blocks)
    assert "Confidential" in repeated
