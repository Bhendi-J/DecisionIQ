"""Isolation Forest inference, shared by the API and training tools."""

import logging
from functools import lru_cache

import joblib
import numpy as np
import pandas as pd

from decisioniq.config import configured_path
from decisioniq.errors import ModelUnavailable

logger = logging.getLogger(__name__)
FEATURES = ["login_hour", "failed_attempts", "new_device", "login_frequency", "location_difference"]
K = 15


def to_anomaly_score(decision):
    # This monotonic transform is a risk indicator, not a calibrated probability.
    return 1 / (1 + np.exp(np.clip(K * np.asarray(decision), -700, 700)))


@lru_cache(maxsize=1)
def _load_model():
    path = configured_path("ANOMALY_MODEL_PATH", "services/anomaly/models/isolation_forest.joblib")
    if not path.is_file():
        raise ModelUnavailable("Login anomaly model is missing; configure ANOMALY_MODEL_PATH.")
    try:
        return joblib.load(path)
    except Exception as exc:
        logger.exception("Cannot load anomaly model")
        raise ModelUnavailable("Login anomaly model could not be loaded.") from exc


def predict_login(login: dict) -> dict:
    model = _load_model()
    features = pd.DataFrame([login])[FEATURES]
    score = float(to_anomaly_score(model.decision_function(features))[0])
    return {
        "is_anomaly": bool(model.predict(features)[0] == -1),
        "anomaly_score": round(score, 6),
        "risk_score": round(score * 100),
    }
