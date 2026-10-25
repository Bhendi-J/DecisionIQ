from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict, Field

from services.anomaly.predict import _load_model, predict_login

router = APIRouter(prefix="/anomaly", tags=["Login anomaly"])


class LoginData(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    login_hour: float = Field(ge=0, lt=24)
    failed_attempts: int = Field(ge=0)
    new_device: int = Field(ge=0, le=1)
    login_frequency: float = Field(ge=0)
    location_difference: int = Field(ge=0, le=1)


class LoginResult(BaseModel):
    is_anomaly: bool
    anomaly_score: float = Field(ge=0, le=1)
    risk_score: int = Field(ge=0, le=100)


@router.get("/health")
def health():
    _load_model()
    return {"status": "healthy", "model_loaded": True}


@router.post("/score", response_model=LoginResult)
def score_login(login: LoginData):
    return predict_login(login.model_dump())
