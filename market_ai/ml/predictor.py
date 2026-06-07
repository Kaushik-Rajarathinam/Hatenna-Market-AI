from __future__ import annotations

from pathlib import Path
from typing import Any

import joblib
import pandas as pd

from market_ai.ml.train import FEATURES, MODEL_PATH
from market_ai.models import PredictionInput


class PricePredictor:
    def __init__(self, model_path: Path = MODEL_PATH) -> None:
        self.model_path = model_path
        self._bundle: dict[str, Any] | None = None

    @property
    def is_available(self) -> bool:
        return self.model_path.exists()

    def load(self) -> None:
        if not self.model_path.exists():
            raise FileNotFoundError(f"Model not found at {self.model_path}. Run python -m market_ai.ml.train first.")
        self._bundle = joblib.load(self.model_path)

    @property
    def metadata(self) -> dict[str, Any]:
        if self._bundle is None:
            self.load()
        assert self._bundle is not None
        return dict(self._bundle.get("metadata", {}))

    def predict(self, request: PredictionInput) -> float:
        if self._bundle is None:
            self.load()
        assert self._bundle is not None
        model = self._bundle["model"]
        row = {
            "name": request.name.lower(),
            "level": request.level,
            "shiny": int(request.shiny),
            "gmax": int(request.gmax),
            "gender": request.gender,
            "hp_iv": request.hp_iv,
            "attack_iv": request.attack_iv,
            "defense_iv": request.defense_iv,
            "sp_atk_iv": request.sp_atk_iv,
            "sp_def_iv": request.sp_def_iv,
            "speed_iv": request.speed_iv,
            "total_iv": request.total_iv,
            "iv_percent": request.iv_percent,
            "custom_color": request.custom_color,
            "xp_current": request.xp_current,
            "is_missingno": int(request.is_missingno),
        }
        frame = pd.DataFrame([{feature: row.get(feature) for feature in FEATURES}])
        prediction_log = float(model.predict(frame)[0])
        return max(0.0, float(__import__("math").expm1(prediction_log)))
