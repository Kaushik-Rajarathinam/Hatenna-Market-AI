from __future__ import annotations

import sqlite3

from market_ai.analytics.queries import build_where_clause
from market_ai.analytics.stats import median
from market_ai.db import get_iv_expr_sql
from market_ai.models import MarketFilters, TrendStats


def _median_for_days(
    conn: sqlite3.Connection,
    filters: MarketFilters,
    days: int,
    iv_expr: str,
) -> tuple[float | None, int]:
    where_sql, params = build_where_clause(filters, iv_expr)
    rows = conn.execute(
        f"""
        SELECT a.price
        FROM auctions a
        WHERE {where_sql}
          AND datetime(a.auction_date) >= datetime('now', ?)
        """,
        [*params, f"-{days} days"],
    ).fetchall()
    prices = [int(row["price"]) for row in rows]
    return median(prices), len(prices)


def get_trend_stats(conn: sqlite3.Connection, filters: MarketFilters) -> TrendStats:
    iv_expr = get_iv_expr_sql(conn)
    median_7d, _ = _median_for_days(conn, filters, 7, iv_expr)
    median_30d, volume_30d = _median_for_days(conn, filters, 30, iv_expr)
    median_90d, volume_90d = _median_for_days(conn, filters, 90, iv_expr)
    median_365d, _ = _median_for_days(conn, filters, 365, iv_expr)

    if median_30d is None or median_90d in {None, 0}:
        percent_change = None
        direction = "not enough data"
    else:
        percent_change = ((median_30d - median_90d) / median_90d) * 100.0
        if percent_change >= 10:
            direction = "rising"
        elif percent_change <= -10:
            direction = "falling"
        else:
            direction = "stable"

    return TrendStats(
        filters=filters,
        median_7d=median_7d,
        median_30d=median_30d,
        median_90d=median_90d,
        median_365d=median_365d,
        volume_30d=volume_30d,
        volume_90d=volume_90d,
        percent_change_90d_to_30d=percent_change,
        direction=direction,
    )
