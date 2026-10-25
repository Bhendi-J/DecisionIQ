"""Train Isolation Forest on supplied login features."""

import argparse
from pathlib import Path

import joblib
import pandas as pd
from sklearn.ensemble import IsolationForest

from decisioniq.config import configured_path
from services.anomaly.predict import FEATURES


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, required=True)
    args = parser.parse_args()
    frame = pd.read_csv(args.data)
    model = IsolationForest(n_estimators=200, contamination=0.05, random_state=42)
    model.fit(frame[FEATURES])
    path = configured_path("ANOMALY_MODEL_PATH", "services/anomaly/models/isolation_forest.joblib")
    path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, path)
    print(f"Saved {path}; training diagnostics are not held-out evaluation metrics.")


if __name__ == "__main__":
    main()
