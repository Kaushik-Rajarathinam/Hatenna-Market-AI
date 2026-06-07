from __future__ import annotations

import discord
from discord.ext import commands
from openai import RateLimitError

from market_ai.ai.llm import explain_market_payload
from market_ai.analytics.advisor import collect_market_advice_payload, parse_advisor_query
from market_ai.commands.formatting import format_price
from market_ai.commands.ui import AdvisorLayoutView
from market_ai.db import Database


def fallback_explanation(payload: dict[str, object]) -> str:
    market = payload["market_stats"]
    trend = payload["trend_stats"]
    deal = payload.get("deal_analysis")
    prediction = payload.get("ml_prediction")

    lines = [
        f"Market sample: {market['sample_size']:,} comparable sales.",
        f"Median comparable price: {format_price(market['median_price'])}.",
        f"Recent trend: {trend['direction']} with 30d median {format_price(trend['median_30d'])} and 90d median {format_price(trend['median_90d'])}.",
    ]
    if prediction:
        lines.append(f"ML estimate: {format_price(prediction['price'])}.")
    if deal:
        lines.append(
            f"Listing looks {deal['verdict']} versus comparable median "
            f"{format_price(deal['median_comparable_price'])}."
        )
    lines.append("Confidence is lower when sample size is small or recent sales are thin.")
    return "\n".join(lines)


class AdvisorCommands(commands.Cog):
    def __init__(self, bot: commands.Bot, database: Database) -> None:
        self.bot = bot
        self.database = database

    @commands.command(name="marketai", aliases=["explainprice", "advisor"])
    async def marketai(self, ctx: commands.Context, *, query: str) -> None:
        try:
            filters, iv_percent, listing_price = parse_advisor_query(query)
            with self.database.connect() as conn:
                payload = collect_market_advice_payload(
                    conn,
                    filters=filters,
                    iv_percent=iv_percent,
                    listing_price=listing_price,
                )
        except Exception as exc:
            await ctx.reply(f"Could not build market explanation: {exc}")
            return

        try:
            explanation = explain_market_payload(payload)
            explanation_source = "OpenAI explanation"
        except RateLimitError:
            explanation = fallback_explanation(payload)
            explanation_source = "Local fallback explanation; OpenAI rate limit or quota hit"
        except Exception:
            explanation = fallback_explanation(payload)
            explanation_source = "Local fallback explanation"

        if AdvisorLayoutView is not None:
            view = AdvisorLayoutView(ctx.author.id, payload, explanation, explanation_source)
            msg = await ctx.reply(view=view)
            await view.start(msg)
            return

        prediction = payload.get("ml_prediction")
        market = payload["market_stats"]
        title = f"Market Advisor: {payload['pokemon']}"
        embed = discord.Embed(title=title, description=explanation[:3900], color=discord.Color.purple())
        embed.add_field(name="Median", value=format_price(market["median_price"]), inline=True)
        embed.add_field(name="Sample", value=f"{market['sample_size']:,}", inline=True)
        if prediction:
            embed.add_field(name="ML Estimate", value=format_price(prediction["price"]), inline=True)
        embed.set_footer(text=f"{explanation_source}. Uses real auction stats first; AI only explains summarized data.")
        await ctx.reply(embed=embed)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(AdvisorCommands(bot, bot.database))
