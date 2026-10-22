"""Unit tests for app.generation.llm_client.

Two layers tested separately:
- LLMClient's own retry/orchestration logic, via a simple injected
  FakeBackend (no network, no httpx involved at all).
- _HttpxOllamaBackend's HTTP-to-exception mapping, via httpx's own
  supported MockTransport -- this exercises the REAL httpx call path
  (real request construction, real response parsing) without a real
  network call, catching bugs a pure-Protocol fake couldn't.

Author: Imitiyaz and AI Agent
Project: RAG MVP
Layer: Verification and synthetic fixtures
"""

from __future__ import annotations

import httpx
import pytest

from app.core.exceptions import LLMConnectionError, LLMGenerationError
from app.generation.llm_client import LLMClient, _HttpxOllamaBackend
from app.generation.models import AssembledPrompt
from app.generation.prompt_builder import build_prompt
from app.models.extracted import SourceMetadata
from app.retrieval.models import RetrievalResult


@pytest.mark.parametrize(
    "payload", [{}, {"response": None}, {"response": 123}, {"response": " "}]
)
def test_invalid_ollama_payload_is_generation_error(payload) -> None:
    with httpx.Client(
        transport=httpx.MockTransport(lambda request: httpx.Response(200, json=payload))
    ) as client:
        backend = _HttpxOllamaBackend("http://test", client=client)
        with pytest.raises(LLMGenerationError, match="invalid generation response"):
            backend.generate("prompt", "model", 0.1)


def test_ollama_read_error_is_retryable_connection_error() -> None:
    def fail(request):
        raise httpx.ReadError("connection dropped", request=request)

    with httpx.Client(transport=httpx.MockTransport(fail)) as client:
        backend = _HttpxOllamaBackend("http://test", client=client)
        with pytest.raises(LLMConnectionError, match="Transport error"):
            backend.generate("prompt", "model", 0.1)


def test_backend_close_preserves_injected_http_client() -> None:
    with httpx.Client(trust_env=False) as client:
        backend = _HttpxOllamaBackend("http://test", client=client)
        backend.close()
        assert not client.is_closed


def test_backend_close_releases_owned_http_client() -> None:
    backend = _HttpxOllamaBackend("http://test")
    backend.close()
    assert backend._client.is_closed


def make_prompt() -> AssembledPrompt:
    result = RetrievalResult(
        text="North Q3 revenue is 45000.",
        metadata=SourceMetadata(
            source_file="sample_sales.xlsx", sheet_or_page="Q3", row_or_location=2
        ),
        score=0.9,
        rank=1,
    )
    return build_prompt("What was the Q3 revenue for the North region?", [result])


class FakeBackend:
    """A LLMBackend test double. Raises the configured exception for the
    first `fail_times` calls, then returns `response_text`."""

    def __init__(
        self,
        response_text: str = "The North region's Q3 revenue was 45000. (Source: [1])",
        fail_times: int = 0,
        fail_with: type[Exception] = LLMConnectionError,
    ) -> None:
        self.response_text = response_text
        self.fail_times = fail_times
        self.fail_with = fail_with
        self.call_count = 0
        self.last_model: str | None = None
        self.last_temperature: float | None = None

    def generate(self, prompt: str, model: str, temperature: float) -> str:
        self.call_count += 1
        self.last_model = model
        self.last_temperature = temperature
        if self.call_count <= self.fail_times:
            raise self.fail_with("simulated failure")
        return self.response_text


# --- LLMClient orchestration tests (FakeBackend, no network) ---


def test_generate_returns_generated_answer_with_backend_response() -> None:
    backend = FakeBackend(response_text="The answer is 45000.")
    client = LLMClient(
        backend=backend,
        model="test-model",
        min_wait_seconds=0.01,
        max_wait_seconds=0.02,
    )

    answer = client.generate(make_prompt())

    assert answer.raw_text == "The answer is 45000."


def test_generate_uses_explicit_model_over_settings_default() -> None:
    backend = FakeBackend()
    client = LLMClient(
        backend=backend,
        model="custom-model",
        min_wait_seconds=0.01,
        max_wait_seconds=0.02,
    )

    client.generate(make_prompt())

    assert backend.last_model == "custom-model"


def test_generate_passes_configured_temperature_to_backend() -> None:
    backend = FakeBackend()
    client = LLMClient(
        backend=backend,
        model="test-model",
        temperature=0.2,
        min_wait_seconds=0.01,
        max_wait_seconds=0.02,
    )

    client.generate(make_prompt())

    assert backend.last_temperature == 0.2


def test_generate_returns_answer_carrying_the_originating_prompt() -> None:
    backend = FakeBackend()
    prompt = make_prompt()
    client = LLMClient(
        backend=backend,
        model="test-model",
        min_wait_seconds=0.01,
        max_wait_seconds=0.02,
    )

    answer = client.generate(prompt)

    assert answer.prompt is prompt
    assert answer.prompt.citation_map == prompt.citation_map


def test_generate_records_model_name_on_the_answer() -> None:
    backend = FakeBackend()
    client = LLMClient(
        backend=backend,
        model="test-model",
        min_wait_seconds=0.01,
        max_wait_seconds=0.02,
    )

    answer = client.generate(make_prompt())

    assert answer.model == "test-model"


def test_generate_records_nonnegative_latency() -> None:
    backend = FakeBackend()
    client = LLMClient(
        backend=backend,
        model="test-model",
        min_wait_seconds=0.01,
        max_wait_seconds=0.02,
    )

    answer = client.generate(make_prompt())

    assert answer.latency_seconds >= 0.0


def test_generate_retries_connection_errors_and_eventually_succeeds() -> None:
    backend = FakeBackend(fail_times=2, fail_with=LLMConnectionError)
    client = LLMClient(
        backend=backend,
        model="test-model",
        max_attempts=3,
        min_wait_seconds=0.01,
        max_wait_seconds=0.02,
    )

    answer = client.generate(make_prompt())

    assert backend.call_count == 3
    assert answer.raw_text == backend.response_text


def test_generate_raises_after_exhausting_retries() -> None:
    backend = FakeBackend(fail_times=99, fail_with=LLMConnectionError)
    client = LLMClient(
        backend=backend,
        model="test-model",
        max_attempts=3,
        min_wait_seconds=0.01,
        max_wait_seconds=0.02,
    )

    with pytest.raises(LLMConnectionError):
        client.generate(make_prompt())

    assert backend.call_count == 3  # exactly max_attempts, not more


def test_generate_does_not_retry_generation_errors() -> None:
    # LLMGenerationError means the service is reachable and rejecting
    # the request for a reason retrying won't fix -- must fail on the
    # first attempt, not be retried like a connection error.
    backend = FakeBackend(fail_times=99, fail_with=LLMGenerationError)
    client = LLMClient(
        backend=backend,
        model="test-model",
        max_attempts=3,
        min_wait_seconds=0.01,
        max_wait_seconds=0.02,
    )

    with pytest.raises(LLMGenerationError):
        client.generate(make_prompt())

    assert backend.call_count == 1


def test_generate_uses_settings_default_model_when_not_specified() -> None:
    from app.core.config import settings

    backend = FakeBackend()
    client = LLMClient(backend=backend, min_wait_seconds=0.01, max_wait_seconds=0.02)

    client.generate(make_prompt())

    assert backend.last_model == settings.ollama_model


# --- _HttpxOllamaBackend tests (real httpx call path, mocked transport) ---


def test_httpx_backend_returns_response_text_on_success() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"response": "The answer is 45000."})

    mock_client = httpx.Client(transport=httpx.MockTransport(handler))
    backend = _HttpxOllamaBackend(
        base_url="http://fake-ollama:11434", client=mock_client
    )

    result = backend.generate(prompt="a prompt", model="test-model", temperature=0.1)

    assert result == "The answer is 45000."


def test_httpx_backend_sends_correct_request_shape() -> None:
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["body"] = request.read()
        return httpx.Response(200, json={"response": "ok"})

    mock_client = httpx.Client(transport=httpx.MockTransport(handler))
    backend = _HttpxOllamaBackend(
        base_url="http://fake-ollama:11434", client=mock_client
    )

    backend.generate(
        prompt="What was Q3 revenue?",
        model="llama3.1:8b-instruct-q4_K_M",
        temperature=0.1,
    )

    assert captured["url"] == "http://fake-ollama:11434/api/generate"
    assert b"What was Q3 revenue?" in captured["body"]
    assert b"llama3.1:8b-instruct-q4_K_M" in captured["body"]


def test_httpx_backend_raises_generation_error_on_400() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(400, text="model not found")

    mock_client = httpx.Client(transport=httpx.MockTransport(handler))
    backend = _HttpxOllamaBackend(
        base_url="http://fake-ollama:11434", client=mock_client
    )

    with pytest.raises(LLMGenerationError, match="model not found"):
        backend.generate(prompt="a prompt", model="missing-model", temperature=0.1)


def test_httpx_backend_raises_connection_error_on_500() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="internal error")

    mock_client = httpx.Client(transport=httpx.MockTransport(handler))
    backend = _HttpxOllamaBackend(
        base_url="http://fake-ollama:11434", client=mock_client
    )

    with pytest.raises(LLMConnectionError):
        backend.generate(prompt="a prompt", model="test-model", temperature=0.1)


def test_httpx_backend_raises_connection_error_on_timeout() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.TimeoutException("simulated timeout", request=request)

    mock_client = httpx.Client(transport=httpx.MockTransport(handler))
    backend = _HttpxOllamaBackend(
        base_url="http://fake-ollama:11434", client=mock_client
    )

    with pytest.raises(LLMConnectionError, match="Timed out"):
        backend.generate(prompt="a prompt", model="test-model", temperature=0.1)


def test_httpx_backend_raises_connection_error_when_unreachable() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("simulated connection refused", request=request)

    mock_client = httpx.Client(transport=httpx.MockTransport(handler))
    backend = _HttpxOllamaBackend(
        base_url="http://fake-ollama:11434", client=mock_client
    )

    with pytest.raises(LLMConnectionError, match="is it running"):
        backend.generate(prompt="a prompt", model="test-model", temperature=0.1)
