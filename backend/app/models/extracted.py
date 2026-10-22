# SPDX-License-Identifier: AGPL-3.0-only
"""Data models representing content extracted from source documents.

These are intentionally plain dataclasses, not pydantic models. They are
internal pipeline data structures passed between Stage 1 (Loaders) and
Stage 2 (Cleaning) -- not API request/response bodies. API schemas
(pydantic, for request validation) are a separate concern, added in
Stage 10 under `app/api/schemas.py`. Keeping the two separate means a
change to the API's JSON shape never has to touch this internal model,
and vice versa.

Author: Imitiyaz and AI Agent
Project: RAG MVP
Layer: Models
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class SourceMetadata:
    """Citation metadata attached to every extracted row or text block.

    This is captured once, here, at extraction time -- per
    `ARCHITECTURE.md`'s citation design, this metadata travels with its
    content through every later pipeline stage and is never
    reconstructed after the fact.

    Attributes:
        source_file: Original file name (not full path -- the path is an
            ingestion-time implementation detail, not something a user's
            citation should expose).
        sheet_or_page: Excel sheet name (e.g. "Q3 Sales") or PDF page
            label (e.g. "page_3").
        row_or_location: Excel row number (matching what a user would see
            if they opened the file in Excel), or a PDF-specific location
            string (e.g. "table_1_row_4") when a page-number alone isn't
            precise enough.
    """

    source_file: str
    sheet_or_page: str
    row_or_location: str | int


def format_citation(metadata: SourceMetadata) -> str:
    """Human-readable citation string: "file / sheet-or-page / row N".

    A single shared implementation, used by both Stage 7's prompt
    assembly (`app/generation/prompt_builder.py`) and Stage 9's citation
    resolution (`app/generation/citation_resolver.py`) -- kept here,
    next to `SourceMetadata` itself, rather than duplicated in each
    caller, so the display format only needs to change in one place.
    Matches the format already used throughout this project's manual
    smoke tests and logs (e.g. "sample_sales.xlsx / Q3 Sales / row 2").
    """
    return f"{metadata.source_file} / {metadata.sheet_or_page} / row {metadata.row_or_location}"


@dataclass
class ExtractedRow:
    """One row of tabular data, with its citation metadata.

    Attributes:
        data: Column name -> cell value. Values may be None for empty
            cells -- normalizing/dropping those is Stage 2's job, not
            this stage's.
        metadata: Where this row came from.
    """

    data: dict[str, Any]
    metadata: SourceMetadata
    cell_origins: dict[str, str] = field(default_factory=dict)
    merged_values: dict[str, Any] = field(default_factory=dict)
    cell_formats: dict[str, str] = field(default_factory=dict)
    formula_fields: set[str] = field(default_factory=set)


@dataclass
class ExtractedText:
    """A block of narrative (non-tabular) text, with its citation metadata.

    Only produced by the PDF loader today (Excel files are tabular by
    definition). Whole-page text for now; splitting into
    paragraph-sized blocks is a Stage 2/3 concern, not extraction.
    """

    text: str
    metadata: SourceMetadata


@dataclass
class ExtractedDocument:
    """The full result of loading one source document.

    A single document can contain both tabular rows (from an Excel sheet
    or a detected PDF table) and narrative text blocks (from PDF
    non-table regions) -- most real PDFs contain both.
    """

    source_file: str
    rows: list[ExtractedRow] = field(default_factory=list)
    text_blocks: list[ExtractedText] = field(default_factory=list)

    warnings: list[str] = field(default_factory=list)

    def is_empty(self) -> bool:
        """True if nothing was extracted at all -- callers should treat
        this as a warning condition, not silently proceed as if ingestion
        succeeded."""
        return not self.rows and not self.text_blocks
