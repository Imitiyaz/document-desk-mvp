"""Unit tests for the loader registry (app/loaders/__init__.py).

Author: Imitiyaz and AI Agent
Project: RAG MVP
Layer: Verification and synthetic fixtures
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.core.exceptions import UnsupportedFileTypeError
from app.loaders import get_loader_for_file
from app.loaders.pdf_loader import PdfLoader
from app.loaders.xlsx_loader import XlsxLoader


def test_dispatch_routes_xlsx_to_xlsx_loader() -> None:
    loader = get_loader_for_file(Path("report.xlsx"))
    assert isinstance(loader, XlsxLoader)


def test_dispatch_routes_pdf_to_pdf_loader() -> None:
    loader = get_loader_for_file(Path("report.pdf"))
    assert isinstance(loader, PdfLoader)


def test_dispatch_raises_for_truly_unsupported_extension() -> None:
    with pytest.raises(UnsupportedFileTypeError, match=r"\.docx"):
        get_loader_for_file(Path("report.docx"))
