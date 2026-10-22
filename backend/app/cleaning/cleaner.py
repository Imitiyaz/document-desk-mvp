# SPDX-License-Identifier: AGPL-3.0-only
"""Stage 2 orchestrator: `clean_document()` composes every cleaning step
into the one function the rest of the pipeline calls.

Order matters and is deliberate:
1. Group rows by sheet/page, sorted into original order (defensive --
   Stage 1 already extracts in order, but Cleaning shouldn't silently
   depend on that if it's ever violated).
2. Forward-fill string columns within each group (approximates merged
   cells -- see app/cleaning/row_cleaning.py for the documented tradeoff).
3. Clean row data (drop empty fields, fix whitespace/encoding).
4. For narrative text: strip repeated headers/footers first (using the
   ORIGINAL, uncleaned text-block set, since detection needs to compare
   raw lines across pages before any single page's text is modified),
   then remove table-duplicate lines, then apply whitespace/encoding
   cleaning last.

Author: Imitiyaz and AI Agent
Project: RAG MVP
Layer: Cleaning
"""

from __future__ import annotations

from loguru import logger

from app.cleaning.header_footer import detect_repeated_lines, strip_repeated_lines
from app.cleaning.row_cleaning import clean_row_data, forward_fill_group
from app.cleaning.table_dedup import (
    build_table_tokens_by_page,
    remove_table_duplicate_lines,
)
from app.cleaning.text_cleaning import clean_text
from app.models.cleaned import CleanedDocument, CleanedRow, CleanedText
from app.models.extracted import ExtractedDocument, ExtractedRow


def _group_rows_by_page(rows: list[ExtractedRow]) -> dict[str, list[ExtractedRow]]:
    """Groups rows by sheet_or_page, preserving first-seen page order.
    Within a group, sorts by row_or_location when it's an int (the xlsx
    case) to guarantee top-to-bottom order regardless of extraction
    order; PDF table rows (string row_or_location) are left in extracted
    order, which the loader already produces sequentially.
    """
    groups: dict[str, list[ExtractedRow]] = {}
    for row in rows:
        groups.setdefault(row.metadata.sheet_or_page, []).append(row)

    for page_rows in groups.values():
        if page_rows and isinstance(page_rows[0].metadata.row_or_location, int):
            page_rows.sort(key=lambda r: r.metadata.row_or_location)  # type: ignore[arg-type,return-value]

    return groups


def clean_document(document: ExtractedDocument) -> CleanedDocument:
    """Cleans an ExtractedDocument (Stage 1 output) into a CleanedDocument
    (Stage 3's input). Deterministic -- no LLM involved, per
    ARCHITECTURE.md § 2.
    """
    logger.info("Cleaning document: {}", document.source_file)

    groups = _group_rows_by_page(document.rows)
    filled_groups = {page: forward_fill_group(rows) for page, rows in groups.items()}

    cleaned_rows: list[CleanedRow] = []
    dropped_empty_rows = 0
    for page in groups:  # dict preserves first-seen page order
        for row in filled_groups[page]:
            cleaned_data = clean_row_data(row.data, row.cell_formats)
            if not cleaned_data:
                dropped_empty_rows += 1
                continue
            cleaned_rows.append(CleanedRow(data=cleaned_data, metadata=row.metadata))

    if dropped_empty_rows:
        logger.info(
            "{}: dropped {} row(s) that became empty after cleaning",
            document.source_file,
            dropped_empty_rows,
        )

    repeated_lines = detect_repeated_lines(document.text_blocks)
    if repeated_lines:
        logger.info(
            "{}: detected {} repeated header/footer line(s) across pages",
            document.source_file,
            len(repeated_lines),
        )
    table_tokens_by_page = build_table_tokens_by_page(document.rows)

    cleaned_text_blocks: list[CleanedText] = []
    dropped_empty_text_blocks = 0
    for block in document.text_blocks:
        text = strip_repeated_lines(block.text, repeated_lines)
        page_tokens = table_tokens_by_page.get(block.metadata.sheet_or_page, set())
        text = remove_table_duplicate_lines(text, page_tokens)
        text = clean_text(text)
        if not text:
            dropped_empty_text_blocks += 1
            continue
        cleaned_text_blocks.append(CleanedText(text=text, metadata=block.metadata))

    if dropped_empty_text_blocks:
        logger.info(
            "{}: dropped {} text block(s) that became empty after cleaning",
            document.source_file,
            dropped_empty_text_blocks,
        )

    cleaned_document = CleanedDocument(
        source_file=document.source_file,
        rows=cleaned_rows,
        text_blocks=cleaned_text_blocks,
    )

    if cleaned_document.is_empty():
        logger.warning(
            "{}: nothing left after cleaning -- check whether the source "
            "document had any real content, or whether cleaning was too aggressive",
            document.source_file,
        )

    return cleaned_document
