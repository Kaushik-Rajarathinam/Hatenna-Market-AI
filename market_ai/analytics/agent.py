from __future__ import annotations

import csv
import sqlite3
from dataclasses import asdict
from pathlib import Path
from typing import Any

from market_ai.analytics.stats import median
from market_ai.commands.formatting import format_price
from market_ai.db import get_iv_expr_sql


METADATA_PATH = Path("data/pokemon_metadata.csv")


def _base_valid_clause() -> str:
    return "a.price IS NOT NULL AND a.price > 0 AND a.auction_date IS NOT NULL AND COALESCE(a.is_missingno, 0) = 0"


def _load_metadata_names(category: str, metadata_path: Path = METADATA_PATH) -> list[str]:
    if not metadata_path.exists():
        return []
    names: list[str] = []
    with metadata_path.open(newline="", encoding="utf-8") as file:
        reader = csv.DictReader(file)
        for row in reader:
            name = (row.get("name") or "").strip()
            value = str(row.get(category) or "").strip().lower()
            if name and value in {"1", "true", "yes", "y", "on"}:
                names.append(name)
    return names


def _category_from_question(question: str) -> str | None:
    lower = question.lower()
    for category in ["event", "legendary", "mythical", "ultra_beast"]:
        if category.replace("_", " ") in lower or category in lower:
            return category
    return None


def _flag_filters(question: str) -> tuple[list[str], list[Any]]:
    lower = question.lower()
    clauses: list[str] = []
    params: list[Any] = []
    if "shiny" in lower:
        clauses.append("COALESCE(a.shiny, 0) = 1")
    if "gmax" in lower or "gigantamax" in lower:
        clauses.append("COALESCE(a.gmax, 0) = 1")
    if "non shiny" in lower or "non-shiny" in lower or "normal" in lower:
        clauses.append("COALESCE(a.shiny, 0) = 0")
    category = _category_from_question(question)
    if category:
        names = _load_metadata_names(category)
        if names:
            placeholders = ", ".join("?" for _ in names)
            clauses.append(f"LOWER(a.name) IN ({placeholders})")
            params.extend(name.lower() for name in names)
    return clauses, params


def _category_note(question: str) -> str | None:
    category = _category_from_question(question)
    if not category:
        return None
    if _load_metadata_names(category):
        return None
    return (
        f"The question asks for `{category.replace('_', ' ')}` Pokemon, but "
        "`data/pokemon_metadata.csv` is not present yet. Add metadata columns like "
        "`name,event,legendary,mythical,ultra_beast` for category-aware answers."
    )


def _missing_category_payload(question: str) -> dict[str, Any] | None:
    note = _category_note(question)
    if not note:
        return None
    return {
        "tool": "metadata_required",
        "question_type": "category_lookup",
        "note": note,
        "rows": [],
    }


def _row_to_sale(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "auction_id": row["auction_id"],
        "name": row["name"],
        "price": row["price"],
        "price_text": format_price(row["price"]),
        "iv_percent": row["iv_percent"],
        "level": row["level"],
        "shiny": bool(row["shiny"]),
        "gmax": bool(row["gmax"]),
        "auction_date": row["auction_date"],
    }


def top_sales(conn: sqlite3.Connection, question: str, *, limit: int = 10) -> dict[str, Any]:
    missing_category = _missing_category_payload(question)
    if missing_category:
        return missing_category
    iv_expr = get_iv_expr_sql(conn)
    clauses, params = _flag_filters(question)
    where = " AND ".join([_base_valid_clause(), *clauses])
    rows = conn.execute(
        f"""
        SELECT
            a.auction_id,
            a.name,
            a.price,
            {iv_expr} AS iv_percent,
            a.level,
            COALESCE(a.shiny, 0) AS shiny,
            COALESCE(a.gmax, 0) AS gmax,
            a.auction_date
        FROM auctions a
        WHERE {where}
        ORDER BY a.price DESC
        LIMIT ?
        """,
        [*params, limit],
    ).fetchall()
    return {
        "tool": "top_sales",
        "question_type": "most_expensive",
        "note": _category_note(question),
        "rows": [_row_to_sale(row) for row in rows],
    }


def most_traded(conn: sqlite3.Connection, question: str, *, limit: int = 10) -> dict[str, Any]:
    missing_category = _missing_category_payload(question)
    if missing_category:
        return missing_category
    clauses, params = _flag_filters(question)
    where = " AND ".join([_base_valid_clause(), *clauses])
    rows = conn.execute(
        f"""
        SELECT
            a.name,
            COUNT(*) AS sale_count,
            AVG(a.price) AS average_price,
            MIN(a.price) AS min_price,
            MAX(a.price) AS max_price
        FROM auctions a
        WHERE {where}
        GROUP BY LOWER(a.name)
        HAVING sale_count >= 5
        ORDER BY sale_count DESC
        LIMIT ?
        """,
        [*params, limit],
    ).fetchall()
    return {
        "tool": "most_traded",
        "question_type": "volume",
        "note": _category_note(question),
        "rows": [
            {
                "name": row["name"],
                "sale_count": row["sale_count"],
                "average_price": row["average_price"],
                "average_price_text": format_price(row["average_price"]),
                "min_price_text": format_price(row["min_price"]),
                "max_price_text": format_price(row["max_price"]),
            }
            for row in rows
        ],
    }


def highest_median(conn: sqlite3.Connection, question: str, *, limit: int = 10) -> dict[str, Any]:
    missing_category = _missing_category_payload(question)
    if missing_category:
        return missing_category
    clauses, params = _flag_filters(question)
    where = " AND ".join([_base_valid_clause(), *clauses])
    rows = conn.execute(
        f"""
        SELECT a.name, a.price
        FROM auctions a
        WHERE {where}
        """,
        params,
    ).fetchall()
    grouped: dict[str, list[int]] = {}
    display_names: dict[str, str] = {}
    for row in rows:
        key = str(row["name"]).lower()
        grouped.setdefault(key, []).append(int(row["price"]))
        display_names[key] = str(row["name"])
    ranked = []
    for key, prices in grouped.items():
        if len(prices) < 5:
            continue
        ranked.append(
            {
                "name": display_names[key],
                "sample_size": len(prices),
                "median_price": median(prices),
                "median_price_text": format_price(median(prices)),
                "average_price": sum(prices) / len(prices),
                "average_price_text": format_price(sum(prices) / len(prices)),
                "max_price_text": format_price(max(prices)),
            }
        )
    ranked.sort(key=lambda row: float(row["median_price"] or 0), reverse=True)
    return {
        "tool": "highest_median",
        "question_type": "highest_typical_value",
        "note": _category_note(question),
        "rows": ranked[:limit],
    }


def trend_scan(conn: sqlite3.Connection, question: str, *, limit: int = 10) -> dict[str, Any]:
    missing_category = _missing_category_payload(question)
    if missing_category:
        return missing_category
    clauses, params = _flag_filters(question)
    where = " AND ".join([_base_valid_clause(), *clauses])
    latest_row = conn.execute(
        f"SELECT MAX(a.auction_date) AS latest_date FROM auctions a WHERE {where}",
        params,
    ).fetchone()
    latest_date = latest_row["latest_date"] if latest_row else None
    if not latest_date:
        return {
            "tool": "trend_scan",
            "question_type": "trend",
            "note": _category_note(question),
            "rows": [],
        }
    rows = conn.execute(
        f"""
        SELECT
            a.name,
            a.price,
            CASE
                WHEN datetime(a.auction_date) >= datetime(?, '-30 days') THEN 'recent'
                WHEN datetime(a.auction_date) >= datetime(?, '-90 days') THEN 'prior'
                ELSE 'old'
            END AS bucket
        FROM auctions a
        WHERE {where}
          AND datetime(a.auction_date) >= datetime(?, '-90 days')
        """,
        [latest_date, latest_date, *params, latest_date],
    ).fetchall()
    buckets: dict[str, dict[str, list[int]]] = {}
    display_names: dict[str, str] = {}
    for row in rows:
        key = str(row["name"]).lower()
        display_names[key] = str(row["name"])
        buckets.setdefault(key, {"recent": [], "prior": []})
        if row["bucket"] in {"recent", "prior"}:
            buckets[key][str(row["bucket"])].append(int(row["price"]))

    ranked = []
    for key, bucket in buckets.items():
        recent = bucket["recent"]
        prior = bucket["prior"]
        if len(recent) < 3 or len(prior) < 3:
            continue
        recent_median = median(recent)
        prior_median = median(prior)
        if not recent_median or not prior_median:
            continue
        change = ((recent_median - prior_median) / prior_median) * 100.0
        ranked.append(
            {
                "name": display_names[key],
                "recent_sample": len(recent),
                "prior_sample": len(prior),
                "recent_median": recent_median,
                "recent_median_text": format_price(recent_median),
                "prior_median": prior_median,
                "prior_median_text": format_price(prior_median),
                "percent_change": change,
            }
        )
    reverse = "fall" not in question.lower() and "down" not in question.lower()
    ranked.sort(key=lambda row: float(row["percent_change"]), reverse=reverse)
    return {
        "tool": "trend_scan",
        "question_type": "rising" if reverse else "falling",
        "note": _category_note(question),
        "latest_auction_date": latest_date,
        "rows": ranked[:limit],
    }


def route_auction_question(conn: sqlite3.Connection, question: str) -> dict[str, Any]:
    lower = question.lower()
    if any(word in lower for word in ["rising", "rise", "up", "falling", "fall", "down", "trend"]):
        result = trend_scan(conn, question)
    elif any(word in lower for word in ["most traded", "volume", "popular", "common", "sells the most", "sold the most"]):
        result = most_traded(conn, question)
    elif any(word in lower for word in ["median", "typical", "highest value", "valuable"]):
        result = highest_median(conn, question)
    else:
        result = top_sales(conn, question)

    return {
        "question": question,
        "agent": "auction_intelligence",
        "answer_contract": (
            "Use only the rows and notes supplied here. Do not invent auctions, "
            "prices, categories, or trends."
        ),
        **result,
    }


def compact_agent_answer(payload: dict[str, Any]) -> str:
    note = payload.get("note")
    rows = payload.get("rows") or []
    lines = []
    if note:
        lines.append(str(note))
    if not rows:
        lines.append("No matching auction data found.")
        return "\n".join(lines)
    if payload.get("tool") == "top_sales":
        lines.append("Top matching auction sales:")
        for index, row in enumerate(rows[:5], start=1):
            flags = []
            if row.get("shiny"):
                flags.append("shiny")
            if row.get("gmax"):
                flags.append("gmax")
            flag_text = f" ({', '.join(flags)})" if flags else ""
            iv = row.get("iv_percent")
            iv_text = f", IV {iv:.1f}%" if isinstance(iv, (int, float)) else ""
            lines.append(f"{index}. {row['name']}{flag_text}: {row['price_text']}{iv_text}")
    elif payload.get("tool") == "most_traded":
        lines.append("Most traded matching Pokemon:")
        for index, row in enumerate(rows[:5], start=1):
            lines.append(f"{index}. {row['name']}: {row['sale_count']:,} sales, avg {row['average_price_text']}")
    elif payload.get("tool") == "trend_scan":
        lines.append("Largest matching trend moves:")
        for index, row in enumerate(rows[:5], start=1):
            lines.append(
                f"{index}. {row['name']}: {row['percent_change']:+.1f}% "
                f"({row['prior_median_text']} -> {row['recent_median_text']})"
            )
    else:
        lines.append("Highest median matching markets:")
        for index, row in enumerate(rows[:5], start=1):
            lines.append(f"{index}. {row['name']}: median {row['median_price_text']} from {row['sample_size']:,} sales")
    return "\n".join(lines)
