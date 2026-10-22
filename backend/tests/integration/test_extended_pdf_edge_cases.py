"""Integration tests: full pipeline (loader -> cleaning -> chunking)
against sample_report_extended.pdf -- edge cases the original
sample_report.pdf never exercised (a narrative-only page, a borderless
table, and a repeated footer with an embedded page number across a real
multi-page document). Added after Stage 6's manual smoke test surfaced a
real bug that only became visible against real chunk text; see
docs/pipeline.md's and
docs/pipeline.md's extraction and cleaning policyes for the full
rationale.

Author: Imitiyaz and AI Agent
Project: RAG MVP
Layer: Verification and synthetic fixtures
"""

from __future__ import annotations

from pathlib import Path

from app.chunking import chunk_document
from app.cleaning import clean_document
from app.loaders.pdf_loader import PdfLoader


def test_narrative_only_page_produces_text_block_and_no_rows(
    sample_report_extended_pdf: Path,
) -> None:
    document = PdfLoader().load(sample_report_extended_pdf)
    cleaned = clean_document(document)
    chunks = chunk_document(cleaned)

    page_1_chunks = [c for c in chunks if c.metadata.sheet_or_page == "page_1"]
    assert len(page_1_chunks) == 1
    assert page_1_chunks[0].metadata.row_or_location == "full_page_text"
    assert "Annual Company Overview" in page_1_chunks[0].text


def test_borderless_table_content_reaches_chunks_as_structured_rows(
    sample_report_extended_pdf: Path,
) -> None:
    document = PdfLoader().load(sample_report_extended_pdf)
    cleaned = clean_document(document)
    chunks = chunk_document(cleaned)

    page_2_row_chunks = [
        c
        for c in chunks
        if c.metadata.sheet_or_page == "page_2"
        and c.metadata.row_or_location != "full_page_text"
    ]
    assert len(page_2_row_chunks) == 3
    combined = " ".join(c.text for c in page_2_row_chunks)
    assert "North" in combined and "Headcount is 24" in combined


def test_page_numbered_footer_is_stripped_from_every_page(
    sample_report_extended_pdf: Path,
) -> None:
    document = PdfLoader().load(sample_report_extended_pdf)
    cleaned = clean_document(document)
    chunks = chunk_document(cleaned)

    for chunk in chunks:
        assert "Acme Corp" not in chunk.text
        assert "Confidential" not in chunk.text


def test_coincidental_cross_page_table_values_are_not_stripped_as_noise(
    sample_report_extended_pdf: Path,
) -> None:
    # "North"/"South"/"East" appear as table content on BOTH page_2 and
    # page_3 -- confirms the fix didn't overcorrect into treating that
    # coincidental repetition as header/footer noise (the bug being
    # fixed), while the genuine footer (previous test) is still removed.
    document = PdfLoader().load(sample_report_extended_pdf)
    cleaned = clean_document(document)
    chunks = chunk_document(cleaned)

    row_chunks = [c for c in chunks if c.metadata.row_or_location != "full_page_text"]
    regions_present = {c.text.split("Region is ")[1].split(";")[0] for c in row_chunks}
    assert regions_present == {"North", "South", "East"}
