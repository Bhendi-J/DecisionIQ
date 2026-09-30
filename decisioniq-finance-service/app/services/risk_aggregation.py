"""
Risk Aggregation Engine for DecisionIQ.

DOCUMENTATION & MATHEMATICS:
--------------------------------------------------------------------------------
1. Score Range:
   - Finance Score: [0.0, 1.0] (0.0 = Low Risk, 1.0 = Critical Cash-flow Stress Risk)
   - Security Score: [0.0, 1.0] (0.0 = Secure/Normal, 1.0 = High Security Threat/Malicious)
   - Composite Score: [0.0, 1.0] (0.0 = Healthy, 1.0 = High Combined SME Vulnerability)

2. Weight Allocation Strategy:
   - Finance Weight (w_finance) = 0.70
   - Security Weight (w_security) = 0.30
   
   Reasoning: Primary SME solvency depends overwhelmingly on cash flow survival.
   Cyber/Security threats exacerbate risk (e.g. ransomware payload impacting operations),
   acting as a secondary multiplier/threat vector.

3. Formula:
   composite_score = (w_finance * finance_score) + (w_security * security_score)

4. Fault Tolerance:
   If the external Security Service is offline, unreachable, or times out,
   the aggregation engine falls back gracefully:
   - Defaults security_score to neutral 0.0 (or last known healthy baseline)
   - Rescales composite score purely on finance metrics without crashing the API.
"""

import os
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

DEFAULT_FINANCE_WEIGHT = float(os.getenv("FINANCE_SECURITY_WEIGHT", "0.7"))
DEFAULT_SECURITY_WEIGHT = float(os.getenv("SECURITY_FINANCE_WEIGHT", "0.3"))

def calculate_composite_score(
    finance_score: float,
    security_score: Optional[float] = None,
    w_finance: float = DEFAULT_FINANCE_WEIGHT,
    w_security: float = DEFAULT_SECURITY_WEIGHT
) -> Dict[str, float]:
    """
    Computes weighted composite business health risk score.
    Handles missing or unavailable security score cleanly.
    """
    # Clamp inputs between 0.0 and 1.0
    fin_score = max(0.0, min(1.0, float(finance_score)))
    
    if security_score is None:
        logger.warning("Security score unavailable. Defaulting security risk to 0.0 and using finance score baseline.")
        sec_score = 0.0
        # If security is completely missing, composite reflects 100% finance risk
        comp_score = fin_score
    else:
        sec_score = max(0.0, min(1.0, float(security_score)))
        # Normalize weights to ensure sum == 1.0
        total_w = w_finance + w_security
        norm_w_fin = w_finance / total_w if total_w > 0 else 0.7
        norm_w_sec = w_security / total_w if total_w > 0 else 0.3
        
        comp_score = (norm_w_fin * fin_score) + (norm_w_sec * sec_score)
        
    return {
        "finance_score": round(fin_score, 4),
        "security_score": round(sec_score, 4),
        "composite_score": round(comp_score, 4),
        "finance_weight": w_finance,
        "security_weight": w_security
    }
