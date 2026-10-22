# SPDX-License-Identifier: AGPL-3.0-only
"""Custom exceptions for the pipeline.

Using specific exception types (instead of a bare `Exception`) lets
calling code react differently to different failure modes. For example,
once Stage 10 builds the FastAPI ingestion endpoint, it can map
`UnsupportedFileTypeError` to HTTP 415 and `CorruptFileError` to HTTP 422
-- a distinction that's impossible to make cleanly with generic exceptions.

Author: Imitiyaz and AI Agent
Project: RAG MVP
Layer: Core
"""


class LoaderError(Exception):
    """Base class for all document loading errors. Catch this to handle
    any loader failure generically; catch a specific subclass below to
    handle one failure mode differently from another."""


class UnsupportedFileTypeError(LoaderError):
    """Raised when no registered loader supports the given file extension."""


class CorruptFileError(LoaderError):
    """Raised when a file has a supported extension but cannot be parsed
    (e.g., truncated download, non-PDF content saved with a .pdf extension)."""


class EncryptedDocumentError(LoaderError):
    """Raised when a document is password-protected and cannot be read
    without a password we don't have."""


class LegacyExcelFormatError(LoaderError):
    """Raised for legacy binary `.xls` files, which openpyxl does not
    support. The user needs to re-save as `.xlsx` first."""


class EmbeddingModelLoadError(Exception):
    """Raised when the configured Sentence Transformers model fails to
    load -- e.g. no network on first run (the model downloads from
    Hugging Face the first time), an invalid model name, or insufficient
    disk/memory. Not a LoaderError subclass -- this is a different stage
    with a different failure domain, not a document-loading concern."""


class VectorStoreConnectionError(Exception):
    """Raised when the configured vector store backend fails to load or
    connect -- e.g. the persistence directory can't be created/written,
    or the underlying client library fails to initialize. Not a
    LoaderError subclass -- a different stage, a different failure
    domain."""


class LLMClientError(Exception):
    """Base class for all LLM client errors. Catch this to handle any
    generation failure generically; catch a specific subclass below to
    handle one failure mode differently -- e.g. Stage 10's API can map
    LLMConnectionError to a 503 (transient, try again later) and
    LLMGenerationError to a 502 (the LLM itself rejected the request)."""


class LLMConnectionError(LLMClientError):
    """Raised when the LLM service (Ollama) could not be reached at all,
    even after retrying transient failures -- e.g. it isn't running, or
    the configured base URL is wrong. Distinct from LLMGenerationError:
    this means we never got a response to evaluate, not that we got a
    response indicating failure."""


class LLMGenerationError(LLMClientError):
    """Raised when the LLM service responded, but with an error -- e.g.
    the configured model isn't pulled, or the request was malformed.
    Not retried: the service is reachable and rejecting the request for
    a reason retrying won't fix."""


class InvalidFilenameError(ValueError):
    """An upload name is missing or unsafe as a portable filename."""


class UploadTooLargeError(Exception):
    """An upload exceeds the configured byte budget."""


class EmptyDocumentError(Exception):
    """A file is empty or produced no usable chunks (including scanned PDFs)."""


class DocumentAlreadyExistsError(Exception):
    """This source filename already has indexed chunks; no overwrite occurred."""


class DocumentNotFoundError(Exception):
    """A query explicitly selected a source filename that is not indexed."""


class VectorStoreOperationError(Exception):
    """A vector-store read/write failed after initial connection."""


class InvalidRecordSelectionError(LLMClientError):
    """The model did not provide a valid selection of supplied context references."""


class ReindexRequiredError(Exception):
    """An existing vector-only index lacks validated records for the current policy."""


class ExtractionLimitError(Exception):
    """Extraction exceeds declared workbook/page/row resource limits."""


class StaleWorkspaceError(Exception):
    """The document, workspace or acknowledged conversation context changed."""


class UnsupportedLayoutError(Exception):
    """Ambiguous headers or cells cannot be interpreted without losing evidence."""
