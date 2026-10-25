import math
from datetime import date, timedelta

import pytest
from xgboost import DMatrix

from decisioniq.errors import ModelUnavailable
from services.finance.app.api.routes import get_finance_service
from services.finance.app.schemas.finance_schema import RiskPredictRequest
from services.finance.app.services.feature_engineering import engineer_single_input


def test_actual_finance_prediction_and_native_shap(client):
    response = client.post("/finance/predict", json={"revenue_usd": 80000, "opex_usd": 30000})
    assert response.status_code == 200
    result = response.json()
    assert 0 <= result["risk_probability"] <= 1
    assert len(result["shap_features"]) == 5
    service = get_finance_service()
    features = engineer_single_input(
        RiskPredictRequest(revenue_usd=80000, opex_usd=30000).model_dump()
    )
    booster = service.risk_model.model.get_booster()
    matrix = DMatrix(features)
    contributions = booster.predict(matrix, pred_contribs=True)[0]
    margin = booster.predict(matrix, output_margin=True)[0]
    assert float(contributions.sum()) == pytest.approx(float(margin), abs=1e-5)
    assert result["risk_probability"] == pytest.approx(1 / (1 + math.exp(-float(margin))), abs=1e-6)


def test_forecast_contains_requested_future_dates(client):
    response = client.get("/finance/forecast?horizon_days=7")
    assert response.status_code == 200
    result = response.json()
    assert len(result["historical"]) == 374
    assert len(result["future"]) == 7
    last = date.fromisoformat(result["historical"][-1]["ds"])
    assert result["future"][0]["ds"] == (last + timedelta(days=1)).isoformat()
    assert all(math.isfinite(row["yhat"]) for row in result["future"])


def test_company_summary_scores_supplied_financials(client):
    payload = {"revenue_usd": 100000, "opex_usd": 10000}
    direct = client.post("/finance/predict", json=payload).json()
    response = client.post("/finance/summary", json=payload)
    assert response.status_code == 200
    result = response.json()
    assert result["risk_score"] == direct["risk_probability"]
    assert result["security_score"] is None
    assert result["composite_score"] == result["risk_score"]
    assert len(result["forecast"]["future"]) == 90


def test_what_if_recomputes_supplied_profile_without_mutation(client):
    base = {"revenue_usd": 65000, "opex_usd": 40000}
    before = client.post("/finance/predict", json=base).json()
    response = client.post(
        "/finance/simulate?security_score=0.8",
        json={
            "base_input": base,
            "expenses_change_pct": 15,
            "revenue_change_pct": -10,
        },
    )
    assert response.status_code == 200
    result = response.json()
    changed = client.post("/finance/predict", json={"revenue_usd": 58500, "opex_usd": 46000}).json()
    assert result["simulated_risk_score"] == pytest.approx(changed["risk_probability"], abs=1e-4)
    assert result["simulated_composite_score"] == pytest.approx(
        0.7 * changed["risk_probability"] + 0.3 * 0.8,
        abs=1e-4,
    )
    assert client.post("/finance/predict", json=base).json() == before


def test_real_anomaly_model_uses_consistent_score_scale(client, login):
    response = client.post("/anomaly/score", json=login)
    assert response.status_code == 200
    suspicious = response.json()
    normal = client.post(
        "/anomaly/score",
        json={
            "login_hour": 10,
            "failed_attempts": 0,
            "new_device": 0,
            "login_frequency": 5,
            "location_difference": 0,
        },
    ).json()
    assert suspicious["anomaly_score"] > normal["anomaly_score"]
    assert suspicious["risk_score"] == round(100 * suspicious["anomaly_score"])


def test_combined_assessment_preserves_available_signal_when_phishing_is_missing(client, login):
    response = client.post(
        "/assess",
        json={
            "finance": {"revenue_usd": 90000},
            "login": login,
            "email": {"text": "Please review"},
        },
    )
    assert response.status_code == 200
    result = response.json()
    assert result["security"]["phishing"]["status"] == "unavailable"
    assert result["security"]["anomaly"]["status"] == "available"
    assert result["security_coverage"] == "partial"
    assert result["security_score"] == result["security"]["anomaly"]["result"]["anomaly_score"]
    assert result["composite_score"] == pytest.approx(
        0.7 * result["finance"]["risk_probability"] + 0.3 * result["security_score"],
        abs=1e-6,
    )


def test_no_security_data_uses_finance_baseline(client):
    response = client.post("/assess", json={"finance": {}})
    assert response.status_code == 200
    result = response.json()
    assert result["security_score"] is None
    assert result["security_coverage"] == "none"
    assert result["composite_score"] == result["finance"]["risk_probability"]


def test_all_signals_combine_phishing_probability_instead_of_confidence(client, login, monkeypatch):
    # A legitimate email can have HIGH confidence but LOW phishing risk.
    monkeypatch.setattr(
        "decisioniq.assessment.detect_phishing",
        lambda text: {
            "is_phishing": False,
            "confidence": 0.99,
            "phishing_probability": 0.01,
            "risk_score": 1,
            "truncated": False,
        },
    )
    response = client.post(
        "/assess", json={"finance": {}, "login": login, "email": {"text": "Hello"}}
    )
    assert response.status_code == 200
    result = response.json()
    assert result["security_coverage"] == "complete"
    assert result["security_score"] == max(
        result["security"]["anomaly"]["result"]["anomaly_score"], 0.01
    )


def test_missing_phishing_model_has_explicit_readiness_and_503(client):
    health = client.get("/health")
    assert health.status_code == 200
    assert health.json()["status"] == "degraded"
    assert health.json()["models"]["finance"]["status"] == "ready"
    assert client.get("/ready").status_code == 503
    response = client.post("/phishing/predict", json={"text": "Hello"})
    assert response.status_code == 503
    assert response.json()["code"] == "model_unavailable"


def test_unavailable_finance_dependency_returns_503(client):
    from decisioniq.main import app

    def missing():
        raise ModelUnavailable("Finance model is missing")

    app.dependency_overrides[get_finance_service] = missing
    try:
        assert client.post("/assess", json={"finance": {}}).status_code == 503
    finally:
        app.dependency_overrides.clear()


@pytest.mark.parametrize(
    "url,payload",
    [
        ("/finance/predict", {"monthly_revenue": 50000}),
        ("/finance/predict", {"revenue_usd": -1}),
        ("/finance/predict", {"sector": "unsupported"}),
        ("/finance/simulate", {"expenses_change_pct": -101}),
        (
            "/anomaly/score",
            {
                "login_hour": 24,
                "failed_attempts": 0,
                "new_device": 0,
                "login_frequency": 5,
                "location_difference": 0,
            },
        ),
        (
            "/anomaly/score",
            {
                "login_hour": 10,
                "failed_attempts": 0,
                "new_device": 3,
                "login_frequency": 5,
                "location_difference": 0,
            },
        ),
        ("/phishing/predict", {"text": "   "}),
        ("/assess", {"email": {"text": "Hello"}}),
    ],
)
def test_invalid_input_is_rejected(client, url, payload):
    assert client.post(url, json=payload).status_code == 422


def test_security_query_cannot_accept_percent_scores(client):
    assert client.get("/finance/summary?security_score=80").status_code == 422


def test_openapi_has_unique_operations_for_all_services(client):
    schema = client.get("/openapi.json").json()
    for path in ["/assess", "/finance/predict", "/anomaly/score", "/phishing/predict"]:
        assert "post" in schema["paths"][path]
    ids = [
        operation["operationId"] for item in schema["paths"].values() for operation in item.values()
    ]
    assert len(ids) == len(set(ids))
