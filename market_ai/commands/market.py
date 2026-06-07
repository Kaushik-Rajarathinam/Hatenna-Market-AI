from __future__ import annotations

import discord
from discord.ext import commands

from market_ai.analytics.filters import parse_market_filters
from market_ai.analytics.queries import get_market_stats, get_recent_sales
from market_ai.commands.formatting import describe_filters_name, format_price
from market_ai.commands.ui import HATENNA_PINK, MarketStatsLayoutView, RecentSalesLayoutView, market_subject
from market_ai.db import Database


class MarketCommands(commands.Cog):
    def __init__(self, bot: commands.Bot, database: Database) -> None:
        self.bot = bot
        self.database = database

    @commands.command(name="market")
    async def market(self, ctx: commands.Context, *, query: str) -> None:
        filters = parse_market_filters(query)
        try:
            with self.database.connect() as conn:
                stats = get_market_stats(conn, filters)
                recent_sales = get_recent_sales(conn, filters)
        except Exception as exc:
            await ctx.reply(f"Could not analyze market: {exc}")
            return

        if MarketStatsLayoutView is not None:
            view = MarketStatsLayoutView(ctx.author.id, stats, recent_sales)
            msg = await ctx.reply(view=view)
            await view.start(msg)
            return

        embed = discord.Embed(
            title=f"Market: {describe_filters_name(stats)}",
            color=HATENNA_PINK,
        )
        embed.add_field(name="Sample", value=f"{stats.sample_size:,}", inline=True)
        embed.add_field(name="Median", value=format_price(stats.median_price), inline=True)
        embed.add_field(name="Average", value=format_price(stats.average_price), inline=True)
        embed.add_field(name="Min", value=format_price(stats.min_price), inline=True)
        embed.add_field(name="Max", value=format_price(stats.max_price), inline=True)
        embed.add_field(name="25th / 75th", value=f"{format_price(stats.percentile_25)} / {format_price(stats.percentile_75)}", inline=False)
        embed.add_field(name="Newest", value=stats.newest_sale or "n/a", inline=True)
        embed.add_field(name="Oldest", value=stats.oldest_sale or "n/a", inline=True)
        await ctx.reply(embed=embed)

    @commands.command(name="recent")
    async def recent(self, ctx: commands.Context, *, query: str) -> None:
        filters = parse_market_filters(query)
        try:
            with self.database.connect() as conn:
                sales = get_recent_sales(conn, filters)
        except Exception as exc:
            await ctx.reply(f"Could not fetch recent sales: {exc}")
            return

        if RecentSalesLayoutView is not None:
            view = RecentSalesLayoutView(ctx.author.id, market_subject(filters), sales)
            msg = await ctx.reply(view=view)
            await view.start(msg)
            return

        embed = discord.Embed(title=f"Recent: {filters.name or query}", color=HATENNA_PINK)
        if not sales:
            embed.description = "No matching sales found."
        else:
            lines = []
            for sale in sales:
                flags = " shiny" if sale.shiny else ""
                flags += " gmax" if sale.gmax else ""
                iv = f"{sale.iv_percent:.1f}%" if sale.iv_percent is not None else "n/a"
                lines.append(
                    f"`{sale.auction_id}` {sale.name}{flags} | IV {iv} | "
                    f"Lv {sale.level or 'n/a'} | {format_price(sale.price)} | {sale.auction_date}"
                )
            embed.description = "\n".join(lines)
        await ctx.reply(embed=embed)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(MarketCommands(bot, bot.database))
