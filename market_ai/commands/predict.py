from __future__ import annotations

import discord
from discord.ext import commands

from market_ai.analytics.filters import parse_market_filters
from market_ai.commands.formatting import format_price
from market_ai.ml.predictor import PricePredictor
from market_ai.models import PredictionInput


def parse_prediction_query(query: str) -> PredictionInput:
    tokens = query.split()
    if len(tokens) < 2:
        raise ValueError("Usage: !predict Garchomp 91 or !predict shiny Garchomp 91")
    iv_percent = float(tokens[-1])
    filters = parse_market_filters(" ".join(tokens[:-1]))
    if not filters.name:
        raise ValueError("Please include a Pokemon name.")
    return PredictionInput(
        name=filters.name,
        iv_percent=iv_percent,
        shiny=bool(filters.shiny),
        gmax=bool(filters.gmax),
        is_missingno=filters.include_missingno,
    )


class PredictCommands(commands.Cog):
    def __init__(self) -> None:
        self.predictor = PricePredictor()

    @commands.command(name="predict")
    async def predict(self, ctx: commands.Context, *, query: str) -> None:
        try:
            request = parse_prediction_query(query)
            price = self.predictor.predict(request)
            metadata = self.predictor.metadata
        except Exception as exc:
            await ctx.reply(f"Could not predict price: {exc}")
            return

        embed = discord.Embed(title=f"Prediction: {request.name}", color=discord.Color.purple())
        flags = []
        if request.shiny:
            flags.append("shiny")
        if request.gmax:
            flags.append("gmax")
        embed.add_field(name="Input", value=f"{' '.join(flags) or 'normal'} | IV {request.iv_percent:.1f}%", inline=False)
        embed.add_field(name="Predicted Price", value=format_price(price), inline=True)
        embed.add_field(name="Model", value=str(metadata.get("model_type", "unknown")), inline=True)
        embed.add_field(name="Training Date", value=str(metadata.get("training_date", "unknown")), inline=False)
        embed.set_footer(text="Prediction is an estimate; compare against !market and !deal before buying.")
        await ctx.reply(embed=embed)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(PredictCommands())
