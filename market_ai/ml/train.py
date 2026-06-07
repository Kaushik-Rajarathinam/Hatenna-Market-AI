from __future__ import annotations

import argparse
import json
import math
import os
import sqlite3
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

os.environ.setdefault("LOKY_MAX_CPU_COUNT", "8")

import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingRegressor, RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OrdinalEncoder

from market_ai.config import get_settings
from market_ai.db import Database, get_iv_expr_sql


MODEL_PATH = Path("models/price_model.pkl")
METADATA_PATH = Path("models/model_metadata.json")

CATEGORICAL_FEATURES = ["name", "gender", "custom_color"]
NUMERIC_FEATURES = [
    "level",
    "shiny",
    "gmax",
    "hp_iv",
    "attack_iv",
    "defense_iv",
    "sp_atk_iv",
    "sp_def_iv",
    "speed_iv",
    "total_iv",
    "iv_percent",
    "xp_current",
    "is_missingno",
]
FEATURES = CATEGORICAL_FEATURES + NUMERIC_FEATURES


@dataclass(frozen=True)
class TrainingMetadata:
    training_date: str
    model_type: str
    training_strategy: str
    row_count: int
    train_rows: int
    test_rows: int
    mae: float
    rmse: float
    r2: float
    target: str
    features: list[str]
    database_path: str


def _load_training_frame(
    conn: sqlite3.Connection,
    *,
    limit: int | None,
    strategy: str,
) -> pd.DataFrame:
    iv_expr = get_iv_expr_sql(conn)
    limit_sql = "LIMIT ?" if limit else ""
    params = [limit] if limit else []
    order_by = "a.auction_date DESC" if strategy == "recent" else "RANDOM()"
    query = f"""
        SELECT
            a.name,
            a.level,
            COALESCE(a.shiny, 0) AS shiny,
            COALESCE(a.gmax, 0) AS gmax,
            a.gender,
            a.hp_iv,
            a.attack_iv,
            a.defense_iv,
            a.sp_atk_iv,
            a.sp_def_iv,
            a.speed_iv,
            (
                COALESCE(a.hp_iv, 0)
                + COALESCE(a.attack_iv, 0)
                + COALESCE(a.defense_iv, 0)
                + COALESCE(a.sp_atk_iv, 0)
                + COALESCE(a.sp_def_iv, 0)
                + COALESCE(a.speed_iv, 0)
            ) AS total_iv,
            {iv_expr} AS iv_percent,
            a.custom_color,
            a.xp_current,
            COALESCE(a.is_missingno, 0) AS is_missingno,
            a.price
        FROM auctions a
        WHERE a.price IS NOT NULL
          AND a.price > 0
          AND a.name IS NOT NULL
          AND {iv_expr} IS NOT NULL
        ORDER BY {order_by}
        {limit_sql}
    """
    return pd.read_sql_query(query, conn, params=params)


def _build_model(model_type: str, *, estimators: int, max_depth: int | None) -> Pipeline:
    preprocessor = ColumnTransformer(
        transformers=[
            (
                "categorical",
                Pipeline(
                    steps=[
                        ("imputer", SimpleImputer(strategy="constant", fill_value="unknown")),
                        (
                            "encoder",
                            OrdinalEncoder(
                                handle_unknown="use_encoded_value",
                                unknown_value=-1,
                                encoded_missing_value=-1,
                            ),
                        ),
                    ]
                ),
                CATEGORICAL_FEATURES,
            ),
            (
                "numeric",
                Pipeline(steps=[("imputer", SimpleImputer(strategy="median"))]),
                NUMERIC_FEATURES,
            ),
        ]
    )

    if model_type == "random_forest":
        regressor = RandomForestRegressor(
            n_estimators=estimators,
            max_depth=max_depth,
            random_state=42,
            n_jobs=-1,
            min_samples_leaf=3,
        )
    else:
        regressor = HistGradientBoostingRegressor(
            max_iter=estimators,
            max_leaf_nodes=31 if max_depth is None else max(2, 2**max_depth - 1),
            learning_rate=0.08,
            random_state=42,
        )

    return Pipeline(steps=[("preprocessor", preprocessor), ("regressor", regressor)])


def train_price_model(
    *,
    database_path: Path,
    limit: int | None,
    strategy: str,
    test_size: float,
    model_type: str,
    estimators: int,
    max_depth: int | None,
) -> TrainingMetadata:
    database = Database(database_path)
    with database.connect() as conn:
        frame = _load_training_frame(conn, limit=limit, strategy=strategy)

    if len(frame) < 100:
        raise RuntimeError(f"Need at least 100 valid rows to train; found {len(frame):,}.")

    frame["name"] = frame["name"].astype(str).str.lower()
    frame["gender"] = frame["gender"].fillna("unknown").astype(str)
    frame["custom_color"] = frame["custom_color"].fillna("none").astype(str)

    x = frame[FEATURES]
    y_log = np.log1p(frame["price"].astype(float))

    x_train, x_test, y_train_log, y_test_log = train_test_split(
        x,
        y_log,
        test_size=test_size,
        random_state=42,
    )

    model = _build_model(model_type, estimators=estimators, max_depth=max_depth)
    model.fit(x_train, y_train_log)

    predictions = np.expm1(model.predict(x_test))
    actual = np.expm1(y_test_log)

    metadata = TrainingMetadata(
        training_date=datetime.now(timezone.utc).isoformat(),
        model_type=model_type,
        training_strategy=strategy,
        row_count=len(frame),
        train_rows=len(x_train),
        test_rows=len(x_test),
        mae=float(mean_absolute_error(actual, predictions)),
        rmse=float(math.sqrt(mean_squared_error(actual, predictions))),
        r2=float(r2_score(actual, predictions)),
        target="log1p(price)",
        features=FEATURES,
        database_path=str(database_path),
    )

    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump({"model": model, "metadata": asdict(metadata)}, MODEL_PATH)
    METADATA_PATH.write_text(json.dumps(asdict(metadata), indent=2), encoding="utf-8")
    return metadata


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train the Poketwo auction price model.")
    parser.add_argument("--limit", type=int, default=200_000, help="Training row limit. Use 0 for all rows.")
    parser.add_argument(
        "--strategy",
        choices=["recent", "random"],
        default="recent",
        help="Choose most recent valid rows or a random historical sample.",
    )
    parser.add_argument("--test-size", type=float, default=0.2)
    parser.add_argument(
        "--model",
        choices=["hist_gradient_boosting", "random_forest"],
        default="hist_gradient_boosting",
    )
    parser.add_argument("--estimators", type=int, default=250)
    parser.add_argument("--max-depth", type=int, default=None)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    settings = get_settings()
    metadata = train_price_model(
        database_path=settings.database_path,
        limit=None if args.limit == 0 else args.limit,
        strategy=args.strategy,
        test_size=args.test_size,
        model_type=args.model,
        estimators=args.estimators,
        max_depth=args.max_depth,
    )
    print(json.dumps(asdict(metadata), indent=2))


if __name__ == "__main__":
    main()
