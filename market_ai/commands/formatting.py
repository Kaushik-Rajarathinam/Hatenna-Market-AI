from __future__ import annotations

from market_ai.models import DealAnalysis, MarketStats, TrendStats


def format_price(value: float | int | None) -> str:
    if value is None:
        return "n/a"
    value = float(value)
    abs_value = abs(value)
    if abs_value >= 1_000_000_000:
        return f"{value / 1_000_000_000:.2f}".rstrip("0").rstrip(".") + "B pc"
    if abs_value >= 1_000_000:
        return f"{value / 1_000_000:.2f}".rstrip("0").rstrip(".") + "M pc"
    return f"{value:,.0f} pc"


def format_percent(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"{value:+.1f}%"


def describe_filters_name(stats: MarketStats | DealAnalysis | TrendStats) -> str:
    filters = stats.filters
    bits: list[str] = []
    if filters.shiny:
        bits.append("shiny")
    if filters.gmax:
        bits.append("gmax")
    bits.append(filters.name or "market")
    if filters.iv_min is not None or filters.iv_max is not None:
        low = f"{filters.iv_min:.0f}" if filters.iv_min is not None else "0"
        high = f"{filters.iv_max:.0f}" if filters.iv_max is not None else "100"
        bits.append(f"IV {low}-{high}%")
    return " ".join(bits)
