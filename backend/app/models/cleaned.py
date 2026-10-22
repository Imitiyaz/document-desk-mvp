# SPDX-License-Identifier: AGPL-3.0-only
"""Data models representing *cleaned* document content.

Deliberately separate types from `app.models.extracted` (ExtractedRow,
ExtractedText, ExtractedDocument) rather than reusing them for cleaned
output. Per the project's "explicit over implicit" standard: a function
that returns a `CleanedDocument` cannot be mistaken for one that still
needs cleaning, and a type checker (mypy) will catch it if code
accidentally passes raw extracted data somewhere a cleaned document was
expected. The shapes are intentionally similar to `extracted.py` --
this stage doesn't restructure data, it normalizes it in place.

Author: Imitiyaz and AI Agent
Project: RAG MVP
Layer: Models
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.models.extracted import SourceMetadata


@dataclass
class CleanedRow:
    """One row of tabular data after cleaning.

    Unlike ExtractedRow, `data` never contains None values -- fields
    with no value are omitted entirely (see app/cleaning/row_cleaning.py),
    so downstream chunking (Stage 3) never has to special-case an absent
    field.
    """

    data: dict[str, Any]
    metadata: SourceMetadata


@dataclass
class CleanedText:
    """A block of narrative text after cleaning (whitespace/encoding
    normalized, repeated headers/footers and table-duplicate lines
    removed)."""

    text: str
    metadata: SourceMetadata


@dataclass
class CleanedDocument:
    """The full result of cleaning one source document."""

    source_file: str
    rows: list[CleanedRow] = field(default_factory=list)
    text_blocks: list[CleanedText] = field(default_factory=list)

    def is_empty(self) -> bool:
        """Report whether cleaning left any rows or narrative blocks to chunk."""
        return not self.rows and not self.text_blocks
