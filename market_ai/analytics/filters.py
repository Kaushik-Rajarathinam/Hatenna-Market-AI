from __future__ import annotations

import re

from market_ai.models import MarketFilters


_FILTER_RE = re.compile(r"^(iv|price|level)(>=|<=|=)(\d+(?:\.\d+)?)$", re.IGNORECASE)


def parse_market_filters(query: str) -> MarketFilters:
    name_parts: list[str] = []
    shiny: bool | None = None
    gmax: bool | None = None
    include_missingno = False
    iv_min: float | None = None
    iv_max: float | None = None
    iv_exact: float | None = None
    price_min: int | None = None
    price_max: int | None = None
    level_min: int | None = None
    level_max: int | None = None

    for raw_token in query.split():
        token = raw_token.strip()
        lower = token.lower()
        if lower in {"shiny", "sh"}:
            shiny = True
            continue
        if lower in {"gmax", "gigantamax"}:
            gmax = True
            continue
        if lower == "missingno":
            include_missingno = True
            name_parts.append(token)
            continue

        match = _FILTER_RE.match(lower)
        if match:
            field, operator, raw_value = match.groups()
            if field == "iv":
                value = float(raw_value)
                if operator == ">=":
                    iv_min = value
                elif operator == "<=":
                    iv_max = value
                else:
                    iv_exact = value
            elif field == "price":
                value = int(float(raw_value))
                if operator == ">=":
                    price_min = value
                elif operator == "<=":
                    price_max = value
            elif field == "level":
                value = int(float(raw_value))
                if operator == ">=":
                    level_min = value
                elif operator == "<=":
                    level_max = value
            continue

        name_parts.append(token)

    name = " ".join(name_parts).strip() or None
    return MarketFilters(
        name=name,
        shiny=shiny,
        gmax=gmax,
        include_missingno=include_missingno,
        iv_min=iv_min,
        iv_max=iv_max,
        iv_exact=iv_exact,
        price_min=price_min,
        price_max=price_max,
        level_min=level_min,
        level_max=level_max,
    )


def parse_deal_query(query: str) -> tuple[MarketFilters, float, int]:
    tokens = query.split()
    if len(tokens) < 3:
        raise ValueError("Usage: !deal Garchomp 91 750000")

    listing_price = int(float(tokens[-1].replace(",", "")))
    listing_iv = float(tokens[-2])
    filters = parse_market_filters(" ".join(tokens[:-2]))
    if not filters.name:
        raise ValueError("Please include a Pokemon name.")
    return filters, listing_iv, listing_price
