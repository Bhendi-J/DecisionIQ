from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict, Field, field_validator

from services.phishing.predict import _load_bundle, detect_phishing

router = APIRouter(prefix="/phishing", tags=["Email phishing"])


class EmailData(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str = Field(min_length=1, max_length=100_000)

    @field_validator("text")
    @classmethod
    def reject_blank(cls, value):
        if not value.strip():
            raise ValueError("Email text cannot be blank")
        return value


class PhishingResult(BaseModel):
    is_phishing: bool
    confidence: float = Field(ge=0, le=1)
    phishing_probability: float = Field(ge=0, le=1)
    risk_score: int = Field(ge=0, le=100)
    truncated: bool


@router.get("/health")
def health():
    _load_bundle()
    return {"status": "healthy", "model_loaded": True}


@router.post("/predict", response_model=PhishingResult)
def predict_email(email: EmailData):
    return detect_phishing(email.text)
