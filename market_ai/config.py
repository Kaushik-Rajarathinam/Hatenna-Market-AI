from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


load_dotenv()


@dataclass(frozen=True)
class Settings:
    discord_token: str | None
    command_prefix: str
    database_path: Path
    llm_provider: str
    openai_api_key: str | None
    openai_model: str
    openai_explanations_enabled: bool
    ollama_model: str
    ollama_base_url: str


def get_settings() -> Settings:
    openai_enabled = os.getenv("OPENAI_EXPLANATIONS_ENABLED", "true").strip().lower()
    return Settings(
        discord_token=os.getenv("DISCORD_TOKEN"),
        command_prefix=os.getenv("COMMAND_PREFIX", "!"),
        database_path=Path(os.getenv("AUCTIONS_DB_PATH", "data/auctions.db")),
        llm_provider=os.getenv("LLM_PROVIDER", "openai").strip().lower(),
        openai_api_key=os.getenv("OPENAI_API_KEY"),
        openai_model=os.getenv("OPENAI_MODEL", "gpt-5.4-nano"),
        openai_explanations_enabled=openai_enabled in {"1", "true", "yes", "y", "on"},
        ollama_model=os.getenv("OLLAMA_MODEL", "llama3.1:8b"),
        ollama_base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/"),
    )
