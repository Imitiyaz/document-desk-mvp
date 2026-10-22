# SPDX-License-Identifier: AGPL-3.0-only
"""Detects and strips repeated running headers/footers from PDF narrative
text -- lines like a document title, page number, or "Confidential" stamp
that appear near-identically on nearly every page, and are noise rather
than content for retrieval purposes.

Author: Imitiyaz and AI Agent
Project: RAG MVP
Layer: Cleaning
"""

from __future__ import annotations

import re

from app.cleaning.text_cleaning import normalize_whitespace
from app.models.extracted import ExtractedText

DEFAULT_MIN_PAGES = 3
DEFAULT_FREQUENCY_THRESHOLD = 0.6
DEFAULT_EDGE_ZONE_LINES = 3

_DIGIT_RUN_PATTERN = re.compile(r"\d+")


def _normalize_for_repetition_grouping(line: str) -> str:
    """Collapses digit runs to a placeholder so a page-numbered footer
    ("Page 1", "Page 2", "Page 3") is recognized as the SAME repeating
    line across pages, rather than three different one-off lines that
    each happen to appear on only a single page. Used only for grouping
    and counting -- the original literal line text is still what
    ultimately gets matched and removed by strip_repeated_lines(), so
    each literal digit variant is preserved individually in the
    returned set, not replaced by the placeholder.
    """
    return _DIGIT_RUN_PATTERN.sub("#", line)


def _lines_in_edge_zone(text: str, edge_zone_lines: int) -> list[str]:
    """Returns this page's non-blank lines, restricted to the first and
    last `edge_zone_lines` lines -- the zone where a genuine running
    header/footer actually lives, as opposed to a page's main body
    content. Short pages (too few lines for the zones to be meaningful)
    return every line unrestricted.
    """
    all_lines = [line for line in text.split("\n") if line.strip()]
    if len(all_lines) <= edge_zone_lines * 2:
        return all_lines
    return all_lines[:edge_zone_lines] + all_lines[-edge_zone_lines:]


def detect_repeated_lines(
    text_blocks: list[ExtractedText],
    min_pages: int = DEFAULT_MIN_PAGES,
    frequency_threshold: float = DEFAULT_FREQUENCY_THRESHOLD,
    edge_zone_lines: int = DEFAULT_EDGE_ZONE_LINES,
) -> set[str]:
    """Returns the set of (whitespace-normalized) lines that appear on at
    least `frequency_threshold` of pages.

    Requires at least `min_pages` pages before considering anything
    "repeated" -- on a short document, two pages sharing a line is not
    meaningful evidence of a running header, it's as likely to be
    coincidence or genuinely repeated content.

    Page-edge position and repeated-line frequency are both required:

    1. Only lines within the first/last `edge_zone_lines` lines of each
       page are eligible candidates at all. Without this, two DIFFERENT
       tables on different pages that coincidentally share cell values
       (e.g. "Region", "North" appearing as column header / data in two
       unrelated tables) were being treated as document-wide
       header/footer noise and silently deleted -- a real, confirmed
       false positive, not a hypothetical one. Genuine headers/footers
       live at a page's top/bottom edge; table bodies don't.
    2. Digit runs are normalized away for COUNTING purposes only -- a
       page-numbered footer like "Page 1"/"Page 2"/"Page 3" is the same
       repeating line in spirit, just with a different number each
       time, but was never being recognized as repeated at all under
       exact-string matching. The original literal text of every
       qualifying line is what's actually returned, so
       strip_repeated_lines()'s exact-match removal is unaffected --
       each literal digit variant is removed individually.
    """
    if len(text_blocks) < min_pages:
        return set()

    # grouping_key -> count of distinct pages it appeared on (decides
    # repetition); grouping_key -> the literal line variants seen (what
    # actually gets removed once a key clears the threshold).
    grouped_page_counts: dict[str, int] = {}
    grouped_literals: dict[str, set[str]] = {}

    for block in text_blocks:
        seen_keys_this_page: set[str] = set()
        for line in _lines_in_edge_zone(block.text, edge_zone_lines):
            normalized_line = normalize_whitespace(line)
            grouping_key = _normalize_for_repetition_grouping(normalized_line)
            grouped_literals.setdefault(grouping_key, set()).add(normalized_line)
            seen_keys_this_page.add(grouping_key)
        for grouping_key in seen_keys_this_page:
            grouped_page_counts[grouping_key] = (
                grouped_page_counts.get(grouping_key, 0) + 1
            )

    threshold_count = len(text_blocks) * frequency_threshold
    repeated_literals: set[str] = set()
    for grouping_key, count in grouped_page_counts.items():
        if count >= threshold_count:
            repeated_literals.update(grouped_literals[grouping_key])
    return repeated_literals


def strip_repeated_lines(text: str, repeated_lines: set[str]) -> str:
    """Removes any line matching the repeated-lines set (after whitespace
    normalization) from `text`."""
    if not repeated_lines:
        return text
    kept_lines = [
        line
        for line in text.split("\n")
        if normalize_whitespace(line) not in repeated_lines
    ]
    return "\n".join(kept_lines)
