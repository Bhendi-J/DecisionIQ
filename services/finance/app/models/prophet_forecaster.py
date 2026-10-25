"""Revenue forecasting using portable Prophet JSON and daily ds/y observations."""

from pathlib import Path

import numpy as np
import pandas as pd


class ProphetForecaster:
    def __init__(self, model_path: str | None = None):
        self.model = None
        if model_path:
            self.load(model_path)

    def preprocess_retail_data(self, frame: pd.DataFrame) -> pd.DataFrame:
        frame = frame.copy()
        frame.columns = frame.columns.str.strip()
        frame = frame[~frame.InvoiceNo.astype(str).str.startswith("C", na=False)]
        for column in ["Quantity", "UnitPrice"]:
            frame[column] = pd.to_numeric(frame[column], errors="coerce")
        frame = frame[(frame.Quantity > 0) & (frame.UnitPrice > 0)]
        frame["ds"] = pd.to_datetime(frame.InvoiceDate).dt.normalize()
        frame["y"] = frame.Quantity * frame.UnitPrice
        daily = frame.groupby("ds")["y"].sum()
        dates = pd.date_range(daily.index.min(), daily.index.max(), freq="D")
        return daily.reindex(dates, fill_value=0).rename_axis("ds").reset_index()

    def fit_and_evaluate(self, history: pd.DataFrame, test_days: int = 90) -> dict:
        from prophet import Prophet

        history = history.sort_values("ds").reset_index(drop=True)
        if len(history) <= test_days:
            raise ValueError("Training history must exceed the held-out forecast window")

        def new_model():
            return Prophet(
                yearly_seasonality=True, weekly_seasonality=True, daily_seasonality=False
            )

        training, test = history.iloc[:-test_days], history.iloc[-test_days:]
        evaluation_model = new_model().fit(training)
        predicted = evaluation_model.predict(test[["ds"]])["yhat"].to_numpy()
        actual = test["y"].to_numpy()
        nonzero = actual > 0
        metrics = {
            "mae": round(float(np.mean(np.abs(actual - predicted))), 2),
            "rmse": round(float(np.sqrt(np.mean((actual - predicted) ** 2))), 2),
            "mape_pct": round(
                float(
                    np.mean(np.abs((actual[nonzero] - predicted[nonzero]) / actual[nonzero])) * 100
                ),
                2,
            )
            if nonzero.any()
            else None,
            "train_size": len(training),
            "test_size": len(test),
            "model_type": "Prophet",
        }
        self.model = new_model().fit(history)
        return metrics

    def predict_future(self, history: pd.DataFrame, horizon_days: int = 90) -> dict:
        if self.model is None:
            raise RuntimeError("A trained forecasting model is required for inference")
        dates = pd.date_range(
            history.ds.max() + pd.Timedelta(days=1), periods=horizon_days, freq="D"
        )
        predicted = self.model.predict(pd.DataFrame({"ds": dates}))
        return {
            "historical": [
                {"ds": row.ds.strftime("%Y-%m-%d"), "yhat": round(float(row.y), 2)}
                for row in history.itertuples()
            ],
            "future": [
                {
                    "ds": row.ds.strftime("%Y-%m-%d"),
                    "yhat": round(float(row.yhat), 2),
                    "yhat_lower": round(float(row.yhat_lower), 2),
                    "yhat_upper": round(float(row.yhat_upper), 2),
                }
                for row in predicted.itertuples()
            ],
        }

    def save(self, file_path: str):
        from prophet.serialize import model_to_json

        path = Path(file_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(model_to_json(self.model))

    def load(self, file_path: str):
        from prophet.serialize import model_from_json

        self.model = model_from_json(Path(file_path).read_text())
