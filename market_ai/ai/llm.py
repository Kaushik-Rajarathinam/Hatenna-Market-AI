from __future__ import annotations

import json

from openai import OpenAI

from market_ai.ai.prompts import MARKET_ANALYST_SYSTEM_PROMPT
from market_ai.config import get_settings


def explain_market_payload(payload: dict[str, object]) -> str:
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
                "content": (
                    "Explain this Poketwo market valuation. Use the supplied "
                    "stats only and keep it Discord-friendly:\n"
                    f"{json.dumps(payload, indent=2)}"
                ),
            },
        ],
    )
    return response.output_text.strip()
