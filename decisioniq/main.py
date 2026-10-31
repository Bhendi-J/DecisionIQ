import logging
import os
import asyncio
from contextlib import suppress
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from decisioniq.assessment import router as assessment_router
from decisioniq.errors import ModelUnavailable
from services.anomaly.api import router as anomaly_router
from services.anomaly.predict import _load_model
from services.finance.app.api.routes import get_finance_service, router as finance_router
from services.phishing.api import router as phishing_router
from services.phishing.predict import _load_bundle
from decisioniq.config import ROOT
from decisioniq.dashboard.api import router as dashboard_router
from decisioniq.dashboard.auth import router as accounts_router, require_admin, current_user
from decisioniq.dashboard import store as dashboard_store
from decisioniq.dashboard.analytics import get_forecast, refresh_forecast
from decisioniq.dashboard.reminders import run_scheduler, evaluate_reminders

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
    await asyncio.to_thread(dashboard_store.initialize)
    for row in dashboard_store.rows("SELECT id FROM companies"):
        if get_forecast(row["id"])["status"] == "pending":
            await asyncio.to_thread(refresh_forecast, row["id"])
    await asyncio.to_thread(evaluate_reminders)
    scheduler = asyncio.create_task(run_scheduler())
    try:
        yield
    finally:
        scheduler.cancel()
        with suppress(asyncio.CancelledError):
            await scheduler


app = FastAPI(
    title="ForeSight",
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


@app.middleware("http")
async def private_responses(request: Request, call_next):
    response = await call_next(request)
    if request.url.path.startswith(("/api/", "/finance/", "/anomaly/", "/phishing/", "/assess")):
        response.headers["Cache-Control"] = "no-store"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    return response


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


app.include_router(finance_router, dependencies=[Depends(current_user)])
app.include_router(anomaly_router, dependencies=[Depends(require_admin)])
app.include_router(phishing_router, dependencies=[Depends(require_admin)])
app.include_router(assessment_router, dependencies=[Depends(require_admin)])
app.include_router(dashboard_router)
app.include_router(accounts_router)

frontend = ROOT / "frontend/dist"
if (frontend / "assets").is_dir():
    app.mount("/assets", StaticFiles(directory=frontend / "assets"), name="dashboard-assets")


@app.get("/", include_in_schema=False)
def dashboard_index():
    if (frontend / "index.html").is_file():
        return FileResponse(frontend / "index.html")
    return JSONResponse(
        status_code=503,
        content={"detail": "Build the dashboard with: cd frontend && npm ci && npm run build"},
    )


@app.get("/favicon.svg", include_in_schema=False)
def favicon():
    built = frontend / "favicon.svg"
    return FileResponse(
        built if built.is_file() else ROOT / "frontend/public/favicon.svg",
        media_type="image/svg+xml",
    )
