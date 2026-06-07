from __future__ import annotations

import sqlite3
from dataclasses import asdict

from market_ai.analytics.comparables import analyze_deal
from market_ai.analytics.filters import parse_market_filters
from market_ai.analytics.queries import get_market_stats, get_recent_sales
from market_ai.analytics.trends import get_trend_stats
from market_ai.ml.predictor import PricePredictor
from market_ai.models import MarketFilters, PredictionInput


def collect_market_advice_payload(
    conn: sqlite3.Connection,
    *,
    filters: MarketFilters,
    iv_percent: float | None,
    listing_price: int | None,
) -> dict[str, object]:
    market_filters = filters
    if iv_percent is not None:
        market_filters = MarketFilters(
            name=filters.name,
            shiny=filters.shiny,
            gmax=filters.gmax,
            include_missingno=filters.include_missingno,
            iv_min=iv_percent - 3,
            iv_max=iv_percent + 3,
            price_min=filters.price_min,
            price_max=filters.price_max,
            level_min=filters.level_min,
            level_max=filters.level_max,
        )

    market_stats = get_market_stats(conn, market_filters)
    trend_stats = get_trend_stats(conn, filters)
    recent_sales = get_recent_sales(conn, market_filters, limit=5)

    deal = None
    if iv_percent is not None and listing_price is not None:
        deal = analyze_deal(
            conn,
            filters,
            listing_iv=iv_percent,
            listing_price=listing_price,
        )

    prediction = None
    predictor = PricePredictor()
    if iv_percent is not None and filters.name and predictor.is_available:
        request = PredictionInput(
            name=filters.name,
            iv_percent=iv_percent,
            shiny=bool(filters.shiny),
            gmax=bool(filters.gmax),
            is_missingno=filters.include_missingno,
        )
        prediction = {
            "price": predictor.predict(request),
            "metadata": predictor.metadata,
        }

    return {
        "pokemon": filters.name,
        "filters": asdict(market_filters),
        "user_listing": {
            "iv_percent": iv_percent,
            "price": listing_price,
        },
        "market_stats": asdict(market_stats),
        "trend_stats": asdict(trend_stats),
        "deal_analysis": asdict(deal) if deal else None,
        "ml_prediction": prediction,
        "recent_comparable_sales": [asdict(sale) for sale in recent_sales],
    }


def parse_advisor_query(query: str) -> tuple[MarketFilters, float | None, int | None]:
    ignored_words = {
        "why",
        "is",
        "are",
        "this",
        "that",
        "the",
        "a",
        "an",
        "worth",
        "valued",
        "value",
        "price",
        "priced",
        "at",
        "for",
        "estimate",
        "explain",
        "advisor",
        "marketai",
        "explainprice",
        "please",
    }
    cleaned = (
        query.replace(",", "")
        .replace("?", " ")
        .replace("$", " ")
        .replace("pc", " ")
    )
    tokens = cleaned.split()
    numeric_indexes: list[tuple[int, float]] = []
    for index, token in enumerate(tokens):
        try:
            numeric_indexes.append((index, float(token)))
        except ValueError:
            continue

    iv_percent = None
    listing_price = None
    remove_indexes: set[int] = set()
    if numeric_indexes:
        iv_index, iv_percent = numeric_indexes[-1]
        remove_indexes.add(iv_index)
    if len(numeric_indexes) >= 2:
        price_index, price_value = numeric_indexes[-1]
        iv_index, iv_value = numeric_indexes[-2]
        if price_value > 100 and 0 <= iv_value <= 100:
            listing_price = int(price_value)
            iv_percent = iv_value
            remove_indexes = {price_index, iv_index}

    filter_query = " ".join(
        token
        for index, token in enumerate(tokens)
        if index not in remove_indexes and token.lower() not in ignored_words
    )
    filters = parse_market_filters(filter_query)
    if not filters.name:
        raise ValueError("Please include a Pokemon name, like `!marketai shiny Garchomp 91 750000`.")
    return filters, iv_percent, listing_price
