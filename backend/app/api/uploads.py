# SPDX-License-Identifier: AGPL-3.0-only
"""Portable upload names and bounded copying; temporary files never become IDs.

Author: Imitiyaz and AI Agent
Project: RAG MVP
Layer: Api
"""

from __future__ import annotations

from pathlib import Path
from typing import BinaryIO

from loguru import logger

from app.core.exceptions import (
    EmptyDocumentError,
    InvalidFilenameError,
    UploadTooLargeError,
)

_WINDOWS_RESERVED = {"CON", "PRN", "AUX", "NUL"} | {
    f"{prefix}{i}" for prefix in ("COM", "LPT") for i in range(1, 10)
}


def validate_filename(filename: str | None) -> str:
    """Require a single portable filename, rejecting paths rather than stripping them."""
    if (
        not filename
        or len(filename) > 255
        or filename in {".", ".."}
        or filename.endswith((" ", "."))
        or any(ord(c) < 32 or c in '/\\:<>"|?*' for c in filename)
        or filename.split(".", 1)[0].upper() in _WINDOWS_RESERVED
    ):
        raise InvalidFilenameError(
            "Provide a plain filename without a path or reserved characters."
        )
    return filename


def save_upload(stream: BinaryIO, destination: Path, max_bytes: int) -> int:
    """Copy within the byte budget, deleting partial output on every failure.

    Format validation belongs to the loader registry and parsers. MIME headers
    are supplied by the client and are not treated as evidence of file format.
    """
    total = 0
    try:
        with destination.open("xb") as output:
            while data := stream.read(min(64 * 1024, max_bytes - total + 1)):
                total += len(data)
                if total > max_bytes:
                    raise UploadTooLargeError(
                        f"File exceeds the {max_bytes}-byte upload limit."
                    )
                output.write(data)
        if total == 0:
            raise EmptyDocumentError("The uploaded file contains no bytes.")
        return total
    except Exception:
        destination.unlink(missing_ok=True)
        logger.exception("Could not stage upload {}", destination.name)
        raise
