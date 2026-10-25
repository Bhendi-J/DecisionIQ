"""Train on a supplied daily ds/y CSV or an original Online Retail workbook."""

import argparse
import json
from pathlib import Path

import pandas as pd

from decisioniq.config import ROOT, configured_path
from services.finance.app.models.prophet_forecaster import ProphetForecaster


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--data", type=Path, default=ROOT / "services/finance/data/revenue_history.csv"
    )
    args = parser.parse_args()
    forecaster = ProphetForecaster()
    if args.data.suffix.lower() == ".xlsx":
        history = forecaster.preprocess_retail_data(pd.read_excel(args.data))
    else:
        history = pd.read_csv(args.data, parse_dates=["ds"])
    history = history.sort_values("ds").reset_index(drop=True)
    if len(history) <= 90:
        parser.error("More than 90 daily observations are required for held-out evaluation")
    metrics = forecaster.fit_and_evaluate(history, test_days=90)
    path = (
        configured_path("FINANCE_MODEL_DIR", "services/finance/models")
        / "prophet/prophet_model.json"
    )
    forecaster.save(str(path))
    history.to_csv(ROOT / "services/finance/data/revenue_history.csv", index=False)
    print(json.dumps(metrics, indent=2))
    print(f"Saved {path}")


if __name__ == "__main__":
    main()
