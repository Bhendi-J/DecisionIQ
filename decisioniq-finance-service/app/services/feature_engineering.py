"""
Feature Engineering Module for DecisionIQ Finance Service.

DOCUMENTATION OF ENGINEERED FEATURES:
--------------------------------------------------------------------------------
1. Feature Name: profit
   Formula: revenue_usd - opex_usd
   Business Meaning: Operating profitability proxy per month.
   Reason for Inclusion: Baseline proxy metric for net profitability before debt and tax obligations.

2. Feature Name: expense_ratio
   Formula: opex_usd / (revenue_usd + 1e-5)
   Business Meaning: Operating expense ratio (burn rate relative to sales).
   Reason for Inclusion: High expense ratio directly indicates cash flow vulnerability and thin buffer against revenue drops.

3. Feature Name: debt_to_revenue_ratio
   Formula: loan_balance_usd / (revenue_usd + 1e-5)
   Business Meaning: Leverage ratio measuring total debt against single-month revenue.
   Reason for Inclusion: High debt burden drains cash flow via interest and principal payments.

4. Feature Name: injection_reliance
   Formula: owner_injections_usd / (revenue_usd + 1e-5)
   Business Meaning: Degree to which business operations rely on owner capital support.
   Reason for Inclusion: Frequent owner injections signal organic cash flow deficiency.

5. Feature Name: cash_cycle_risk
   Formula: accounts_receivable_days + inventory_days
   Business Meaning: Working capital cash conversion cycle duration in days.
   Reason for Inclusion: Longer cash conversion cycles trap cash in working capital, driving liquidity stress.

DATA LEAKAGE PREVENTION:
--------------------------------------------------------------------------------
- Target: cashflow_stress_next_month (binary risk indicator for Month N+1)
- Predictors: All features are derived strictly from Month N financials.
- Excluded: record_id, customer/transaction IDs, and any future period metrics.

DATASET NOTE:
--------------------------------------------------------------------------------
- small_business_cashflow.csv is a PROTOTYPE/SYNTHETIC dataset.
- cashflow_stress_next_month is the supervised classification target.
- Feature correlations with target are weak (max ~0.11), expected for synthetic data.

BUG FIX LOG:
--------------------------------------------------------------------------------
- v1.1: Fixed sector encoding mismatch. Original SECTORS list missed Hospitality,
  IT Services, and Logistics from the actual dataset. str.capitalize() only
  capitalizes the first word, breaking multi-word sectors like 'IT Services'.
  Now using str.title() and matching actual dataset sectors.
- v1.1: Data must be sorted by 'month' before chronological splitting.
"""

import pandas as pd
import numpy as np
from typing import Dict, Any, List

# FIXED: Match actual sectors present in small_business_cashflow.csv
# plus reasonable default sectors for API input
SECTORS = [
    "Retail", "Manufacturing", "Healthcare",
    "Hospitality", "It Services", "Logistics",
    "Services", "Technology", "Construction", "Other"
]

FEATURE_COLUMNS = [
    'employees',
    'revenue_usd',
    'opex_usd',
    'accounts_receivable_days',
    'inventory_days',
    'loan_balance_usd',
    'owner_injections_usd',
    'profit',
    'expense_ratio',
    'debt_to_revenue_ratio',
    'injection_reliance',
    'cash_cycle_risk',
] + [f"sector_{s.lower().replace(' ', '_')}" for s in SECTORS]

def _clean_sector(raw: str) -> str:
    """
    Normalize sector string for consistent one-hot encoding.
    Uses .title() instead of .capitalize() so 'IT Services' -> 'It Services' consistently.
    """
    return str(raw).strip().title()

def build_features_df(df: pd.DataFrame) -> pd.DataFrame:
    """
    Transforms raw dataframe into model-ready features.
    Handles categorical sector encoding and feature engineering.
    """
    df_out = df.copy()
    
    # 1. Basic cleaning / type conversion
    numeric_cols = [
        'employees', 'revenue_usd', 'opex_usd', 
        'accounts_receivable_days', 'inventory_days', 
        'loan_balance_usd', 'owner_injections_usd'
    ]
    for col in numeric_cols:
        if col in df_out.columns:
            df_out[col] = pd.to_numeric(df_out[col], errors='coerce').fillna(0.0)
            
    # 2. Feature Engineering
    eps = 1e-5
    df_out['profit'] = df_out['revenue_usd'] - df_out['opex_usd']
    df_out['expense_ratio'] = df_out['opex_usd'] / (df_out['revenue_usd'] + eps)
    df_out['debt_to_revenue_ratio'] = df_out['loan_balance_usd'] / (df_out['revenue_usd'] + eps)
    df_out['injection_reliance'] = df_out['owner_injections_usd'] / (df_out['revenue_usd'] + eps)
    df_out['cash_cycle_risk'] = df_out['accounts_receivable_days'] + df_out['inventory_days']
    
    # 3. Categorical Encoding (Sector) - FIXED
    if 'sector' in df_out.columns:
        df_out['sector_clean'] = df_out['sector'].apply(_clean_sector)
    else:
        df_out['sector_clean'] = "Retail"

    for sector_name in SECTORS:
        col_name = f"sector_{sector_name.lower().replace(' ', '_')}"
        df_out[col_name] = (df_out['sector_clean'] == sector_name).astype(float)

    # 4. Ensure all expected feature columns are present
    for col in FEATURE_COLUMNS:
        if col not in df_out.columns:
            df_out[col] = 0.0

    return df_out[FEATURE_COLUMNS]

def prepare_cashflow_dataset(df: pd.DataFrame) -> pd.DataFrame:
    """
    Sorts the small_business_cashflow dataset by month for proper chronological splitting.
    Must be called before train/test splitting.
    """
    if 'month' in df.columns:
        df_sorted = df.sort_values('month').reset_index(drop=True)
        return df_sorted
    return df

def engineer_single_input(data_dict: Dict[str, Any]) -> pd.DataFrame:
    """
    Transforms single API payload into a 1-row feature DataFrame.
    """
    df_single = pd.DataFrame([data_dict])
    return build_features_df(df_single)
