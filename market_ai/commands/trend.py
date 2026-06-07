from __future__ import annotations

import discord
from discord.ext import commands

from market_ai.analytics.filters import parse_market_filters
from market_ai.analytics.trends import get_trend_stats
from market_ai.commands.formatting import describe_filters_name, format_percent, format_price
from market_ai.commands.ui import HATENNA_PINK, TrendLayoutView
from market_ai.db import Database


class TrendCommands(commands.Cog):
    def __init__(self, bot: commands.Bot, database: Database) -> None:
        self.bot = bot
        self.database = database

    @commands.command(name="trend")
    async def trend(self, ctx: commands.Context, *, query: str) -> None:
        filters = parse_market_filters(query)
        try:
            with self.database.connect() as conn:
                stats = get_trend_stats(conn, filters)
        except Exception as exc:
            await ctx.reply(f"Could not analyze trend: {exc}")
            return

        if TrendLayoutView is not None:
            view = TrendLayoutView(ctx.author.id, stats)
            msg = await ctx.reply(view=view)
            await view.start(msg)
            return

        embed = discord.Embed(
            title=f"Trend: {describe_filters_name(stats)}",
            color=HATENNA_PINK,
        )
        embed.add_field(name="7d Median", value=format_price(stats.median_7d), inline=True)
        embed.add_field(name="30d Median", value=format_price(stats.median_30d), inline=True)
        embed.add_field(name="90d Median", value=format_price(stats.median_90d), inline=True)
        embed.add_field(name="365d Median", value=format_price(stats.median_365d), inline=True)
        embed.add_field(name="30d / 90d Volume", value=f"{stats.volume_30d:,} / {stats.volume_90d:,}", inline=True)
        embed.add_field(name="30d vs 90d", value=format_percent(stats.percent_change_90d_to_30d), inline=True)
        embed.add_field(name="Market", value=stats.direction.title(), inline=True)
        await ctx.reply(embed=embed)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(TrendCommands(bot, bot.database))
