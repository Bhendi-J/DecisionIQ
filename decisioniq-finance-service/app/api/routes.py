import os
from fastapi import APIRouter, HTTPException, Query, Depends
from typing import Optional

from app.schemas.finance_schema import (
    RiskPredictRequest, RiskPredictResponse,
    FinanceSummaryResponse, WhatIfRequest, WhatIfResponse
)
from app.services.finance_service import FinanceService

router = APIRouter()

def get_finance_service():
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    return FinanceService(base_dir)

@router.get("/health", tags=["Health"])
def health_check():
    return {
        "status": "healthy",
        "service": "decisioniq-finance-service",
        "version": "2.0.0"
    }

@router.get("/finance/summary", response_model=FinanceSummaryResponse, tags=["Finance"])
def get_finance_summary(
    security_score: Optional[float] = Query(0.40, description="Security risk score obtained from Security Service"),
    service: FinanceService = Depends(get_finance_service)
):
    """
    Returns aggregated financial health: 90-day Prophet revenue forecast,
    XGBoost cash-flow stress prediction, SHAP risk drivers, and weighted composite score.
    """
    try:
        return service.get_summary(security_score=security_score)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/finance/predict", response_model=RiskPredictResponse, tags=["Finance"])
def predict_cashflow_risk(
    request: RiskPredictRequest,
    service: FinanceService = Depends(get_finance_service)
):
    """
    Evaluates SME cash-flow stress probability and outputs top SHAP feature contributors.
    """
    try:
        return service.predict_risk(request)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/finance/simulate", response_model=WhatIfResponse, tags=["Finance"])
def simulate_what_if_scenario(
    request: WhatIfRequest,
    security_score: Optional[float] = Query(0.40, description="Cached or mock security risk score"),
    service: FinanceService = Depends(get_finance_service)
):
    """
    Runs a pure in-memory What-If financial simulation scenario (e.g. OPEX +15%, AR Days +10).
    Does NOT modify persistent storage.
    """
    try:
        return service.simulate_what_if(request, security_score=security_score)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/finance/unified", tags=["Finance - Unified Intelligence"])
def get_unified_intelligence(
    security_score: Optional[float] = Query(0.40, description="Security risk score"),
    service: FinanceService = Depends(get_finance_service)
):
    """
    Returns the unified DecisionIQ multi-model financial intelligence output including:
    - Revenue forecast
    - Cash-stress probability
    - Financial distress signal (from benchmark models)
    - SHAP feature explanations
    - Early warning assessment
    - Overall financial signal

    NOTE: Probabilities from different datasets are NOT directly calibrated against each other.
    """
    try:
        summary = service.get_summary(security_score=security_score)

        from app.services.early_warning import generate_early_warning

        forecast_future = [item.model_dump() if hasattr(item, 'model_dump') else item
                           for item in summary.forecast.future]

        early_warning = generate_early_warning(
            forecast_future=forecast_future,
            cash_stress_probability=summary.risk_score,
            distress_probability=None,  # Distress benchmarks are separate experiments
        )

        return {
            "revenue_forecast": {
                "historical_count": len(summary.forecast.historical),
                "future_count": len(summary.forecast.future),
                "future_sample": [item.model_dump() if hasattr(item, 'model_dump') else item
                                  for item in summary.forecast.future[:5]],
            },
            "cash_stress_probability": summary.risk_score,
            "cash_stress_class": summary.risk_class,
            "financial_distress_signal": None,
            "security_score": summary.security_score,
            "composite_score": summary.composite_score,
            "shap_features": [feat.model_dump() for feat in summary.shap_features],
            "early_warning": early_warning,
            "overall_financial_signal": early_warning["overall_financial_signal"],
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
