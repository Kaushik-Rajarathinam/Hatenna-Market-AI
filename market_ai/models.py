from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class MarketFilters:
    name: str | None = None
    shiny: bool | None = None
    gmax: bool | None = None
    include_missingno: bool = False
    iv_min: float | None = None
    iv_max: float | None = None
    iv_exact: float | None = None
    price_min: int | None = None
    price_max: int | None = None
    level_min: int | None = None
    level_max: int | None = None


@dataclass(frozen=True)
class MarketStats:
    filters: MarketFilters
    sample_size: int
    median_price: float | None
    average_price: float | None
    min_price: int | None
    max_price: int | None
    percentile_25: float | None
    percentile_75: float | None
    newest_sale: str | None
    oldest_sale: str | None


@dataclass(frozen=True)
class ComparableSale:
    auction_id: int | None
    name: str
    iv_percent: float | None
    level: int | None
    shiny: bool
    gmax: bool
    price: int
    auction_date: str


@dataclass(frozen=True)
class DealAnalysis:
    filters: MarketFilters
    listing_price: int
    listing_iv: float
    comparable_count: int
    median_comparable_price: float | None
    verdict: str
    percent_vs_median: float | None


@dataclass(frozen=True)
class TrendStats:
    filters: MarketFilters
    median_7d: float | None
    median_30d: float | None
    median_90d: float | None
    median_365d: float | None
    volume_30d: int
    volume_90d: int
    percent_change_90d_to_30d: float | None
    direction: str


@dataclass(frozen=True)
class PredictionInput:
    name: str
    iv_percent: float
    level: int | None = None
    shiny: bool = False
    gmax: bool = False
    gender: str | None = None
    hp_iv: int | None = None
    attack_iv: int | None = None
    defense_iv: int | None = None
    sp_atk_iv: int | None = None
    sp_def_iv: int | None = None
    speed_iv: int | None = None
    custom_color: str | None = None
    xp_current: int | None = None
    is_missingno: bool = False

    @property
    def total_iv(self) -> float:
        if all(
            value is not None
            for value in [
                self.hp_iv,
                self.attack_iv,
                self.defense_iv,
                self.sp_atk_iv,
                self.sp_def_iv,
                self.speed_iv,
            ]
        ):
            return float(
                self.hp_iv
                + self.attack_iv
                + self.defense_iv
                + self.sp_atk_iv
                + self.sp_def_iv
                + self.speed_iv
            )
        return (self.iv_percent / 100.0) * 186.0


Row = dict[str, Any]


def parse_sqlite_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    normalized = value.strip().replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(normalized)
    except ValueError:
        return None
