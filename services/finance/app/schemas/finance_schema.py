from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from services.finance.app.services.feature_engineering import SECTORS


class ForecastItem(BaseModel):
    ds: str
    yhat: float
    yhat_lower: float | None = None
    yhat_upper: float | None = None


class ForecastResponse(BaseModel):
    historical: list[ForecastItem]
    future: list[ForecastItem]


class SHAPFeature(BaseModel):
    feature: str
    direction: Literal["increases_risk", "reduces_risk"]
    magnitude: float = Field(ge=0, description="Absolute TreeSHAP impact in log-odds")


class RiskPredictRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    sector: str = "Retail"
    employees: int = Field(10, ge=0)
    revenue_usd: float = Field(50000, ge=0)
    opex_usd: float = Field(35000, ge=0)
    accounts_receivable_days: float = Field(45, ge=0)
    inventory_days: float = Field(30, ge=0)
    loan_balance_usd: float = Field(20000, ge=0)
    owner_injections_usd: float = Field(5000, ge=0)

    @field_validator("sector")
    @classmethod
    def supported_sector(cls, value):
        sector = value.strip().title()
        if sector not in SECTORS:
            raise ValueError(f"Supported sectors: {', '.join(SECTORS)}")
        return sector


class RiskPredictResponse(BaseModel):
    risk_probability: float = Field(ge=0, le=1)
    risk_class: Literal[0, 1]
    shap_features: list[SHAPFeature]


class FinanceSummaryResponse(BaseModel):
    forecast: ForecastResponse
    risk_score: float = Field(ge=0, le=1)
    risk_class: Literal[0, 1]
    security_score: float | None = Field(ge=0, le=1)
    composite_score: float = Field(ge=0, le=1)
    shap_features: list[SHAPFeature]


class WhatIfRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    expenses_change_pct: float = Field(0, ge=-100, le=100)
    revenue_change_pct: float = Field(0, ge=-100, le=100)
    receivable_days_change: float = 0
    loan_balance_change_pct: float = Field(0, ge=-100, le=100)
    base_input: RiskPredictRequest | None = None


class WhatIfResponse(BaseModel):
    original_risk_score: float
    simulated_risk_score: float
    risk_score_delta: float
    original_composite_score: float
    simulated_composite_score: float
    original_shap: list[SHAPFeature]
    simulated_shap: list[SHAPFeature]
    summary_message: str
