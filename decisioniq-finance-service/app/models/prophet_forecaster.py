"""
Prophet Forecasting Engine for DecisionIQ Finance Service.

DATASET STRATEGY & REASONING:
--------------------------------------------------------------------------------
Dataset: Online Retail.xlsx
Proxy: Revenue = Quantity * UnitPrice aggregated daily as ds and y.
Cancelled Transactions: Filtered out where InvoiceNo starts with 'C' or Quantity <= 0.
Time-Series Split: Chronological split (last 90 days held out for validation).
Forecast Horizon: 90 days.
Metrics: MAE, RMSE, MAPE.
"""

import os
import joblib
import pandas as pd
import numpy as np
from typing import Dict, Any, Tuple, Optional, List

class ProphetForecaster:
    def __init__(self, model_path: Optional[str] = None):
        self.model = None
        self.model_path = model_path
        if model_path and os.path.exists(model_path):
            self.load(model_path)
            
    def preprocess_retail_data(self, df_raw: pd.DataFrame) -> pd.DataFrame:
        """
        Cleans Online Retail dataset into Prophet-compatible (ds, y) format.
        """
        df = df_raw.copy()
        
        # 1. Column standardization
        df.columns = [c.strip() for c in df.columns]
        
        # 2. Filter cancelled transactions & invalid quantities/prices
        if 'InvoiceNo' in df.columns:
            df['InvoiceNo'] = df['InvoiceNo'].astype(str)
            df = df[~df['InvoiceNo'].str.startswith('C', na=False)]
            
        df['Quantity'] = pd.to_numeric(df['Quantity'], errors='coerce')
        df['UnitPrice'] = pd.to_numeric(df['UnitPrice'], errors='coerce')
        
        df = df[(df['Quantity'] > 0) & (df['UnitPrice'] > 0)]
        
        # 3. Calculate Revenue
        df['Revenue'] = df['Quantity'] * df['UnitPrice']
        
        # 4. Parse InvoiceDate
        df['InvoiceDate'] = pd.to_datetime(df['InvoiceDate'])
        df['ds'] = df['InvoiceDate'].dt.date
        
        # 5. Aggregate Daily
        df_daily = df.groupby('ds')['Revenue'].sum().reset_index()
        df_daily.columns = ['ds', 'y']
        df_daily['ds'] = pd.to_datetime(df_daily['ds'])
        
        # Fill missing dates with 0 revenue
        full_date_range = pd.date_range(start=df_daily['ds'].min(), end=df_daily['ds'].max(), freq='D')
        df_daily = df_daily.set_index('ds').reindex(full_date_range, fill_value=0.0).reset_index()
        df_daily.columns = ['ds', 'y']
        
        return df_daily

    def fit_and_evaluate(self, df_daily: pd.DataFrame, test_days: int = 90) -> Dict[str, Any]:
        """
        Chronologically splits data, fits Prophet (or seasonal trend fallback), and evaluates on unseen test window.
        """
        try:
            from prophet import Prophet
            use_prophet = True
        except ImportError:
            use_prophet = False
            
        if len(df_daily) <= test_days:
            train_df = df_daily
            test_df = df_daily
        else:
            train_df = df_daily.iloc[:-test_days].copy()
            test_df = df_daily.iloc[-test_days:].copy()
            
        if use_prophet:
            m = Prophet(
                yearly_seasonality=True,
                weekly_seasonality=True,
                daily_seasonality=False,
                seasonality_mode='multiplicative'
            )
            m.fit(train_df)
            future_test = m.make_future_dataframe(periods=len(test_df), freq='D')
            forecast_test = m.predict(future_test)
            full_model = Prophet(yearly_seasonality=True, weekly_seasonality=True, daily_seasonality=False)
            full_model.fit(df_daily)
            self.model = full_model
        else:
            # Fallback Seasonal Trend Model using Ridge Regression & Fourier Features
            from sklearn.linear_model import Ridge
            
            def extract_time_features(df_in):
                t = (df_in['ds'] - df_in['ds'].min()).dt.days.values.reshape(-1, 1)
                day_of_week = df_in['ds'].dt.dayofweek.values
                day_of_year = df_in['ds'].dt.dayofyear.values
                
                # Fourier terms for annual & weekly seasonality
                sin_week = np.sin(2 * np.pi * day_of_week / 7.0).reshape(-1, 1)
                cos_week = np.cos(2 * np.pi * day_of_week / 7.0).reshape(-1, 1)
                sin_year = np.sin(2 * np.pi * day_of_year / 365.25).reshape(-1, 1)
                cos_year = np.cos(2 * np.pi * day_of_year / 365.25).reshape(-1, 1)
                
                return np.hstack([t, sin_week, cos_week, sin_year, cos_year])

            X_tr = extract_time_features(train_df)
            y_tr = train_df['y'].values
            
            reg = Ridge(alpha=1.0)
            reg.fit(X_tr, y_tr)
            
            # Predict on test
            X_te = extract_time_features(test_df)
            y_pred_vals = np.maximum(0, reg.predict(X_te))
            
            forecast_test = test_df[['ds']].copy()
            forecast_test['yhat'] = y_pred_vals
            
            # Save fallback model params
            self.model = ("fallback", reg, df_daily['ds'].min())

        # Evaluate on test set
        merged = pd.merge(test_df, forecast_test[['ds', 'yhat']], on='ds', how='inner')
        
        if len(merged) > 0:
            y_true = merged['y'].values
            y_pred = merged['yhat'].values
            
            mae = float(np.mean(np.abs(y_true - y_pred)))
            rmse = float(np.sqrt(np.mean((y_true - y_pred) ** 2)))
            # MAPE: exclude zero-revenue days to avoid division-by-zero inflation
            nonzero = y_true > 0
            if nonzero.sum() > 0:
                mape = float(np.mean(np.abs((y_true[nonzero] - y_pred[nonzero]) / y_true[nonzero]))) * 100.0
            else:
                mape = 0.0
        else:
            mae, rmse, mape = 0.0, 0.0, 0.0
            
        metrics = {
            "mae": round(mae, 2),
            "rmse": round(rmse, 2),
            "mape_pct": round(mape, 2),
            "train_size": len(train_df),
            "test_size": len(test_df),
            "model_type": "Prophet" if use_prophet else "Ridge-Fourier-Seasonal (Prophet Fallback)"
        }
        return metrics

    def predict_future(self, df_daily: pd.DataFrame, horizon_days: int = 90) -> Dict[str, List[Dict[str, Any]]]:
        """
        Generates 90-day future forecast and returns formatted historical & future items.
        """
        try:
            from prophet import Prophet
            use_prophet = True
        except ImportError:
            use_prophet = False
            
        if use_prophet:
            if self.model is None or not isinstance(self.model, Prophet):
                self.model = Prophet(yearly_seasonality=True, weekly_seasonality=True, daily_seasonality=False)
                self.model.fit(df_daily)
                
            future = self.model.make_future_dataframe(periods=horizon_days, freq='D')
            forecast = self.model.predict(future)
        else:
            from sklearn.linear_model import Ridge
            min_date = df_daily['ds'].min()
            
            def extract_time_features(ds_series):
                t = (ds_series - min_date).dt.days.values.reshape(-1, 1)
                day_of_week = ds_series.dt.dayofweek.values
                day_of_year = ds_series.dt.dayofyear.values
                
                sin_week = np.sin(2 * np.pi * day_of_week / 7.0).reshape(-1, 1)
                cos_week = np.cos(2 * np.pi * day_of_week / 7.0).reshape(-1, 1)
                sin_year = np.sin(2 * np.pi * day_of_year / 365.25).reshape(-1, 1)
                cos_year = np.cos(2 * np.pi * day_of_year / 365.25).reshape(-1, 1)
                
                return np.hstack([t, sin_week, cos_week, sin_year, cos_year])

            full_date_range = pd.date_range(start=min_date, end=df_daily['ds'].max() + pd.Timedelta(days=horizon_days), freq='D')
            forecast_df = pd.DataFrame({'ds': full_date_range})
            
            X_all = extract_time_features(forecast_df['ds'])
            reg = Ridge(alpha=1.0)
            reg.fit(extract_time_features(df_daily['ds']), df_daily['y'].values)
            
            y_all = np.maximum(0, reg.predict(X_all))
            
            forecast = forecast_df.copy()
            forecast['yhat'] = y_all
            forecast['yhat_lower'] = forecast['yhat'] * 0.85
            forecast['yhat_upper'] = forecast['yhat'] * 1.15

        forecast['ds_str'] = forecast['ds'].dt.strftime('%Y-%m-%d')
        last_hist_date = df_daily['ds'].max().strftime('%Y-%m-%d')
        
        hist_df = forecast[forecast['ds_str'] <= last_hist_date].copy()
        fut_df = forecast[forecast['ds_str'] > last_hist_date].copy()
        
        df_daily_copy = df_daily.copy()
        df_daily_copy['ds_str'] = df_daily_copy['ds'].dt.strftime('%Y-%m-%d')
        hist_df = pd.merge(hist_df, df_daily_copy[['ds_str', 'y']], on='ds_str', how='left')
        
        historical_items = [
            {
                "ds": row['ds_str'],
                "yhat": round(float(row['y'] if pd.notnull(row['y']) else row['yhat']), 2),
                "yhat_lower": round(float(row['yhat_lower']), 2),
                "yhat_upper": round(float(row['yhat_upper']), 2)
            }
            for _, row in hist_df.iterrows()
        ]
        
        future_items = [
            {
                "ds": row['ds_str'],
                "yhat": round(float(row['yhat']), 2),
                "yhat_lower": round(float(row['yhat_lower']), 2),
                "yhat_upper": round(float(row['yhat_upper']), 2)
            }
            for _, row in fut_df.iterrows()
        ]
        
        return {
            "historical": historical_items,
            "future": future_items
        }

    def save(self, file_path: str):
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        joblib.dump(self.model, file_path)

    def load(self, file_path: str):
        self.model = joblib.load(file_path)
