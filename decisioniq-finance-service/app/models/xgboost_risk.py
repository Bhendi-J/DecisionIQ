"""
XGBoost Cash-Flow Stress Risk Model for DecisionIQ Finance Service.

MODEL CONCEPTS & RULES:
--------------------------------------------------------------------------------
1. Supervised Target: cashflow_stress_next_month (0 = No stress, 1 = Cash-flow stress)
2. Predictors: Engineered financial features from current month.
3. Model: XGBClassifier with scale_pos_weight to handle class imbalance if present.
4. Outputs: Probability (0.0 to 1.0) and Risk Class (0 or 1).
"""

import os
import joblib
import numpy as np
import pandas as pd
from typing import Dict, Any, Tuple, Optional
from xgboost import XGBClassifier
from sklearn.metrics import (
    precision_score, recall_score, f1_score, roc_auc_score, confusion_matrix
)
from app.services.feature_engineering import build_features_df, prepare_cashflow_dataset, FEATURE_COLUMNS

class XGBoostRiskModel:
    def __init__(self, model_path: Optional[str] = None):
        self.model: Optional[XGBClassifier] = None
        self.model_path = model_path
        if model_path and os.path.exists(model_path):
            self.load(model_path)
            
    def train_and_evaluate(self, df: pd.DataFrame) -> Tuple[Dict[str, Any], Any]:
        """
        Processes dataset, sorts chronologically, splits, trains XGBoost,
        and returns unbiased evaluation metrics.
        
        BUG FIX: Previous version did not sort by month before splitting,
        causing a pseudo-random split instead of chronological.
        """
        target_col = 'cashflow_stress_next_month'
        if target_col not in df.columns:
            raise ValueError(f"Target column '{target_col}' missing from dataset!")

        # CRITICAL FIX: Sort by month before chronological split
        df_sorted = prepare_cashflow_dataset(df)
        
        # 1. Feature Engineering
        X = build_features_df(df_sorted)
        y = df_sorted[target_col].astype(int)
        
        # 2. Chronological Split (80% Train, 20% Test) on sorted data
        split_idx = int(len(df_sorted) * 0.8)
        X_train, X_test = X.iloc[:split_idx], X.iloc[split_idx:]
        y_train, y_test = y.iloc[:split_idx], y.iloc[split_idx:]
        
        # Log split diagnostics
        if 'month' in df_sorted.columns:
            train_months = df_sorted['month'].iloc[:split_idx]
            test_months = df_sorted['month'].iloc[split_idx:]
            print(f"  Train months: {train_months.min()} to {train_months.max()}")
            print(f"  Test months: {test_months.min()} to {test_months.max()}")
            overlap = set(train_months.unique()) & set(test_months.unique())
            if overlap:
                print(f"  WARNING: Train/Test month overlap: {overlap}")
            else:
                print(f"  OK: No temporal overlap between train and test sets.")
        
        print(f"  Train target distribution: {dict(y_train.value_counts())}")
        print(f"  Test target distribution: {dict(y_test.value_counts())}")
        
        # Calculate class imbalance for scale_pos_weight
        num_pos = (y_train == 1).sum()
        num_neg = (y_train == 0).sum()
        pos_weight = (num_neg / max(1, num_pos)) if num_pos > 0 else 1.0
        
        # 3. Model Training
        self.model = XGBClassifier(
            n_estimators=200,
            max_depth=4,
            learning_rate=0.05,
            scale_pos_weight=pos_weight,
            subsample=0.8,
            colsample_bytree=0.8,
            random_state=42,
            eval_metric='logloss'
        )
        self.model.fit(X_train, y_train)
        
        # 4. Model Evaluation on Unseen Test Set
        y_pred = self.model.predict(X_test)
        y_prob = self.model.predict_proba(X_test)[:, 1]
        
        prec = float(precision_score(y_test, y_pred, zero_division=0))
        rec = float(recall_score(y_test, y_pred, zero_division=0))
        f1 = float(f1_score(y_test, y_pred, zero_division=0))
        
        try:
            auc = float(roc_auc_score(y_test, y_prob))
        except:
            auc = 0.5
            
        cm = confusion_matrix(y_test, y_pred).tolist()
        
        metrics = {
            "precision": round(prec, 4),
            "recall": round(rec, 4),
            "f1_score": round(f1, 4),
            "roc_auc": round(auc, 4),
            "confusion_matrix": cm,
            "class_imbalance": {
                "positive_count": int(num_pos),
                "negative_count": int(num_neg),
                "scale_pos_weight": round(pos_weight, 2)
            },
            "train_samples": len(X_train),
            "test_samples": len(X_test)
        }
        
        return metrics, self.model

    def predict(self, X_features: pd.DataFrame) -> Tuple[float, int]:
        """
        Returns predicted risk probability and binary risk class.
        """
        if self.model is None:
            # Fallback heuristic predictor if model file isn't loaded yet
            return self._heuristic_predict(X_features)
            
        prob = float(self.model.predict_proba(X_features)[0, 1])
        risk_class = 1 if prob >= 0.5 else 0
        return prob, risk_class

    def _heuristic_predict(self, X_features: pd.DataFrame) -> Tuple[float, int]:
        """
        Fallback logic based on financial ratios before model training.
        """
        exp_ratio = float(X_features['expense_ratio'].iloc[0]) if 'expense_ratio' in X_features else 0.7
        ar_days = float(X_features['accounts_receivable_days'].iloc[0]) if 'accounts_receivable_days' in X_features else 30.0
        
        prob = min(0.95, max(0.05, 0.3 + (exp_ratio * 0.4) + (ar_days / 200.0)))
        risk_class = 1 if prob >= 0.5 else 0
        return prob, risk_class

    def save(self, file_path: str):
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        joblib.dump(self.model, file_path)

    def load(self, file_path: str):
        self.model = joblib.load(file_path)
