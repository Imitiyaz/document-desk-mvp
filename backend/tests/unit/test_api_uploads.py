"""Upload byte/name boundaries independent of HTTP or model dependencies.

Author: Imitiyaz and AI Agent
Project: RAG MVP
Layer: Verification and synthetic fixtures
"""

from __future__ import annotations

from io import BytesIO

import pytest

from app.api.uploads import save_upload, validate_filename
from app.core.exceptions import (
    EmptyDocumentError,
    InvalidFilenameError,
    UploadTooLargeError,
)


@pytest.mark.parametrize(
    "name",
    [
        None,
        "",
        ".",
        "..",
        "../a.pdf",
        "a/b.xlsx",
        "a\\b.pdf",
        "C:a.pdf",
        "NUL.xlsx",
        "COM1.pdf",
        "a.pdf.",
        "a.pdf ",
        "a\x00.pdf",
        "x" * 256,
    ],
)
def test_rejects_unsafe_names(name) -> None:
    with pytest.raises(InvalidFilenameError):
        validate_filename(name)


@pytest.mark.parametrize(
    "name", ["Sales report.xlsx", "résumé.PDF", "收入.xlsx", "report.newformat"]
)
def test_preserves_portable_names_without_format_assumptions(name: str) -> None:
    assert validate_filename(name) == name


def test_upload_accepts_exact_byte_limit(tmp_path) -> None:
    destination = tmp_path / "a.pdf"
    assert save_upload(BytesIO(b"1234"), destination, 4) == 4
    assert destination.read_bytes() == b"1234"


@pytest.mark.parametrize(
    "content,error", [(b"", EmptyDocumentError), (b"12345", UploadTooLargeError)]
)
def test_invalid_upload_removes_partial_file(tmp_path, content, error) -> None:
    destination = tmp_path / "a.pdf"
    with pytest.raises(error):
        save_upload(BytesIO(content), destination, 4)
    assert not destination.exists()
