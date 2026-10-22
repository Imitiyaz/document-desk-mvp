# SPDX-License-Identifier: AGPL-3.0-only
"""Text normalization primitives.

Two independently testable concerns, per ARCHITECTURE.md § 2's design:
fixing character-level encoding artifacts, and normalizing whitespace.
Kept as small pure functions rather than one "clean everything" function,
so each rule can be tested (and fixed) in isolation.

Author: Imitiyaz and AI Agent
Project: RAG MVP
Layer: Cleaning
"""

from __future__ import annotations

import re

# Common PDF-extraction encoding artifacts. Ligatures (fi/fl/ff/ffi/ffl)
# are a well-known PyMuPDF/PDF quirk -- many fonts encode these as single
# glyphs, which extractors surface as their own Unicode codepoints instead
# of decomposing them into the letters they represent.
_ENCODING_REPLACEMENTS = {
    "\ufb01": "fi",
    "\ufb02": "fl",
    "\ufb00": "ff",
    "\ufb03": "ffi",
    "\ufb04": "ffl",
    "\xa0": " ",  # non-breaking space
    "\x0c": "\n",  # form feed -- PyMuPDF emits this at page boundaries sometimes
}


def fix_encoding_artifacts(text: str) -> str:
    """Replaces known PDF-extraction encoding artifacts with their plain-text
    equivalents. Does not touch legitimate typography (smart quotes, em
    dashes) -- those are stylistic, not mis-encodings, and rewriting them
    would lose information for no correctness benefit.
    """
    for bad, good in _ENCODING_REPLACEMENTS.items():
        text = text.replace(bad, good)
    return text


def normalize_whitespace(text: str) -> str:
    """Collapses runs of horizontal whitespace to a single space, collapses
    multiple blank lines to at most one, strips whitespace around each
    line break, and trims the whole string. Preserves paragraph breaks
    (a single blank line) since that's meaningful structure for narrative
    PDF text, not noise to remove.
    """
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r" *\n *", "\n", text)
    text = re.sub(r"\n\s*\n+", "\n\n", text)
    return text.strip()


def clean_text(text: str) -> str:
    """Applies both normalization steps, in order. Encoding fixes must run
    first -- e.g. a form-feed character becoming a newline needs to happen
    before whitespace collapsing sees it as a line break to normalize."""
    text = fix_encoding_artifacts(text)
    text = normalize_whitespace(text)
    return text
