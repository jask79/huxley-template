"""
Market intelligence and benchmarking for Sourcerer.

Provides margin analysis, quote comparison, multi-criteria decision matrices,
and break-even calculations for product sourcing decisions.

All functions are pure (no side effects, no database access, no network calls).

Dependencies: None (stdlib only).
"""

from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# Category Margin Benchmarks
# ---------------------------------------------------------------------------
# Typical retail margin ranges by product category.
# "low" = highly competitive / commoditized. "high" = strong brand premium.

CATEGORY_MARGINS: Dict[str, Dict[str, Any]] = {
    "phone_accessories": {
        "low": 0.40, "typical": 0.60, "high": 0.80,
        "notes": "Highly competitive. Volume-dependent. Private label margins higher.",
    },
    "apparel": {
        "low": 0.50, "typical": 0.65, "high": 0.80,
        "notes": "Brand-dependent. Private label higher. Fast fashion lower.",
    },
    "home_decor": {
        "low": 0.45, "typical": 0.60, "high": 0.75,
        "notes": "Design-driven. Unique products command premium.",
    },
    "electronics": {
        "low": 0.20, "typical": 0.35, "high": 0.50,
        "notes": "Thin margins. Volume critical. Warranty costs reduce net margin.",
    },
    "jewelry": {
        "low": 0.60, "typical": 0.80, "high": 0.90,
        "notes": "High perceived value. Brand and design premium significant.",
    },
    "beauty": {
        "low": 0.50, "typical": 0.70, "high": 0.85,
        "notes": "Strong brand premium. Compliance costs (FDA/labeling) factor in.",
    },
    "toys": {
        "low": 0.35, "typical": 0.55, "high": 0.70,
        "notes": "Seasonal demand. Compliance costs (CPSIA) significant.",
    },
    "bags_luggage": {
        "low": 0.50, "typical": 0.65, "high": 0.80,
        "notes": "Design-driven. Material quality impacts perception and price.",
    },
    "kitchenware": {
        "low": 0.40, "typical": 0.55, "high": 0.70,
        "notes": "Competitive market. Unique designs or materials differentiate.",
    },
    "pet_products": {
        "low": 0.45, "typical": 0.60, "high": 0.75,
        "notes": "Growing market. Premium pet products have higher margins.",
    },
    "fitness": {
        "low": 0.40, "typical": 0.55, "high": 0.70,
        "notes": "Seasonal demand peaks. Brand loyalty matters for premium pricing.",
    },
    "stationery": {
        "low": 0.40, "typical": 0.55, "high": 0.75,
        "notes": "Design-driven. Low unit cost but high margin percentage.",
    },
    "automotive_accessories": {
        "low": 0.35, "typical": 0.50, "high": 0.65,
        "notes": "Compatibility critical. Returns can be high if fitment is off.",
    },
    "outdoor_garden": {
        "low": 0.40, "typical": 0.55, "high": 0.70,
        "notes": "Seasonal. Bulky items have higher shipping cost impact.",
    },
}


# ---------------------------------------------------------------------------
# Functions
# ---------------------------------------------------------------------------

def analyze_margin(
    landed_cost: float,
    sell_price: float,
    category: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Analyze margin for a product and compare against category benchmarks.

    Args:
        landed_cost: Per-unit landed cost (FOB + duty + freight + fees).
        sell_price: Retail selling price.
        category: Optional product category for benchmark comparison.

    Returns:
        Dict with margin details and category comparison.
    """
    if sell_price <= 0:
        return {"error": "Sell price must be greater than 0"}

    gross_profit = sell_price - landed_cost
    margin_pct = gross_profit / sell_price
    markup = gross_profit / landed_cost if landed_cost > 0 else 0

    result: Dict[str, Any] = {
        "landed_cost": round(landed_cost, 2),
        "sell_price": round(sell_price, 2),
        "gross_profit": round(gross_profit, 2),
        "margin_pct": round(margin_pct, 4),
        "markup_pct": round(markup, 4),
        "assessment": "",
    }

    if margin_pct >= 0.70:
        result["assessment"] = "Excellent margin — strong pricing power"
    elif margin_pct >= 0.50:
        result["assessment"] = "Good margin — sustainable business"
    elif margin_pct >= 0.30:
        result["assessment"] = "Moderate margin — watch for cost increases"
    elif margin_pct >= 0.15:
        result["assessment"] = "Thin margin — vulnerable to cost fluctuations"
    else:
        result["assessment"] = "Very thin or negative margin — reconsider pricing or costs"

    if category:
        cat = CATEGORY_MARGINS.get(category.lower())
        if cat:
            result["category_benchmark"] = {
                "category": category,
                "low": cat["low"],
                "typical": cat["typical"],
                "high": cat["high"],
                "notes": cat.get("notes", ""),
            }
            if margin_pct >= cat["high"]:
                result["vs_category"] = "above_high"
                result["category_note"] = "Margin is above category high — excellent positioning"
            elif margin_pct >= cat["typical"]:
                result["vs_category"] = "above_typical"
                result["category_note"] = "Margin is above typical for this category"
            elif margin_pct >= cat["low"]:
                result["vs_category"] = "within_range"
                result["category_note"] = "Margin is within normal range for this category"
            else:
                result["vs_category"] = "below_low"
                result["category_note"] = "Margin is below category low — may need repricing"

    return result


def compare_quotes(
    quotes: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Side-by-side comparison of supplier quotes.

    Each quote dict should have:
        - supplier_id or supplier_name
        - unit_price
        - moq (optional)
        - lead_time_days (optional)
        - quality_score (optional)
        - payment_terms (optional)
        - incoterm (optional)

    Args:
        quotes: List of quote dicts.

    Returns:
        Dict with comparison table, rankings, and recommendation.
    """
    if not quotes:
        return {"error": "No quotes provided"}

    if len(quotes) == 1:
        return {
            "comparison": quotes,
            "note": "Only one quote — get at least 3 for meaningful comparison",
        }

    # Score each quote
    scored = []
    for q in quotes:
        score = 50.0  # base

        # Price scoring (lower is better) — compare against average
        prices = [r["unit_price"] for r in quotes if "unit_price" in r]
        avg_price = sum(prices) / len(prices) if prices else 0
        if avg_price > 0 and "unit_price" in q:
            price_ratio = q["unit_price"] / avg_price
            if price_ratio <= 0.8:
                score += 20  # significantly below average
            elif price_ratio <= 0.95:
                score += 10
            elif price_ratio >= 1.2:
                score -= 15  # significantly above average
            elif price_ratio >= 1.05:
                score -= 5

        # Quality score
        quality = q.get("quality_score", 0)
        if quality >= 80:
            score += 15
        elif quality >= 60:
            score += 5
        elif quality > 0 and quality < 40:
            score -= 10

        # Lead time (shorter is better)
        lead_times = [r.get("lead_time_days") for r in quotes if r.get("lead_time_days")]
        avg_lt = sum(lead_times) / len(lead_times) if lead_times else 0
        lt = q.get("lead_time_days")
        if lt and avg_lt > 0:
            if lt < avg_lt * 0.8:
                score += 10
            elif lt > avg_lt * 1.2:
                score -= 5

        # MOQ (lower is better for flexibility)
        moq = q.get("moq")
        if moq is not None and moq <= 100:
            score += 5
        elif moq is not None and moq >= 5000:
            score -= 5

        scored.append({
            **q,
            "_comparison_score": round(score, 1),
        })

    # Sort by comparison score
    scored.sort(key=lambda x: x["_comparison_score"], reverse=True)

    # Find best in each dimension
    best_price = min(quotes, key=lambda x: x.get("unit_price", float("inf")))
    best_quality = max(quotes, key=lambda x: x.get("quality_score", 0))
    best_lead = min(quotes, key=lambda x: x.get("lead_time_days", float("inf")))

    return {
        "ranked_quotes": scored,
        "total_quotes": len(quotes),
        "best_price": {
            "supplier": best_price.get("supplier_name", best_price.get("supplier_id", "?")),
            "price": best_price.get("unit_price"),
        },
        "best_quality": {
            "supplier": best_quality.get("supplier_name", best_quality.get("supplier_id", "?")),
            "score": best_quality.get("quality_score"),
        },
        "best_lead_time": {
            "supplier": best_lead.get("supplier_name", best_lead.get("supplier_id", "?")),
            "days": best_lead.get("lead_time_days"),
        },
        "recommendation": scored[0].get("supplier_name", scored[0].get("supplier_id", "?")),
    }


def generate_decision_matrix(
    options: List[Dict[str, Any]],
    weights: Optional[Dict[str, float]] = None,
    lower_is_better: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Generate a multi-criteria decision matrix for supplier/product selection.

    Each option dict should contain numeric values for the criteria being compared.
    Non-numeric or missing values are treated as neutral (score 50).

    By default, higher values score better. Use *lower_is_better* for criteria
    like price or lead_time where lower values are preferable.

    Args:
        options: List of option dicts, each with a 'name' key and criteria values.
        weights: Optional dict mapping criteria names to weights (0-1).
                 Defaults to equal weighting.
        lower_is_better: Optional list of criteria names where lower values
                         score higher (e.g. ['price', 'lead_time_days']).

    Returns:
        Dict with scored options, criteria analysis, and winner.
    """
    if not options:
        return {"error": "No options provided"}

    invert = set(lower_is_better or [])

    # Collect all criteria (keys except 'name')
    criteria = set()
    for opt in options:
        criteria.update(k for k in opt.keys() if k != "name")

    criteria_list = sorted(criteria)

    # Default to equal weights
    if weights is None:
        w = 1.0 / len(criteria_list) if criteria_list else 1.0
        weights = {c: w for c in criteria_list}

    # Normalize weights to sum to 1.0
    total_w = sum(weights.get(c, 0) for c in criteria_list)
    if total_w > 0:
        norm_weights = {c: weights.get(c, 0) / total_w for c in criteria_list}
    else:
        norm_weights = {c: 1.0 / len(criteria_list) for c in criteria_list}

    # Score each option per criterion (0-100 relative to range)
    scored = []
    for opt in options:
        total_score = 0.0
        criterion_scores = {}

        for crit in criteria_list:
            val = opt.get(crit)
            if val is None or not isinstance(val, (int, float)):
                criterion_scores[crit] = 50.0  # neutral
                total_score += 50.0 * norm_weights.get(crit, 0)
                continue

            # Get range for this criterion
            all_vals = [o.get(crit) for o in options if isinstance(o.get(crit), (int, float))]
            if not all_vals:
                criterion_scores[crit] = 50.0
                total_score += 50.0 * norm_weights.get(crit, 0)
                continue

            min_val = min(all_vals)
            max_val = max(all_vals)

            if max_val == min_val:
                normalized = 50.0
            else:
                # Higher = better by default; invert for lower-is-better criteria
                normalized = ((val - min_val) / (max_val - min_val)) * 100.0
                if crit in invert:
                    normalized = 100.0 - normalized

            criterion_scores[crit] = round(normalized, 1)
            total_score += normalized * norm_weights.get(crit, 0)

        scored.append({
            "name": opt.get("name", "Option"),
            "total_score": round(total_score, 1),
            "criteria_scores": criterion_scores,
            "raw_values": {c: opt.get(c) for c in criteria_list},
        })

    scored.sort(key=lambda x: x["total_score"], reverse=True)

    return {
        "options": scored,
        "criteria": criteria_list,
        "weights": {c: round(norm_weights.get(c, 0), 3) for c in criteria_list},
        "winner": scored[0]["name"] if scored else None,
    }


def estimate_break_even(
    fixed_costs: float,
    per_unit_landed: float,
    sell_price: float,
) -> Dict[str, Any]:
    """
    Calculate break-even point for a product.

    Args:
        fixed_costs: Total fixed costs (mold, samples, certification, etc.).
        per_unit_landed: Per-unit landed cost.
        sell_price: Per-unit selling price.

    Returns:
        Dict with break-even units, revenue, and sensitivity analysis.
    """
    if sell_price <= per_unit_landed:
        return {
            "error": "Sell price must exceed per-unit landed cost to break even",
            "contribution_margin": round(sell_price - per_unit_landed, 2),
        }

    contribution_margin = sell_price - per_unit_landed
    break_even_units = fixed_costs / contribution_margin
    break_even_revenue = break_even_units * sell_price

    # Sensitivity: what if costs are 10/20% higher?
    sensitivity = []
    for cost_increase in [0, 0.10, 0.20, 0.30]:
        adj_cost = per_unit_landed * (1.0 + cost_increase)
        adj_margin = sell_price - adj_cost
        if adj_margin > 0:
            adj_be = fixed_costs / adj_margin
            sensitivity.append({
                "cost_increase_pct": round(cost_increase * 100),
                "adjusted_landed_cost": round(adj_cost, 2),
                "contribution_margin": round(adj_margin, 2),
                "break_even_units": int(adj_be) + 1,
            })
        else:
            sensitivity.append({
                "cost_increase_pct": round(cost_increase * 100),
                "adjusted_landed_cost": round(adj_cost, 2),
                "contribution_margin": round(adj_margin, 2),
                "break_even_units": None,
                "note": "Cannot break even at this cost level",
            })

    return {
        "fixed_costs": round(fixed_costs, 2),
        "per_unit_landed": round(per_unit_landed, 2),
        "sell_price": round(sell_price, 2),
        "contribution_margin": round(contribution_margin, 2),
        "break_even_units": int(break_even_units) + 1,  # Round up
        "break_even_revenue": round(break_even_revenue, 2),
        "sensitivity": sensitivity,
    }
