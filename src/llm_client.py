import json
import logging
import os
from pathlib import Path
import re
import time
from typing import TypeVar
from openai import OpenAI, pydantic_function_tool
from pydantic import BaseModel

logger = logging.getLogger(__name__)

DEFAULT_OPENROUTER_MODEL = "nvidia/nemotron-3-ultra-550b-a55b:free"
DEFAULT_OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
DEFAULT_REFERER = "https://github.com/stars/D2S-MTP"
DEFAULT_TITLE = "Hazardous Waste Management"

T = TypeVar("T", bound=BaseModel)


def load_env_file(dotenv_path: Path | None = None) -> None:
    """Load environment variables from .env file into os.environ if present."""
    if dotenv_path is None:
        dotenv_path = Path(__file__).resolve().parent.parent / ".env"
    if dotenv_path.is_file():
        try:
            with open(dotenv_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    if "=" in line:
                        key, val = line.split("=", 1)
                        key = key.strip()
                        val = val.strip().strip("'\"")
                        if key:
                            os.environ[key] = val
        except Exception as e:
            logger.debug(f"Could not load .env file from {dotenv_path}: {e}")


# Load .env at import time if present
load_env_file()


def get_model_name() -> str:
    """Get configured OpenRouter model name with default fallback."""
    load_env_file()
    return os.getenv("OPENROUTER_MODEL") or DEFAULT_OPENROUTER_MODEL


def get_openrouter_client(
    api_key: str | None = None,
    base_url: str | None = None,
) -> OpenAI:
    """Initialize OpenAI client configured for OpenRouter endpoint and headers."""
    load_env_file()
    resolved_key = (
        api_key
        or os.getenv("OPENROUTER_API_KEY")
        or os.getenv("OPENAI_API_KEY")
    )
    if not resolved_key:
        raise RuntimeError(
            "OPENROUTER_API_KEY environment variable is not set. "
            "Please provide a valid OpenRouter API key in your .env file."
        )

    resolved_base_url = (
        base_url
        or os.getenv("OPENROUTER_BASE_URL")
        or DEFAULT_OPENROUTER_BASE_URL
    )

    return OpenAI(
        base_url=resolved_base_url,
        api_key=resolved_key,
        default_headers={
            "HTTP-Referer": os.getenv("OPENROUTER_REFERER", DEFAULT_REFERER),
            "X-Title": os.getenv("OPENROUTER_TITLE", DEFAULT_TITLE),
        },
    )


def extract_json_from_text(text: str) -> str:
    """Strip markdown code fence blocks if present around JSON text."""
    cleaned = text.strip()
    match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", cleaned, re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return cleaned


def generate_structured_output(
    client: OpenAI,
    model: str,
    prompt: str,
    response_model: type[T],
    max_retries: int = 2,
    reasoning_effort: str | None = None,
) -> T:
    """Generate validated structured Pydantic output using tool calling or JSON content fallback.

    Handles exponential backoff on transient errors (429 rate limit, 503 unavailable, etc.).
    """
    tool = pydantic_function_tool(response_model)
    function_name = tool["function"]["name"]

    extra_body = {}
    effort = reasoning_effort or os.getenv("OPENROUTER_REASONING_EFFORT")
    if effort:
        extra_body["reasoning"] = {"effort": effort}

    last_exception = None

    for attempt in range(max_retries + 1):
        try:
            kwargs = {
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "tools": [tool],
                "tool_choice": {"type": "function", "function": {"name": function_name}},
            }
            if extra_body:
                kwargs["extra_body"] = extra_body

            response = client.chat.completions.create(**kwargs)
            message = response.choices[0].message

            # Strategy 1: Tool call arguments
            if message.tool_calls:
                for tc in message.tool_calls:
                    if getattr(tc, "function", None) and tc.function.arguments:
                        return response_model.model_validate_json(tc.function.arguments)

            # Strategy 2: Content markdown / JSON fallback
            if message.content:
                raw_json = extract_json_from_text(message.content)
                return response_model.model_validate_json(raw_json)

            raise RuntimeError(f"OpenRouter model '{model}' returned neither tool calls nor message content.")

        except Exception as e:
            last_exception = e
            err_str = str(e).lower()
            is_transient = any(code in err_str for code in ["429", "rate limit", "503", "busy", "timeout", "temporarily unavailable"])
            if is_transient and attempt < max_retries:
                backoff_time = (2 ** attempt) * 1.0
                logger.warning(
                    f"Transient error querying OpenRouter (attempt {attempt + 1}/{max_retries + 1}): {e}. Backing off {backoff_time}s..."
                )
                time.sleep(backoff_time)
                continue
            raise e

    raise last_exception or RuntimeError(f"Failed to generate structured output after {max_retries + 1} attempts.")
