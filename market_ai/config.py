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
    openai_api_key: str | None
    openai_model: str
    openai_explanations_enabled: bool


def get_settings() -> Settings:
    openai_enabled = os.getenv("OPENAI_EXPLANATIONS_ENABLED", "true").strip().lower()
    return Settings(
        discord_token=os.getenv("DISCORD_TOKEN"),
        command_prefix=os.getenv("COMMAND_PREFIX", "!"),
        database_path=Path(os.getenv("AUCTIONS_DB_PATH", "data/auctions.db")),
        openai_api_key=os.getenv("OPENAI_API_KEY"),
        openai_model=os.getenv("OPENAI_MODEL", "gpt-5.4-nano"),
        openai_explanations_enabled=openai_enabled in {"1", "true", "yes", "y", "on"},
    )
