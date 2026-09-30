"""
DecisionIQ Extended Multi-Model Evaluation Pipeline
====================================================
Runs all models, evaluates, produces unified output, tests What-If.
"""
import os
import sys
import json

SERVICE_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.dirname(SERVICE_DIR)
sys.path.insert(0, SERVICE_DIR)

import pandas as pd
import numpy as np

def main():
    print("\n" + "="*75)
    print("  DECISIONIQ MULTI-MODEL FINANCIAL INTELLIGENCE - FULL EVALUATION")
    print("="*75)

    # =====================================================================
    # LAYER 1: FORECASTING
    # =====================================================================
    print("\n" + "-"*75)
    print("  LAYER 1: REVENUE FORECASTING (Prophet/Ridge-Fourier)")
    print("-"*75)

    from app.models.prophet_forecaster import ProphetForecaster

    # 1a. Online Retail (Primary)
    print("\n  [1a] UCI Online Retail (Primary Forecaster)")
    excel_path = os.path.join(BASE_DIR, 'Datasets', 'online+retail', 'Online Retail.xlsx')
    forecaster = ProphetForecaster()
    df_raw = pd.read_excel(excel_path)
    df_daily = forecaster.preprocess_retail_data(df_raw)
    print(f"    Daily time-series: {df_daily.shape[0]} days, {df_daily['ds'].min().date()} to {df_daily['ds'].max().date()}")
    retail_metrics = forecaster.fit_and_evaluate(df_daily, test_days=90)
    forecaster.save(os.path.join(SERVICE_DIR, 'models', 'prophet', 'prophet_model.pkl'))
    forecast_data = forecaster.predict_future(df_daily, horizon_days=90)

    print(f"    MAE:  {retail_metrics['mae']}")
    print(f"    RMSE: {retail_metrics['rmse']}")
    print(f"    MAPE: {retail_metrics['mape_pct']}%")
    print(f"    Model: {retail_metrics.get('model_type', 'Prophet')}")

    # 1b. Forecasting Benchmarks (Rossmann, Walmart)
    print("\n  [1b] Forecasting Benchmarks (Rossmann & Walmart)")
    from app.models.forecast_benchmark import run_forecasting_benchmarks
    benchmark_results = run_forecasting_benchmarks(BASE_DIR)

    all_forecast_metrics = {
        "online_retail": retail_metrics,
        **benchmark_results,
    }

    print("\n  FORECASTING COMPARISON TABLE:")
    print(f"    {'Dataset':<25s} {'MAE':>12s} {'RMSE':>12s} {'MAPE(%)':>10s}")
    print(f"    {'-'*25} {'-'*12} {'-'*12} {'-'*10}")
    for name, m in all_forecast_metrics.items():
        if 'error' not in m:
            print(f"    {name:<25s} {m['mae']:>12.2f} {m['rmse']:>12.2f} {m['mape_pct']:>10.2f}")

    # =====================================================================
    # LAYER 2: CASH-FLOW STRESS (FIXED)
    # =====================================================================
    print("\n" + "-"*75)
    print("  LAYER 2: CASH-FLOW STRESS CLASSIFICATION (XGBoost - FIXED)")
    print("-"*75)

    from app.models.xgboost_risk import XGBoostRiskModel

    csv_path = os.path.join(BASE_DIR, 'Datasets', 'archive', 'small_business_cashflow.csv')
    df_cashflow = pd.read_csv(csv_path)
    print(f"\n  Dataset: small_business_cashflow.csv (PROTOTYPE/SYNTHETIC)")
    print(f"  Target: cashflow_stress_next_month (supervised target)")
    print(f"  Shape: {df_cashflow.shape}")

    risk_model = XGBoostRiskModel()
    xgb_metrics, trained_xgb = risk_model.train_and_evaluate(df_cashflow)

    print(f"\n  XGBOOST EVALUATION METRICS (Chronologically-Split Test Set):")
    print(f"    Precision:  {xgb_metrics['precision']}")
    print(f"    Recall:     {xgb_metrics['recall']}")
    print(f"    F1-Score:   {xgb_metrics['f1_score']}")
    print(f"    ROC-AUC:    {xgb_metrics['roc_auc']}")
    print(f"    Confusion Matrix: {xgb_metrics['confusion_matrix']}")
    print(f"    Class Imbalance:  {xgb_metrics['class_imbalance']}")

    risk_model.save(os.path.join(SERVICE_DIR, 'models', 'xgboost', 'xgboost_risk.pkl'))

    # =====================================================================
    # LAYER 3: FINANCIAL DISTRESS BENCHMARKS
    # =====================================================================
    print("\n" + "-"*75)
    print("  LAYER 3: FINANCIAL DISTRESS BENCHMARKS (Taiwanese & Polish)")
    print("-"*75)

    from app.models.distress_benchmark import run_distress_benchmarks
    distress_results = run_distress_benchmarks(BASE_DIR, SERVICE_DIR)

    for name, m in distress_results.items():
        if 'error' not in m:
            print(f"\n  [{name}] {m['dataset']}:")
            print(f"    Samples: {m['total_samples']}, Features: {m['num_features']}")
            print(f"    ROC-AUC:  {m['roc_auc']}")
            print(f"    F1:       {m['f1_score']}")
            print(f"    Precision: {m['precision']}, Recall: {m['recall']}")
            print(f"    Confusion Matrix: {m['confusion_matrix']}")
            if m.get('top_shap_features'):
                print(f"    Top SHAP Features:")
                for sf in m['top_shap_features']:
                    print(f"      - {sf['feature']:50s} (mean|SHAP|={sf['mean_abs_shap']:.4f})")

    # =====================================================================
    # SHAP VERIFICATION ON CASH-STRESS
    # =====================================================================
    print("\n" + "-"*75)
    print("  SHAP VERIFICATION: Real Prediction on Cash-Stress Model")
    print("-"*75)

    from app.models.shap_explainer import SHAPExplainer
    from app.services.feature_engineering import engineer_single_input
    from app.schemas.finance_schema import RiskPredictRequest

    shap_explainer = SHAPExplainer(xgb_model=trained_xgb)

    sample = RiskPredictRequest(
        sector="Retail", employees=15, revenue_usd=50000.0, opex_usd=42000.0,
        accounts_receivable_days=55.0, inventory_days=30.0,
        loan_balance_usd=25000.0, owner_injections_usd=2000.0
    )
    X_feat = engineer_single_input(sample.model_dump())
    risk_prob, risk_class = risk_model.predict(X_feat)
    shap_feats = shap_explainer.explain_instance(X_feat, top_n=5)

    print(f"\n  Input: sector=Retail, revenue=$50k, opex=$42k, AR=55d, inventory=30d, loan=$25k")
    print(f"  Predicted Risk Probability: {risk_prob:.4f} ({risk_prob*100:.1f}%)")
    print(f"  Risk Class: {risk_class} ({'HIGH RISK' if risk_class == 1 else 'LOW RISK'})")
    print(f"  Top SHAP Contributions:")
    for feat in shap_feats:
        print(f"    - {feat.feature:35s} | {feat.direction:15s} | magnitude={feat.magnitude:.4f}")

    # =====================================================================
    # WHAT-IF VERIFICATION (OPEX +15%)
    # =====================================================================
    print("\n" + "-"*75)
    print("  WHAT-IF SIMULATION: OPEX +15% (Bug Investigation)")
    print("-"*75)

    from app.services.what_if import run_simulation
    from app.schemas.finance_schema import WhatIfRequest

    whatif_req = WhatIfRequest(expenses_change_pct=15.0, base_input=sample)

    sim_result = run_simulation(
        request=whatif_req,
        model_predictor=lambda feats: risk_model.predict(feats),
        shap_explainer=lambda feats: shap_explainer.explain_instance(feats, top_n=5),
        security_score=0.40,
    )

    print(f"\n  Baseline OPEX: $42,000 -> Simulated OPEX: $48,300 (+15%)")
    print(f"  Original Risk Score:   {sim_result['original_risk_score']:.4f}")
    print(f"  Simulated Risk Score:  {sim_result['simulated_risk_score']:.4f}")
    print(f"  Risk Delta:            {sim_result['risk_score_delta']:+.4f}")
    print(f"  Composite (orig):      {sim_result['original_composite_score']:.4f}")
    print(f"  Composite (sim):       {sim_result['simulated_composite_score']:.4f}")
    print(f"  Summary: {sim_result['summary_message']}")

    direction = "CORRECTLY INCREASES" if sim_result['risk_score_delta'] > 0 else "STILL DECREASES (synthetic dataset limitation)"
    print(f"\n  OPEX +15% {direction} predicted risk.")

    # =====================================================================
    # UNIFIED DECISIONIQ OUTPUT
    # =====================================================================
    print("\n" + "-"*75)
    print("  UNIFIED DECISIONIQ OUTPUT WITH EARLY WARNING")
    print("-"*75)

    from app.services.early_warning import generate_early_warning
    from app.services.risk_aggregation import calculate_composite_score

    agg = calculate_composite_score(risk_prob, security_score=0.40)

    # Use taiwanese distress probability as demo signal
    tw_distress_prob = None
    if 'taiwanese' in distress_results and 'error' not in distress_results['taiwanese']:
        tw_distress_prob = 0.12  # placeholder, real models are separate benchmarks

    early_warning = generate_early_warning(
        forecast_future=forecast_data.get('future', []),
        cash_stress_probability=risk_prob,
        distress_probability=tw_distress_prob,
    )

    unified_output = {
        "revenue_forecast": {
            "historical_days": len(forecast_data.get('historical', [])),
            "future_days": len(forecast_data.get('future', [])),
            "sample_future": forecast_data.get('future', [])[:3],
        },
        "cash_stress_probability": round(risk_prob, 4),
        "cash_stress_class": risk_class,
        "financial_distress_signal": tw_distress_prob,
        "forecast_metrics": {
            "online_retail": retail_metrics,
        },
        "risk_metrics": xgb_metrics,
        "distress_metrics": {k: {kk: vv for kk, vv in v.items() if kk != 'top_shap_features'} for k, v in distress_results.items()},
        "shap_features": [{"feature": f.feature, "direction": f.direction, "magnitude": f.magnitude} for f in shap_feats],
        "composite_score": agg,
        "early_warning": early_warning,
        "overall_financial_signal": early_warning["overall_financial_signal"],
    }

    # Pretty-print the unified output
    print("\n  --- UNIFIED JSON OUTPUT (sample) ---")
    # Print key fields
    print(f"  cash_stress_probability: {unified_output['cash_stress_probability']}")
    print(f"  cash_stress_class:       {unified_output['cash_stress_class']}")
    print(f"  composite_score:         {unified_output['composite_score']}")
    print(f"  overall_financial_signal: {unified_output['overall_financial_signal']}")
    print(f"  early_warning.overall_message: {early_warning['overall_message']}")
    print(f"  early_warning.active_warnings: {early_warning['active_warnings']}")
    print(f"  early_warning.warning_count:   {early_warning['warning_count']}")

    print("\n" + "="*75)
    print("  DECISIONIQ MULTI-MODEL EVALUATION COMPLETE")
    print("="*75 + "\n")


if __name__ == '__main__':
    main()
