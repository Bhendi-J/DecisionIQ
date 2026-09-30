"""
Forecasting Benchmark Module for DecisionIQ Finance Service.

Compares Prophet/Ridge-Fourier-Seasonal forecasting performance across:
- UCI Online Retail (primary)
- Rossmann Store Sales (benchmark)
- Walmart Store Sales (benchmark)

Each dataset is processed INDEPENDENTLY. No merging.
"""

import os
import pandas as pd
import numpy as np
from typing import Dict, Any, List
from sklearn.linear_model import Ridge


def extract_time_features(ds_series, min_date):
    """Fourier seasonal features for Ridge fallback model."""
    t = (ds_series - min_date).dt.days.values.reshape(-1, 1)
    dow = ds_series.dt.dayofweek.values
    doy = ds_series.dt.dayofyear.values
    return np.hstack([
        t,
        np.sin(2 * np.pi * dow / 7.0).reshape(-1, 1),
        np.cos(2 * np.pi * dow / 7.0).reshape(-1, 1),
        np.sin(2 * np.pi * doy / 365.25).reshape(-1, 1),
        np.cos(2 * np.pi * doy / 365.25).reshape(-1, 1),
    ])


def _train_evaluate_ridge(df_daily: pd.DataFrame, test_days: int = 90) -> Dict[str, Any]:
    """Train Ridge-Fourier model on (ds, y) dataframe and evaluate chronologically."""
    if len(df_daily) <= test_days:
        train_df, test_df = df_daily, df_daily
    else:
        train_df = df_daily.iloc[:-test_days].copy()
        test_df = df_daily.iloc[-test_days:].copy()

    min_date = train_df['ds'].min()
    X_tr = extract_time_features(train_df['ds'], min_date)
    y_tr = train_df['y'].values

    reg = Ridge(alpha=1.0)
    reg.fit(X_tr, y_tr)

    X_te = extract_time_features(test_df['ds'], min_date)
    y_pred = np.maximum(0, reg.predict(X_te))
    y_true = test_df['y'].values

    mae = float(np.mean(np.abs(y_true - y_pred)))
    rmse = float(np.sqrt(np.mean((y_true - y_pred) ** 2)))
    nonzero = y_true > 0
    if nonzero.sum() > 0:
        mape = float(np.mean(np.abs((y_true[nonzero] - y_pred[nonzero]) / y_true[nonzero]))) * 100
    else:
        mape = 0.0

    return {
        "mae": round(mae, 2),
        "rmse": round(rmse, 2),
        "mape_pct": round(mape, 2),
        "train_size": len(train_df),
        "test_size": len(test_df),
    }


def prepare_rossmann(base_dir: str) -> pd.DataFrame:
    """Load and aggregate Rossmann store sales into daily totals."""
    path = os.path.join(base_dir, 'Datasets', 'rossmann-store-sales', 'train.csv')
    df = pd.read_csv(path, parse_dates=['Date'], low_memory=False)
    # Use only open-store records with positive sales
    df = df[(df['Open'] == 1) & (df['Sales'] > 0)]
    daily = df.groupby('Date')['Sales'].sum().reset_index()
    daily.columns = ['ds', 'y']
    daily = daily.sort_values('ds').reset_index(drop=True)
    return daily


def prepare_walmart(base_dir: str) -> pd.DataFrame:
    """Load and aggregate Walmart store sales into weekly totals."""
    path = os.path.join(base_dir, 'Datasets', 'walmart-recruiting-store-sales-forecasting', 'train.csv.zip')
    df = pd.read_csv(path)
    df['Date'] = pd.to_datetime(df['Date'])
    # Filter positive sales
    df = df[df['Weekly_Sales'] > 0]
    weekly = df.groupby('Date')['Weekly_Sales'].sum().reset_index()
    weekly.columns = ['ds', 'y']
    weekly = weekly.sort_values('ds').reset_index(drop=True)
    return weekly


def run_forecasting_benchmarks(base_dir: str) -> Dict[str, Dict[str, Any]]:
    """
    Runs forecasting evaluation on Rossmann and Walmart datasets.
    Returns metrics dict keyed by dataset name.
    """
    results = {}

    # --- Rossmann ---
    print("  Loading Rossmann Store Sales...")
    try:
        ross_daily = prepare_rossmann(base_dir)
        print(f"    Rossmann daily aggregated shape: {ross_daily.shape}, date range: {ross_daily['ds'].min()} to {ross_daily['ds'].max()}")
        ross_metrics = _train_evaluate_ridge(ross_daily, test_days=90)
        ross_metrics['dataset'] = 'Rossmann Store Sales'
        ross_metrics['frequency'] = 'daily'
        results['rossmann'] = ross_metrics
        print(f"    Rossmann MAE={ross_metrics['mae']}, RMSE={ross_metrics['rmse']}, MAPE={ross_metrics['mape_pct']}%")
    except Exception as e:
        print(f"    Rossmann error: {e}")
        results['rossmann'] = {"error": str(e)}

    # --- Walmart ---
    print("  Loading Walmart Store Sales...")
    try:
        walmart_weekly = prepare_walmart(base_dir)
        print(f"    Walmart weekly aggregated shape: {walmart_weekly.shape}, date range: {walmart_weekly['ds'].min()} to {walmart_weekly['ds'].max()}")
        # Walmart is weekly data, so use ~13 weeks (1 quarter) as test
        walmart_metrics = _train_evaluate_ridge(walmart_weekly, test_days=13)
        walmart_metrics['dataset'] = 'Walmart Store Sales'
        walmart_metrics['frequency'] = 'weekly'
        results['walmart'] = walmart_metrics
        print(f"    Walmart MAE={walmart_metrics['mae']}, RMSE={walmart_metrics['rmse']}, MAPE={walmart_metrics['mape_pct']}%")
    except Exception as e:
        print(f"    Walmart error: {e}")
        results['walmart'] = {"error": str(e)}

    return results
