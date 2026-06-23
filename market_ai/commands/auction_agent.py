from __future__ import annotations

import discord
from discord.ext import commands

from market_ai.ai.llm import explain_market_payload
from market_ai.analytics.agent import compact_agent_answer, route_auction_question
from market_ai.commands.ui import AuctionAgentLayoutView, HATENNA_DEEP_PINK
from market_ai.config import get_settings
from market_ai.db import Database


class AuctionAgentCommands(commands.Cog):
    def __init__(self, bot: commands.Bot, database: Database) -> None:
        self.bot = bot
        self.database = database

    @commands.command(name="auctionai", aliases=["aai", "auctionagent"])
    async def auctionai(self, ctx: commands.Context, *, question: str) -> None:
        try:
            with self.database.connect() as conn:
                payload = route_auction_question(conn, question)
        except Exception as exc:
            await ctx.reply(f"Could not answer auction question: {exc}")
            return

        try:
            explanation = explain_market_payload(payload)
            provider = get_settings().llm_provider
            explanation_source = "Ollama local LLM explanation" if provider == "ollama" else "OpenAI explanation"
        except Exception:
            explanation = compact_agent_answer(payload)
            explanation_source = "Local tool summary"

        if AuctionAgentLayoutView is not None:
            view = AuctionAgentLayoutView(ctx.author.id, payload, explanation, explanation_source)
            msg = await ctx.reply(view=view)
            await view.start(msg)
            return

        embed = discord.Embed(
            title="Auction Intelligence",
            description=explanation[:3900],
            color=HATENNA_DEEP_PINK,
        )
        embed.set_footer(text=f"{explanation_source}. SQLite tools ran before the LLM.")
        await ctx.reply(embed=embed)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(AuctionAgentCommands(bot, bot.database))
