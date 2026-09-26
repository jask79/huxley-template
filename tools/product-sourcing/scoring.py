"""
Supplier quality scoring engine for Sourcerer.

Implements a 7-factor weighted scoring model with platform-aware weight
redistribution, confidence penalties, and 12 red flag detection rules.

The scoring algorithm is designed by the Algo Wizard and should not be
modified without consulting the algorithm design document.

Score Interpretation Guide:
    90-100  Excellent   Top-tier supplier. Proceed with confidence.
    75-89   Good        Reliable supplier. Standard due diligence.
    60-74   Fair        Acceptable with caveats. Request references.
    40-59   Marginal    Proceed cautiously. Extra verification needed.
    20-39   Poor        High risk. Consider alternatives first.
     0-19   Critical    Do not engage without extraordinary justification.

Dependencies: math (log10, sqrt, exp) — stdlib only.
"""

import math
from typing import Any, Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Factor Weights (must sum to 1.0)
# ---------------------------------------------------------------------------
WEIGHTS = {
    "delivery_reliability": 0.20,
    "transaction_volume": 0.18,
    "trust_signals": 0.18,
    "responsiveness": 0.15,
    "longevity": 0.12,
    "verification_depth": 0.10,
    "company_size": 0.07,
}

# ---------------------------------------------------------------------------
# Normalization Thresholds (named constants)
# ---------------------------------------------------------------------------

# Delivery reliability — piecewise linear
DELIVERY_EXCELLENT = 0.98   # 100 points
DELIVERY_GOOD = 0.95        # 80 points
DELIVERY_FAIR = 0.90        # 50 points
DELIVERY_POOR = 0.80        # 20 points

# Transaction volume — log10 scale
TXN_MIN = 0                 # 0 points
TXN_LOW = 10                # ~25 points
TXN_MEDIUM = 100            # ~50 points
TXN_HIGH = 1000             # ~75 points
TXN_EXCELLENT = 10000       # 100 points

# Trust signals (composite of gold_years, trade_assurance, verified)
GOLD_YEARS_MAX = 10         # Cap at 10yr for normalization
TRADE_ASSURANCE_WEIGHT = 0.35
GOLD_YEARS_WEIGHT = 0.40
VERIFIED_WEIGHT = 0.25

# Responsiveness — linear with saturation
RESPONSE_EXCELLENT = 0.98   # 100 points
RESPONSE_GOOD = 0.90        # 75 points
RESPONSE_LOW = 0.50         # 20 points

# Longevity — sqrt scale
LONGEVITY_MAX_YEARS = 25    # Cap at 25yr for normalization

# Verification depth — lookup table
VERIFICATION_FACTORY = 100
VERIFICATION_MANUFACTURER = 90
VERIFICATION_TRADING = 50
VERIFICATION_UNKNOWN = 20

# Company size — lookup table
SIZE_LARGE = 100            # 500+
SIZE_MEDIUM = 75            # 100-499
SIZE_SMALL = 50             # 10-99
SIZE_MICRO = 25             # 1-9
SIZE_UNKNOWN = 30           # No data

# ---------------------------------------------------------------------------
# Red Flag Rules (RF01-RF12)
# ---------------------------------------------------------------------------
RED_FLAG_RULES = {
    "RF01": {
        "name": "no_trade_assurance",
        "desc": "No Trade Assurance coverage",
        "severity": "WARNING",
        "penalty": 5.0,
    },
    "RF02": {
        "name": "zero_transactions",
        "desc": "Zero recorded transactions",
        "severity": "CRITICAL",
        "penalty": 15.0,
    },
    "RF03": {
        "name": "new_supplier",
        "desc": "Supplier established less than 2 years ago",
        "severity": "WARNING",
        "penalty": 5.0,
    },
    "RF04": {
        "name": "low_response_rate",
        "desc": "Response rate below 50%",
        "severity": "WARNING",
        "penalty": 8.0,
    },
    "RF05": {
        "name": "no_verification",
        "desc": "Supplier is not verified on the platform",
        "severity": "WARNING",
        "penalty": 5.0,
    },
    "RF06": {
        "name": "poor_delivery",
        "desc": "On-time delivery rate below 80%",
        "severity": "CRITICAL",
        "penalty": 12.0,
    },
    "RF07": {
        "name": "trading_company",
        "desc": "Trading company (not direct factory/manufacturer)",
        "severity": "WARNING",
        "penalty": 3.0,
    },
    "RF08": {
        "name": "unknown_type",
        "desc": "Supplier type is unknown or unverified",
        "severity": "WARNING",
        "penalty": 4.0,
    },
    "RF09": {
        "name": "no_gold_status",
        "desc": "No Gold Supplier status (0 years)",
        "severity": "WARNING",
        "penalty": 3.0,
    },
    "RF10": {
        "name": "very_low_transactions",
        "desc": "Fewer than 10 transactions recorded",
        "severity": "WARNING",
        "penalty": 5.0,
    },
    "RF11": {
        "name": "no_employee_data",
        "desc": "No employee count data available",
        "severity": "WARNING",
        "penalty": 2.0,
    },
    "RF12": {
        "name": "suspiciously_perfect",
        "desc": "All metrics are suspiciously perfect (possible data fabrication)",
        "severity": "CRITICAL",
        "penalty": 10.0,
    },
}

# Confidence levels
CONFIDENCE_LOW_THRESHOLD = 3    # <3 factors available
CONFIDENCE_MEDIUM_THRESHOLD = 5  # <5 factors available
CONFIDENCE_LOW_PENALTY = 0.80
CONFIDENCE_MEDIUM_PENALTY = 0.95
CONFIDENCE_HIGH_PENALTY = 1.00


# ---------------------------------------------------------------------------
# Normalization Functions (pure, no side effects)
# ---------------------------------------------------------------------------

def _normalize_delivery(on_time_delivery: Optional[float]) -> Optional[float]:
    """
    Normalize on-time delivery rate to 0-100 score.

    Uses piecewise linear interpolation:
        >= 98% -> 100
        95-98% -> 80-100
        90-95% -> 50-80
        80-90% -> 20-50
        <  80% -> 0-20
    """
    if on_time_delivery is None:
        return None

    rate = max(0.0, min(1.0, on_time_delivery))

    if rate >= DELIVERY_EXCELLENT:
        return 100.0
    elif rate >= DELIVERY_GOOD:
        return 80.0 + (rate - DELIVERY_GOOD) / (DELIVERY_EXCELLENT - DELIVERY_GOOD) * 20.0
    elif rate >= DELIVERY_FAIR:
        return 50.0 + (rate - DELIVERY_FAIR) / (DELIVERY_GOOD - DELIVERY_FAIR) * 30.0
    elif rate >= DELIVERY_POOR:
        return 20.0 + (rate - DELIVERY_POOR) / (DELIVERY_FAIR - DELIVERY_POOR) * 30.0
    else:
        return rate / DELIVERY_POOR * 20.0


def _normalize_transactions(count: int) -> float:
    """
    Normalize transaction count to 0-100 score using log10 scale.

    log10(1) = 0  -> ~0
    log10(10) = 1 -> ~25
    log10(100) = 2 -> ~50
    log10(1000) = 3 -> ~75
    log10(10000) = 4 -> 100
    """
    if count <= 0:
        return 0.0

    log_val = math.log10(max(1, count))
    log_max = math.log10(TXN_EXCELLENT)

    return min(100.0, (log_val / log_max) * 100.0)


def _normalize_trust(
    gold_years: int,
    trade_assurance: int,
    verified: int,
) -> float:
    """
    Normalize trust signals to 0-100 score (composite).

    Weighted combination of:
        - Gold Supplier years (40%): capped at 10yr, linear
        - Trade Assurance (35%): binary 0 or 100
        - Verified status (25%): binary 0 or 100
    """
    gold_score = min(gold_years / GOLD_YEARS_MAX, 1.0) * 100.0
    ta_score = 100.0 if trade_assurance else 0.0
    ver_score = 100.0 if verified else 0.0

    return (
        gold_score * GOLD_YEARS_WEIGHT
        + ta_score * TRADE_ASSURANCE_WEIGHT
        + ver_score * VERIFIED_WEIGHT
    )


def _normalize_responsiveness(response_rate: Optional[float]) -> Optional[float]:
    """
    Normalize response rate to 0-100 score using linear interpolation.

        >= 98% -> 100
        90-98% -> 75-100
        50-90% -> 20-75
        <  50% -> 0-20
    """
    if response_rate is None:
        return None

    rate = max(0.0, min(1.0, response_rate))

    if rate >= RESPONSE_EXCELLENT:
        return 100.0
    elif rate >= RESPONSE_GOOD:
        return 75.0 + (rate - RESPONSE_GOOD) / (RESPONSE_EXCELLENT - RESPONSE_GOOD) * 25.0
    elif rate >= RESPONSE_LOW:
        return 20.0 + (rate - RESPONSE_LOW) / (RESPONSE_GOOD - RESPONSE_LOW) * 55.0
    else:
        return rate / RESPONSE_LOW * 20.0


def _normalize_longevity(year_established: Optional[int]) -> Optional[float]:
    """
    Normalize years in business to 0-100 score using sqrt scale.

    sqrt(years / max_years) * 100, capped at 100.
    Rewards early years more than late years (diminishing returns).
    """
    if year_established is None:
        return None

    import datetime
    current_year = datetime.datetime.now().year
    years = max(0, current_year - year_established)

    if years <= 0:
        return 0.0

    return min(100.0, math.sqrt(years / LONGEVITY_MAX_YEARS) * 100.0)


def _normalize_verification(supplier_type: str) -> float:
    """
    Normalize supplier type to 0-100 score via lookup table.

    Factory/Manufacturer > Trading Company > Unknown
    """
    type_lower = supplier_type.lower().strip() if supplier_type else "unknown"

    if type_lower in ("factory", "factory / manufacturer"):
        return float(VERIFICATION_FACTORY)
    elif type_lower in ("manufacturer", "mfg"):
        return float(VERIFICATION_MANUFACTURER)
    elif type_lower in ("trading", "trading company", "trader"):
        return float(VERIFICATION_TRADING)
    else:
        return float(VERIFICATION_UNKNOWN)


def _normalize_company_size(employee_count: Optional[str]) -> Optional[float]:
    """
    Normalize employee count string to 0-100 score via lookup table.

    Parses ranges like "100-200", "500+", "50-99" and maps to size tiers.
    """
    if not employee_count:
        return None

    text = employee_count.strip().lower()
    if not text or text == "unknown":
        return None

    # Try to extract the maximum number from the range
    import re
    numbers = re.findall(r"\d+", text)
    if not numbers:
        return None

    max_employees = max(int(n) for n in numbers)

    if max_employees >= 500:
        return float(SIZE_LARGE)
    elif max_employees >= 100:
        return float(SIZE_MEDIUM)
    elif max_employees >= 10:
        return float(SIZE_SMALL)
    else:
        return float(SIZE_MICRO)


# ---------------------------------------------------------------------------
# Red Flag Detection
# ---------------------------------------------------------------------------

def _detect_red_flags(supplier: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Detect red flags for a supplier.

    Returns a list of red flag dicts with keys: code, name, desc, severity, penalty.
    Does not mutate the input supplier dict.
    """
    flags: List[Dict[str, Any]] = []

    trade_assurance = supplier.get("trade_assurance", 0)
    transaction_count = supplier.get("transaction_count", 0)
    year_established = supplier.get("year_established")
    response_rate = supplier.get("response_rate")
    verified = supplier.get("verified", 0)
    on_time_delivery = supplier.get("on_time_delivery")
    supplier_type = supplier.get("supplier_type", "unknown")
    gold_years = supplier.get("gold_years", 0)
    employee_count = supplier.get("employee_count")

    # RF01: No Trade Assurance
    if not trade_assurance:
        flags.append({"code": "RF01", **RED_FLAG_RULES["RF01"]})

    # RF02: Zero transactions
    if transaction_count == 0:
        flags.append({"code": "RF02", **RED_FLAG_RULES["RF02"]})

    # RF03: New supplier (< 2 years)
    if year_established is not None:
        import datetime
        current_year = datetime.datetime.now().year
        if current_year - year_established < 2:
            flags.append({"code": "RF03", **RED_FLAG_RULES["RF03"]})

    # RF04: Low response rate
    if response_rate is not None and response_rate < 0.50:
        flags.append({"code": "RF04", **RED_FLAG_RULES["RF04"]})

    # RF05: Not verified
    if not verified:
        flags.append({"code": "RF05", **RED_FLAG_RULES["RF05"]})

    # RF06: Poor delivery
    if on_time_delivery is not None and on_time_delivery < 0.80:
        flags.append({"code": "RF06", **RED_FLAG_RULES["RF06"]})

    # RF07: Trading company
    type_lower = (supplier_type or "").lower().strip()
    if type_lower in ("trading", "trading company", "trader"):
        flags.append({"code": "RF07", **RED_FLAG_RULES["RF07"]})

    # RF08: Unknown type
    if type_lower in ("unknown", "") or not type_lower:
        flags.append({"code": "RF08", **RED_FLAG_RULES["RF08"]})

    # RF09: No Gold status
    if gold_years == 0:
        flags.append({"code": "RF09", **RED_FLAG_RULES["RF09"]})

    # RF10: Very low transactions
    if 0 < transaction_count < 10:
        flags.append({"code": "RF10", **RED_FLAG_RULES["RF10"]})

    # RF11: No employee data
    if not employee_count or employee_count.strip().lower() in ("", "unknown"):
        flags.append({"code": "RF11", **RED_FLAG_RULES["RF11"]})

    # RF12: Suspiciously perfect (all metrics at maximum)
    perfect_count = 0
    if on_time_delivery is not None and on_time_delivery >= 1.0:
        perfect_count += 1
    if response_rate is not None and response_rate >= 1.0:
        perfect_count += 1
    if transaction_count >= 50000:
        perfect_count += 1
    if gold_years >= 10:
        perfect_count += 1
    if perfect_count >= 3:
        flags.append({"code": "RF12", **RED_FLAG_RULES["RF12"]})

    return flags


# ---------------------------------------------------------------------------
# Weight Redistribution for Missing Data
# ---------------------------------------------------------------------------

def _redistribute_weights(
    available_factors: Dict[str, float],
) -> Dict[str, float]:
    """
    Redistribute weights when some factors have missing data.

    Weights of missing factors are distributed proportionally among
    available factors. Returns a new dict with redistributed weights.
    """
    total_available = sum(
        WEIGHTS[k] for k in available_factors if k in WEIGHTS
    )

    if total_available <= 0:
        # All factors missing — return equal weights for whatever we have
        n = len(available_factors) or 1
        return {k: 1.0 / n for k in available_factors}

    # Scale available weights so they sum to 1.0
    return {
        k: WEIGHTS[k] / total_available
        for k in available_factors
        if k in WEIGHTS
    }


# ---------------------------------------------------------------------------
# Confidence Calculation
# ---------------------------------------------------------------------------

def _calculate_confidence(factor_count: int) -> Tuple[str, float]:
    """
    Calculate confidence level and penalty based on available factor count.

    Returns (level_label, penalty_multiplier).
    """
    if factor_count < CONFIDENCE_LOW_THRESHOLD:
        return "LOW", CONFIDENCE_LOW_PENALTY
    elif factor_count < CONFIDENCE_MEDIUM_THRESHOLD:
        return "MEDIUM", CONFIDENCE_MEDIUM_PENALTY
    else:
        return "HIGH", CONFIDENCE_HIGH_PENALTY


# ---------------------------------------------------------------------------
# Main Scoring Function
# ---------------------------------------------------------------------------

def score_supplier(
    supplier: Dict[str, Any],
) -> Tuple[float, Dict[str, Any], List[Dict[str, Any]]]:
    """
    Score a supplier based on 7 weighted factors with red flag detection.

    This is a pure function — it does not mutate the input dict, does not
    access the database, and has no side effects.

    Args:
        supplier: Dict with supplier fields matching the schema. Expected keys:
            on_time_delivery (float or None), transaction_count (int),
            gold_years (int), trade_assurance (int), verified (int),
            response_rate (float or None), year_established (int or None),
            supplier_type (str), employee_count (str or None)

    Returns:
        Tuple of (score, breakdown, red_flags) where:
            score: float 0-100 (after confidence penalty and red flag deductions)
            breakdown: dict with per-factor scores, weights, confidence info
            red_flags: list of detected red flag dicts
    """
    # 1. Compute individual factor scores
    factor_scores: Dict[str, Optional[float]] = {}

    factor_scores["delivery_reliability"] = _normalize_delivery(
        supplier.get("on_time_delivery")
    )
    factor_scores["transaction_volume"] = _normalize_transactions(
        supplier.get("transaction_count", 0)
    )
    factor_scores["trust_signals"] = _normalize_trust(
        supplier.get("gold_years", 0),
        supplier.get("trade_assurance", 0),
        supplier.get("verified", 0),
    )
    factor_scores["responsiveness"] = _normalize_responsiveness(
        supplier.get("response_rate")
    )
    factor_scores["longevity"] = _normalize_longevity(
        supplier.get("year_established")
    )
    factor_scores["verification_depth"] = _normalize_verification(
        supplier.get("supplier_type", "unknown")
    )
    factor_scores["company_size"] = _normalize_company_size(
        supplier.get("employee_count")
    )

    # 2. Identify available factors (non-None scores)
    available: Dict[str, float] = {
        k: v for k, v in factor_scores.items() if v is not None
    }

    # 3. Redistribute weights for missing data
    if available:
        adjusted_weights = _redistribute_weights(available)
    else:
        # No data at all — return minimum score
        return 0.0, {
            "factors": {},
            "available_count": 0,
            "confidence_level": "LOW",
            "confidence_penalty": CONFIDENCE_LOW_PENALTY,
            "raw_score": 0.0,
            "penalty_total": 0.0,
            "final_score": 0.0,
        }, _detect_red_flags(supplier)

    # 4. Compute weighted raw score
    raw_score = sum(
        available[k] * adjusted_weights[k]
        for k in available
    )

    # 5. Apply confidence penalty
    confidence_level, confidence_penalty = _calculate_confidence(len(available))
    penalized_score = raw_score * confidence_penalty

    # 6. Detect red flags and apply deductions
    red_flags = _detect_red_flags(supplier)
    total_penalty = sum(f["penalty"] for f in red_flags)
    final_score = max(0.0, min(100.0, penalized_score - total_penalty))

    # 7. Build breakdown
    factor_details = {}
    for k in WEIGHTS:
        raw_val = factor_scores[k]
        factor_details[k] = {
            "raw_score": round(raw_val, 2) if raw_val is not None else None,
            "weight": round(WEIGHTS[k], 3),
            "adjusted_weight": round(adjusted_weights.get(k, 0.0), 3),
            "available": raw_val is not None,
        }

    breakdown = {
        "factors": factor_details,
        "available_count": len(available),
        "total_factors": len(WEIGHTS),
        "confidence_level": confidence_level,
        "confidence_penalty": confidence_penalty,
        "raw_score": round(raw_score, 2),
        "after_confidence": round(penalized_score, 2),
        "red_flag_penalty": round(total_penalty, 2),
        "final_score": round(final_score, 2),
    }

    return round(final_score, 1), breakdown, red_flags


def interpret_score(score: float) -> str:
    """
    Return a human-readable interpretation label for a score.

    Returns one of: 'Excellent', 'Good', 'Fair', 'Marginal', 'Poor', 'Critical'.
    """
    if score >= 90:
        return "Excellent"
    elif score >= 75:
        return "Good"
    elif score >= 60:
        return "Fair"
    elif score >= 40:
        return "Marginal"
    elif score >= 20:
        return "Poor"
    else:
        return "Critical"
