from __future__ import annotations

from market_ai.config import get_settings
from market_ai.db import Database, ensure_indexes, get_columns


def main() -> None:
    settings = get_settings()
    database = Database(settings.database_path)
    with database.connect() as conn:
        columns = get_columns(conn)
        ensure_indexes(conn)
        row_count = conn.execute("SELECT COUNT(*) AS count FROM auctions").fetchone()["count"]

    print(f"Database: {settings.database_path}")
    print(f"Rows: {row_count:,}")
    print(f"Columns: {', '.join(sorted(columns))}")
    print("Indexes: ensured")


if __name__ == "__main__":
    main()
