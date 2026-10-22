# SPDX-License-Identifier: AGPL-3.0-only
"""Resolves the known limitation documented in `app/loaders/pdf_loader.py`:
PyMuPDF's whole-page text extraction includes the raw text of any tables
on that page, since it has no concept of "skip this region" -- producing
overlapping content between `document.rows` (from pdfplumber) and
`document.text_blocks` (from PyMuPDF) for pages containing a table.

APPROACH AND ITS LIMITATION: this is a token-overlap heuristic, not a
geometric one. A true fix would compare pdfplumber's table bounding boxes
against PyMuPDF's text block positions and exclude overlapping regions
directly -- neither loader currently captures bounding-box coordinates.
Instead, this builds a set of normalized tokens from each page's extracted
table cells -- both header names and cell values -- then removes any
narrative line whose tokens overlap that set above a threshold. This
catches the common case (a line that's essentially the table row
re-stated as flowing text) without needing positional data, at the cost
of occasionally removing a narrative line that coincidentally shares
most of its words with table content -- an accepted tradeoff, not a
silent one. Including header names in the token set (not just cell
values) makes this specific risk slightly larger: a short generic column
header like "Date" or "Total" is more likely to coincidentally appear in
genuine narrative prose than a specific data value like "45000" is --
still judged worth it, since without header tokens, header rows in
PyMuPDF's whole-page text (e.g. a literal "Region" / "Q3 Revenue" line)
were never removed at all.

Author: Imitiyaz and AI Agent
Project: RAG MVP
Layer: Cleaning
"""

from __future__ import annotations

import re

from app.models.extracted import ExtractedRow

DEFAULT_MIN_LINE_TOKENS = 1
DEFAULT_OVERLAP_THRESHOLD = 0.8

_TOKEN_PATTERN = re.compile(r"[a-z0-9]+")


def _tokenize(text: str) -> list[str]:
    return _TOKEN_PATTERN.findall(text.lower())


def build_table_tokens_by_page(rows: list[ExtractedRow]) -> dict[str, set[str]]:
    """Builds a set of normalized tokens per page (`sheet_or_page`) from
    every extracted table cell -- both the column header names and the
    cell values. Headers are included (not just values) because a
    PDF's rendered table header row ("Region", "Q3 Revenue") is just as
    much duplicated table content as a data cell is, and PyMuPDF's
    whole-page text extraction includes header cells as their own lines
    the same way it includes data cells.
    """
    tokens_by_page: dict[str, set[str]] = {}
    for row in rows:
        page_tokens = tokens_by_page.setdefault(row.metadata.sheet_or_page, set())
        for key, value in row.data.items():
            page_tokens.update(_tokenize(key))
            if value is not None:
                page_tokens.update(_tokenize(str(value)))
    return tokens_by_page


def remove_table_duplicate_lines(
    text: str,
    table_tokens: set[str],
    min_line_tokens: int = DEFAULT_MIN_LINE_TOKENS,
    overlap_threshold: float = DEFAULT_OVERLAP_THRESHOLD,
) -> str:
    """Removes lines from `text` whose tokens overlap `table_tokens` above
    `overlap_threshold`. Lines with fewer than `min_line_tokens` tokens
    (i.e., blank lines, by default) are always kept -- an overlap ratio
    over zero tokens is undefined, not just unreliable.

    A single-token line's overlap ratio IS well-defined (it's either 0%
    or 100% -- no in-between is possible), so it is no longer given a
    blanket exemption the way it was in an earlier version of this
    function. That earlier exemption was a real bug, not a safe default:
    PyMuPDF (Stage 1's whole-page PDF text extractor) commonly renders
    each table cell on its own line -- e.g. a "Region"/"North"/"45000"
    table becomes three separate one-token lines, not one multi-token
    line -- and exempting every such line from overlap checking meant
    this function silently did nothing at all against the single most
    common real-world shape of PDF table dumps, while still correctly
    handling the artificial "North 45000 52000" single-line case its
    original test suite happened to cover. Found via Stage 6's manual
    smoke test actually printing real chunk text from a real PDF; see
    docs/pipeline.md's second extraction and cleaning policy for
    the full incident writeup.
    """
    if not table_tokens:
        return text

    kept_lines = []
    for line in text.split("\n"):
        line_tokens = _tokenize(line)
        if len(line_tokens) < min_line_tokens:
            kept_lines.append(line)
            continue
        overlap = sum(1 for token in line_tokens if token in table_tokens) / len(
            line_tokens
        )
        if overlap < overlap_threshold:
            kept_lines.append(line)
    return "\n".join(kept_lines)
