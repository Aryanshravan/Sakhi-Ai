import json
import time

import httpx

from app.config import settings

# The lite model is fast enough for spoken conversation, and its free-tier quota is separate
# from the regular flash model's (which is only 20 requests per day).
MODEL = "gemini-3.5-flash-lite"
_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent"

# Gemini occasionally answers 429/500/503 when it is busy; a short retry usually clears it.
_RETRY_STATUSES = {429, 500, 503}
_ATTEMPTS = 3


def generate_json(system_instruction: str, contents: list[dict]) -> dict:
    """Ask Gemini for a JSON object. Raises httpx.HTTPError or ValueError on failure."""
    payload = {
        "system_instruction": {"parts": [{"text": system_instruction}]},
        "contents": contents,
        "generationConfig": {"responseMimeType": "application/json", "temperature": 0.7},
    }
    for attempt in range(1, _ATTEMPTS + 1):
        response = httpx.post(_URL, headers={"x-goog-api-key": settings.gemini_api_key}, json=payload, timeout=30)
        if response.status_code in _RETRY_STATUSES and attempt < _ATTEMPTS:
            time.sleep(attempt)
            continue
        response.raise_for_status()
        break
    text = response.json()["candidates"][0]["content"]["parts"][0]["text"]
    return json.loads(text)
