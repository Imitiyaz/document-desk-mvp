# SPDX-License-Identifier: AGPL-3.0-only
"""Loader registry and format dispatcher.

This is the one place in the codebase that knows the full list of
supported formats. Every call site elsewhere (ingestion endpoint, CLI,
tests) calls `get_loader_for_file()` rather than importing `XlsxLoader`
or `PdfLoader` directly -- adding a new format later means registering
it here, not touching every call site.

Author: Imitiyaz and AI Agent
Project: RAG MVP
Layer: Loaders
"""

from __future__ import annotations

from pathlib import Path

from app.core.exceptions import UnsupportedFileTypeError
from app.loaders.base import BaseLoader
from app.loaders.pdf_loader import PdfLoader
from app.loaders.xlsx_loader import XlsxLoader

_REGISTERED_LOADERS: list[BaseLoader] = [XlsxLoader(), PdfLoader()]


def get_loader_for_file(file_path: Path) -> BaseLoader:
    """Return the loader capable of handling this file.

    Args:
        file_path: Path to the source file.

    Returns:
        A loader instance whose `.supports()` returned True for this file.

    Raises:
        UnsupportedFileTypeError: if no registered loader supports the
            file's extension (including legacy `.xls`, which is handled
            with a more specific error by `XlsxLoader.load()` -- but
            `.xls` files aren't registered as "supported" here, so a
            direct dispatch attempt still fails clearly).
    """
    for loader in _REGISTERED_LOADERS:
        if loader.supports(file_path):
            return loader
    raise UnsupportedFileTypeError(
        f"No loader registered for file type '{file_path.suffix}' "
        f"({file_path.name}). Supported types: {', '.join(supported_extensions())}"
    )


def supported_extensions() -> list[str]:
    """Discover UI-upload suffixes from registered loader capabilities."""
    return sorted(
        {
            suffix
            for loader in _REGISTERED_LOADERS
            for suffix in loader.supported_extensions
        }
    )
