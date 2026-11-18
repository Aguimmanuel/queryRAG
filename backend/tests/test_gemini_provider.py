"""Unit tests for the Gemini adapter.

All HTTP traffic goes through ``httpx.MockTransport``, so these tests never
call Google, need no API key and run offline (including in CI).
"""

import json

import httpx
import pytest
from queryrag.config import Settings
from queryrag.generation import GenerationProviderError
from queryrag.providers.gemini import (
    GeminiTextGenerator,
    create_gemini_generator,
)

FAKE_KEY = "test-key-not-real"


def make_generator(handler, sleeps: list[float] | None = None) -> GeminiTextGenerator:
    """Build a generator whose HTTP calls are answered by ``handler``.

    Retry delays are appended to ``sleeps`` instead of actually sleeping,
    which keeps the suite fast and lets tests assert the backoff schedule.
    """
    client = httpx.Client(transport=httpx.MockTransport(handler))
    recorded = sleeps if sleeps is not None else []

    return GeminiTextGenerator(
        api_key=FAKE_KEY,
        model="test-model",
        client=client,
        sleep=recorded.append,
    )


def gemini_payload(text: str) -> dict:
    """Minimal successful ``generateContent`` response body."""
    return {"candidates": [{"content": {"role": "model", "parts": [{"text": text}]}}]}


# --- Request/response contract ---------------------------------------------


def test_gemini_returns_text_and_sends_expected_request() -> None:
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["key"] = request.headers.get("x-goog-api-key")
        captured["body"] = json.loads(request.content)
        return httpx.Response(200, json=gemini_payload("Grounded answer."))

    answer = make_generator(handler).generate("What is preserved?")

    assert answer == "Grounded answer."
    assert captured["url"].endswith("/models/test-model:generateContent")
    assert captured["key"] == FAKE_KEY
    assert captured["body"]["contents"][0]["parts"][0]["text"] == "What is preserved?"


# --- Error handling -----------------------------------------------------------


@pytest.mark.parametrize("status_code", [400, 429, 500, 503])
def test_gemini_http_errors_raise_provider_error(status_code: int) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code, json={"error": "failure"})

    with pytest.raises(GenerationProviderError) as error:
        make_generator(handler).generate("prompt")

    assert str(status_code) in str(error.value)
    # The API key must never leak into error messages or logs.
    assert FAKE_KEY not in str(error.value)


def test_gemini_error_includes_google_message() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            404,
            json={
                "error": {"status": "NOT_FOUND", "message": "Model is not available."}
            },
        )

    with pytest.raises(GenerationProviderError) as error:
        make_generator(handler).generate("prompt")

    assert str(error.value) == "Gemini returned HTTP 404: Model is not available."


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"candidates": []},
        {"candidates": [{"finishReason": "SAFETY"}]},
        gemini_payload("   "),
    ],
)
def test_gemini_malformed_or_empty_response_raises(payload: dict) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload)

    with pytest.raises(GenerationProviderError):
        make_generator(handler).generate("prompt")


def test_gemini_timeout_raises_provider_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timed out", request=request)

    with pytest.raises(GenerationProviderError, match="timed out"):
        make_generator(handler).generate("prompt")


def test_missing_api_key_fails_fast() -> None:
    settings = Settings(gemini_api_key=None)

    with pytest.raises(GenerationProviderError, match="GEMINI_API_KEY"):
        create_gemini_generator(settings)


# --- Retry behaviour ----------------------------------------------------------


def test_temporary_503_is_retried_then_succeeds() -> None:
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(1)
        if len(calls) == 1:
            return httpx.Response(503, json={"error": {"message": "overloaded"}})
        return httpx.Response(200, json=gemini_payload("Recovered answer."))

    sleeps: list[float] = []
    answer = make_generator(handler, sleeps).generate("prompt")

    assert answer == "Recovered answer."
    assert len(calls) == 2
    assert sleeps == [1.0]


def test_persistent_503_gives_up_after_three_attempts() -> None:
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(1)
        return httpx.Response(503, json={"error": {"message": "overloaded"}})

    sleeps: list[float] = []

    with pytest.raises(GenerationProviderError, match="after 3 attempts"):
        make_generator(handler, sleeps).generate("prompt")

    assert len(calls) == 3
    assert sleeps == [1.0, 2.0]


@pytest.mark.parametrize("status_code", [400, 401, 403, 404])
def test_permanent_errors_are_not_retried(status_code: int) -> None:
    """Client errors are deterministic, so exactly one request is made."""
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(1)
        return httpx.Response(status_code, json={"error": {"message": "nope"}})

    with pytest.raises(GenerationProviderError):
        make_generator(handler).generate("prompt")

    assert len(calls) == 1


def test_timeout_is_retried_then_succeeds() -> None:
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(1)
        if len(calls) == 1:
            raise httpx.ReadTimeout("timed out", request=request)
        return httpx.Response(200, json=gemini_payload("Answer after timeout."))

    assert make_generator(handler).generate("prompt") == "Answer after timeout."
    assert len(calls) == 2
