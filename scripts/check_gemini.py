"""Send one tiny request to Gemini and print the real status and error.

Never prints the API key.
"""

import httpx
from queryrag.config import get_settings
from queryrag.providers.gemini import GEMINI_BASE_URL


def main() -> None:
    settings = get_settings()
    key = (settings.gemini_api_key or "").strip()

    print(f"Model:          {settings.gemini_model}")
    print(f"Key present:    {bool(key)}")
    print(f"Key length:     {len(key)}")
    has_quotes = key[:1] in ("'", '"')
    print(f"Key has quotes: {has_quotes}")

    if not key:
        print("GEMINI_API_KEY is empty. Check your .env file.")
        return

    url = f"{GEMINI_BASE_URL}/models/{settings.gemini_model}:generateContent"

    try:
        response = httpx.post(
            url,
            headers={"x-goog-api-key": key},
            json={"contents": [{"parts": [{"text": "Reply with the word: ready"}]}]},
            timeout=30,
        )
    except httpx.HTTPError as error:
        print(f"Network error:  {type(error).__name__}: {error}")
        return

    print(f"HTTP status:    {response.status_code}")

    try:
        payload = response.json()
    except ValueError:
        print(response.text[:500])
        return

    if response.status_code >= 400:
        error = payload.get("error", {})
        print(f"Error status:   {error.get('status')}")
        print(f"Error message:  {error.get('message')}")
        return

    parts = payload["candidates"][0]["content"]["parts"]
    print("Gemini replied: " + "".join(p.get("text", "") for p in parts).strip())


if __name__ == "__main__":
    main()
