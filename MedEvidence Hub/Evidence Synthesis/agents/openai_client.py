import json
import time

from openai import OpenAI

from config import OPENAI_API_KEY


MODEL_NAME = "gpt-5.6-sol"
RETRYABLE_ERROR_MARKERS = (
    "408",
    "409",
    "429",
    "500",
    "502",
    "503",
    "504",
    "timeout",
    "rate limit",
    "connection",
    "temporarily unavailable",
)


def generate_json(prompt: str, model_name: str = MODEL_NAME, max_retries: int = 4) -> dict:
    if not OPENAI_API_KEY:
        raise RuntimeError("Missing OPENAI_API_KEY. Add it to the project .env file.")

    client = OpenAI(api_key=OPENAI_API_KEY.strip())
    last_error = None

    for attempt in range(max_retries + 1):
        try:
            response = client.responses.create(
                model=model_name,
                input=prompt,
                reasoning={"effort": "medium"},
                text={
                    "format": {"type": "json_object"},
                    "verbosity": "medium",
                },
            )
            return json.loads(response.output_text)
        except Exception as exc:
            last_error = exc
            message = str(exc).lower()
            is_retryable = any(marker in message for marker in RETRYABLE_ERROR_MARKERS)
            if not is_retryable or attempt >= max_retries:
                raise
            time.sleep(min(30, 3 * (2 ** attempt)))

    raise last_error
