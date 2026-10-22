# SPDX-License-Identifier: AGPL-3.0-only
"""Abstract base class defining the loader interface.

Every format-specific loader (XlsxLoader, PdfLoader, ...) implements this
interface, so the rest of the ingestion pipeline can treat all loaders
uniformly -- it calls `.load()` and gets back an `ExtractedDocument`
either way, without needing a chain of `if file_type == "xlsx"` checks
scattered through the codebase. Adding a new format later (e.g., .csv)
means writing one new class here, not modifying every call site that
currently handles xlsx/PDF.

Author: Imitiyaz and AI Agent
Project: RAG MVP
Layer: Loaders
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from app.models.extracted import ExtractedDocument


class BaseLoader(ABC):
    """Interface every document loader must implement."""

    supported_extensions: frozenset[str] = frozenset()

    @abstractmethod
    def supports(self, file_path: Path) -> bool:
        """Return True if this loader can handle the given file.

        Checked by the registry in `app/loaders/__init__.py` to route a
        file to the right loader without hardcoding format logic there.
        """

    @abstractmethod
    def load(self, file_path: Path) -> ExtractedDocument:
        """Extract structured content from the file.

        Args:
            file_path: Path to the source file on disk.

        Returns:
            An ExtractedDocument containing every row/text block found,
            each carrying its own citation metadata.

        Raises:
            CorruptFileError: if the file cannot be parsed at all.
            EncryptedDocumentError: if the file is password-protected.
            LegacyExcelFormatError: (XlsxLoader only) for unsupported
                legacy `.xls` files.
        """
