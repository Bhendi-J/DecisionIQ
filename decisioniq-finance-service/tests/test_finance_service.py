import os
import sys
import pytest
from fastapi.testclient import TestClient

# Add root service directory to sys.path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BASE_DIR)

from app.main import app
from app.services.feature_engineering import engineer_single_input, build_features_df
from app.services.risk_aggregation import calculate_composite_score
from app.services.what_if import run_simulation
from app.schemas.finance_schema import RiskPredictRequest, WhatIfRequest

client = TestClient(app)

def test_health_endpoint():
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["service"] == "decisioniq-finance-service"

def test_feature_engineering():
    req = RiskPredictRequest(
        revenue_usd=50000.0,
        opex_usd=30000.0,
        accounts_receivable_days=45.0,
        inventory_days=25.0
    )
    df_feat = engineer_single_input(req.model_dump())
    assert "profit" in df_feat.columns
    assert "expense_ratio" in df_feat.columns
    assert "cash_cycle_risk" in df_feat.columns
    assert df_feat["profit"].iloc[0] == 20000.0
    assert df_feat["cash_cycle_risk"].iloc[0] == 70.0

def test_risk_aggregation():
    # Test standard weighted combination
    res = calculate_composite_score(finance_score=0.80, security_score=0.20, w_finance=0.7, w_security=0.3)
    assert res["composite_score"] == pytest.approx(0.62, 0.01)
    
    # Test graceful fallback when security score is None
    res_fallback = calculate_composite_score(finance_score=0.75, security_score=None)
    assert res_fallback["composite_score"] == 0.75

def test_what_if_simulation():
    req = WhatIfRequest(
        expenses_change_pct=15.0,
        revenue_change_pct=-10.0,
        base_input=RiskPredictRequest(revenue_usd=50000.0, opex_usd=30000.0)
    )
    
    # Mock predictor and SHAP explainer functions
    mock_predictor = lambda df: (0.65 if df["expense_ratio"].iloc[0] > 0.7 else 0.35, 1)
    mock_shap = lambda df: []
    
    res = run_simulation(req, mock_predictor, mock_shap, security_score=0.40)
    assert "simulated_risk_score" in res
    assert "original_risk_score" in res
    assert "risk_score_delta" in res
    assert res["simulated_risk_score"] >= res["original_risk_score"]
