"""Edge-case tests for PdfLoader -- documents with no table, encrypted
documents (simulated), and entirely blank documents. These generate
throwaway PDFs on the fly via reportlab rather than adding more committed
fixtures, since they're single-use and don't need to be inspected by hand.

Author: Imitiyaz and AI Agent
Project: RAG MVP
Layer: Verification and synthetic fixtures
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

from app.core.exceptions import EncryptedDocumentError
from app.loaders.pdf_loader import PdfLoader


def _make_narrative_only_pdf(path: Path) -> None:
    """A PDF with text but no table at all."""
    c = canvas.Canvas(str(path), pagesize=letter)
    c.drawString(72, 700, "This document has no tables, only narrative text.")
    c.save()


def _make_blank_pdf(path: Path) -> None:
    """A PDF with a single, completely blank page."""
    c = canvas.Canvas(str(path), pagesize=letter)
    c.showPage()
    c.save()


def test_pdf_loader_handles_page_with_no_table(tmp_path: Path) -> None:
    pdf_path = tmp_path / "narrative_only.pdf"
    _make_narrative_only_pdf(pdf_path)

    loader = PdfLoader()
    document = loader.load(pdf_path)

    assert document.rows == []  # no table detected -> no rows, not an error
    assert len(document.text_blocks) == 1
    assert "no tables" in document.text_blocks[0].text


def test_pdf_loader_blank_document_is_empty_and_does_not_raise(tmp_path: Path) -> None:
    pdf_path = tmp_path / "blank.pdf"
    _make_blank_pdf(pdf_path)

    loader = PdfLoader()
    document = loader.load(pdf_path)  # should log a warning, not raise

    assert document.is_empty() is True


def test_pdf_loader_raises_for_encrypted_document(tmp_path: Path) -> None:
    """Simulates pdfplumber reporting an encrypted PDF, without needing a
    real password-protected binary fixture -- isolates our error-handling
    branch from pdfplumber's own encryption-detection logic, which is
    pdfplumber's responsibility to get right, not ours to re-test."""
    pdf_path = tmp_path / "encrypted.pdf"
    _make_narrative_only_pdf(pdf_path)  # content doesn't matter, we mock metadata

    mock_pdf = MagicMock()
    mock_pdf.metadata = {"Encrypted": True}
    mock_pdf.pages = []
    mock_context_manager = MagicMock()
    mock_context_manager.__enter__.return_value = mock_pdf
    mock_context_manager.__exit__.return_value = False

    with patch("pdfplumber.open", return_value=mock_context_manager):
        loader = PdfLoader()
        with pytest.raises(EncryptedDocumentError, match="password-protected"):
            loader.load(pdf_path)
