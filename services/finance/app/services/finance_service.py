"""Cached finance models and a compact, pre-aggregated demonstration time series."""

import logging
from functools import lru_cache
from pathlib import Path

import pandas as pd

from decisioniq.config import configured_path
from decisioniq.errors import ModelUnavailable
from services.finance.app.models.prophet_forecaster import ProphetForecaster
from services.finance.app.models.shap_explainer import SHAPExplainer
from services.finance.app.models.xgboost_risk import XGBoostRiskModel
from services.finance.app.schemas.finance_schema import (
    FinanceSummaryResponse,
    ForecastResponse,
    RiskPredictRequest,
    RiskPredictResponse,
    WhatIfRequest,
    WhatIfResponse,
)
from services.finance.app.services.feature_engineering import engineer_single_input
from services.finance.app.services.risk_aggregation import calculate_composite_score
from services.finance.app.services.what_if import run_simulation

logger = logging.getLogger(__name__)


class FinanceService:
    def __init__(self):
        base = configured_path("FINANCE_MODEL_DIR", "services/finance/models")
        prophet_path = base / "prophet/prophet_model.json"
        xgb_path = base / "xgboost/xgboost_risk.json"
        if not prophet_path.is_file() or not xgb_path.is_file():
            raise ModelUnavailable(
                "Finance model artifacts are missing; configure FINANCE_MODEL_DIR."
            )
        try:
            self.forecaster = ProphetForecaster(model_path=str(prophet_path))
            self.risk_model = XGBoostRiskModel(model_path=str(xgb_path))
            self.shap_explainer = SHAPExplainer(xgb_model=self.risk_model.model)
            history_path = Path(__file__).resolve().parents[2] / "data/revenue_history.csv"
            self.history = pd.read_csv(history_path, parse_dates=["ds"])
        except Exception as exc:
            logger.exception("Cannot initialize finance models")
            raise ModelUnavailable(
                "Finance models or revenue history could not be loaded."
            ) from exc

    @lru_cache(maxsize=8)
    def get_forecast(self, horizon_days: int = 90) -> ForecastResponse:
        if self.forecaster.model is None:
            raise ModelUnavailable("Revenue forecasting model is unavailable.")
        result = self.forecaster.predict_future(self.history, horizon_days=horizon_days)
        return ForecastResponse(**result)

    def get_summary(
        self, security_score: float | None = None, request: RiskPredictRequest | None = None
    ) -> FinanceSummaryResponse:
        prediction = self.predict_risk(request or RiskPredictRequest())
        aggregate = calculate_composite_score(prediction.risk_probability, security_score)
        return FinanceSummaryResponse(
            forecast=self.get_forecast(),
            risk_score=prediction.risk_probability,
            risk_class=prediction.risk_class,
            security_score=aggregate["security_score"],
            composite_score=aggregate["composite_score"],
            shap_features=prediction.shap_features,
        )

    def predict_risk(self, request: RiskPredictRequest) -> RiskPredictResponse:
        if self.risk_model.model is None:
            raise ModelUnavailable("Cash-flow risk model is unavailable.")
        features = engineer_single_input(request.model_dump())
        probability, risk_class = self.risk_model.predict(features)
        return RiskPredictResponse(
            risk_probability=round(probability, 6),
            risk_class=risk_class,
            shap_features=self.shap_explainer.explain_instance(features, top_n=5),
        )

    def simulate_what_if(
        self, request: WhatIfRequest, security_score: float | None = None
    ) -> WhatIfResponse:
        result = run_simulation(
            request=request,
            model_predictor=self.risk_model.predict,
            shap_explainer=lambda features: self.shap_explainer.explain_instance(features, top_n=5),
            security_score=security_score,
        )
        return WhatIfResponse(**result)
