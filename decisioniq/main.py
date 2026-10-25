import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from decisioniq.assessment import router as assessment_router
from decisioniq.errors import ModelUnavailable
from services.anomaly.api import router as anomaly_router
from services.anomaly.predict import _load_model
from services.finance.app.api.routes import get_finance_service, router as finance_router
from services.phishing.api import router as phishing_router
from services.phishing.predict import _load_bundle

logger = logging.getLogger(__name__)


def model_status():
    result = {}
    for name, loader in [
        ("finance", get_finance_service),
        ("anomaly", _load_model),
        ("phishing", _load_bundle),
    ]:
        try:
            loader()
            result[name] = {"status": "ready"}
        except ModelUnavailable as exc:
            result[name] = {"status": "unavailable", "message": str(exc)}
    return result


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Load once per worker; each optional service can be unavailable independently.
    model_status()
    yield


app = FastAPI(
    title="DecisionIQ",
    description="Finance, login anomaly detection, and email phishing analysis through one API.",
    version="1.0.0",
    lifespan=lifespan,
)
origins = [value.strip() for value in os.getenv("CORS_ORIGINS", "").split(",") if value.strip()]
if origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
    )


@app.exception_handler(ModelUnavailable)
async def unavailable_handler(request: Request, exc: ModelUnavailable):
    return JSONResponse(status_code=503, content={"detail": str(exc), "code": "model_unavailable"})


@app.get("/health", tags=["Health"])
def health():
    models = model_status()
    return {
        "status": "healthy" if all(v["status"] == "ready" for v in models.values()) else "degraded",
        "models": models,
    }


@app.get("/ready", tags=["Health"])
def ready():
    models = model_status()
    available = all(v["status"] == "ready" for v in models.values())
    return JSONResponse(status_code=200 if available else 503, content={"models": models})


app.include_router(finance_router)
app.include_router(anomaly_router)
app.include_router(phishing_router)
app.include_router(assessment_router)
