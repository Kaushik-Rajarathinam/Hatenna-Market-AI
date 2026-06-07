from __future__ import annotations

import sqlite3

from market_ai.analytics.queries import build_where_clause
from market_ai.analytics.stats import median
from market_ai.db import get_iv_expr_sql
from market_ai.models import DealAnalysis, MarketFilters


def analyze_deal(
    conn: sqlite3.Connection,
    filters: MarketFilters,
    *,
    listing_iv: float,
    listing_price: int,
    iv_window: float = 3.0,
) -> DealAnalysis:
    iv_expr = get_iv_expr_sql(conn)
    comparable_filters = MarketFilters(
        name=filters.name,
        shiny=filters.shiny,
        gmax=filters.gmax,
        include_missingno=filters.include_missingno,
        iv_min=listing_iv - iv_window,
        iv_max=listing_iv + iv_window,
    )
    where_sql, params = build_where_clause(comparable_filters, iv_expr)
    rows = conn.execute(
        f"SELECT a.price FROM auctions a WHERE {where_sql}",
        params,
    ).fetchall()
    prices = [int(row["price"]) for row in rows]
    median_price = median(prices)
    if median_price is None:
        verdict = "not enough data"
        percent_vs_median = None
    else:
        percent_vs_median = ((listing_price - median_price) / median_price) * 100.0
        if listing_price <= median_price * 0.85:
            verdict = "underpriced"
        elif listing_price >= median_price * 1.15:
            verdict = "overpriced"
        else:
            verdict = "fair"

    return DealAnalysis(
        filters=comparable_filters,
        listing_price=listing_price,
        listing_iv=listing_iv,
        comparable_count=len(prices),
        median_comparable_price=median_price,
        verdict=verdict,
        percent_vs_median=percent_vs_median,
    )
