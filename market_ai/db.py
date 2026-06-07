from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path


AUCTIONS_TABLE = "auctions"


class Database:
    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        if not self.path.exists():
            raise FileNotFoundError(
                f"SQLite database not found at {self.path}. "
                "Move your auctions.db there or set AUCTIONS_DB_PATH."
            )
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()


def get_columns(conn: sqlite3.Connection, table: str = AUCTIONS_TABLE) -> set[str]:
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return {str(row["name"]) for row in rows}


def get_iv_expr_sql(conn: sqlite3.Connection, table_alias: str = "a") -> str:
    columns = get_columns(conn)
    prefix = f"{table_alias}." if table_alias else ""
    if "iv" in columns:
        iv_col = f"{prefix}iv"
        return (
            "CASE "
            f"WHEN {iv_col} IS NULL THEN NULL "
            f"WHEN {iv_col} BETWEEN 0 AND 1 THEN {iv_col} * 100.0 "
            f"WHEN {iv_col} > 100 THEN ({iv_col} / 186.0) * 100.0 "
            f"ELSE {iv_col} "
            "END"
        )

    iv_columns = ["hp_iv", "attack_iv", "defense_iv", "sp_atk_iv", "sp_def_iv", "speed_iv"]
    if all(column in columns for column in iv_columns):
        total = " + ".join(f"COALESCE({prefix}{column}, 0)" for column in iv_columns)
        return f"(({total}) / 186.0) * 100.0"

    return "NULL"


def calculate_iv_percent(row: sqlite3.Row | dict[str, object]) -> float | None:
    data = dict(row)
    iv = data.get("iv")
    if iv is not None:
        iv_float = float(iv)
        if 0 <= iv_float <= 1:
            return iv_float * 100.0
        if iv_float > 100:
            return (iv_float / 186.0) * 100.0
        return iv_float

    iv_columns = ["hp_iv", "attack_iv", "defense_iv", "sp_atk_iv", "sp_def_iv", "speed_iv"]
    values = [data.get(column) for column in iv_columns]
    if any(value is None for value in values):
        return None
    return (sum(float(value) for value in values) / 186.0) * 100.0


def ensure_indexes(conn: sqlite3.Connection) -> None:
    columns = get_columns(conn)
    statements = [
        "CREATE INDEX IF NOT EXISTS idx_auctions_lower_name ON auctions(LOWER(name))",
        "CREATE INDEX IF NOT EXISTS idx_auctions_auction_date ON auctions(auction_date)",
        "CREATE INDEX IF NOT EXISTS idx_auctions_price ON auctions(price)",
        "CREATE INDEX IF NOT EXISTS idx_auctions_shiny ON auctions(shiny)",
        "CREATE INDEX IF NOT EXISTS idx_auctions_gmax ON auctions(gmax)",
    ]
    if "iv" in columns:
        statements.append("CREATE INDEX IF NOT EXISTS idx_auctions_iv ON auctions(iv)")

    for statement in statements:
        conn.execute(statement)
    conn.commit()
