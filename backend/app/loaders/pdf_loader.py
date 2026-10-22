# SPDX-License-Identifier: AGPL-3.0-only
"""PDF document loader.

Deliberately uses two libraries -- see `docs/decisions/pdf-parser-selection.md`
for the full comparison:

- pdfplumber: detects table regions and extracts them with row/column
  structure intact.
- PyMuPDF (fitz): fast, accurate general text extraction for narrative
  content.

Extraction only -- no cleaning, no chunking. That's Stage 2/3.

KNOWN LIMITATION (tracked, not silently ignored): PyMuPDF's whole-page
text extraction includes the raw text of any tables on that page, since
it has no concept of "skip this region." This means a page containing a
table will produce overlapping content between `document.rows` (from
pdfplumber) and `document.text_blocks` (from PyMuPDF) for that page.
This is intentional for Stage 1 -- de-duplication requires deciding how
much of a text block overlaps a table's content, which is a cleaning
decision, not an extraction one. Stage 2 (Cleaning) is responsible for
resolving this; see `docs/TROUBLESHOOTING.md` for the tracking note.

Author: Imitiyaz and AI Agent
Project: RAG MVP
Layer: Loaders
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pdfplumber
import pymupdf as fitz  # PyMuPDF
from loguru import logger

from app.core.config import settings
from app.core.exceptions import (
    CorruptFileError,
    EncryptedDocumentError,
    ExtractionLimitError,
    UnsupportedLayoutError,
)
from app.loaders.base import BaseLoader
from app.models.extracted import (
    ExtractedDocument,
    ExtractedRow,
    ExtractedText,
    SourceMetadata,
)

SUPPORTED_EXTENSIONS = {".pdf"}
MIN_TABLE_ROWS = 2  # a table needs at least a header row + one data row to be useful


class PdfLoader(BaseLoader):
    """Loads PDF files into `ExtractedDocument` records (tables + narrative text)."""

    supported_extensions = frozenset(SUPPORTED_EXTENSIONS)

    def supports(self, file_path: Path) -> bool:
        """Recognize PDF suffixes; parsing still validates that the bytes are readable."""
        return file_path.suffix.lower() in SUPPORTED_EXTENSIONS

    def load(self, file_path: Path) -> ExtractedDocument:
        """Extract table rows and narrative blocks with original page provenance.


        Args:
            file_path: Existing PDF to parse; original file bytes are not modified.

        Returns:
            An ExtractedDocument containing rows/text and parsing warnings.

        Raises:
            FileNotFoundError: The supplied path does not exist.
            CorruptFileError: A parser cannot read the document.
            EncryptedDocumentError: Password protection prevents extraction.
            ExtractionLimitError: A configured extraction budget is exceeded.

        Image-only PDFs are not OCR'd here. The service rejects an empty usable result.
        """
        logger.info("Loading PDF: {}", file_path.name)
        document = ExtractedDocument(source_file=file_path.name)

        self._extract_tables(file_path, document)
        self._extract_narrative_text(file_path, document)

        if document.is_empty():
            logger.warning(
                "No content extracted from {} -- file may be a scanned/"
                "image-only PDF (OCR is out of scope for this MVP, see "
                "docs/TROUBLESHOOTING.md).",
                file_path.name,
            )

        return document

    def _extract_tables(self, file_path: Path, document: ExtractedDocument) -> None:
        """Populate document.rows using pdfplumber's table detection."""
        try:
            with pdfplumber.open(file_path) as pdf:
                if pdf.metadata.get("Encrypted"):
                    raise EncryptedDocumentError(
                        f"{file_path.name} is password-protected and cannot be read."
                    )
                if len(pdf.pages) > settings.max_pdf_pages:
                    raise ExtractionLimitError(
                        "PDF page count exceeds the configured extraction budget."
                    )
                for page_number, page in enumerate(pdf.pages, start=1):
                    self._extract_tables_from_page(
                        page, page_number, file_path.name, document
                    )
        except (EncryptedDocumentError, ExtractionLimitError, UnsupportedLayoutError):
            raise
        except Exception as exc:
            raise CorruptFileError(
                f"Failed to read PDF {file_path.name} with pdfplumber: {exc}"
            ) from exc

    @staticmethod
    def _extract_tables_from_page(
        page: Any,
        page_number: int,
        source_file: str,
        document: ExtractedDocument,
    ) -> None:
        tables = page.extract_tables()  # default: strict "lines" strategy

        if not tables:
            # Text alignment can recover borderless tables. Require multiple
            # columns below to avoid classifying wrapped prose as a table.
            candidate_tables = page.extract_tables(
                table_settings={
                    "vertical_strategy": "text",
                    "horizontal_strategy": "text",
                }
            )
            tables = [
                table for table in candidate_tables if table and len(table[0]) >= 2
            ]

        if not tables:
            return

        for table_index, table in enumerate(tables, start=1):
            if not table or len(table) < MIN_TABLE_ROWS:
                continue  # too small to be a meaningful table

            headers = [
                str(cell) if cell is not None else f"column_{i + 1}"
                for i, cell in enumerate(table[0])
            ]

            if len({h.strip().casefold() for h in headers}) != len(headers):
                raise UnsupportedLayoutError(
                    f"Page {page_number} table {table_index} has duplicate headers; no source column was silently overwritten."
                )
            for row_index, raw_row in enumerate(table[1:], start=1):
                if len(raw_row) > len(headers) and any(
                    v not in (None, "") for v in raw_row[len(headers) :]
                ):
                    raise UnsupportedLayoutError(
                        "PDF table row has values without header columns; no source cell was discarded."
                    )
                padded = list(raw_row[: len(headers)]) + [None] * max(
                    0, len(headers) - len(raw_row)
                )
                row_data: dict[str, Any] = dict(zip(headers, padded, strict=True))

                # The "text" strategy fallback fills gaps with "" rather
                # than None (confirmed via manual testing), so a fully
                # blank row must check for both -- an all-None check alone
                # (sufficient for the default "lines" strategy) silently
                # let spacer rows from flowable padding through as bogus
                # data rows.
                if all(
                    value is None or (isinstance(value, str) and value.strip() == "")
                    for value in row_data.values()
                ):
                    continue

                if len(document.rows) >= settings.max_extracted_rows:
                    raise ExtractionLimitError(
                        "PDF table row count exceeds the configured extraction budget."
                    )
                document.rows.append(
                    ExtractedRow(
                        data=row_data,
                        metadata=SourceMetadata(
                            source_file=source_file,
                            sheet_or_page=f"page_{page_number}",
                            row_or_location=f"table_{table_index}_row_{row_index}",
                        ),
                    )
                )

    def _extract_narrative_text(
        self, file_path: Path, document: ExtractedDocument
    ) -> None:
        """Populate document.text_blocks using PyMuPDF's text extraction."""
        try:
            with fitz.open(file_path) as pdf_doc:
                for page_number, page in enumerate(pdf_doc, start=1):
                    text = page.get_text("text").strip()
                    if not text:
                        continue
                    document.text_blocks.append(
                        ExtractedText(
                            text=text,
                            metadata=SourceMetadata(
                                source_file=file_path.name,
                                sheet_or_page=f"page_{page_number}",
                                row_or_location="full_page_text",
                            ),
                        )
                    )
        except Exception as exc:
            raise CorruptFileError(
                f"Failed to read PDF {file_path.name} with PyMuPDF: {exc}"
            ) from exc
