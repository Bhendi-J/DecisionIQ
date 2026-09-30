"""
DecisionIQ Extended Investigation Script
=========================================
1. Diagnose XGBoost ROC-AUC ~0.49 issue
2. Investigate SHAP/What-If OPEX bug (risk DECREASED when OPEX increased)  
3. Inspect Walmart, Rossmann, Taiwanese & Polish datasets
"""
import os
import sys
import pandas as pd
import numpy as np

SERVICE_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.dirname(SERVICE_DIR)
sys.path.insert(0, SERVICE_DIR)

from app.services.feature_engineering import build_features_df, engineer_single_input, FEATURE_COLUMNS, SECTORS

print("="*70)
print("INVESTIGATION 1: XGBoost ROC-AUC & Feature Engineering Diagnosis")
print("="*70)

csv_path = os.path.join(BASE_DIR, 'Datasets', 'archive', 'small_business_cashflow.csv')
df = pd.read_csv(csv_path)

print(f"\nDataset shape: {df.shape}")
print(f"Columns: {list(df.columns)}")
print(f"\nTarget distribution:")
print(df['cashflow_stress_next_month'].value_counts())

# Check if data has temporal ordering
print(f"\nSample 'month' values (first 10): {df['month'].head(10).tolist()}")
print(f"Unique months: {sorted(df['month'].unique())}")
print(f"Number of unique months: {df['month'].nunique()}")

# Check if sector assignment affects target
print(f"\nTarget by sector:")
print(df.groupby('sector')['cashflow_stress_next_month'].mean())

# Check feature correlations with target
target = df['cashflow_stress_next_month']
for col in ['employees', 'revenue_usd', 'opex_usd', 'accounts_receivable_days', 
            'inventory_days', 'loan_balance_usd', 'owner_injections_usd']:
    corr = df[col].corr(target)
    print(f"  Correlation {col:30s} vs target: {corr:+.4f}")

# Build features and check
X = build_features_df(df)
print(f"\nFeature matrix shape: {X.shape}")
print(f"Feature columns: {list(X.columns)}")

# Check engineered feature correlations
for col in ['profit', 'expense_ratio', 'debt_to_revenue_ratio', 'injection_reliance', 'cash_cycle_risk']:
    corr = X[col].corr(target)
    print(f"  Correlation {col:30s} vs target: {corr:+.4f}")

# CRITICAL: Check the sector encoding
print(f"\nSECTOR ENCODING ANALYSIS:")
print(f"  Sectors in FEATURE_COLUMNS list: {SECTORS}")
print(f"  Actual sectors in dataset: {sorted(df['sector'].unique())}")
# Check if capitalization matches
for s in df['sector'].unique():
    clean = s.strip().capitalize()
    matches = [sec for sec in SECTORS if sec == clean]
    print(f"    Raw='{s}' -> Cleaned='{clean}' -> Match in SECTORS: {matches}")

print("\n" + "="*70)
print("INVESTIGATION 2: What-If OPEX Bug Trace")
print("="*70)

# Reproduce the exact What-If scenario that showed OPEX+15% REDUCING risk
original = {
    'sector': 'Retail', 'employees': 15, 'revenue_usd': 50000.0,
    'opex_usd': 42000.0, 'accounts_receivable_days': 55.0,
    'inventory_days': 30.0, 'loan_balance_usd': 25000.0,
    'owner_injections_usd': 2000.0
}
simulated = original.copy()
simulated['opex_usd'] = 42000.0 * 1.15  # $48,300

orig_feats = engineer_single_input(original)
sim_feats = engineer_single_input(simulated)

print("\nOriginal vs Simulated Feature Comparison:")
for col in FEATURE_COLUMNS:
    orig_val = orig_feats[col].iloc[0]
    sim_val = sim_feats[col].iloc[0]
    delta = sim_val - orig_val
    if abs(delta) > 1e-6:
        print(f"  {col:35s}: {orig_val:>12.4f} -> {sim_val:>12.4f}  (delta = {delta:+.4f})")
    else:
        print(f"  {col:35s}: {orig_val:>12.4f} (unchanged)")

# Check: the XGBoost model currently loaded uses heuristic if no .pkl exists
# The heuristic_predict in xgboost_risk.py uses expense_ratio and ar_days
# But the SHAP explainer is using heuristic_explanation which has different logic
# Let's check if the trained model .pkl exists
xgb_path = os.path.join(SERVICE_DIR, 'models', 'xgboost', 'xgboost_risk.pkl')
print(f"\nXGBoost model file exists: {os.path.exists(xgb_path)}")

print("\n" + "="*70)
print("INVESTIGATION 3: Dataset Inspection for New Models")
print("="*70)

# -- Rossmann --
print("\n--- Rossmann Store Sales ---")
ross_path = os.path.join(BASE_DIR, 'Datasets', 'rossmann-store-sales', 'train.csv')
ross_df = pd.read_csv(ross_path, nrows=5)
print(f"Columns: {list(ross_df.columns)}")
print(ross_df.head())
ross_full = pd.read_csv(ross_path, usecols=['Date', 'Sales', 'Store'], parse_dates=['Date'])
print(f"Full shape: {ross_full.shape}")
print(f"Date range: {ross_full['Date'].min()} to {ross_full['Date'].max()}")
print(f"Unique stores: {ross_full['Store'].nunique()}")

# -- Walmart --
print("\n--- Walmart Store Sales ---")
walmart_dir = os.path.join(BASE_DIR, 'Datasets', 'walmart-recruiting-store-sales-forecasting')
walmart_train_zip = os.path.join(walmart_dir, 'train.csv.zip')
walmart_df = pd.read_csv(walmart_train_zip)
print(f"Columns: {list(walmart_df.columns)}")
print(f"Shape: {walmart_df.shape}")
print(walmart_df.head())
print(f"Date range: {walmart_df['Date'].min()} to {walmart_df['Date'].max()}")
print(f"Unique stores: {walmart_df['Store'].nunique()}")

# -- Taiwanese Bankruptcy --
print("\n--- Taiwanese Bankruptcy ---")
tw_path = os.path.join(BASE_DIR, 'Datasets', 'taiwanese+bankruptcy+prediction', 'data.csv')
tw_df = pd.read_csv(tw_path)
print(f"Shape: {tw_df.shape}")
print(f"Columns (first 10): {list(tw_df.columns[:10])}")
print(f"Columns (last 5): {list(tw_df.columns[-5:])}")
# Find target column
for col in tw_df.columns:
    if 'bankrupt' in col.lower() or 'class' in col.lower():
        print(f"Potential target: '{col}' -> distribution: {tw_df[col].value_counts().to_dict()}")

# -- Polish Bankruptcy (1year.arff) --
print("\n--- Polish Bankruptcy (1year.arff sample) ---")
polish_path = os.path.join(BASE_DIR, 'Datasets', 'polish+companies+bankruptcy+data', '1year.arff')
# Read ARFF manually
with open(polish_path, 'r') as f:
    lines = f.readlines()
    header_lines = [l.strip() for l in lines if l.strip().startswith('@')]
    data_start = next(i for i, l in enumerate(lines) if l.strip().upper() == '@DATA')
    
print(f"Number of @ATTRIBUTE lines: {sum(1 for h in header_lines if h.upper().startswith('@ATTRIBUTE'))}")
# Parse data portion
data_lines = [l.strip() for l in lines[data_start+1:] if l.strip() and not l.strip().startswith('%')]
print(f"Number of data rows: {len(data_lines)}")
# Parse first row to check structure
sample_row = data_lines[0].split(',')
print(f"Features per row: {len(sample_row)}")
print(f"Last column (target) sample values: {[data_lines[i].split(',')[-1] for i in range(min(5, len(data_lines)))]}")

# Count target distribution
targets = [l.split(',')[-1].strip() for l in data_lines]
from collections import Counter
print(f"Target distribution: {Counter(targets)}")

print("\n" + "="*70)
print("INVESTIGATION COMPLETE")
print("="*70)
