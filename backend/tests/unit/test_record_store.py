"""SQLite persistence and provenance are checked separately from vector storage.

Author: Imitiyaz and AI Agent
Project: RAG MVP
Layer: Verification and synthetic fixtures
"""

import sqlite3

import pytest

from app.models.extracted import ExtractedDocument, ExtractedRow, SourceMetadata
from app.structured.store import RecordStore


def document():
    return ExtractedDocument(
        "same.xlsx",
        rows=[
            ExtractedRow(
                {"Region": "North", "Revenue": 45000, "Comment": None},
                SourceMetadata("same.xlsx", "Sheet", 2),
                {"Region": "A2", "Revenue": "B2", "Comment": "C2"},
            ),
            ExtractedRow(
                {"Region": None, "Revenue": 47000, "Comment": None},
                SourceMetadata("same.xlsx", "Sheet", 3),
                {"Region": "A2", "Revenue": "B3", "Comment": "C3"},
                {"Region": "North"},
            ),
        ],
    )


def test_restart_preserves_raw_blank_merge_anchor_and_missing_cell(tmp_path):
    path = str(tmp_path / "index" / "source.sqlite3")
    store = RecordStore(path)
    store.add(document(), b"original workbook")
    store.close()
    reopened = RecordStore(path)
    payload = reopened.get("same.xlsx")
    assert payload["rows"][1]["raw_values"]["Region"] is None
    assert payload["rows"][1]["values"]["Region"] == "North"
    assert payload["rows"][1]["values"]["Comment"] is None
    assert payload["rows"][1]["cell_origins"]["Region"] == "A2"
    assert reopened.sources()[0]["ready"] is True
    reopened.close()


def test_duplicate_does_not_replace_existing_document():
    store = RecordStore()
    store.add(document(), b"one")
    before = store.get("same.xlsx")
    with pytest.raises(sqlite3.IntegrityError):
        store.add(document(), b"two")
    assert store.get("same.xlsx") == before
    store.close()


def test_unknown_policy_is_explicitly_not_ready():
    store = RecordStore()
    store.add(document(), b"data")
    with store.connection:
        store.connection.execute("UPDATE documents SET version='old'")
    assert store.get("same.xlsx") is None
    assert store.sources()[0]["ready"] is False
    store.close()


def test_delete_targets_exact_source_name():
    store = RecordStore()
    store.add(document(), b"data")
    store.delete("x' OR 1=1 --")
    assert store.get("same.xlsx") is not None
    store.delete("same.xlsx")
    assert store.get("same.xlsx") is None
    assert store.sources() == []
    store.close()
