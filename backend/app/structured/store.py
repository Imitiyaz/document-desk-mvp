# SPDX-License-Identifier: AGPL-3.0-only
"""Persist complete source rows independently of retrieval fragments.

The SQLite ledger stores raw and normalized values, physical coordinates,
document identity and processing policy. A read-time continuation view discloses
approved Region assumptions without rewriting raw blanks. SQLite transactions
are local; workspace coordination handles the separate vector-store lifecycle.

Author: Imitiyaz and AI Agent
Project: RAG MVP
Layer: Structured
"""

from __future__ import annotations

import datetime
import hashlib
import json
import sqlite3
import uuid
from pathlib import Path
from typing import Any

from app.cleaning.row_cleaning import clean_row_data
from app.core.config import settings
from app.core.exceptions import ReindexRequiredError
from app.models.extracted import ExtractedDocument

POLICY_VERSION = "merge-aware-formats-v2"


class RecordStore:
    """Persist complete documents in atomic SQLite transactions, with typed values.

    File paths are scoped to one Chroma collection; :memory: supports tests.
    SQL parameters bind every document value/name. No model text becomes SQL.
    """

    def __init__(self, path: str = ":memory:") -> None:
        if path != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(path, check_same_thread=False)
        self.connection.execute(
            "CREATE TABLE IF NOT EXISTS documents "
            "(source TEXT PRIMARY KEY, version TEXT NOT NULL, digest TEXT NOT NULL, payload TEXT NOT NULL)"
        )
        self.connection.execute(
            "CREATE TABLE IF NOT EXISTS document_state (source TEXT PRIMARY KEY, document_id TEXT NOT NULL, state TEXT NOT NULL, profile TEXT NOT NULL)"
        )
        self.connection.execute(
            "CREATE TABLE IF NOT EXISTS workspace (id INTEGER PRIMARY KEY CHECK(id=1), revision INTEGER NOT NULL)"
        )
        self.connection.execute("INSERT OR IGNORE INTO workspace VALUES(1,0)")
        self.connection.execute(
            "CREATE TABLE IF NOT EXISTS pipeline_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)"
        )
        for source, previous_version in self.connection.execute(
            "SELECT source, version FROM documents"
        ).fetchall():
            self.connection.execute(
                "INSERT OR IGNORE INTO document_state VALUES(?,?, 'ready', ?)",
                (
                    source,
                    str(uuid.uuid4()),
                    json.dumps(
                        {
                            **json.loads(self.profile()),
                            "name": "legacy-adopted",
                            "record_policy": previous_version,
                        }
                    ),
                ),
            )
        self.connection.commit()

    def add(
        self, document: ExtractedDocument, original: bytes, *, state: str = "ready"
    ) -> None:
        """Persist one complete document and its identity in a SQLite transaction.


        Args:
            document: Extracted raw cells, actual merge metadata and source locations.
            original: Upload bytes used only for the SHA-256 identity; not an archive.
            state: Lifecycle state, usually indexing until vector writes complete.

        Returns:
            None. Rows retain both normalized values and original values/coordinates.

        Raises:
            TypeError: A source value cannot be represented by the supported serializer.
            sqlite3.Error: The local transaction cannot be committed.

        Formula caches are recorded, not evaluated. The service coordinates vector writes
        and compensation outside this transaction.
        """
        rows = []
        for row in document.rows:
            data = {
                key: row.merged_values.get(key, value) if value is None else value
                for key, value in row.data.items()
            }
            clean = clean_row_data(data, row.cell_formats)
            normalized = {key: clean.get(key) for key in data}
            rows.append(
                {
                    "sheet_or_page": row.metadata.sheet_or_page,
                    "row_or_location": row.metadata.row_or_location,
                    "values": normalized,
                    "raw_values": row.data,
                    "cell_origins": row.cell_origins,
                    "merged_fields": sorted(row.merged_values),
                    "cell_formats": row.cell_formats,
                    "formula_fields": {
                        f: "cache_missing" if data.get(f) is None else "cached"
                        for f in row.formula_fields
                    },
                }
            )
        payload = {
            "warnings": document.warnings,
            "rows": rows,
            "text_blocks": [
                {
                    "sheet_or_page": t.metadata.sheet_or_page,
                    "row_or_location": t.metadata.row_or_location,
                    "text": t.text,
                }
                for t in document.text_blocks
            ],
        }

        def encode(value: Any) -> str:
            """Serialize supported temporal values; reject unhandled cell types explicitly."""
            if isinstance(value, (datetime.datetime, datetime.date, datetime.time)):
                return value.isoformat()
            if isinstance(value, datetime.timedelta):
                return str(value)
            raise TypeError(f"Unsupported cell type: {type(value).__name__}")

        # Persist identity and payload together; no half-document becomes visible in SQLite.
        with self.connection:
            self.connection.execute(
                "INSERT INTO document_state VALUES(?,?,?,?)",
                (document.source_file, str(uuid.uuid4()), state, self.profile()),
            )
            self.connection.execute(
                "INSERT INTO documents VALUES (?, ?, ?, ?)",
                (
                    document.source_file,
                    POLICY_VERSION,
                    hashlib.sha256(original).hexdigest(),
                    json.dumps(
                        payload, ensure_ascii=False, allow_nan=False, default=encode
                    ),
                ),
            )

    def get(self, source: str) -> dict[str, Any] | None:
        """Load one versioned source or return None; never mix policy versions."""
        row = self.connection.execute(
            "SELECT version, payload FROM documents WHERE source=?", (source,)
        ).fetchone()
        if (
            row is None
            or row[0] != POLICY_VERSION
            or (self.identity(source) or {}).get("state") != "ready"
        ):
            return None
        from app.structured.continuation import apply_continuations

        # Apply the disclosed view on read; raw_values in the stored payload remain unchanged.
        return apply_continuations(dict(json.loads(row[1])), source)

    @staticmethod
    def profile() -> str:
        """Persist reproducible automatic processing identity, without a settings UI."""
        return json.dumps(
            {
                "name": "automatic-v1",
                "record_policy": POLICY_VERSION,
                "table_chunking": "row-aware-v1",
                "prose_chunking": "recursive-800-100",
                "embedding_model": settings.embedding_model,
            }
        )

    def bind_embedding(self, model: str, dimension: int, existing: bool) -> None:
        """Reject incompatible vector spaces without deleting the old index."""
        current = self.connection.execute(
            "SELECT value FROM pipeline_meta WHERE key='embedding'"
        ).fetchone()
        value = json.dumps({"model": model, "dimension": dimension}, sort_keys=True)
        if current and current[0] != value:
            raise ReindexRequiredError(
                "This index uses another embedding model/dimension. Restore its configuration or select a fresh CHROMA_PERSIST_DIR."
            )
        if (
            not current
            and existing
            and (model != "BAAI/bge-base-en-v1.5" or dimension != 768)
        ):
            raise ReindexRequiredError(
                "Legacy vectors require the known BGE 768-dimensional configuration or a separate fresh index."
            )
        with self.connection:
            self.connection.execute(
                "INSERT OR IGNORE INTO pipeline_meta VALUES('embedding',?)", (value,)
            )

    def revision(self) -> int:
        """Return persisted request generation."""
        return int(
            self.connection.execute(
                "SELECT revision FROM workspace WHERE id=1"
            ).fetchone()[0]
        )

    def bump_revision(self) -> int:
        """Invalidate requests created before removal/reset."""
        with self.connection:
            self.connection.execute(
                "UPDATE workspace SET revision=revision+1 WHERE id=1"
            )
        return self.revision()

    def identity(self, source: str) -> dict[str, str] | None:
        """Include unavailable entries so cleanup can be retried."""
        row = self.connection.execute(
            "SELECT document_id,state,profile FROM document_state WHERE source=?",
            (source,),
        ).fetchone()
        return (
            {"document_id": row[0], "state": row[1], "profile": row[2]} if row else None
        )

    def set_state(self, source: str, state: str) -> None:
        """Commit availability before changing the separate vector store."""
        if state not in {"ready", "indexing", "deleting"}:
            raise ValueError("Unknown document lifecycle state")
        with self.connection:
            self.connection.execute(
                "INSERT INTO document_state VALUES(?,?,?,?) ON CONFLICT(source) DO UPDATE SET state=excluded.state",
                (source, str(uuid.uuid4()), state, self.profile()),
            )

    def pending(self) -> list[str]:
        """Find interrupted operations on startup."""
        return [
            row[0]
            for row in self.connection.execute(
                "SELECT source FROM document_state WHERE state!='ready'"
            )
        ]

    def sources(self) -> list[dict[str, Any]]:
        """List ready/pending/legacy documents and available schema choices."""
        items = []
        for source, version, digest in self.connection.execute(
            "SELECT s.source, COALESCE(d.version,''),COALESCE(d.digest,'') FROM document_state s LEFT JOIN documents d ON s.source=d.source ORDER BY s.source"
        ):
            document = self.get(source)
            identity = self.identity(source) or {}
            sheets: dict[str, set[str]] = {}
            if document:
                for row in document["rows"]:
                    sheets.setdefault(row["sheet_or_page"], set()).update(row["values"])
                for block in document["text_blocks"]:
                    sheets.setdefault(block["sheet_or_page"], set())
            items.append(
                {
                    "source_file": source,
                    "policy_version": version,
                    "sha256": digest,
                    "ready": document is not None,
                    "document_id": identity.get("document_id"),
                    "state": (
                        identity.get("state")
                        if document or identity.get("state") != "ready"
                        else "reindex_required"
                    ),
                    "workspace_revision": self.revision(),
                    "processing_profile": json.loads(identity.get("profile", "{}")),
                    "extracted_rows": len(document["rows"]) if document else 0,
                    "extracted_text_blocks": (
                        len(document["text_blocks"]) if document else 0
                    ),
                    "warnings": (
                        document.get("warnings", [])
                        if document
                        else [
                            "This source requires cleanup or selective remove/re-upload; its original payload was preserved."
                        ]
                    ),
                    "sheets": [
                        {"name": name, "fields": sorted(fields)}
                        for name, fields in sheets.items()
                    ],
                }
            )
        return items

    def delete(self, source: str) -> None:
        """Compensate only a newly attempted source after ingestion failure."""
        with self.connection:
            self.connection.execute("DELETE FROM documents WHERE source=?", (source,))
            self.connection.execute(
                "DELETE FROM document_state WHERE source=?", (source,)
            )

    def close(self) -> None:
        """Release the owned connection."""
        self.connection.close()
