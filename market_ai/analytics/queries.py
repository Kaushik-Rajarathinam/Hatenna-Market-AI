from __future__ import annotations

import sqlite3
from typing import Any

from market_ai.db import get_iv_expr_sql
from market_ai.models import ComparableSale, MarketFilters, MarketStats
from market_ai.analytics.stats import median, percentile


def build_where_clause(
    filters: MarketFilters,
    iv_expr: str,
    *,
    require_name: bool = True,
) -> tuple[str, list[Any]]:
    clauses = ["a.price IS NOT NULL", "a.price > 0", "a.auction_date IS NOT NULL"]
    params: list[Any] = []

    if not filters.include_missingno:
        clauses.append("COALESCE(a.is_missingno, 0) = 0")
    if filters.name:
        clauses.append("LOWER(a.name) = LOWER(?)")
        params.append(filters.name)
    elif require_name:
        raise ValueError("Please include a Pokemon name.")
    if filters.shiny is not None:
        clauses.append("COALESCE(a.shiny, 0) = ?")
        params.append(1 if filters.shiny else 0)
    if filters.gmax is not None:
        clauses.append("COALESCE(a.gmax, 0) = ?")
        params.append(1 if filters.gmax else 0)
    if filters.iv_exact is not None:
        clauses.append(f"{iv_expr} BETWEEN ? AND ?")
        params.extend([filters.iv_exact - 0.0001, filters.iv_exact + 0.0001])
    if filters.iv_min is not None:
        clauses.append(f"{iv_expr} >= ?")
        params.append(filters.iv_min)
    if filters.iv_max is not None:
        clauses.append(f"{iv_expr} <= ?")
        params.append(filters.iv_max)
    if filters.price_min is not None:
        clauses.append("a.price >= ?")
        params.append(filters.price_min)
    if filters.price_max is not None:
        clauses.append("a.price <= ?")
        params.append(filters.price_max)
    if filters.level_min is not None:
        clauses.append("a.level >= ?")
        params.append(filters.level_min)
    if filters.level_max is not None:
        clauses.append("a.level <= ?")
        params.append(filters.level_max)

    return " AND ".join(clauses), params


def get_market_stats(conn: sqlite3.Connection, filters: MarketFilters) -> MarketStats:
    iv_expr = get_iv_expr_sql(conn)
    where_sql, params = build_where_clause(filters, iv_expr)
    rows = conn.execute(
        f"""
        SELECT a.price, a.auction_date
        FROM auctions a
        WHERE {where_sql}
        ORDER BY a.auction_date DESC
        """,
        params,
    ).fetchall()
    prices = [int(row["price"]) for row in rows]
    return MarketStats(
        filters=filters,
        sample_size=len(prices),
        median_price=median(prices),
        average_price=(sum(prices) / len(prices)) if prices else None,
        min_price=min(prices) if prices else None,
        max_price=max(prices) if prices else None,
        percentile_25=percentile(prices, 0.25),
        percentile_75=percentile(prices, 0.75),
        newest_sale=str(rows[0]["auction_date"]) if rows else None,
        oldest_sale=str(rows[-1]["auction_date"]) if rows else None,
    )


def get_recent_sales(
    conn: sqlite3.Connection,
    filters: MarketFilters,
    *,
    limit: int = 10,
) -> list[ComparableSale]:
    iv_expr = get_iv_expr_sql(conn)
    where_sql, params = build_where_clause(filters, iv_expr)
    rows = conn.execute(
        f"""
        SELECT
            a.auction_id,
            a.name,
            {iv_expr} AS iv_percent,
            a.level,
            COALESCE(a.shiny, 0) AS shiny,
            COALESCE(a.gmax, 0) AS gmax,
            a.price,
            a.auction_date
        FROM auctions a
        WHERE {where_sql}
        ORDER BY a.auction_date DESC
        LIMIT ?
        """,
        [*params, limit],
    ).fetchall()
    return [
        ComparableSale(
            auction_id=row["auction_id"],
            name=str(row["name"]),
            iv_percent=float(row["iv_percent"]) if row["iv_percent"] is not None else None,
            level=int(row["level"]) if row["level"] is not None else None,
            shiny=bool(row["shiny"]),
            gmax=bool(row["gmax"]),
            price=int(row["price"]),
            auction_date=str(row["auction_date"]),
        )
        for row in rows
    ]
