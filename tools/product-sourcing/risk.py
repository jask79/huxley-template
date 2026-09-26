"""
Supply chain risk scoring for Sourcerer.

Provides multi-factor risk assessment for suppliers and supply chain
concentration analysis. Risk scores range from 0 (no risk) to 100
(critical risk).

Risk Score Interpretation:
    0-30    Low risk       Standard procurement procedures
    30-60   Moderate risk  Enhanced due diligence recommended
    60-80   High risk      Proceed with caution; consider alternatives
    80-100  Critical risk  Do not engage without extraordinary mitigation

All functions are pure (no side effects, no database access, no network calls).

Dependencies: None (stdlib only).
"""

from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# Risk Factor Weights (must sum to 1.0)
# ---------------------------------------------------------------------------

RISK_WEIGHTS: Dict[str, float] = {
    "concentration": 0.25,
    "geographic": 0.20,
    "quality": 0.20,
    "financial": 0.15,
    "lead_time": 0.10,
    "compliance": 0.10,
}

# ---------------------------------------------------------------------------
# Geographic Risk Profiles — Chinese manufacturing regions
# ---------------------------------------------------------------------------

GEOGRAPHIC_RISKS: Dict[str, Dict[str, Any]] = {
    "guangdong": {
        "risk": 0.30,
        "events": ["typhoons", "port congestion", "labor shortages post-CNY"],
        "strengths": ["largest manufacturing hub", "Shenzhen/Yantian port", "mature supply chains"],
        "major_cities": ["Shenzhen", "Guangzhou", "Dongguan", "Foshan", "Zhongshan"],
    },
    "zhejiang": {
        "risk": 0.25,
        "events": ["typhoons", "flooding"],
        "strengths": ["Yiwu small goods market", "Ningbo port", "e-commerce hub"],
        "major_cities": ["Hangzhou", "Ningbo", "Yiwu", "Wenzhou", "Taizhou"],
    },
    "fujian": {
        "risk": 0.35,
        "events": ["typhoons", "strait tensions"],
        "strengths": ["footwear hub", "stone/ceramics", "Xiamen port"],
        "major_cities": ["Xiamen", "Quanzhou", "Fuzhou", "Putian"],
    },
    "jiangsu": {
        "risk": 0.20,
        "events": ["flooding", "environmental regulation"],
        "strengths": ["Shanghai proximity", "advanced manufacturing", "electronics"],
        "major_cities": ["Suzhou", "Nanjing", "Wuxi", "Changzhou", "Kunshan"],
    },
    "shandong": {
        "risk": 0.25,
        "events": ["drought", "cold weather"],
        "strengths": ["heavy industry", "agriculture", "Qingdao port"],
        "major_cities": ["Qingdao", "Jinan", "Yantai", "Weihai"],
    },
    "hebei": {
        "risk": 0.30,
        "events": ["air quality shutdowns", "environmental regulation"],
        "strengths": ["steel/iron", "Beijing proximity"],
        "major_cities": ["Shijiazhuang", "Tangshan", "Baoding"],
    },
    "shanghai": {
        "risk": 0.20,
        "events": ["typhoons", "port congestion"],
        "strengths": ["largest port (by TEU)", "financial center", "advanced tech"],
        "major_cities": ["Shanghai"],
    },
    "henan": {
        "risk": 0.25,
        "events": ["flooding", "inland logistics delays"],
        "strengths": ["labor pool", "electronics assembly (Foxconn)"],
        "major_cities": ["Zhengzhou", "Luoyang"],
    },
    "sichuan": {
        "risk": 0.35,
        "events": ["earthquakes", "power shortages", "inland logistics"],
        "strengths": ["electronics", "low labor costs", "tech hub (Chengdu)"],
        "major_cities": ["Chengdu", "Mianyang"],
    },
    "hubei": {
        "risk": 0.30,
        "events": ["flooding", "pandemic risk (Wuhan)"],
        "strengths": ["automotive", "optics", "central logistics hub"],
        "major_cities": ["Wuhan", "Yichang"],
    },
    "liaoning": {
        "risk": 0.30,
        "events": ["cold weather", "energy shortages"],
        "strengths": ["heavy industry", "Dalian port"],
        "major_cities": ["Dalian", "Shenyang"],
    },
    "anhui": {
        "risk": 0.25,
        "events": ["flooding"],
        "strengths": ["growing manufacturing base", "low costs"],
        "major_cities": ["Hefei", "Wuhu"],
    },
}

# ---------------------------------------------------------------------------
# Sourcing Scam Patterns
# ---------------------------------------------------------------------------

SOURCING_SCAMS: List[Dict[str, Any]] = [
    {
        "name": "bait_and_switch",
        "description": "Sample quality differs from production run",
        "red_flags": [
            "refuses pre-shipment inspection",
            "sample from different factory",
            "price too good to be true",
            "rushes you to place large order after sample approval",
        ],
        "prevention": (
            "Always do pre-shipment inspection (PSI). Get samples from the actual "
            "production run, not showroom samples. Include quality specs in the PO."
        ),
    },
    {
        "name": "middleman_markup",
        "description": "Claims to be factory but is actually a trading company",
        "red_flags": [
            "broad product range (factories specialize)",
            "can't show production line on video",
            "generic factory photos / stock images",
            "reluctant to share business license",
            "address doesn't match on map/Baidu Maps",
        ],
        "prevention": (
            "Request factory audit or live video tour of production line. Check "
            "business license on National Enterprise Credit Information Publicity "
            "System. Use Baidu Maps street view to verify address."
        ),
    },
    {
        "name": "payment_scam",
        "description": "Changed bank details mid-transaction",
        "red_flags": [
            "sudden bank change email",
            "different account name than company",
            "email address subtly different from prior correspondence",
            "urgency pressure ('pay today or lose the slot')",
        ],
        "prevention": (
            "Always verify bank changes by phone/video call with your known contact. "
            "Use Trade Assurance for Alibaba orders. Never send >30% deposit to a "
            "new supplier's personal account."
        ),
    },
    {
        "name": "ip_theft",
        "description": "Shares your designs with competitors or sells directly",
        "red_flags": [
            "asks too many questions about your market/pricing",
            "requests full design files upfront before any agreement",
            "has similar products from other brands on display",
            "unwilling to sign NDA",
        ],
        "prevention": (
            "NDA before sharing designs (use Chinese-language NDA, enforceable in "
            "China courts). Stagger design disclosure — don't send everything at "
            "once. Register trademarks in China (first-to-file)."
        ),
    },
    {
        "name": "quantity_shortage",
        "description": "Ships fewer units than invoiced",
        "red_flags": [
            "no container loading inspection",
            "refuses piece count verification",
            "cartons are lighter than expected",
            "no packing list per carton",
        ],
        "prevention": (
            "Container Loading Inspection (CLI). Weigh cartons against standard "
            "weight. Require detailed packing list. Random carton count check."
        ),
    },
    {
        "name": "inspection_manipulation",
        "description": "Pre-stages good units for inspection",
        "red_flags": [
            "inspector only sees pre-selected cartons",
            "re-packed or freshly sealed boxes at inspection",
            "factory insists on specific inspection date far in advance",
            "production not complete but 'these are representative samples'",
        ],
        "prevention": (
            "Random carton selection by inspector (AQL sampling). Unannounced "
            "inspection date when possible. During-production inspection (DUPRO) "
            "in addition to pre-shipment inspection (PSI)."
        ),
    },
]


# ---------------------------------------------------------------------------
# Functions
# ---------------------------------------------------------------------------

def assess_supplier_risk(
    supplier: Dict[str, Any],
    order_history: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """
    Comprehensive risk assessment for a single supplier.

    Args:
        supplier: Supplier dict with fields from the database schema.
        order_history: Optional list of past orders for quality/lead time analysis.

    Returns:
        Dict with overall_risk (0-100), per-factor scores, and recommendations.
    """
    factors: Dict[str, float] = {}
    recommendations: List[str] = []

    # --- Quality risk ---
    quality_score = supplier.get("quality_score")
    if quality_score is not None:
        # Invert: high quality score = low risk
        factors["quality"] = max(0, 100.0 - quality_score)
    else:
        factors["quality"] = 60.0  # Unknown quality = moderate risk
        recommendations.append("No quality score available — request samples and conduct inspection")

    # --- Financial risk ---
    trade_assurance = supplier.get("trade_assurance", 0)
    transaction_count = supplier.get("transaction_count", 0)
    gold_years = supplier.get("gold_years", 0)

    financial_risk = 50.0  # base
    if trade_assurance:
        financial_risk -= 15
    if transaction_count > 1000:
        financial_risk -= 15
    elif transaction_count > 100:
        financial_risk -= 10
    elif transaction_count < 10:
        financial_risk += 15
    if gold_years >= 5:
        financial_risk -= 10
    elif gold_years == 0:
        financial_risk += 10

    factors["financial"] = max(0, min(100, financial_risk))

    if not trade_assurance:
        recommendations.append("No Trade Assurance — use escrow or LC for payment protection")
    if transaction_count < 10:
        recommendations.append("Very low transaction count — start with a small trial order")

    # --- Geographic risk ---
    location = (supplier.get("location") or "").lower()
    geo_risk = assess_geographic_risk(location)
    factors["geographic"] = geo_risk.get("risk_score", 40.0)

    if geo_risk.get("risk_score", 0) > 50:
        recommendations.append(f"Geographic risk elevated for {location}: {', '.join(geo_risk.get('events', []))}")

    # --- Lead time risk ---
    lead_time_risk = 40.0  # base
    if order_history:
        late_orders = sum(1 for o in order_history if o.get("late", False))
        late_ratio = late_orders / len(order_history) if order_history else 0
        lead_time_risk = late_ratio * 100.0
    else:
        on_time = supplier.get("on_time_delivery")
        if on_time is not None:
            lead_time_risk = max(0, (1.0 - on_time) * 100.0)
        else:
            lead_time_risk = 50.0  # Unknown
            recommendations.append("No delivery reliability data — request references from existing buyers")

    factors["lead_time"] = max(0, min(100, lead_time_risk))

    # --- Compliance risk ---
    supplier_type = (supplier.get("supplier_type") or "unknown").lower()
    verified = supplier.get("verified", 0)

    compliance_risk = 40.0
    if supplier_type in ("factory", "factory / manufacturer", "manufacturer"):
        compliance_risk -= 15
    elif supplier_type in ("trading", "trading company"):
        compliance_risk += 10
        recommendations.append("Trading company — verify the actual factory behind them")

    if verified:
        compliance_risk -= 10
    else:
        compliance_risk += 10
        recommendations.append("Supplier is not platform-verified — request business license")

    factors["compliance"] = max(0, min(100, compliance_risk))

    # --- Concentration risk (placeholder — needs portfolio data) ---
    factors["concentration"] = 0.0  # Must be assessed at portfolio level

    # --- Calculate weighted overall risk ---
    overall = calculate_risk_score(factors)

    return {
        "overall_risk": overall,
        "risk_level": _risk_level(overall),
        "factors": factors,
        "recommendations": recommendations,
    }


def assess_concentration_risk(
    suppliers: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Analyze supplier concentration risk across a portfolio.

    High concentration = over-reliance on a single supplier or region.

    Args:
        suppliers: List of supplier dicts, each with 'supplier_id', 'location',
                   and optionally 'order_volume' (percentage or absolute).

    Returns:
        Dict with concentration score, per-supplier percentages, and recommendations.
    """
    if not suppliers:
        return {"concentration_risk": 0.0, "suppliers": [], "recommendations": []}

    total_suppliers = len(suppliers)
    recommendations = []

    # If no order_volume data, assume equal distribution
    has_volume = any(s.get("order_volume") for s in suppliers)
    if has_volume:
        total_volume = sum(s.get("order_volume", 0) for s in suppliers)
        shares = []
        for s in suppliers:
            vol = s.get("order_volume", 0)
            share = vol / total_volume if total_volume > 0 else 1.0 / total_suppliers
            shares.append({
                "supplier_id": s.get("supplier_id", "unknown"),
                "share": round(share, 3),
                "location": s.get("location", "unknown"),
            })
    else:
        share_each = 1.0 / total_suppliers
        shares = [
            {
                "supplier_id": s.get("supplier_id", "unknown"),
                "share": round(share_each, 3),
                "location": s.get("location", "unknown"),
            }
            for s in suppliers
        ]

    # Herfindahl-Hirschman Index (HHI) for concentration
    hhi = sum(sh["share"] ** 2 for sh in shares)
    # HHI ranges from 1/N (perfectly distributed) to 1.0 (monopoly)
    # Normalize to 0-100 scale
    min_hhi = 1.0 / total_suppliers if total_suppliers > 0 else 1.0
    if hhi <= min_hhi:
        concentration_score = 0.0
    else:
        concentration_score = ((hhi - min_hhi) / (1.0 - min_hhi)) * 100.0

    # Geographic concentration
    regions = {}
    for sh in shares:
        loc = sh["location"].lower()
        regions[loc] = regions.get(loc, 0.0) + sh["share"]

    max_region_share = max(regions.values()) if regions else 0
    if max_region_share > 0.70:
        recommendations.append(
            f"Over 70% of supply from one region — diversify geographically"
        )

    # Single-supplier dominance
    max_share = max(sh["share"] for sh in shares) if shares else 0
    if max_share > 0.50:
        recommendations.append(
            "Single supplier accounts for >50% of volume — develop alternatives"
        )

    if total_suppliers < 3:
        recommendations.append(
            f"Only {total_suppliers} supplier(s) — aim for at least 3 qualified suppliers"
        )

    return {
        "concentration_risk": round(concentration_score, 1),
        "risk_level": _risk_level(concentration_score),
        "hhi": round(hhi, 4),
        "total_suppliers": total_suppliers,
        "suppliers": shares,
        "geographic_concentration": {k: round(v, 3) for k, v in regions.items()},
        "recommendations": recommendations,
    }


def assess_geographic_risk(location: str) -> Dict[str, Any]:
    """
    Assess geographic risk for a supplier location.

    Args:
        location: Location string (e.g. 'Guangdong, China' or 'Shenzhen').

    Returns:
        Dict with risk_score (0-100), events, and strengths.
    """
    location_lower = location.lower() if location else ""

    # Try to match against known regions
    for region, data in GEOGRAPHIC_RISKS.items():
        if region in location_lower:
            return {
                "region": region,
                "risk_score": data["risk"] * 100,
                "events": data["events"],
                "strengths": data.get("strengths", []),
                "major_cities": data.get("major_cities", []),
            }
        # Check city names
        for city in data.get("major_cities", []):
            if city.lower() in location_lower:
                return {
                    "region": region,
                    "risk_score": data["risk"] * 100,
                    "events": data["events"],
                    "strengths": data.get("strengths", []),
                    "major_cities": data.get("major_cities", []),
                }

    # Unknown region
    return {
        "region": "unknown",
        "risk_score": 40.0,
        "events": ["unknown region — limited risk data"],
        "strengths": [],
        "major_cities": [],
    }


def calculate_risk_score(factors: Dict[str, float]) -> float:
    """
    Calculate weighted risk score from individual risk factors.

    Args:
        factors: Dict mapping factor names to risk scores (0-100).

    Returns:
        Weighted risk score 0-100 (higher = riskier).
    """
    total = 0.0
    total_weight = 0.0

    for factor, weight in RISK_WEIGHTS.items():
        if factor in factors:
            total += factors[factor] * weight
            total_weight += weight

    if total_weight <= 0:
        return 50.0  # Default moderate risk if no data

    # Normalize so partial-factor scores scale to 0-100 range
    return round(total / total_weight, 1)


def get_scam_indicators(supplier: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Check a supplier profile against known scam patterns.

    Args:
        supplier: Supplier dict with fields from the database schema.

    Returns:
        List of matching scam indicators with risk descriptions.
    """
    indicators = []

    supplier_type = (supplier.get("supplier_type") or "unknown").lower()
    trade_assurance = supplier.get("trade_assurance", 0)
    transaction_count = supplier.get("transaction_count", 0)
    gold_years = supplier.get("gold_years", 0)
    response_rate = supplier.get("response_rate")
    main_products = (supplier.get("main_products") or "").lower()

    # Middleman check — broad product range suggests trading company
    product_categories = len(main_products.split(",")) if main_products else 0
    if product_categories > 5 and supplier_type != "trading":
        indicators.append({
            "scam_type": "middleman_markup",
            "confidence": "medium",
            "reason": f"Very broad product range ({product_categories} categories) but claims to be {supplier_type}",
            "prevention": SOURCING_SCAMS[1]["prevention"],
        })

    # Too good to be true — new supplier with perfect metrics
    if gold_years == 0 and transaction_count > 10000:
        indicators.append({
            "scam_type": "data_fabrication",
            "confidence": "medium",
            "reason": "No gold status but claims very high transaction count — data may be fabricated",
            "prevention": "Verify transaction count independently. Request recent buyer references.",
        })

    # Payment risk — no Trade Assurance on Alibaba
    platform = (supplier.get("platform") or "").lower()
    if platform == "alibaba" and not trade_assurance:
        indicators.append({
            "scam_type": "payment_scam",
            "confidence": "low",
            "reason": "Alibaba supplier without Trade Assurance — limited payment protection",
            "prevention": SOURCING_SCAMS[2]["prevention"],
        })

    # New supplier with aggressive pricing
    if gold_years <= 1 and transaction_count < 50:
        indicators.append({
            "scam_type": "bait_and_switch",
            "confidence": "low",
            "reason": "New supplier with limited track record — higher bait-and-switch risk",
            "prevention": SOURCING_SCAMS[0]["prevention"],
        })

    # Low response rate might indicate inactive/zombie listing
    if response_rate is not None and response_rate < 0.30:
        indicators.append({
            "scam_type": "inactive_listing",
            "confidence": "medium",
            "reason": f"Very low response rate ({response_rate:.0%}) — listing may be abandoned or fraudulent",
            "prevention": "Verify supplier is active before sending any payment.",
        })

    return indicators


def _risk_level(score: float) -> str:
    """Return human-readable risk level label."""
    if score < 30:
        return "LOW"
    elif score < 60:
        return "MODERATE"
    elif score < 80:
        return "HIGH"
    else:
        return "CRITICAL"
