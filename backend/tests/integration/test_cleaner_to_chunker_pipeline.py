"""Integration test: Stage 1 loaders -> Stage 2 cleaning -> Stage 3
chunking, using the real fixture files end-to-end.

Author: Imitiyaz and AI Agent
Project: RAG MVP
Layer: Verification and synthetic fixtures
"""

from __future__ import annotations

from pathlib import Path

from app.chunking import chunk_document
from app.cleaning import clean_document
from app.loaders.pdf_loader import PdfLoader
from app.loaders.xlsx_loader import XlsxLoader


def test_xlsx_full_pipeline_to_chunks(sample_sales_xlsx: Path) -> None:
    document = XlsxLoader().load(sample_sales_xlsx)
    cleaned = clean_document(document)
    chunks = chunk_document(cleaned)

    # One chunk per surviving row (6 rows, none wide enough to split)
    assert len(chunks) == 6
    # Every chunk is properly citable back to its source
    for chunk in chunks:
        assert chunk.metadata.source_file == "sample_sales.xlsx"
        assert chunk.metadata.sheet_or_page in {"Q3 Sales", "Q4 Notes"}
    # Chunk text is a coherent, embeddable sentence, not raw dict repr
    north_chunk = next(c for c in chunks if "North" in c.text)
    assert "45000" in north_chunk.text
    # Strict check, not just substring -- "45000.0" also contains "45000"
    # as a substring, which is exactly how the original pandas
    # NaN-column-upcast bug (see row_cleaning.py) slipped past testing
    # until a manual smoke test surfaced it.
    assert "45000.0" not in north_chunk.text
    assert north_chunk.text.startswith("In '")


def test_pdf_full_pipeline_to_chunks(sample_report_pdf: Path) -> None:
    document = PdfLoader().load(sample_report_pdf)
    cleaned = clean_document(document)
    chunks = chunk_document(cleaned)

    # 3 table-row chunks + at least 1 narrative-text chunk
    row_chunks = [c for c in chunks if c.metadata.row_or_location != "full_page_text"]
    text_chunks = [c for c in chunks if c.metadata.row_or_location == "full_page_text"]
    assert len(row_chunks) == 3
    assert len(text_chunks) >= 1
    assert any("Quarterly Regional Sales Report" in c.text for c in text_chunks)
