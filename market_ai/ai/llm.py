from __future__ import annotations

import json
import urllib.error
import urllib.request

from openai import OpenAI

from market_ai.ai.prompts import MARKET_ANALYST_SYSTEM_PROMPT
from market_ai.config import get_settings


def _valuation_prompt(payload: dict[str, object]) -> str:
    return (
        "Explain this Poketwo market valuation. Use the supplied stats only "
        "and keep it Discord-friendly:\n"
        f"{json.dumps(payload, indent=2)}"
    )


def _explain_with_openai(payload: dict[str, object]) -> str:
    settings = get_settings()
    if not settings.openai_explanations_enabled:
        raise RuntimeError("OpenAI explanations are disabled.")
    if not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY is not set.")

    client = OpenAI(api_key=settings.openai_api_key, max_retries=0)
    response = client.responses.create(
        model=settings.openai_model,
        input=[
            {
                "role": "system",
                "content": MARKET_ANALYST_SYSTEM_PROMPT,
            },
            {
                "role": "user",
                "content": _valuation_prompt(payload),
            },
        ],
    )
    return response.output_text.strip()


def _explain_with_ollama(payload: dict[str, object]) -> str:
    settings = get_settings()
    body = {
        "model": settings.ollama_model,
        "stream": False,
        "messages": [
            {
                "role": "system",
                "content": MARKET_ANALYST_SYSTEM_PROMPT,
            },
            {
                "role": "user",
                "content": _valuation_prompt(payload),
            },
        ],
        "options": {
            "temperature": 0.2,
            "num_predict": 450,
        },
    }
    request = urllib.request.Request(
        f"{settings.ollama_base_url}/api/chat",
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            data = json.loads(response.read().decode("utf-8"))
    except urllib.error.URLError as exc:
        raise RuntimeError(
            "Could not reach Ollama. Make sure the Ollama app is running and "
            f"{settings.ollama_model} is pulled."
        ) from exc

    message = data.get("message") or {}
    content = str(message.get("content") or "").strip()
    if not content:
        raise RuntimeError("Ollama returned an empty explanation.")
    return content


def explain_market_payload(payload: dict[str, object]) -> str:
    settings = get_settings()
    if settings.llm_provider == "ollama":
        return _explain_with_ollama(payload)
    if settings.llm_provider == "openai":
        return _explain_with_openai(payload)
    if settings.llm_provider in {"off", "none", "local"}:
        raise RuntimeError("LLM explanations are disabled.")
    raise RuntimeError(f"Unsupported LLM_PROVIDER: {settings.llm_provider}")
