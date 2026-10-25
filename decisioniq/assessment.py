"""Combine available signals without representing missing models as low risk."""

from typing import Annotated, Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field

from decisioniq.errors import ModelUnavailable
from services.anomaly.api import LoginData
from services.anomaly.predict import predict_login
from services.finance.app.api.routes import get_finance_service
from services.finance.app.schemas.finance_schema import RiskPredictRequest, RiskPredictResponse
from services.finance.app.services.finance_service import FinanceService
from services.finance.app.services.risk_aggregation import calculate_composite_score
from services.phishing.api import EmailData
from services.phishing.predict import detect_phishing

router = APIRouter(tags=["Assessment"])


class AssessmentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    finance: RiskPredictRequest
    login: LoginData | None = None
    email: EmailData | None = None


class SecuritySignal(BaseModel):
    status: Literal["available", "unavailable", "not_requested"]
    result: dict | None = None
    message: str | None = None


class AssessmentResponse(BaseModel):
    finance: RiskPredictResponse
    security: dict[str, SecuritySignal]
    security_score: float | None = Field(ge=0, le=1)
    composite_score: float = Field(ge=0, le=1)
    security_coverage: Literal["none", "partial", "complete"]
    score_policy: str = "max_available_security_signal; finance=0.7, security=0.3"


@router.post("/assess", response_model=AssessmentResponse)
def assess(
    request: AssessmentRequest,
    finance_service: Annotated[FinanceService, Depends(get_finance_service)],
):
    finance = finance_service.predict_risk(request.finance)
    signals = {}
    scores = []
    requested = 0
    for name, payload, predictor, score_key in [
        ("anomaly", request.login, predict_login, "anomaly_score"),
        ("phishing", request.email, detect_phishing, "phishing_probability"),
    ]:
        if payload is None:
            signals[name] = SecuritySignal(status="not_requested")
            continue
        requested += 1
        try:
            value = payload.model_dump() if name == "anomaly" else payload.text
            result = predictor(value)
            scores.append(result[score_key])
            signals[name] = SecuritySignal(status="available", result=result)
        except ModelUnavailable as exc:
            signals[name] = SecuritySignal(status="unavailable", message=str(exc))
    # The anomaly score is a transformed model decision, not a calibrated probability.
    security_score = max(scores) if scores else None
    aggregate = calculate_composite_score(finance.risk_probability, security_score)
    coverage = "none" if not scores else "complete" if len(scores) == requested else "partial"
    return AssessmentResponse(
        finance=finance.model_dump(),
        security=signals,
        security_score=security_score,
        composite_score=aggregate["composite_score"],
        security_coverage=coverage,
    )
