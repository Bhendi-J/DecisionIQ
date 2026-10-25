from functools import lru_cache
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from services.finance.app.schemas.finance_schema import (
    FinanceSummaryResponse,
    ForecastResponse,
    RiskPredictRequest,
    RiskPredictResponse,
    WhatIfRequest,
    WhatIfResponse,
)
from services.finance.app.services.early_warning import generate_early_warning
from services.finance.app.services.finance_service import FinanceService

router = APIRouter(prefix="/finance", tags=["Finance"])


@lru_cache(maxsize=1)
def get_finance_service():
    return FinanceService()


Service = Annotated[FinanceService, Depends(get_finance_service)]
SecurityScore = Annotated[float | None, Query(ge=0, le=1)]


@router.get("/health")
def health_check(service: Service):
    return {"status": "healthy", "model_loaded": True}


@router.get("/summary", response_model=FinanceSummaryResponse)
def get_finance_summary(service: Service, security_score: SecurityScore = None):
    """Demonstration summary using a default SME profile and historical retail series."""
    return service.get_summary(security_score=security_score)


@router.post("/summary", response_model=FinanceSummaryResponse)
def company_finance_summary(
    request: RiskPredictRequest, service: Service, security_score: SecurityScore = None
):
    """Score supplied company financials; forecast remains the bundled demo retail series."""
    return service.get_summary(security_score=security_score, request=request)


@router.get("/forecast", response_model=ForecastResponse)
def forecast(service: Service, horizon_days: int = Query(90, ge=7, le=180)):
    return service.get_forecast(horizon_days)


@router.post("/predict", response_model=RiskPredictResponse)
def predict_risk(request: RiskPredictRequest, service: Service):
    return service.predict_risk(request)


@router.post("/simulate", response_model=WhatIfResponse)
def simulate(request: WhatIfRequest, service: Service, security_score: SecurityScore = None):
    return service.simulate_what_if(request, security_score=security_score)


def unified_result(service, request, security_score):
    summary = service.get_summary(security_score=security_score, request=request)
    early_warning = generate_early_warning(
        forecast_future=[item.model_dump() for item in summary.forecast.future],
        cash_stress_probability=summary.risk_score,
        distress_probability=None,
    )
    return {
        "revenue_forecast": {
            "historical_count": len(summary.forecast.historical),
            "future_count": len(summary.forecast.future),
            "future_sample": [item.model_dump() for item in summary.forecast.future[:5]],
            "source": "demo_retail_history",
        },
        "cash_stress_probability": summary.risk_score,
        "cash_stress_class": summary.risk_class,
        "financial_distress_signal": None,
        "security_score": summary.security_score,
        "composite_score": summary.composite_score,
        "shap_features": [item.model_dump() for item in summary.shap_features],
        "early_warning": early_warning,
        "overall_financial_signal": early_warning["overall_financial_signal"],
    }


@router.get("/unified")
def get_unified(service: Service, security_score: SecurityScore = None):
    return unified_result(service, None, security_score)


@router.post("/unified")
def post_unified(
    request: RiskPredictRequest, service: Service, security_score: SecurityScore = None
):
    return unified_result(service, request, security_score)
