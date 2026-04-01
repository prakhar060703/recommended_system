import json
import os
from urllib.request import Request, urlopen


GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"


def groq_api_key():
    return os.getenv("GROQ_API_KEY", "").strip()


def groq_available():
    return bool(groq_api_key())


def enrich_content_item(payload):
    key = groq_api_key()
    if not key:
        return None

    prompt = (
        "You are enriching media content for a recommendation engine. "
        "Return strict JSON with keys: summary, topics, mood, recommendation_note. "
        "summary must be 1 sentence under 180 chars. "
        "topics must be an array of 3 to 6 short lowercase topics. "
        "mood must be one of: curious, focused, relaxed, inspired, upbeat. "
        "recommendation_note must be 1 short user-facing reason under 90 chars.\n\n"
        f"Content:\n{json.dumps(payload, ensure_ascii=True)}"
    )
    body = json.dumps(
        {
            "model": "llama-3.1-8b-instant",
            "temperature": 0.2,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": "Return only valid JSON."},
                {"role": "user", "content": prompt},
            ],
        }
    ).encode("utf-8")
    request = Request(
        GROQ_API_URL,
        data=body,
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urlopen(request, timeout=30) as response:
        data = json.loads(response.read().decode("utf-8"))
    content = data["choices"][0]["message"]["content"]
    return json.loads(content)
