"""Train the cash-flow classifier on an externally supplied SME dataset."""

import argparse
import json
from pathlib import Path

import pandas as pd

from decisioniq.config import configured_path
from services.finance.app.models.xgboost_risk import XGBoostRiskModel


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, required=True)
    args = parser.parse_args()
    model = XGBoostRiskModel()
    metrics, _ = model.train_and_evaluate(pd.read_csv(args.data))
    path = (
        configured_path("FINANCE_MODEL_DIR", "services/finance/models")
        / "xgboost/xgboost_risk.json"
    )
    model.save(str(path))
    print(json.dumps(metrics, indent=2))
    print(f"Saved {path}")


if __name__ == "__main__":
    main()
