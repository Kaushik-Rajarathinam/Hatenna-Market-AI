from __future__ import annotations

import discord
from discord.ext import commands

from market_ai.analytics.comparables import analyze_deal
from market_ai.analytics.filters import parse_deal_query
from market_ai.commands.formatting import describe_filters_name, format_percent, format_price
from market_ai.commands.ui import DealLayoutView
from market_ai.db import Database


class DealCommands(commands.Cog):
    def __init__(self, bot: commands.Bot, database: Database) -> None:
        self.bot = bot
        self.database = database

    @commands.command(name="deal")
    async def deal(self, ctx: commands.Context, *, query: str) -> None:
        try:
            filters, listing_iv, listing_price = parse_deal_query(query)
            with self.database.connect() as conn:
                analysis = analyze_deal(
                    conn,
                    filters,
                    listing_iv=listing_iv,
                    listing_price=listing_price,
                )
        except Exception as exc:
            await ctx.reply(f"Could not analyze deal: {exc}")
            return

        if DealLayoutView is not None:
            view = DealLayoutView(ctx.author.id, analysis)
            msg = await ctx.reply(view=view)
            await view.start(msg)
            return

        color = {
            "underpriced": discord.Color.green(),
            "fair": discord.Color.gold(),
            "overpriced": discord.Color.red(),
        }.get(analysis.verdict, discord.Color.light_grey())
        embed = discord.Embed(
            title=f"Deal: {describe_filters_name(analysis)}",
            color=color,
        )
        embed.add_field(name="Listing", value=f"IV {analysis.listing_iv:.1f}% at {format_price(analysis.listing_price)}", inline=False)
        embed.add_field(name="Comparable Sales", value=f"{analysis.comparable_count:,}", inline=True)
        embed.add_field(name="Median Comparable", value=format_price(analysis.median_comparable_price), inline=True)
        embed.add_field(name="Verdict", value=analysis.verdict.title(), inline=True)
        embed.add_field(name="Vs Median", value=format_percent(analysis.percent_vs_median), inline=True)
        await ctx.reply(embed=embed)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(DealCommands(bot, bot.database))
