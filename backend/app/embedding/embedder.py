# SPDX-License-Identifier: AGPL-3.0-only
"""Adapt an embedding model behind a small injectable application interface.

Load Sentence Transformers lazily so imports and isolated tests do not require
Torch or model downloads. The adapter normalizes third-party overloads and checks
the reported dimension. BGE's query instruction is applied to queries only;
passage text remains unchanged. Model/dimension compatibility is bound separately
to each persisted index. See docs/decisions/embedding-model-selection.md.

Author: Imitiyaz and AI Agent
Project: RAG MVP
Layer: Embedding
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any, Protocol

from loguru import logger

from app.chunking.models import Chunk
from app.core.config import settings
from app.core.exceptions import EmbeddingModelLoadError
from app.embedding.models import EmbeddedChunk

QUERY_INSTRUCTION = "Represent this sentence for searching relevant passages: "


class EncoderBackend(Protocol):
    """The minimal interface Embedder needs from an encoding backend.

    Implemented by our Sentence Transformers adapter (used by
    default) and by any lightweight test double. Decoupling this
    interface from the real library -- rather than importing it directly
    -- is what makes Embedder unit-testable without the real library
    installed.
    """

    def encode(self, texts: Any, normalize_embeddings: bool = ...) -> Any:
        """Encode text batches through the injected backend; preserve its output contract."""
        ...  # noqa: E704

    def get_sentence_embedding_dimension(self) -> int:
        """Return the model dimension used to validate the persisted vector space."""
        ...  # noqa: E704


class _SentenceTransformerModel(Protocol):
    """Third-party boundary: positional text, explicit array output, nullable size."""

    def encode(
        self,
        texts: Any,
        /,
        *,
        normalize_embeddings: bool,
        convert_to_numpy: bool,
        convert_to_tensor: bool,
    ) -> Any:
        """Encode text batches through the injected backend; preserve its output contract."""
        ...

    def get_sentence_embedding_dimension(self) -> int | None:
        """Return the model dimension used to validate the persisted vector space."""
        ...


class SentenceTransformerAdapter:
    """Adapt library overloads to the small, stable application interface."""

    def __init__(self, model: _SentenceTransformerModel) -> None:
        self._model = model

    def encode(self, texts: Any, normalize_embeddings: bool = True) -> Any:
        """Pass text positionally so renamed library parameters remain compatible."""
        return self._model.encode(
            texts,
            normalize_embeddings=normalize_embeddings,
            convert_to_numpy=True,
            convert_to_tensor=False,
        )

    def get_sentence_embedding_dimension(self) -> int:
        """Validate nullable library dimensions before advertising readiness."""
        get_new = getattr(self._model, "get_embedding_dimension", None)
        dimension = (
            get_new()
            if callable(get_new)
            else self._model.get_sentence_embedding_dimension()
        )
        if (
            isinstance(dimension, bool)
            or not isinstance(dimension, int)
            or dimension <= 0
        ):
            raise EmbeddingModelLoadError(
                "The embedding model did not report a positive integer dimension."
            )
        return dimension


def _load_default_backend(model_name: str) -> EncoderBackend:
    """Lazily imports and loads the real Sentence Transformers model.

    Imported here, not at module top-level -- see module docstring for
    why that matters.
    """
    try:
        from sentence_transformers import SentenceTransformer

        return SentenceTransformerAdapter(SentenceTransformer(model_name))
    except Exception as exc:
        raise EmbeddingModelLoadError(
            f"Failed to load embedding model '{model_name}'. Check your "
            "network connection (the first run downloads the model from "
            "Hugging Face) and that the model name is correct. "
            f"Underlying error: {exc}"
        ) from exc


def _resolve_embedding_dimension(model: EncoderBackend) -> int:
    """Newer sentence-transformers versions renamed
    `get_sentence_embedding_dimension()` to `get_embedding_dimension()`
    (the old name still works, just emits a FutureWarning). Prefers the
    new name when present, falls back to the old one otherwise -- works
    against either version without triggering the warning on newer
    installs.
    """
    get_new = getattr(model, "get_embedding_dimension", None)
    if callable(get_new):
        return get_new()  # type: ignore[no-any-return]
    return model.get_sentence_embedding_dimension()


class Embedder:
    """Embeds passages and queries via an EncoderBackend.

    Fails fast: if the default backend can't load (no network for the
    first-time Hugging Face download, bad model name, etc.), we find out
    immediately at construction time, not confusingly deep inside the
    first real request.
    """

    def __init__(
        self,
        model_name: str | None = None,
        backend: EncoderBackend | None = None,
    ) -> None:
        self.model_name = model_name or settings.embedding_model
        if backend is not None:
            self._model = backend
        else:
            logger.info("Loading embedding model: {}", self.model_name)
            self._model = _load_default_backend(self.model_name)
        logger.info(
            "Embedding model ready: {} (dimension: {})",
            self.model_name,
            _resolve_embedding_dimension(self._model),
        )

    def embed_passages(self, texts: Sequence[str]) -> list[list[float]]:
        """Embeds document/passage text -- no instruction prefix, per
        BAAI's guidance that only queries benefit from one.
        """
        if not texts:
            return []
        vectors = self._model.encode(list(texts), normalize_embeddings=True)
        return vectors.tolist()  # type: ignore[no-any-return]

    def embed_query(self, text: str) -> list[float]:
        """Embeds a user's search query, WITH the BGE-recommended
        instruction prefix. Never call this for passage/document text --
        use embed_passages() for that.
        """
        vector = self._model.encode(QUERY_INSTRUCTION + text, normalize_embeddings=True)
        return vector.tolist()  # type: ignore[no-any-return]

    @property
    def dimension(self) -> int:
        """Expose the validated vector-space dimension for persistent compatibility."""
        return _resolve_embedding_dimension(self._model)

    def embed_chunks(self, chunks: list[Chunk]) -> list[EmbeddedChunk]:
        """Embeds a batch of Chunks (as passages -- chunks are always
        document content, never queries) and pairs each with its vector,
        carrying citation metadata through unchanged.
        """
        if not chunks:
            return []
        vectors = self.embed_passages([chunk.text for chunk in chunks])
        embedded = [
            EmbeddedChunk(text=chunk.text, metadata=chunk.metadata, vector=vector)
            for chunk, vector in zip(chunks, vectors, strict=True)
        ]
        logger.info("Embedded {} chunk(s) using {}", len(embedded), self.model_name)
        return embedded
