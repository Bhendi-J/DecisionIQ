"""Exact TreeSHAP contributions from XGBoost's native implementation."""

import pandas as pd
from xgboost import DMatrix

from decisioniq.errors import ModelUnavailable
from services.finance.app.schemas.finance_schema import SHAPFeature


class SHAPExplainer:
    def __init__(self, xgb_model=None):
        self.xgb_model = xgb_model

    def explain_instance(self, features: pd.DataFrame, top_n: int = 5) -> list[SHAPFeature]:
        if self.xgb_model is None:
            raise ModelUnavailable("Trained cash-flow model is required for SHAP explanations.")
        contributions = self.xgb_model.get_booster().predict(DMatrix(features), pred_contribs=True)[
            0
        ]
        # Last contribution is the bias term, not an input feature.
        result = [
            SHAPFeature(
                feature=name,
                direction="increases_risk" if float(value) >= 0 else "reduces_risk",
                magnitude=round(abs(float(value)), 6),
            )
            for name, value in zip(features.columns, contributions[:-1])
        ]
        return sorted(result, key=lambda item: item.magnitude, reverse=True)[:top_n]
