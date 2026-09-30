"""
What-If Financial Simulation Engine for DecisionIQ.

CRITICAL ARCHITECTURAL CONSTRAINTS:
--------------------------------------------------------------------------------
1. Pure Temporary Recomputation: NO database mutations or persistent state changes.
2. Independent Pipeline: Executes feature recalculation, model inference, and SHAP
   explanation strictly in-memory.
3. Security Integration: Uses existing/cached security score without re-running security models.
"""

from typing import Dict, Any, Tuple
from app.schemas.finance_schema import WhatIfRequest, RiskPredictRequest
from app.services.feature_engineering import engineer_single_input
from app.services.risk_aggregation import calculate_composite_score

def apply_what_if_scenario(
    base_input: RiskPredictRequest,
    expenses_change_pct: float = 0.0,
    revenue_change_pct: float = 0.0,
    receivable_days_change: float = 0.0,
    loan_balance_change_pct: float = 0.0
) -> Dict[str, Any]:
    """
    Applies scenario deltas to baseline input without mutating original object.
    Returns modified parameter dictionary.
    """
    sim_data = base_input.model_dump()
    
    # 1. Adjust Operating Expenses
    if expenses_change_pct != 0.0:
        sim_data['opex_usd'] = max(0.0, sim_data['opex_usd'] * (1.0 + (expenses_change_pct / 100.0)))
        
    # 2. Adjust Revenue
    if revenue_change_pct != 0.0:
        sim_data['revenue_usd'] = max(0.0, sim_data['revenue_usd'] * (1.0 + (revenue_change_pct / 100.0)))
        
    # 3. Adjust Accounts Receivable Days
    if receivable_days_change != 0.0:
        sim_data['accounts_receivable_days'] = max(0.0, sim_data['accounts_receivable_days'] + receivable_days_change)
        
    # 4. Adjust Loan Balance
    if loan_balance_change_pct != 0.0:
        sim_data['loan_balance_usd'] = max(0.0, sim_data['loan_balance_usd'] * (1.0 + (loan_balance_change_pct / 100.0)))
        
    return sim_data

def run_simulation(
    request: WhatIfRequest,
    model_predictor,
    shap_explainer,
    security_score: float = 0.40
) -> Dict[str, Any]:
    """
    Executes end-to-end What-If simulation flow:
    Baseline Predict -> Scenario Apply -> Scenario Feature Eng -> Scenario Predict -> SHAP -> Aggregation
    """
    # Use default baseline if none provided
    base = request.base_input or RiskPredictRequest()
    
    # 1. Evaluate Baseline
    base_features = engineer_single_input(base.model_dump())
    orig_prob, orig_class = model_predictor(base_features)
    orig_shap = shap_explainer(base_features)
    orig_agg = calculate_composite_score(orig_prob, security_score)
    
    # 2. Construct Scenario Parameters
    sim_params = apply_what_if_scenario(
        base_input=base,
        expenses_change_pct=request.expenses_change_pct or 0.0,
        revenue_change_pct=request.revenue_change_pct or 0.0,
        receivable_days_change=request.receivable_days_change or 0.0,
        loan_balance_change_pct=request.loan_balance_change_pct or 0.0
    )
    
    # 3. Feature Engineering on Scenario Parameters
    sim_features = engineer_single_input(sim_params)
    
    # 4. Run Model & SHAP on Scenario
    sim_prob, sim_class = model_predictor(sim_features)
    sim_shap = shap_explainer(sim_features)
    sim_agg = calculate_composite_score(sim_prob, security_score)
    
    delta = sim_prob - orig_prob
    if delta > 0.05:
        summary_msg = f"Scenario INCREASES cash-flow stress risk by {abs(delta)*100:.1f}% percentage points."
    elif delta < -0.05:
        summary_msg = f"Scenario REDUCES cash-flow stress risk by {abs(delta)*100:.1f}% percentage points."
    else:
        summary_msg = "Scenario has minimal impact on predicted financial risk."
        
    return {
        "original_risk_score": round(orig_prob, 4),
        "simulated_risk_score": round(sim_prob, 4),
        "risk_score_delta": round(delta, 4),
        "original_composite_score": orig_agg["composite_score"],
        "simulated_composite_score": sim_agg["composite_score"],
        "original_shap": orig_shap,
        "simulated_shap": sim_shap,
        "summary_message": summary_msg
    }
