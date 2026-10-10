import httpx

from queryrag.config import Settings, get_settings
from queryrag.generation import GenerationProviderError

GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta"


class GeminiTextGenerator:
    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        timeout_seconds: float = 30.0,
        client: httpx.Client | None = None,
    ) -> None:
        if not api_key:
            raise GenerationProviderError(
                "GEMINI_API_KEY is required for Gemini generation"
            )

        self.api_key = api_key
        self.model = model
        self.timeout_seconds = timeout_seconds
        self.client = client or httpx.Client()

    def generate(self, prompt: str) -> str:
        url = f"{GEMINI_BASE_URL}/models/{self.model}:generateContent"

        try:
            response = self.client.post(
                url,
                headers={"x-goog-api-key": self.api_key},
                json={"contents": [{"parts": [{"text": prompt}]}]},
                timeout=self.timeout_seconds,
            )
        except httpx.TimeoutException as error:
            raise GenerationProviderError("Gemini request timed out") from error
        except httpx.HTTPError as error:
            raise GenerationProviderError("Gemini request failed") from error

        if response.status_code >= 400:
            raise GenerationProviderError(
                f"Gemini returned HTTP {response.status_code}: "
                f"{_error_message(response)}"
            )        

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
    try:
        message = response.json()["error"]["message"]
    except (ValueError, KeyError, TypeError):
        return "no error message"

    return str(message)[:300]

def create_gemini_generator(
    settings: Settings | None = None,
) -> GeminiTextGenerator:
    settings = settings or get_settings()

    return GeminiTextGenerator(
        api_key=settings.gemini_api_key or "",
        model=settings.gemini_model,
    )
