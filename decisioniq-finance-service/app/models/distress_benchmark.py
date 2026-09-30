"""
Financial Distress Benchmark Module for DecisionIQ Finance Service.

Trains separate simple baseline models on:
- UCI Taiwanese Bankruptcy dataset (96 financial ratios, target: Bankrupt?)
- UCI Polish Companies Bankruptcy dataset (64 financial ratios, target: class)

These are SEPARATE models, NOT merged with small_business_cashflow.
Purpose: Demonstrate DecisionIQ can analyze broader financial distress beyond
short-term cash-flow stress.
"""

import os
import numpy as np
import pandas as pd
from typing import Dict, Any, List, Tuple, Optional
from xgboost import XGBClassifier
from sklearn.metrics import (
    precision_score, recall_score, f1_score, roc_auc_score, confusion_matrix
)
import joblib


def load_taiwanese_bankruptcy(base_dir: str) -> Tuple[pd.DataFrame, str]:
    """Load Taiwanese bankruptcy dataset."""
    path = os.path.join(base_dir, 'Datasets', 'taiwanese+bankruptcy+prediction', 'data.csv')
    df = pd.read_csv(path)
    # Clean column names (they have leading spaces)
    df.columns = [c.strip() for c in df.columns]
    target_col = 'Bankrupt?'
    return df, target_col


def load_polish_bankruptcy(base_dir: str, year: int = 1) -> Tuple[pd.DataFrame, str]:
    """Load Polish companies bankruptcy dataset from ARFF file."""
    path = os.path.join(base_dir, 'Datasets', 'polish+companies+bankruptcy+data', f'{year}year.arff')

    # Parse ARFF manually
    with open(path, 'r') as f:
        lines = f.readlines()

    # Extract attribute names
    attr_names = []
    data_start = 0
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.upper().startswith('@ATTRIBUTE'):
            parts = stripped.split()
            attr_names.append(parts[1])
        elif stripped.upper() == '@DATA':
            data_start = i + 1
            break

    # Parse data rows
    data_rows = []
    for line in lines[data_start:]:
        stripped = line.strip()
        if stripped and not stripped.startswith('%'):
            values = stripped.split(',')
            # Replace '?' with NaN
            values = [np.nan if v.strip() == '?' else float(v.strip()) for v in values]
            data_rows.append(values)

    df = pd.DataFrame(data_rows, columns=attr_names)
    target_col = attr_names[-1]  # Last column is the class/target
    return df, target_col


def train_distress_model(
    df: pd.DataFrame,
    target_col: str,
    dataset_name: str,
    save_path: Optional[str] = None
) -> Dict[str, Any]:
    """
    Train a simple XGBoost baseline for financial distress classification.
    Uses stratified random split (these datasets lack clear temporal ordering).
    """
    from sklearn.model_selection import train_test_split

    # Separate features and target
    y = df[target_col].astype(int)
    X = df.drop(columns=[target_col])

    # Handle missing values with median imputation
    X = X.fillna(X.median())

    # Handle infinite values
    X = X.replace([np.inf, -np.inf], np.nan)
    X = X.fillna(X.median())

    # Stratified 80/20 split
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )

    num_pos = int((y_train == 1).sum())
    num_neg = int((y_train == 0).sum())
    pos_weight = (num_neg / max(1, num_pos)) if num_pos > 0 else 1.0

    model = XGBClassifier(
        n_estimators=100,
        max_depth=4,
        learning_rate=0.05,
        scale_pos_weight=pos_weight,
        random_state=42,
        eval_metric='logloss'
    )
    model.fit(X_train, y_train)

    y_pred = model.predict(X_test)
    y_prob = model.predict_proba(X_test)[:, 1]

    prec = float(precision_score(y_test, y_pred, zero_division=0))
    rec = float(recall_score(y_test, y_pred, zero_division=0))
    f1 = float(f1_score(y_test, y_pred, zero_division=0))
    try:
        auc = float(roc_auc_score(y_test, y_prob))
    except:
        auc = 0.5
    cm = confusion_matrix(y_test, y_pred).tolist()

    # Extract top SHAP features
    shap_features = []
    try:
        import shap
        explainer = shap.TreeExplainer(model)
        shap_vals = explainer.shap_values(X_test.iloc[:50])  # Sample for speed
        if isinstance(shap_vals, list):
            shap_vals = shap_vals[1]

        mean_abs_shap = np.mean(np.abs(shap_vals), axis=0)
        top_indices = np.argsort(mean_abs_shap)[::-1][:5]
        for idx in top_indices:
            feat_name = X.columns[idx]
            mag = float(mean_abs_shap[idx])
            shap_features.append({
                "feature": feat_name,
                "mean_abs_shap": round(mag, 4),
            })
    except Exception as e:
        print(f"    SHAP extraction warning for {dataset_name}: {e}")

    if save_path:
        os.makedirs(os.path.dirname(save_path), exist_ok=True)
        joblib.dump(model, save_path)

    return {
        "dataset": dataset_name,
        "total_samples": len(df),
        "num_features": X.shape[1],
        "precision": round(prec, 4),
        "recall": round(rec, 4),
        "f1_score": round(f1, 4),
        "roc_auc": round(auc, 4),
        "confusion_matrix": cm,
        "class_imbalance": {
            "positive_count": num_pos,
            "negative_count": num_neg,
            "scale_pos_weight": round(pos_weight, 2),
        },
        "top_shap_features": shap_features,
        "train_samples": len(X_train),
        "test_samples": len(X_test),
    }


def run_distress_benchmarks(base_dir: str, service_dir: str) -> Dict[str, Dict[str, Any]]:
    """
    Run financial distress classification on Taiwanese and Polish datasets.
    Returns metrics dict keyed by dataset name.
    """
    results = {}

    # --- Taiwanese ---
    print("  Loading Taiwanese Bankruptcy dataset...")
    try:
        tw_df, tw_target = load_taiwanese_bankruptcy(base_dir)
        print(f"    Shape: {tw_df.shape}, Target: '{tw_target}', Distribution: {dict(tw_df[tw_target].value_counts())}")
        tw_save = os.path.join(service_dir, 'models', 'distress', 'taiwanese_xgb.pkl')
        tw_metrics = train_distress_model(tw_df, tw_target, "Taiwanese Bankruptcy", save_path=tw_save)
        results['taiwanese'] = tw_metrics
        print(f"    ROC-AUC={tw_metrics['roc_auc']}, F1={tw_metrics['f1_score']}, Precision={tw_metrics['precision']}, Recall={tw_metrics['recall']}")
    except Exception as e:
        print(f"    Taiwanese error: {e}")
        results['taiwanese'] = {"error": str(e)}

    # --- Polish (1-year horizon) ---
    print("  Loading Polish Companies Bankruptcy dataset (1-year horizon)...")
    try:
        pl_df, pl_target = load_polish_bankruptcy(base_dir, year=1)
        print(f"    Shape: {pl_df.shape}, Target: '{pl_target}', Distribution: {dict(pl_df[pl_target].astype(int).value_counts())}")
        pl_save = os.path.join(service_dir, 'models', 'distress', 'polish_1yr_xgb.pkl')
        pl_metrics = train_distress_model(pl_df, pl_target, "Polish Companies (1-Year)", save_path=pl_save)
        results['polish_1yr'] = pl_metrics
        print(f"    ROC-AUC={pl_metrics['roc_auc']}, F1={pl_metrics['f1_score']}, Precision={pl_metrics['precision']}, Recall={pl_metrics['recall']}")
    except Exception as e:
        print(f"    Polish error: {e}")
        results['polish_1yr'] = {"error": str(e)}

    return results
