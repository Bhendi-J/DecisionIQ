"""
Financial Early Warning Layer for DecisionIQ.

This is a RULE-BASED decision-support layer on top of ML model outputs.
It is NOT a new ML model. It aggregates signals from:
- Revenue forecast trend
- Cash-stress probability
- Financial distress model signal

And produces structured warnings for downstream consumers (GenAI, frontend).
"""

from typing import Dict, Any, List, Optional


def assess_revenue_trend(forecast_future: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Checks if the 90-day revenue forecast shows a declining trend.
    Compares the average of the first 30 days vs last 30 days of the forecast.
    """
    if not forecast_future or len(forecast_future) < 30:
        return {"warning": False, "signal": "insufficient_data", "detail": "Not enough forecast data points."}

    first_30 = [item.get('yhat', 0) for item in forecast_future[:30]]
    last_30 = [item.get('yhat', 0) for item in forecast_future[-30:]]

    avg_first = sum(first_30) / len(first_30) if first_30 else 0
    avg_last = sum(last_30) / len(last_30) if last_30 else 0

    if avg_first > 0:
        pct_change = ((avg_last - avg_first) / avg_first) * 100
    else:
        pct_change = 0.0

    if pct_change < -10.0:
        return {
            "warning": True,
            "signal": "revenue_declining",
            "severity": "high",
            "detail": f"Forecasted revenue declining by {abs(pct_change):.1f}% over 90-day horizon.",
            "pct_change": round(pct_change, 2),
        }
    elif pct_change < -5.0:
        return {
            "warning": True,
            "signal": "revenue_softening",
            "severity": "medium",
            "detail": f"Forecasted revenue softening by {abs(pct_change):.1f}% over 90-day horizon.",
            "pct_change": round(pct_change, 2),
        }
    else:
        return {
            "warning": False,
            "signal": "revenue_stable_or_growing",
            "severity": "low",
            "detail": f"Forecasted revenue trend: {pct_change:+.1f}% over 90-day horizon.",
            "pct_change": round(pct_change, 2),
        }


def assess_cash_stress(cash_stress_probability: float) -> Dict[str, Any]:
    """
    Evaluates cash-flow stress risk level.
    """
    if cash_stress_probability >= 0.7:
        return {
            "warning": True,
            "signal": "liquidity_critical",
            "severity": "high",
            "detail": f"Cash-flow stress probability is {cash_stress_probability*100:.1f}% - critical liquidity risk.",
        }
    elif cash_stress_probability >= 0.5:
        return {
            "warning": True,
            "signal": "liquidity_warning",
            "severity": "medium",
            "detail": f"Cash-flow stress probability is {cash_stress_probability*100:.1f}% - elevated liquidity risk.",
        }
    else:
        return {
            "warning": False,
            "signal": "liquidity_normal",
            "severity": "low",
            "detail": f"Cash-flow stress probability is {cash_stress_probability*100:.1f}% - within acceptable range.",
        }


def assess_distress_signal(distress_probability: Optional[float]) -> Dict[str, Any]:
    """
    Evaluates financial distress (bankruptcy/solvency) signal.
    """
    if distress_probability is None:
        return {"warning": False, "signal": "distress_not_evaluated", "severity": "low", "detail": "Financial distress model not evaluated."}

    if distress_probability >= 0.6:
        return {
            "warning": True,
            "signal": "distress_elevated",
            "severity": "high",
            "detail": f"Financial distress probability is {distress_probability*100:.1f}% - structural solvency risk detected.",
        }
    elif distress_probability >= 0.3:
        return {
            "warning": True,
            "signal": "distress_watch",
            "severity": "medium",
            "detail": f"Financial distress probability is {distress_probability*100:.1f}% - monitoring recommended.",
        }
    else:
        return {
            "warning": False,
            "signal": "distress_low",
            "severity": "low",
            "detail": f"Financial distress probability is {distress_probability*100:.1f}% - low structural risk.",
        }


def generate_early_warning(
    forecast_future: List[Dict[str, Any]],
    cash_stress_probability: float,
    distress_probability: Optional[float] = None,
) -> Dict[str, Any]:
    """
    Aggregates all signals into a unified early-warning output.
    """
    revenue_assessment = assess_revenue_trend(forecast_future)
    cash_assessment = assess_cash_stress(cash_stress_probability)
    distress_assessment = assess_distress_signal(distress_probability)

    warnings = []
    if revenue_assessment["warning"]:
        warnings.append(revenue_assessment["signal"])
    if cash_assessment["warning"]:
        warnings.append(cash_assessment["signal"])
    if distress_assessment["warning"]:
        warnings.append(distress_assessment["signal"])

    warning_count = len(warnings)

    if warning_count >= 3:
        overall = "critical"
        overall_message = "CRITICAL: Multiple financial risk indicators detected - revenue, liquidity, and solvency risks present simultaneously."
    elif warning_count == 2:
        overall = "elevated"
        overall_message = f"ELEVATED: Two financial risk indicators detected - {', '.join(warnings)}."
    elif warning_count == 1:
        overall = "watch"
        overall_message = f"WATCH: Financial risk indicator detected - {warnings[0]}."
    else:
        overall = "normal"
        overall_message = "Financial health indicators within acceptable ranges."

    return {
        "overall_financial_signal": overall,
        "overall_message": overall_message,
        "warning_count": warning_count,
        "active_warnings": warnings,
        "revenue_assessment": revenue_assessment,
        "cash_stress_assessment": cash_assessment,
        "distress_assessment": distress_assessment,
    }
