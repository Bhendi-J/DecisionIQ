"""Risk indicators in [0, 1], with a fixed 70/30 finance/security policy."""

import math


def calculate_composite_score(
    finance_score: float,
    security_score: float | None = None,
    w_finance: float = 0.7,
    w_security: float = 0.3,
) -> dict:
    values = [finance_score] + ([] if security_score is None else [security_score])
    if any(not math.isfinite(value) or not 0 <= value <= 1 for value in values):
        raise ValueError("Risk scores must be finite values between 0 and 1")
    if any(not math.isfinite(w) or w < 0 for w in [w_finance, w_security]):
        raise ValueError("Weights must be finite and nonnegative")
    if w_finance + w_security <= 0:
        raise ValueError("At least one risk weight must be positive")
    if security_score is None:
        finance_weight, security_weight = 1.0, 0.0
    else:
        total = w_finance + w_security
        finance_weight, security_weight = w_finance / total, w_security / total
    composite = finance_weight * finance_score + security_weight * (security_score or 0)
    return {
        "finance_score": round(finance_score, 6),
        "security_score": security_score,
        "composite_score": round(composite, 6),
        "finance_weight": finance_weight,
        "security_weight": security_weight,
    }
