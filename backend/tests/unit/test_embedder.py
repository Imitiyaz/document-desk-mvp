"""Unit tests for app.embedding.embedder.Embedder.

All tests inject a lightweight FakeBackend implementing the
EncoderBackend protocol -- `sentence_transformers` is never imported
here at all (only numpy, already a project dependency via pandas). This
is what "lazy import + injectable backend" (see embedder.py's module
docstring) actually buys: full unit coverage of Embedder's logic
(instruction prefixing, batch handling, metadata preservation, error
handling) without the real, heavy ML library installed anywhere.

The real model is exercised separately in
tests/integration/test_real_embedding_model.py (marked `embedding_model`,
excluded from the default run -- see pytest.ini and docs/testing.md).

Author: Imitiyaz and AI Agent
Project: RAG MVP
Layer: Verification and synthetic fixtures
"""

from __future__ import annotations

import sys
from types import SimpleNamespace
from typing import Any

import numpy as np
import pytest

from app.chunking.models import Chunk
from app.core.exceptions import EmbeddingModelLoadError
from app.embedding.embedder import (
    QUERY_INSTRUCTION,
    Embedder,
    SentenceTransformerAdapter,
    _load_default_backend,
)
from app.models.extracted import SourceMetadata


class FakeBackend:
    """A minimal EncoderBackend test double. Records every call to
    encode() so tests can assert on exactly what was passed."""

    def __init__(self, dimension: int = 3, fail: bool = False) -> None:
        self.dimension = dimension
        self.fail = fail
        self.encode_calls: list[tuple] = []

    def get_sentence_embedding_dimension(self) -> int:
        return self.dimension

    def encode(self, texts, normalize_embeddings: bool = True):  # noqa: ANN001
        if self.fail:
            raise OSError("simulated backend failure")
        self.encode_calls.append((texts, normalize_embeddings))
        if isinstance(texts, str):
            return np.array([0.1] * self.dimension)
        return np.array([[0.1 * (i + 1)] * self.dimension for i in range(len(texts))])


def _chunk(text: str, row_num: int = 2) -> Chunk:
    return Chunk(
        text=text,
        metadata=SourceMetadata(
            source_file="test.xlsx", sheet_or_page="Sheet1", row_or_location=row_num
        ),
    )


def test_embedder_uses_injected_backend_without_loading_default() -> None:
    backend = FakeBackend()
    embedder = Embedder(model_name="fake-model", backend=backend)
    assert embedder._model is backend  # never touched _load_default_backend


def test_embedder_uses_settings_default_model_name_when_none_given() -> None:
    backend = FakeBackend()
    embedder = Embedder(backend=backend)
    assert embedder.model_name  # resolved from settings, non-empty


def test_embedder_wraps_backend_load_failure_when_import_fails(monkeypatch) -> None:
    # Forces `from sentence_transformers import SentenceTransformer`
    # (inside _load_default_backend()) to raise ImportError,
    # deterministically -- regardless of whether sentence_transformers is
    # actually installed in the environment running this test. This is
    # what makes the test reliable both on a from-scratch sandbox (where
    # it may genuinely be missing) and a fully set up dev machine (where
    # it IS installed and would otherwise attempt to download a real
    # 440MB model here -- something a unit test must never do).
    monkeypatch.setitem(sys.modules, "sentence_transformers", None)
    with pytest.raises(EmbeddingModelLoadError, match="Failed to load embedding model"):
        Embedder(model_name="BAAI/bge-base-en-v1.5")


def test_embed_passages_calls_encode_without_instruction_prefix() -> None:
    backend = FakeBackend()
    embedder = Embedder(model_name="fake-model", backend=backend)

    result = embedder.embed_passages(["North region revenue grew."])

    texts_passed, normalize = backend.encode_calls[0]
    assert texts_passed == ["North region revenue grew."]
    assert normalize is True
    assert result == [[0.1, 0.1, 0.1]]


def test_embed_passages_handles_empty_list_without_calling_encode() -> None:
    backend = FakeBackend()
    embedder = Embedder(model_name="fake-model", backend=backend)

    result = embedder.embed_passages([])

    assert result == []
    assert backend.encode_calls == []


def test_embed_query_adds_bge_instruction_prefix() -> None:
    backend = FakeBackend()
    embedder = Embedder(model_name="fake-model", backend=backend)

    embedder.embed_query("What was the Q3 revenue?")

    called_text, _ = backend.encode_calls[0]
    assert called_text == QUERY_INSTRUCTION + "What was the Q3 revenue?"


def test_embed_query_never_shares_instruction_with_passages() -> None:
    # Structural guarantee: embed_passages must never see the query
    # instruction, even if called with text that happens to look like a
    # question.
    backend = FakeBackend()
    embedder = Embedder(model_name="fake-model", backend=backend)

    embedder.embed_passages(["What was the Q3 revenue?"])

    called_texts, _ = backend.encode_calls[0]
    assert QUERY_INSTRUCTION not in called_texts[0]


def test_embed_chunks_pairs_each_chunk_with_its_vector() -> None:
    backend = FakeBackend(dimension=2)
    embedder = Embedder(model_name="fake-model", backend=backend)

    chunks = [_chunk("North region", 2), _chunk("South region", 3)]
    embedded = embedder.embed_chunks(chunks)

    assert len(embedded) == 2
    assert embedded[0].text == "North region"
    assert embedded[0].vector == [0.1, 0.1]
    assert embedded[1].text == "South region"
    assert embedded[1].vector == [0.2, 0.2]


def test_embed_chunks_preserves_citation_metadata() -> None:
    backend = FakeBackend()
    embedder = Embedder(model_name="fake-model", backend=backend)

    chunks = [_chunk("North region", row_num=5)]
    embedded = embedder.embed_chunks(chunks)

    assert embedded[0].metadata == chunks[0].metadata
    assert embedded[0].metadata.row_or_location == 5


def test_embed_chunks_handles_empty_list() -> None:
    backend = FakeBackend()
    embedder = Embedder(model_name="fake-model", backend=backend)

    assert embedder.embed_chunks([]) == []
    assert backend.encode_calls == []


def test_resolve_embedding_dimension_prefers_new_method_name_when_available() -> None:
    # Covers the sentence-transformers get_sentence_embedding_dimension ->
    # get_embedding_dimension rename: a backend exposing BOTH should have
    # the new one preferred (avoids the FutureWarning on newer installs).
    from app.embedding.embedder import _resolve_embedding_dimension

    class BackendWithNewMethod(FakeBackend):
        def get_embedding_dimension(self) -> int:
            return 999  # deliberately different, to prove this one wins

    backend = BackendWithNewMethod(dimension=3)
    assert _resolve_embedding_dimension(backend) == 999


def test_resolve_embedding_dimension_falls_back_to_old_method_when_new_absent() -> None:
    from app.embedding.embedder import _resolve_embedding_dimension

    backend = FakeBackend(dimension=5)  # only has get_sentence_embedding_dimension
    assert _resolve_embedding_dimension(backend) == 5


class LibraryLikeBackend:
    """Renamed text parameter and nullable size reproduce the library boundary."""

    def __init__(self, dimension: Any = 3) -> None:
        self.dimension = dimension
        self.calls: list[tuple[Any, bool, bool, bool]] = []

    def encode(
        self,
        inputs: Any,
        /,
        *,
        normalize_embeddings: bool,
        convert_to_numpy: bool,
        convert_to_tensor: bool,
    ) -> Any:
        self.calls.append(
            (inputs, normalize_embeddings, convert_to_numpy, convert_to_tensor)
        )
        return np.array([0.1, 0.2, 0.3])

    def get_sentence_embedding_dimension(self) -> Any:
        return self.dimension


def test_default_factory_wraps_library_without_keyword_parameter_assumptions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    library = LibraryLikeBackend()
    monkeypatch.setitem(
        sys.modules,
        "sentence_transformers",
        SimpleNamespace(SentenceTransformer=lambda model_name: library),
    )
    backend = _load_default_backend("local-test-model")
    assert isinstance(backend, SentenceTransformerAdapter)
    assert Embedder(backend=backend).embed_query("North") == [0.1, 0.2, 0.3]
    assert library.calls == [(QUERY_INSTRUCTION + "North", True, True, False)]


@pytest.mark.parametrize("dimension", [None, 0, -1, True, "768"])
def test_adapter_rejects_missing_or_invalid_dimensions(dimension: Any) -> None:
    with pytest.raises(EmbeddingModelLoadError, match="positive integer dimension"):
        Embedder(backend=SentenceTransformerAdapter(LibraryLikeBackend(dimension)))


def test_adapter_prefers_new_dimension_method() -> None:
    class NewLibrary(LibraryLikeBackend):
        def get_embedding_dimension(self) -> int:
            return 768

    assert (
        SentenceTransformerAdapter(NewLibrary(None)).get_sentence_embedding_dimension()
        == 768
    )
