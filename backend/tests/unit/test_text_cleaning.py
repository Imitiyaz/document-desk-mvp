"""Unit tests for app.cleaning.text_cleaning.

Author: Imitiyaz and AI Agent
Project: RAG MVP
Layer: Verification and synthetic fixtures
"""

from __future__ import annotations

from app.cleaning.text_cleaning import (
    clean_text,
    fix_encoding_artifacts,
    normalize_whitespace,
)


def test_fix_encoding_artifacts_replaces_ligatures() -> None:
    assert fix_encoding_artifacts("of\ufb01ce") == "office"
    assert fix_encoding_artifacts("\ufb02ow") == "flow"


def test_fix_encoding_artifacts_replaces_non_breaking_space() -> None:
    assert fix_encoding_artifacts("North\xa0Region") == "North Region"


def test_fix_encoding_artifacts_replaces_form_feed_with_newline() -> None:
    assert fix_encoding_artifacts("page one\x0cpage two") == "page one\npage two"


def test_fix_encoding_artifacts_leaves_normal_text_unchanged() -> None:
    text = "Regular text with no artifacts."
    assert fix_encoding_artifacts(text) == text


def test_normalize_whitespace_collapses_horizontal_whitespace() -> None:
    assert normalize_whitespace("North    Region\t\there") == "North Region here"


def test_normalize_whitespace_collapses_multiple_blank_lines() -> None:
    assert normalize_whitespace("Para one\n\n\n\nPara two") == "Para one\n\nPara two"


def test_normalize_whitespace_strips_leading_and_trailing_whitespace() -> None:
    assert normalize_whitespace("   text   ") == "text"


def test_normalize_whitespace_strips_spaces_around_newlines() -> None:
    assert normalize_whitespace("line one   \n   line two") == "line one\nline two"


def test_normalize_whitespace_preserves_single_paragraph_break() -> None:
    assert normalize_whitespace("Para one\n\nPara two") == "Para one\n\nPara two"


def test_clean_text_applies_encoding_fix_before_whitespace_normalization() -> None:
    # form feed -> newline (encoding fix), then multiple blank lines collapsed
    result = clean_text("page one\x0c\x0cpage two")
    assert result == "page one\n\npage two"
