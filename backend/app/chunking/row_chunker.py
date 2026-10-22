# SPDX-License-Identifier: AGPL-3.0-only
"""Row-aware chunking for tabular data -- the correctness-critical stage
per docs/decisions/chunking-strategy.md. Each chunk represents exactly
one row (or, for very wide rows, one column-group slice of a single
    row). Wide-row fragments repeat a row anchor so later field groups
    retain the label needed to associate values with their original record.

DELIBERATE SCOPE NOTE: the ADR's pseudocode also describes an optional
`group_by` column that would combine multiple related rows into one
chunk. That is NOT implemented here -- there is no caller or UI/API
control that lets a user configure a grouping column yet (that's a
Stage 10/11 concern), and building it now, untested against a real use
case, would be speculative generality rather than a considered design.
If/when Stage 10/11 exposes this, implement it then, against a real
requirement.

Author: Imitiyaz and AI Agent
Project: RAG MVP
Layer: Chunking
"""

from __future__ import annotations

from typing import Any

from app.chunking.models import Chunk
from app.models.cleaned import CleanedRow
from app.models.extracted import SourceMetadata

DEFAULT_MAX_CHUNK_CHARS = 800


def _render_fields(data: dict[str, Any]) -> str:
    return "; ".join(f"{key} is {value}" for key, value in data.items())


def render_row_as_sentence(data: dict[str, Any], sheet_or_page: str) -> str:
    """Renders a row's fields as a consistent, generic sentence, e.g.:
    "In 'Q3 Sales': Region is North; Q3 Revenue is 45000; Q4 Revenue is 52000."
    Column order follows dict insertion order, which Stage 1/2 preserve
    from the original file. This phrasing is a deliberate, generic choice
    over hand-crafted per-column grammar (which can't generalize to
    arbitrary column names) -- see docs/decisions/chunking-strategy.md,
    which already flags chunk phrasing as something to tune after Stage 7
    evaluation, not something to get perfect now.
    """
    return f"In '{sheet_or_page}': {_render_fields(data)}."


def split_row_into_field_groups(
    data: dict[str, Any], max_chars: int = DEFAULT_MAX_CHUNK_CHARS
) -> list[dict[str, Any]]:
    """Splits a row's fields into groups whose rendered sentence stays
    under `max_chars` -- a character-count proxy for the "token
    threshold" described in the ADR's wide-table edge case, since no
    tokenizer is wired up until Stage 4 (Embedding) picks an embedding
    model. Guarantees at least one field per group even if a single
    field's value alone exceeds max_chars -- an oversized value is kept
    whole rather than truncated, since truncating would corrupt its
    meaning silently.
    """
    if not data:
        return []
    # Preserve all fields exactly. Repeat the first field as a conservative
    # row anchor; no format-specific identifier names or guessed values.
    anchor_key = next(iter(data))
    anchor = {anchor_key: data[anchor_key]}
    groups: list[dict[str, Any]] = []
    current: dict[str, Any] = {}
    for key, value in data.items():
        candidate = {**current, key: value}
        if current and len(_render_fields(candidate)) > max_chars:
            groups.append(current)
            current = {**anchor, key: value}
        else:
            current = candidate
    if current:
        groups.append(current)
    return groups


# Fragments help search, but every part retains the row identity needed to recover full evidence.
def chunk_row(
    row: CleanedRow, max_chunk_chars: int = DEFAULT_MAX_CHUNK_CHARS
) -> list[Chunk]:
    """Converts one CleanedRow into one or more Chunks. Almost always
    exactly one; more than one only for a row wide enough to exceed
    max_chunk_chars, in which case each resulting chunk's metadata gets a
    part suffix on row_or_location -- all parts still trace back to the
    exact same source row, just split for embedding-size reasons, never
    implying a different row.
    """
    field_groups = split_row_into_field_groups(row.data, max_chunk_chars)

    if len(field_groups) == 1:
        text = render_row_as_sentence(field_groups[0], row.metadata.sheet_or_page)
        return [Chunk(text=text, metadata=row.metadata)]

    chunks = []
    for i, group in enumerate(field_groups, start=1):
        text = render_row_as_sentence(group, row.metadata.sheet_or_page)
        metadata = SourceMetadata(
            source_file=row.metadata.source_file,
            sheet_or_page=row.metadata.sheet_or_page,
            row_or_location=f"{row.metadata.row_or_location}_part{i}",
        )
        chunks.append(Chunk(text=text, metadata=metadata))
    return chunks


def chunk_rows(
    rows: list[CleanedRow], max_chunk_chars: int = DEFAULT_MAX_CHUNK_CHARS
) -> list[Chunk]:
    """Chunks every row in `rows` independently (one row = one chunk,
    except wide rows -- see chunk_row)."""
    chunks: list[Chunk] = []
    for row in rows:
        chunks.extend(chunk_row(row, max_chunk_chars))
    return chunks
