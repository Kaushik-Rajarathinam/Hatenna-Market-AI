from __future__ import annotations

from collections.abc import Callable
from typing import Any

import discord

from market_ai.commands.formatting import format_percent, format_price
from market_ai.models import ComparableSale, DealAnalysis, MarketStats, TrendStats


HATENNA_PINK = 0xFCE5E7
HATENNA_DEEP_PINK = 0xD98591
GMAX_MARKER = "<:gigantamax:1417693451268390922>"


def shiny_text(flag: bool | None) -> str:
    return "shiny " if flag else ""


def gmax_text(flag: bool | None) -> str:
    return "gmax " if flag else ""


def market_subject(filters: Any) -> str:
    bits = []
    if getattr(filters, "shiny", None):
        bits.append("shiny")
    if getattr(filters, "gmax", None):
        bits.append("gmax")
    bits.append(getattr(filters, "name", None) or "market")
    return " ".join(bits).title()


def compact_date(value: str | None) -> str:
    if not value:
        return "N/A"
    return value[:10]


def sale_line(sale: ComparableSale) -> str:
    flags = []
    if sale.shiny:
        flags.append("✨")
    if sale.gmax:
        flags.append(GMAX_MARKER)
    flag_text = (" ".join(flags) + " ") if flags else ""
    iv = f"{sale.iv_percent:.1f}%" if sale.iv_percent is not None else "N/A"
    level = sale.level if sale.level is not None else "N/A"
    return (
        f"`{sale.auction_id}` **L{level} {flag_text}{sale.name}**"
        f"　•　{iv}　•　{format_price(sale.price)}　•　{compact_date(sale.auction_date)}"
    )


def make_embed(
    *,
    title: str,
    description: str | None = None,
    color: int = HATENNA_PINK,
) -> discord.Embed:
    return discord.Embed(title=title, description=description, color=color)


if hasattr(discord.ui, "LayoutView"):

    class HatennaLayoutView(discord.ui.LayoutView):  # type: ignore[attr-defined]
        def __init__(self, owner_id: int, *, timeout: float = 180.0) -> None:
            super().__init__(timeout=timeout)
            self.owner_id = owner_id
            self._msg: discord.Message | None = None

        async def start(self, msg: discord.Message) -> None:
            self._msg = msg

        def _button(
            self,
            label: str,
            style: discord.ButtonStyle,
            callback: Callable[..., Any],
            *,
            disabled: bool = False,
        ) -> discord.ui.Button:
            button = discord.ui.Button(label=label, style=style, disabled=disabled)
            button.callback = callback
            return button

        def _separator(self, *, visible: bool = True):
            try:
                return discord.ui.Separator(visible=visible)  # type: ignore[attr-defined]
            except TypeError:
                return discord.ui.Separator(divider=visible)  # type: ignore[attr-defined]

        async def interaction_check(self, interaction: discord.Interaction) -> bool:
            if interaction.user.id != self.owner_id:
                await interaction.response.send_message("Only the command invoker can use this panel.", ephemeral=True)
                return False
            return True

        async def on_timeout(self) -> None:
            for child in self.walk_children():
                if isinstance(child, discord.ui.Button):
                    child.disabled = True
            if self._msg:
                try:
                    await self._msg.edit(view=self)
                except Exception:
                    pass


    class MarketStatsLayoutView(HatennaLayoutView):
        def __init__(
            self,
            owner_id: int,
            stats: MarketStats,
            recent_sales: list[ComparableSale] | None = None,
        ) -> None:
            self.stats = stats
            self.recent_sales = recent_sales or []
            self.mode = "overview"
            super().__init__(owner_id)
            self._rebuild()

        def _rebuild(self) -> None:
            self.clear_items()
            card = discord.ui.Container(accent_color=HATENNA_PINK)  # type: ignore[attr-defined]
            subject = market_subject(self.stats.filters)
            if self.mode == "recent":
                card.add_item(discord.ui.TextDisplay(f"### Recent {subject} Sales"))  # type: ignore[attr-defined]
                lines = "\n".join(sale_line(sale) for sale in self.recent_sales[:10]) or "-# No recent matching sales found."
                card.add_item(discord.ui.TextDisplay(lines))  # type: ignore[attr-defined]
            else:
                card.add_item(discord.ui.TextDisplay(f"### {subject} Market"))  # type: ignore[attr-defined]
                card.add_item(
                    discord.ui.TextDisplay(
                        f"**Sample:** {self.stats.sample_size:,} sales\n"
                        f"**Median / Avg:** {format_price(self.stats.median_price)} / {format_price(self.stats.average_price)}\n"
                        f"**Range:** {format_price(self.stats.min_price)} - {format_price(self.stats.max_price)}\n"
                        f"**Middle 50%:** {format_price(self.stats.percentile_25)} - {format_price(self.stats.percentile_75)}"
                    )
                )  # type: ignore[attr-defined]
                card.add_item(self._separator())  # type: ignore[attr-defined]
                card.add_item(
                    discord.ui.Section(
                        discord.ui.TextDisplay(
                            f"**Newest sale**\n-# {compact_date(self.stats.newest_sale)}"
                        ),
                        accessory=self._button("Recent", discord.ButtonStyle.primary, self.show_recent, disabled=not self.recent_sales),
                    )
                )  # type: ignore[attr-defined]
                card.add_item(
                    discord.ui.Section(
                        discord.ui.TextDisplay(
                            f"**Oldest sale**\n-# {compact_date(self.stats.oldest_sale)}"
                        ),
                        accessory=self._button("Overview", discord.ButtonStyle.secondary, self.show_overview, disabled=True),
                    )
                )  # type: ignore[attr-defined]
            self.add_item(card)
            row = discord.ui.ActionRow()  # type: ignore[attr-defined]
            row.add_item(self._button("Overview", discord.ButtonStyle.secondary, self.show_overview, disabled=self.mode == "overview"))
            row.add_item(self._button("Recent", discord.ButtonStyle.primary, self.show_recent, disabled=self.mode == "recent" or not self.recent_sales))
            self.add_item(row)

        async def show_overview(self, interaction: discord.Interaction) -> None:
            self.mode = "overview"
            self._rebuild()
            await interaction.response.edit_message(view=self)

        async def show_recent(self, interaction: discord.Interaction) -> None:
            self.mode = "recent"
            self._rebuild()
            await interaction.response.edit_message(view=self)


    class DealLayoutView(HatennaLayoutView):
        def __init__(self, owner_id: int, analysis: DealAnalysis) -> None:
            self.analysis = analysis
            super().__init__(owner_id)
            self._rebuild()

        def _rebuild(self) -> None:
            self.clear_items()
            verdict_color = {
                "underpriced": 0x57F287,
                "fair": 0xFEE75C,
                "overpriced": 0xED4245,
            }.get(self.analysis.verdict, HATENNA_PINK)
            card = discord.ui.Container(accent_color=verdict_color)  # type: ignore[attr-defined]
            card.add_item(discord.ui.TextDisplay(f"### Deal Check: {market_subject(self.analysis.filters)}"))  # type: ignore[attr-defined]
            card.add_item(
                discord.ui.TextDisplay(
                    f"**Listing:** IV {self.analysis.listing_iv:.1f}% at {format_price(self.analysis.listing_price)}\n"
                    f"**Comparable Sales:** {self.analysis.comparable_count:,}\n"
                    f"**Comparable Median:** {format_price(self.analysis.median_comparable_price)}\n"
                    f"**Verdict:** {self.analysis.verdict.title()} ({format_percent(self.analysis.percent_vs_median)} vs median)"
                )
            )  # type: ignore[attr-defined]
            card.add_item(self._separator())  # type: ignore[attr-defined]
            card.add_item(
                discord.ui.TextDisplay(
                    "-# Underpriced means at least 15% below comparable median. "
                    "Fair is within 15%. Overpriced is at least 15% above."
                )
            )  # type: ignore[attr-defined]
            self.add_item(card)


    class TrendLayoutView(HatennaLayoutView):
        def __init__(self, owner_id: int, stats: TrendStats) -> None:
            self.stats = stats
            super().__init__(owner_id)
            self._rebuild()

        def _rebuild(self) -> None:
            self.clear_items()
            card = discord.ui.Container(accent_color=HATENNA_PINK)  # type: ignore[attr-defined]
            card.add_item(discord.ui.TextDisplay(f"### Trend: {market_subject(self.stats.filters)}"))  # type: ignore[attr-defined]
            card.add_item(
                discord.ui.TextDisplay(
                    f"**7d / 30d Median:** {format_price(self.stats.median_7d)} / {format_price(self.stats.median_30d)}\n"
                    f"**90d / 365d Median:** {format_price(self.stats.median_90d)} / {format_price(self.stats.median_365d)}\n"
                    f"**30d / 90d Volume:** {self.stats.volume_30d:,} / {self.stats.volume_90d:,}\n"
                    f"**30d vs 90d:** {format_percent(self.stats.percent_change_90d_to_30d)}\n"
                    f"**Market:** {self.stats.direction.title()}"
                )
            )  # type: ignore[attr-defined]
            self.add_item(card)


    class RecentSalesLayoutView(HatennaLayoutView):
        def __init__(self, owner_id: int, title: str, sales: list[ComparableSale]) -> None:
            self.title = title
            self.sales = sales
            super().__init__(owner_id)
            self._rebuild()

        def _rebuild(self) -> None:
            self.clear_items()
            card = discord.ui.Container(accent_color=HATENNA_PINK)  # type: ignore[attr-defined]
            card.add_item(discord.ui.TextDisplay(f"### Recent {self.title} Sales"))  # type: ignore[attr-defined]
            lines = "\n".join(sale_line(sale) for sale in self.sales[:10]) or "-# No matching sales found."
            card.add_item(discord.ui.TextDisplay(lines))  # type: ignore[attr-defined]
            card.add_item(self._separator())  # type: ignore[attr-defined]
            card.add_item(discord.ui.TextDisplay(f"-# Showing {min(len(self.sales), 10):,} most recent matching auction sale(s)."))  # type: ignore[attr-defined]
            self.add_item(card)


    class AdvisorLayoutView(HatennaLayoutView):
        def __init__(self, owner_id: int, payload: dict[str, Any], explanation: str, explanation_source: str) -> None:
            self.payload = payload
            self.explanation = explanation
            self.explanation_source = explanation_source
            self.mode = "explain"
            super().__init__(owner_id)
            self._rebuild()

        def _market(self) -> dict[str, Any]:
            return self.payload["market_stats"]

        def _trend(self) -> dict[str, Any]:
            return self.payload["trend_stats"]

        def _prediction(self) -> dict[str, Any] | None:
            return self.payload.get("ml_prediction")

        def _deal(self) -> dict[str, Any] | None:
            return self.payload.get("deal_analysis")

        def _rebuild(self) -> None:
            self.clear_items()
            card = discord.ui.Container(accent_color=HATENNA_DEEP_PINK)  # type: ignore[attr-defined]
            pokemon = self.payload.get("pokemon") or "Market"
            card.add_item(discord.ui.TextDisplay(f"### Market Advisor: {pokemon}"))  # type: ignore[attr-defined]
            if self.mode == "stats":
                market = self._market()
                trend = self._trend()
                prediction = self._prediction()
                estimate = format_price(prediction["price"]) if prediction else "N/A"
                card.add_item(
                    discord.ui.TextDisplay(
                        f"**Median / Avg:** {format_price(market['median_price'])} / {format_price(market['average_price'])}\n"
                        f"**Sample:** {market['sample_size']:,} comparable sales\n"
                        f"**Middle 50%:** {format_price(market['percentile_25'])} - {format_price(market['percentile_75'])}\n"
                        f"**Trend:** {trend['direction'].title()} ({format_percent(trend['percent_change_90d_to_30d'])})\n"
                        f"**ML Estimate:** {estimate}"
                    )
                )  # type: ignore[attr-defined]
            elif self.mode == "recent":
                sales = self.payload.get("recent_comparable_sales") or []
                lines = []
                for raw in sales[:5]:
                    sale = ComparableSale(**raw)
                    lines.append(sale_line(sale))
                card.add_item(discord.ui.TextDisplay("\n".join(lines) or "-# No recent comparable sales found."))  # type: ignore[attr-defined]
            else:
                card.add_item(discord.ui.TextDisplay(self.explanation[:3800]))  # type: ignore[attr-defined]
                deal = self._deal()
                if deal:
                    card.add_item(self._separator())  # type: ignore[attr-defined]
                    card.add_item(
                        discord.ui.TextDisplay(
                            f"**Deal verdict:** {deal['verdict'].title()}\n"
                            f"-# Listing: {format_price(deal['listing_price'])} • Median: {format_price(deal['median_comparable_price'])}"
                        )
                    )  # type: ignore[attr-defined]
            card.add_item(self._separator())  # type: ignore[attr-defined]
            card.add_item(discord.ui.TextDisplay(f"-# {self.explanation_source}. Uses auction stats first; AI only explains summarized data."))  # type: ignore[attr-defined]
            self.add_item(card)
            row = discord.ui.ActionRow()  # type: ignore[attr-defined]
            row.add_item(self._button("Explain", discord.ButtonStyle.primary, self.show_explain, disabled=self.mode == "explain"))
            row.add_item(self._button("Stats", discord.ButtonStyle.secondary, self.show_stats, disabled=self.mode == "stats"))
            row.add_item(self._button("Recent", discord.ButtonStyle.secondary, self.show_recent, disabled=self.mode == "recent"))
            self.add_item(row)

        async def show_explain(self, interaction: discord.Interaction) -> None:
            self.mode = "explain"
            self._rebuild()
            await interaction.response.edit_message(view=self)

        async def show_stats(self, interaction: discord.Interaction) -> None:
            self.mode = "stats"
            self._rebuild()
            await interaction.response.edit_message(view=self)

        async def show_recent(self, interaction: discord.Interaction) -> None:
            self.mode = "recent"
            self._rebuild()
            await interaction.response.edit_message(view=self)

else:
    HatennaLayoutView = None  # type: ignore[assignment]
    MarketStatsLayoutView = None  # type: ignore[assignment]
    DealLayoutView = None  # type: ignore[assignment]
    TrendLayoutView = None  # type: ignore[assignment]
    RecentSalesLayoutView = None  # type: ignore[assignment]
    AdvisorLayoutView = None  # type: ignore[assignment]
