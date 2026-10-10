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


def make_generator(handler) -> GeminiTextGenerator:
    client = httpx.Client(transport=httpx.MockTransport(handler))
    return GeminiTextGenerator(api_key=FAKE_KEY, model="test-model", client=client)


def gemini_payload(text: str) -> dict:
    return {"candidates": [{"content": {"role": "model", "parts": [{"text": text}]}}]}


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


@pytest.mark.parametrize("status_code", [400, 429, 500, 503])
def test_gemini_http_errors_raise_provider_error(status_code: int) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code, json={"error": "failure"})

    with pytest.raises(GenerationProviderError) as error:
        make_generator(handler).generate("prompt")

    assert str(status_code) in str(error.value)
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
