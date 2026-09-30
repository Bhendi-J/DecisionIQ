from pydantic import BaseModel, Field
from typing import List, Optional

class ForecastItem(BaseModel):
    ds: str = Field(..., description="Date formatted as YYYY-MM-DD")
    yhat: float = Field(..., description="Forecasted/Historical revenue value")
    yhat_lower: Optional[float] = Field(None, description="Lower confidence interval bound")
    yhat_upper: Optional[float] = Field(None, description="Upper confidence interval bound")

class ForecastResponse(BaseModel):
    historical: List[ForecastItem]
    future: List[ForecastItem]

class SHAPFeature(BaseModel):
    feature: str = Field(..., description="Feature name")
    direction: str = Field(..., description="'increases_risk' or 'reduces_risk'")
    magnitude: float = Field(..., description="Absolute impact on model prediction log-odds")

class RiskPredictRequest(BaseModel):
    sector: str = Field("Retail", description="Business sector")
    employees: int = Field(10, description="Number of employees")
    revenue_usd: float = Field(50000.0, description="Monthly revenue in USD")
    opex_usd: float = Field(35000.0, description="Monthly operational expenditure in USD")
    accounts_receivable_days: float = Field(45.0, description="Average collection period in days")
    inventory_days: float = Field(30.0, description="Average inventory holding period in days")
    loan_balance_usd: float = Field(20000.0, description="Total outstanding loan balance in USD")
    owner_injections_usd: float = Field(5000.0, description="Owner capital injection in USD")

class RiskPredictResponse(BaseModel):
    risk_probability: float = Field(..., description="Predicted cash-flow stress probability (0.0 - 1.0)")
    risk_class: int = Field(..., description="Binary risk classification (0 = Low Risk, 1 = High Risk)")
    shap_features: List[SHAPFeature] = Field(..., description="Top contributing factors to the risk decision")

class RiskAggregationResponse(BaseModel):
    finance_score: float = Field(..., description="Finance risk probability")
    security_score: float = Field(..., description="Security risk score")
    composite_score: float = Field(..., description="Weighted composite business health/risk score")
    finance_weight: float
    security_weight: float

class FinanceSummaryResponse(BaseModel):
    forecast: ForecastResponse
    risk_score: float
    risk_class: int
    security_score: float
    composite_score: float
    shap_features: List[SHAPFeature]

class WhatIfRequest(BaseModel):
    expenses_change_pct: Optional[float] = Field(0.0, description="Percentage change in OPEX (-100 to +100)")
    revenue_change_pct: Optional[float] = Field(0.0, description="Percentage change in Revenue (-100 to +100)")
    receivable_days_change: Optional[float] = Field(0.0, description="Absolute change in AR days (e.g. +10 or -5)")
    loan_balance_change_pct: Optional[float] = Field(0.0, description="Percentage change in Loan Balance (-100 to +100)")
    base_input: Optional[RiskPredictRequest] = None

class WhatIfResponse(BaseModel):
    original_risk_score: float
    simulated_risk_score: float
    risk_score_delta: float
    original_composite_score: float
    simulated_composite_score: float
    original_shap: List[SHAPFeature]
    simulated_shap: List[SHAPFeature]
    summary_message: str
