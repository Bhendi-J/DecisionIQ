import os
import sys

SERVICE_DIR = os.path.dirname(os.path.abspath(__file__))
if SERVICE_DIR not in sys.path:
    sys.path.insert(0, SERVICE_DIR)

import pandas as pd
import numpy as np

from scripts.train_prophet import train as train_prophet_func
from scripts.train_xgboost import train as train_xgboost_func
from app.services.finance_service import FinanceService
from app.schemas.finance_schema import RiskPredictRequest, WhatIfRequest

def run_all():
    print("\n" + "="*70)
    print("STEP 1 & 2: RUNNING PROPHET & XGBOOST MODEL TRAINING PIPELINES")
    print("="*70 + "\n")
    
    # 1. Train Prophet
    print("\n--- 1. PROPHET TRAINING & EVALUATION ---")
    train_prophet_func()
    
    # 2. Train XGBoost
    print("\n--- 2. XGBOOST TRAINING & EVALUATION ---")
    train_xgboost_func()
    
    # 3. Test Service In-Memory Models & SHAP Attribution
    print("\n" + "="*70)
    print("STEP 3: SHAP ATTRIBUTION VERIFICATION ON REAL PREDICTION")
    print("="*70 + "\n")
    
    finance_svc = FinanceService(SERVICE_DIR)
    
    sample_request = RiskPredictRequest(
        sector="Retail",
        employees=15,
        revenue_usd=50000.0,
        opex_usd=42000.0,
        accounts_receivable_days=55.0,
        inventory_days=30.0,
        loan_balance_usd=25000.0,
        owner_injections_usd=2000.0
    )
    
    prediction_response = finance_svc.predict_risk(sample_request)
    
    print(f"Sample Business Input Profile: {sample_request.model_dump()}")
    print(f"Predicted Risk Probability: {prediction_response.risk_probability}")
    print(f"Predicted Binary Risk Class: {prediction_response.risk_class} ({'HIGH RISK' if prediction_response.risk_class == 1 else 'LOW RISK'})")
    print("\nTop Contributing SHAP Features:")
    for feat in prediction_response.shap_features:
        print(f"  - Feature: {feat.feature:30s} | Direction: {feat.direction:15s} | Impact (Magnitude): {feat.magnitude:.4f}")
        
    # 4. Test What-If Simulation (OPEX +15%)
    print("\n" + "="*70)
    print("STEP 4: WHAT-IF FINANCIAL SIMULATION VERIFICATION (OPEX +15%)")
    print("="*70 + "\n")
    
    what_if_req = WhatIfRequest(
        expenses_change_pct=15.0,
        base_input=sample_request
    )
    
    sim_response = finance_svc.simulate_what_if(what_if_req, security_score=0.40)
    
    print(f"Original Risk Score (Baseline OPEX $42,000): {sim_response.original_risk_score}")
    print(f"Simulated Risk Score (OPEX +15% -> $48,300) : {sim_response.simulated_risk_score}")
    print(f"Risk Score Delta                            : {sim_response.risk_score_delta:+.4f}")
    print(f"Original Composite Score (Finance + Sec 0.4): {sim_response.original_composite_score}")
    print(f"Simulated Composite Score                  : {sim_response.simulated_composite_score}")
    print(f"Summary Message                             : {sim_response.summary_message}")
    
    print("\nSimulated Top SHAP Drivers:")
    for feat in sim_response.simulated_shap:
        print(f"  - Feature: {feat.feature:30s} | Direction: {feat.direction:15s} | Impact (Magnitude): {feat.magnitude:.4f}")
        
    print("\n" + "="*70)
    print("PIPELINE & DEMO VERIFICATION COMPLETED SUCCESSFULLY!")
    print("="*70 + "\n")

if __name__ == '__main__':
    run_all()
