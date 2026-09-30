from pathlib import Path

import joblib
import numpy as np
import pandas as pd

MODEL_PATH = Path(__file__).parent / "outputs" / "isolation_forest.joblib"

FEATURES = [
    "login_hour",
    "failed_attempts",
    "new_device",
    "login_frequency",
    "location_difference",
]

K = 15


def to_anomaly_score(decision):
    """Convert Isolation Forest decision_function output into a 0-1 score.
    Above 0.5 = suspicious, below 0.5 = normal."""
    return 1 / (1 + np.exp(K * np.asarray(decision)))


_model = None


def _load_model():
    global _model
    if _model is None:
        _model = joblib.load(MODEL_PATH)
    return _model


def predict_login(login: dict) -> dict:
    model = _load_model()
    X = pd.DataFrame([login])[FEATURES]

    is_anomaly = bool(model.predict(X)[0] == -1)
    score = float(to_anomaly_score(model.decision_function(X))[0])

    return {
        "is_anomaly": is_anomaly,
        "anomaly_score": round(score, 2),
        "risk_score": round(score * 100),
    }


if __name__ == "__main__":
    suspicious = {"login_hour": 3, "failed_attempts": 8, "new_device": 1,
                  "login_frequency": 1, "location_difference": 1}
    normal = {"login_hour": 10, "failed_attempts": 0, "new_device": 0,
              "login_frequency": 5, "location_difference": 0}

    print("Suspicious login:", predict_login(suspicious))
    print("Normal login:    ", predict_login(normal))