"""
Finance Service Facade for DecisionIQ.
Encapsulates model loading, inference orchestration, risk aggregation, and what-if simulation.
"""

import os
import logging
import pandas as pd
from typing import Dict, Any, Optional

from app.schemas.finance_schema import (
    RiskPredictRequest, RiskPredictResponse, FinanceSummaryResponse,
    WhatIfRequest, WhatIfResponse, ForecastResponse
)
from app.models.prophet_forecaster import ProphetForecaster
from app.models.xgboost_risk import XGBoostRiskModel
from app.models.shap_explainer import SHAPExplainer
from app.services.feature_engineering import engineer_single_input
from app.services.risk_aggregation import calculate_composite_score
from app.services.what_if import run_simulation

logger = logging.getLogger(__name__)

class FinanceService:
    def __init__(self, base_dir: str):
        self.base_dir = base_dir
        
        prophet_path = os.path.join(base_dir, 'models', 'prophet', 'prophet_model.pkl')
        xgb_path = os.path.join(base_dir, 'models', 'xgboost', 'xgboost_risk.pkl')
        
        self.forecaster = ProphetForecaster(model_path=prophet_path if os.path.exists(prophet_path) else None)
        self.risk_model = XGBoostRiskModel(model_path=xgb_path if os.path.exists(xgb_path) else None)
        self.shap_explainer = SHAPExplainer(xgb_model=self.risk_model.model)

    def get_summary(self, security_score: float = 0.40) -> FinanceSummaryResponse:
        """
        Returns full financial summary: 90-day forecast, cash-flow stress risk,
        SHAP explanations, and composite business health score.
        """
        # 1. 90-day forecast (using pre-aggregated baseline dataset if available)
        retail_path = os.path.join(self.base_dir, '..', 'Datasets', 'online+retail', 'Online Retail.xlsx')
        if os.path.exists(retail_path):
            try:
                df_raw = pd.read_excel(retail_path)
                df_daily = self.forecaster.preprocess_retail_data(df_raw)
                forecast_data = self.forecaster.predict_future(df_daily, horizon_days=90)
            except Exception as e:
                logger.error(f"Error executing Prophet forecast: {e}")
                forecast_data = {"historical": [], "future": []}
        else:
            forecast_data = {"historical": [], "future": []}
            
        # 2. Risk Prediction on standard baseline SME profile
        default_req = RiskPredictRequest()
        X_feat = engineer_single_input(default_req.model_dump())
        risk_prob, risk_class = self.risk_model.predict(X_feat)
        shap_feats = self.shap_explainer.explain_instance(X_feat, top_n=5)
        
        # 3. Composite Risk Aggregation
        agg = calculate_composite_score(risk_prob, security_score)
        
        return FinanceSummaryResponse(
            forecast=ForecastResponse(
                historical=forecast_data["historical"],
                future=forecast_data["future"]
            ),
            risk_score=round(risk_prob, 4),
            risk_class=risk_class,
            security_score=agg["security_score"],
            composite_score=agg["composite_score"],
            shap_features=shap_feats
        )

    def predict_risk(self, request: RiskPredictRequest) -> RiskPredictResponse:
        """
        Predicts risk probability and generates SHAP explanation for given SME inputs.
        """
        X_feat = engineer_single_input(request.model_dump())
        risk_prob, risk_class = self.risk_model.predict(X_feat)
        shap_feats = self.shap_explainer.explain_instance(X_feat, top_n=5)
        
        return RiskPredictResponse(
            risk_probability=round(risk_prob, 4),
            risk_class=risk_class,
            shap_features=shap_feats
        )

    def simulate_what_if(self, request: WhatIfRequest, security_score: float = 0.40) -> WhatIfResponse:
        """
        Runs temporary financial recomputation without modifying database.
        """
        sim_res = run_simulation(
            request=request,
            model_predictor=lambda feats: self.risk_model.predict(feats),
            shap_explainer=lambda feats: self.shap_explainer.explain_instance(feats, top_n=5),
            security_score=security_score
        )
        return WhatIfResponse(**sim_res)
