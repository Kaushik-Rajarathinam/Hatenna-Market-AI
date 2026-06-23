from __future__ import annotations

import asyncio
import logging

import discord
from discord.ext import commands

from market_ai.config import get_settings
from market_ai.db import Database, ensure_indexes


LOGGER = logging.getLogger(__name__)
EXTENSIONS = [
    "market_ai.commands.market",
    "market_ai.commands.deal",
    "market_ai.commands.trend",
    "market_ai.commands.predict",
    "market_ai.commands.advisor",
    "market_ai.commands.auction_agent",
]


class MarketBot(commands.Bot):
    database: Database


async def create_bot() -> MarketBot:
    settings = get_settings()
    intents = discord.Intents.default()
    intents.message_content = True
    bot = MarketBot(command_prefix=settings.command_prefix, intents=intents)
    bot.database = Database(settings.database_path)

    @bot.event
    async def on_ready() -> None:
        LOGGER.info("Logged in as %s", bot.user)

    try:
        with bot.database.connect() as conn:
            ensure_indexes(conn)
    except FileNotFoundError:
        LOGGER.warning("Database not found yet at %s; indexes will be created once it exists.", settings.database_path)

    for extension in EXTENSIONS:
        await bot.load_extension(extension)
    return bot


async def main() -> None:
    logging.basicConfig(level=logging.INFO)
    settings = get_settings()
    if not settings.discord_token:
        raise RuntimeError("DISCORD_TOKEN is required.")
    bot = await create_bot()
    await bot.start(settings.discord_token)


if __name__ == "__main__":
    asyncio.run(main())
