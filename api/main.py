from fastapi import FastAPI
import joblib
from pathlib import Path
from pydantic import BaseModel


app = FastAPI(title="DecisionIQ Security Anomaly API")

# Path to trained Isolation Forest model
MODEL_PATH = Path(__file__).parent.parent / "outputs" / "isolation_forest.joblib"

# Load trained model
model = joblib.load(MODEL_PATH)


@app.get("/health")
def health():
    return {
        "status": "healthy",
        "model_loaded": True
    }


class LoginData(BaseModel):
    login_hour: float
    failed_attempts: float
    new_device: int
    login_frequency: float
    location_difference: int


@app.post("/anomaly/score")
def score_login(login: LoginData):

    features = [[
        login.login_hour,
        login.failed_attempts,
        login.new_device,
        login.login_frequency,
        login.location_difference
    ]]

    prediction = model.predict(features)[0]
    decision_score = model.decision_function(features)[0]

    is_anomaly = prediction == -1

    return {
        "is_anomaly": bool(is_anomaly),
        "decision_score": float(decision_score)
    }