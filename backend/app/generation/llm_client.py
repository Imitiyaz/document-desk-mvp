# SPDX-License-Identifier: AGPL-3.0-only
"""Wraps Ollama's HTTP API behind a clean, testable, retryable client.

DESIGN NOTE -- deliberately NOT fail-fast at construction, unlike
Embedder (Stage 4) and VectorStore (Stage 5): those wrap a heavy LOCAL
resource (a loaded model, a DB connection) where failing immediately at
startup is cheap and desirable -- if it's going to fail, better to know
before the app is "up." LLMClient wraps a REMOTE service that can start
after this app does (Ollama might not be running yet when this app
initializes, then come up moments later) -- eagerly failing at
construction would wrongly prevent building the client before Ollama
has even had a chance to be reachable. Errors surface only when
`generate()` is actually called, which is when a real answer is actually
needed.

The injected backend separates transport/retry tests from actual model behavior.
HTTP clients are lightweight; model and vector adapters load their resources lazily.

Author: Imitiyaz and AI Agent
Project: RAG MVP
Layer: Generation
"""

from __future__ import annotations

import time
from typing import Protocol

import httpx
from loguru import logger
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.core.config import settings
from app.core.exceptions import LLMConnectionError, LLMGenerationError
from app.generation.models import AssembledPrompt, GeneratedAnswer
from app.generation.prompt_builder import RECOMMENDED_TEMPERATURE

DEFAULT_TIMEOUT_SECONDS = 60.0
DEFAULT_MAX_ATTEMPTS = 3
DEFAULT_MIN_WAIT_SECONDS = 1.0
DEFAULT_MAX_WAIT_SECONDS = 10.0


class LLMBackend(Protocol):
    """The minimal interface LLMClient needs to actually call an LLM.
    Implemented by `_HttpxOllamaBackend` (used by default) and by any
    lightweight test double.
    """

    def generate(self, prompt: str, model: str, temperature: float) -> str:
        """Generate using the injected transport; callers validate answer grounding separately."""
        ...  # noqa: E704


class _HttpxOllamaBackend:
    """Real backend: calls Ollama's `/api/generate` endpoint over HTTP.

    Maps failures into this project's own exception types at the point
    of the HTTP call, not deeper in LLMClient -- so LLMClient's retry
    logic only ever has to reason about LLMConnectionError vs.
    LLMGenerationError, never raw httpx exception types.

    Accepts an injected `httpx.Client` (defaulting to a real one) rather
    than calling the bare `httpx.post()` module function -- this is what
    lets unit tests exercise the real HTTP-call-and-parse code path via
    `httpx.MockTransport` cleanly, without monkeypatching httpx globally.
    """

    def __init__(
        self,
        base_url: str,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
        client: httpx.Client | None = None,
    ) -> None:
        self._base_url = base_url
        self._timeout_seconds = timeout_seconds
        self._owns_client = client is None
        # Ollama is local/LAN infrastructure. Ambient proxy variables must
        # not redirect document context or require an unrelated SOCKS extra.
        self._client = client if client is not None else httpx.Client(trust_env=False)

    def close(self) -> None:
        """Release the HTTP pool we own; injected clients belong to their caller."""
        if self._owns_client:
            self._client.close()

    def generate(self, prompt: str, model: str, temperature: float) -> str:
        """Generate using the injected transport; callers validate answer grounding separately."""
        return self._generate(prompt, model, temperature, False)

    def generate_json(self, prompt: str, model: str, temperature: float) -> str:
        """Use Ollama JSON mode with explicit bounded context/output options."""
        return self._generate(prompt, model, temperature, True)

    def _generate(
        self, prompt: str, model: str, temperature: float, json_output: bool
    ) -> str:
        try:
            response = self._client.post(
                f"{self._base_url}/api/generate",
                json={
                    "model": model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "temperature": temperature,
                        **(
                            {
                                "num_ctx": settings.ollama_context_length,
                                "num_predict": settings.ollama_num_predict,
                            }
                            if json_output
                            else {}
                        ),
                    },
                    **({"format": "json"} if json_output else {}),
                },
                timeout=self._timeout_seconds,
            )
        except httpx.TimeoutException as exc:
            raise LLMConnectionError(
                f"Timed out waiting for Ollama at {self._base_url}"
            ) from exc
        except httpx.ConnectError as exc:
            raise LLMConnectionError(
                f"Could not connect to Ollama at {self._base_url} -- is it running?"
            ) from exc
        except httpx.RequestError as exc:
            raise LLMConnectionError(
                f"Transport error communicating with Ollama at {self._base_url}"
            ) from exc

        if response.status_code >= 500:
            # Transient by nature (the service itself errored) -- worth retrying.
            raise LLMConnectionError(
                f"Ollama returned a server error ({response.status_code}) for model "
                f"{model!r} -- may succeed on retry"
            )
        if response.status_code >= 400:
            # The service is reachable and is rejecting the request for a reason
            # retrying won't fix (e.g. model not pulled, malformed request).
            raise LLMGenerationError(
                f"Ollama rejected the request ({response.status_code}) for model "
                f"{model!r}: {response.text}"
            )

        try:
            text = response.json()["response"]
            if not isinstance(text, str) or not text.strip():
                raise ValueError("Missing or empty response text")
        except (ValueError, KeyError, TypeError) as exc:
            raise LLMGenerationError(
                "Ollama returned an invalid generation response."
            ) from exc
        return text


class LLMClient:
    """Generates an answer from an assembled prompt via a local Ollama
    instance, retrying transient failures with exponential backoff.
    """

    def __init__(
        self,
        backend: LLMBackend | None = None,
        model: str | None = None,
        temperature: float = RECOMMENDED_TEMPERATURE,
        max_attempts: int = DEFAULT_MAX_ATTEMPTS,
        min_wait_seconds: float = DEFAULT_MIN_WAIT_SECONDS,
        max_wait_seconds: float = DEFAULT_MAX_WAIT_SECONDS,
    ) -> None:
        """
        Args:
            backend: Injected LLM backend. If omitted, a real
                `_HttpxOllamaBackend` is constructed against
                `settings.ollama_base_url`.
            model: Model name to request. Defaults to
                `settings.ollama_model`.
            temperature: Generation temperature. Defaults to Stage 7's
                `RECOMMENDED_TEMPERATURE` -- the value that stage
                documented but deliberately never enforced itself, since
                Stage 7 never calls an LLM. This is where it's actually used.
            max_attempts: Total attempts (including the first) before
                giving up on a transient failure.
            min_wait_seconds, max_wait_seconds: Exponential backoff
                bounds between retry attempts. Tests override these to
                near-zero so retry logic can be verified without real
                wall-clock delays.
        """
        self._backend: LLMBackend = (
            backend
            if backend is not None
            else _HttpxOllamaBackend(base_url=settings.ollama_base_url)
        )
        self._model = model or settings.ollama_model
        self._temperature = temperature
        self._max_attempts = max_attempts
        self._min_wait_seconds = min_wait_seconds
        self._max_wait_seconds = max_wait_seconds

    def generate(self, prompt: AssembledPrompt) -> GeneratedAnswer:
        """Sends `prompt.text` to the configured model and returns a
        `GeneratedAnswer`.

        Raises:
            LLMConnectionError: If Ollama could not be reached, even
                after retrying transient failures.
            LLMGenerationError: If Ollama was reachable but rejected the
                request (not retried -- see `_HttpxOllamaBackend`).
        """
        logger.info(
            "Generating answer with model {!r} (temperature={})",
            self._model,
            self._temperature,
        )
        start = time.perf_counter()
        raw_text = self._generate_with_retry(prompt.text, prompt.json_output)
        latency = time.perf_counter() - start

        logger.info("Generated answer in {:.2f}s ({} char(s))", latency, len(raw_text))

        return GeneratedAnswer(
            raw_text=raw_text,
            prompt=prompt,
            model=self._model,
            latency_seconds=latency,
        )

    def _generate_with_retry(self, prompt_text: str, json_output: bool = False) -> str:
        @retry(
            retry=retry_if_exception_type(LLMConnectionError),
            stop=stop_after_attempt(self._max_attempts),
            wait=wait_exponential(
                min=self._min_wait_seconds, max=self._max_wait_seconds
            ),
            reraise=True,
        )
        def _call() -> str:
            method = (
                getattr(self._backend, "generate_json", self._backend.generate)
                if json_output
                else self._backend.generate
            )
            return method(
                prompt=prompt_text, model=self._model, temperature=self._temperature
            )

        return _call()

    def close(self) -> None:
        """Release backend resources when it offers a close method."""
        close = getattr(self._backend, "close", None)
        if callable(close):
            close()
