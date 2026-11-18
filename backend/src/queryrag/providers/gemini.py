"""Gemini text-generation adapter.

Implements the ``TextGenerator`` protocol from ``queryrag.generation`` using
the Gemini REST API (``models/{model}:generateContent``). All provider
failures surface as ``GenerationProviderError`` so callers never depend on
httpx or Gemini-specific exceptions.
"""

import logging
import time
from collections.abc import Callable

import httpx

from queryrag.config import Settings, get_settings
from queryrag.generation import GenerationProviderError

GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta"

# Transient failures that can succeed on a later attempt: rate limiting (429)
# and upstream server errors (5xx). Client errors such as 400/401/403/404 are
# deterministic (bad request, invalid key, unknown model), so retrying them
# only burns latency and quota.
RETRYABLE_STATUS_CODES = frozenset({429, 500, 502, 503, 504})

# Delay before each retry. Two entries means at most three attempts in total.
# Increasing delays (backoff) give an overloaded upstream time to recover
# instead of hitting it again immediately.
DEFAULT_BACKOFF_SECONDS: tuple[float, ...] = (1.0, 2.0)

logger = logging.getLogger("queryrag.providers.gemini")


class _RetryableError(Exception):
    """Internal signal that a single attempt failed transiently.

    Never escapes this module: ``generate`` converts it into
    ``GenerationProviderError`` once retries are exhausted.
    """


class GeminiTextGenerator:
    """Synchronous Gemini client with bounded retries for transient errors."""

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        timeout_seconds: float = 30.0,
        client: httpx.Client | None = None,
        backoff_seconds: tuple[float, ...] = DEFAULT_BACKOFF_SECONDS,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        """Create a generator.

        Args:
            api_key: Gemini API key. Required; fails fast when empty.
            model: Gemini model name, e.g. ``gemini-3.5-flash-lite``.
            timeout_seconds: Per-attempt HTTP timeout.
            client: Optional httpx client. Tests inject one backed by
                ``httpx.MockTransport`` so no real network calls are made.
            backoff_seconds: Delay before each retry; ``()`` disables retries.
            sleep: Function used to wait between attempts. Injected in tests
                so retries run instantly and the delays can be asserted.
        """
        if not api_key:
            raise GenerationProviderError(
                "GEMINI_API_KEY is required for Gemini generation"
            )

        self.api_key = api_key
        self.model = model
        self.timeout_seconds = timeout_seconds
        # TODO: share one client across requests. A new client per generator
        # means a fresh TLS handshake per /query and the client is never closed.
        self.client = client or httpx.Client()
        self.backoff_seconds = backoff_seconds
        self.sleep = sleep

    def generate(self, prompt: str) -> str:
        """Return the model's text for ``prompt``, retrying transient failures.

        Raises:
            GenerationProviderError: on a permanent failure, an unusable
                response, or when all retry attempts fail.
        """
        attempts = len(self.backoff_seconds) + 1

        for attempt in range(1, attempts + 1):
            try:
                return self._generate_once(prompt)
            except _RetryableError as error:
                if attempt == attempts:
                    raise GenerationProviderError(
                        f"{error} (after {attempts} attempts)"
                    ) from error

                delay = self.backoff_seconds[attempt - 1]
                # Logged at WARNING so intermittent upstream problems are
                # visible in the server logs even when a retry later succeeds.
                logger.warning(
                    "Gemini attempt %d/%d failed: %s. Retrying in %.1fs",
                    attempt,
                    attempts,
                    error,
                    delay,
                )
                self.sleep(delay)

        # Unreachable: the loop either returns or raises. Kept so the function
        # has an explicit exit for type checkers and future edits.
        raise GenerationProviderError("Gemini retry loop ended unexpectedly")

    def _generate_once(self, prompt: str) -> str:
        """Perform exactly one HTTP call and parse the answer text.

        Raises ``_RetryableError`` for transient failures and
        ``GenerationProviderError`` for failures that will not improve on retry.
        """
        url = f"{GEMINI_BASE_URL}/models/{self.model}:generateContent"

        try:
            response = self.client.post(
                url,
                # Header auth keeps the key out of URLs, which are often logged.
                headers={"x-goog-api-key": self.api_key},
                json={"contents": [{"parts": [{"text": prompt}]}]},
                timeout=self.timeout_seconds,
            )
        except httpx.TimeoutException as error:
            raise _RetryableError("Gemini request timed out") from error
        except httpx.HTTPError as error:
            # Connection resets, DNS failures, etc. are usually transient.
            raise _RetryableError("Gemini request failed") from error

        if response.status_code >= 400:
            message = (
                f"Gemini returned HTTP {response.status_code}: "
                f"{_error_message(response)}"
            )

            if response.status_code in RETRYABLE_STATUS_CODES:
                raise _RetryableError(message)

            raise GenerationProviderError(message)

        # Malformed or empty bodies are not retried: they usually indicate a
        # safety block or an API contract change, not a temporary outage.
        try:
            parts = response.json()["candidates"][0]["content"]["parts"]
            text = "".join(part.get("text", "") for part in parts).strip()
        except (ValueError, KeyError, IndexError, TypeError) as error:
            raise GenerationProviderError(
                "Gemini returned an unexpected response"
            ) from error

        if not text:
            raise GenerationProviderError("Gemini returned an empty answer")

        return text


def _error_message(response: httpx.Response) -> str:
    """Extract Google's error message, truncated to keep log lines bounded."""
    try:
        message = response.json()["error"]["message"]
    except (ValueError, KeyError, TypeError):
        return "no error message"

    return str(message)[:300]


def create_gemini_generator(
    settings: Settings | None = None,
) -> GeminiTextGenerator:
    """Build a generator from application settings (``.env`` / environment)."""
    settings = settings or get_settings()

    return GeminiTextGenerator(
        api_key=settings.gemini_api_key or "",
        model=settings.gemini_model,
    )
