"""
Logistics intelligence for Sourcerer.

Provides freight cost estimation, transit time data, Chinese holiday impact
analysis, container recommendations, and volumetric weight calculations.

All data structures are pure constants. All functions are pure (no side effects,
no database access, no network calls).

Dependencies: None (stdlib only).
"""

import math
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Chinese Holidays — impact on factory production and shipping
# ---------------------------------------------------------------------------

CHINESE_HOLIDAYS: List[Dict[str, Any]] = [
    {
        "name": "Chinese New Year",
        "typical_month": 1,
        "duration_days": 14,
        "factory_shutdown_days": 21,
        "impact": "critical",
        "planning_note": (
            "Order 60-90 days before. Factories stop taking orders 2-3 weeks "
            "prior. Workers may not return for another week after. Freight rates "
            "spike in Jan/Feb. This is the single biggest disruption of the year."
        ),
    },
    {
        "name": "Qingming Festival (Tomb Sweeping)",
        "typical_month": 4,
        "duration_days": 3,
        "factory_shutdown_days": 3,
        "impact": "low",
        "planning_note": (
            "Minor impact. Most factories close 1-3 days. Plan for slight delays."
        ),
    },
    {
        "name": "Labor Day",
        "typical_month": 5,
        "duration_days": 5,
        "factory_shutdown_days": 5,
        "impact": "medium",
        "planning_note": (
            "Extended to 5 days since 2019. Moderate impact. Place orders early April."
        ),
    },
    {
        "name": "Dragon Boat Festival",
        "typical_month": 6,
        "duration_days": 3,
        "factory_shutdown_days": 3,
        "impact": "low",
        "planning_note": (
            "Minor impact. 3-day holiday, most factories resume quickly."
        ),
    },
    {
        "name": "Mid-Autumn Festival",
        "typical_month": 9,
        "duration_days": 3,
        "factory_shutdown_days": 3,
        "impact": "low",
        "planning_note": (
            "Minor impact. 3-day holiday. Sometimes falls near National Day."
        ),
    },
    {
        "name": "National Day / Golden Week",
        "typical_month": 10,
        "duration_days": 7,
        "factory_shutdown_days": 10,
        "impact": "high",
        "planning_note": (
            "Second biggest disruption. 7 official days but many factories close "
            "for 10+. Plan for a 2-week productivity gap. Order by early September."
        ),
    },
    {
        "name": "Singles Day (11.11)",
        "typical_month": 11,
        "duration_days": 1,
        "factory_shutdown_days": 0,
        "impact": "medium",
        "planning_note": (
            "Factories stay open but domestic logistics are overwhelmed. "
            "International freight costs spike. Expect 3-5 day delays on shipments."
        ),
    },
    {
        "name": "12.12 Shopping Festival",
        "typical_month": 12,
        "duration_days": 1,
        "factory_shutdown_days": 0,
        "impact": "low",
        "planning_note": (
            "Smaller than 11.11 but still causes logistics congestion. "
            "Minor delays possible for domestic pickup."
        ),
    },
]

# ---------------------------------------------------------------------------
# Freight Modes — detailed specifications
# ---------------------------------------------------------------------------

FREIGHT_MODES: Dict[str, Dict[str, Any]] = {
    "express": {
        "name": "Express Courier",
        "transit_days": (3, 7),
        "cost_per_kg": (6.0, 12.0),
        "max_weight_kg": 70,
        "min_weight_kg": 0,
        "best_for": "samples, urgent small orders (<30kg)",
        "carriers": ["DHL", "FedEx", "UPS", "TNT"],
        "volumetric_divisor": 5000,
        "notes": "Door-to-door. Includes customs clearance. Fastest option.",
    },
    "air": {
        "name": "Air Freight",
        "transit_days": (5, 12),
        "cost_per_kg": (3.0, 6.0),
        "min_weight_kg": 45,
        "max_weight_kg": None,
        "best_for": "medium orders (45-500kg), time-sensitive goods",
        "carriers": ["Cargo airlines", "Freight forwarders"],
        "volumetric_divisor": 6000,
        "notes": "Airport-to-airport. Need customs broker + last-mile delivery.",
    },
    "sea_lcl": {
        "name": "Ocean LCL (Less than Container Load)",
        "transit_days": (25, 45),
        "cost_per_cbm": (40.0, 80.0),
        "min_cbm": 1.0,
        "max_cbm": 14.0,
        "best_for": "medium orders (1-14 CBM), not time-sensitive",
        "carriers": ["Freight forwarders", "NVOCC"],
        "notes": "Shared container. CFS-to-CFS. Slower due to consolidation/deconsolidation.",
    },
    "sea_fcl_20": {
        "name": "Ocean FCL 20ft Container",
        "transit_days": (25, 40),
        "cost_per_container": (1500.0, 4000.0),
        "capacity_cbm": 28,
        "max_weight_mt": 21,
        "best_for": "large orders filling 15-28 CBM",
        "carriers": ["Maersk", "MSC", "CMA CGM", "COSCO", "Evergreen"],
        "notes": "Full container. Most cost-effective for volume. Port-to-port.",
    },
    "sea_fcl_40": {
        "name": "Ocean FCL 40ft Container",
        "transit_days": (25, 40),
        "cost_per_container": (2500.0, 6000.0),
        "capacity_cbm": 56,
        "max_weight_mt": 26,
        "best_for": "large orders filling 30-56 CBM",
        "carriers": ["Maersk", "MSC", "CMA CGM", "COSCO", "Evergreen"],
        "notes": "Standard full container. Best per-CBM cost at scale.",
    },
    "sea_fcl_40hq": {
        "name": "Ocean FCL 40ft High Cube",
        "transit_days": (25, 40),
        "cost_per_container": (2800.0, 6500.0),
        "capacity_cbm": 68,
        "max_weight_mt": 26,
        "best_for": "large/bulky orders filling 40-68 CBM",
        "carriers": ["Maersk", "MSC", "CMA CGM", "COSCO", "Evergreen"],
        "notes": "1 foot taller than standard 40ft. Best for voluminous light goods.",
    },
    "rail": {
        "name": "China-Europe Rail",
        "transit_days": (16, 22),
        "cost_per_kg": (2.0, 4.0),
        "min_weight_kg": 100,
        "max_weight_kg": None,
        "best_for": "EU-bound shipments, balance of cost and speed",
        "carriers": ["China Railway Express", "DHL Rail", "DB Cargo"],
        "notes": "Not applicable for US-bound. EU only via New Silk Road.",
    },
}

# ---------------------------------------------------------------------------
# Product Weight/Dimension Estimates by Category
# ---------------------------------------------------------------------------

PRODUCT_WEIGHT_ESTIMATES: Dict[str, Dict[str, Any]] = {
    "phone_cases": {
        "weight_kg": 0.05,
        "dims_cm": (16, 8, 2),
        "note": "per unit, thin silicone/TPU case",
    },
    "clothing_light": {
        "weight_kg": 0.2,
        "dims_cm": (30, 20, 3),
        "note": "t-shirt, thin top",
    },
    "clothing_heavy": {
        "weight_kg": 0.5,
        "dims_cm": (35, 25, 5),
        "note": "hoodie, jacket, jeans",
    },
    "electronics_small": {
        "weight_kg": 0.3,
        "dims_cm": (20, 15, 8),
        "note": "earbuds, charger, small device",
    },
    "electronics_medium": {
        "weight_kg": 1.5,
        "dims_cm": (40, 30, 15),
        "note": "tablet, speaker, medium device with packaging",
    },
    "home_decor": {
        "weight_kg": 0.8,
        "dims_cm": (30, 30, 20),
        "note": "vases, frames, decorative items",
    },
    "kitchenware": {
        "weight_kg": 0.6,
        "dims_cm": (25, 20, 15),
        "note": "utensils, small kitchen tools",
    },
    "toys": {
        "weight_kg": 0.3,
        "dims_cm": (25, 20, 15),
        "note": "average toy with packaging",
    },
    "bags": {
        "weight_kg": 0.4,
        "dims_cm": (35, 25, 10),
        "note": "backpack, tote, crossbody bag",
    },
    "jewelry": {
        "weight_kg": 0.03,
        "dims_cm": (10, 8, 3),
        "note": "necklace, ring, bracelet with packaging",
    },
    "shoes": {
        "weight_kg": 0.8,
        "dims_cm": (33, 22, 12),
        "note": "one pair with box",
    },
    "beauty": {
        "weight_kg": 0.15,
        "dims_cm": (15, 10, 5),
        "note": "cosmetic item, skincare, small bottle",
    },
    "pet_products": {
        "weight_kg": 0.4,
        "dims_cm": (25, 20, 10),
        "note": "pet toy, collar, small accessory",
    },
    "stationery": {
        "weight_kg": 0.1,
        "dims_cm": (20, 15, 5),
        "note": "notebooks, pens, desk items",
    },
    "default": {
        "weight_kg": 0.3,
        "dims_cm": (25, 20, 10),
        "note": "generic estimate for unknown product types",
    },
}

# ---------------------------------------------------------------------------
# Port Routes — common shipping routes with transit times
# ---------------------------------------------------------------------------

PORT_ROUTES: List[Dict[str, Any]] = [
    {
        "origin": "Shenzhen/Yantian",
        "dest": "Los Angeles/Long Beach",
        "sea_days": 14,
        "air_hours": 14,
    },
    {
        "origin": "Shanghai/Ningbo",
        "dest": "Los Angeles/Long Beach",
        "sea_days": 16,
        "air_hours": 13,
    },
    {
        "origin": "Shanghai/Ningbo",
        "dest": "New York/Newark",
        "sea_days": 30,
        "air_hours": 16,
    },
    {
        "origin": "Guangzhou",
        "dest": "Los Angeles",
        "sea_days": 15,
        "air_hours": 14,
    },
    {
        "origin": "Xiamen",
        "dest": "Los Angeles",
        "sea_days": 16,
        "air_hours": 15,
    },
    {
        "origin": "Shenzhen",
        "dest": "Rotterdam",
        "sea_days": 28,
        "air_hours": 13,
    },
    {
        "origin": "Shanghai",
        "dest": "Hamburg",
        "sea_days": 30,
        "air_hours": 12,
    },
]


# ---------------------------------------------------------------------------
# Functions
# ---------------------------------------------------------------------------

def calculate_volumetric_weight(
    length_cm: float,
    width_cm: float,
    height_cm: float,
    mode: str = "air",
) -> float:
    """
    Calculate volumetric (dimensional) weight for air/express freight.

    Carriers charge whichever is higher: actual weight or volumetric weight.

    Args:
        length_cm: Length in centimeters.
        width_cm: Width in centimeters.
        height_cm: Height in centimeters.
        mode: Freight mode ('air' or 'express') for divisor selection.

    Returns:
        Volumetric weight in kilograms.
    """
    fm = FREIGHT_MODES.get(mode, {})
    divisor = fm.get("volumetric_divisor", 6000)
    return (length_cm * width_cm * height_cm) / divisor


def calculate_cbm(
    length_cm: float,
    width_cm: float,
    height_cm: float,
    qty: int = 1,
) -> float:
    """
    Calculate cubic meters for sea freight.

    Args:
        length_cm: Length in centimeters (per unit).
        width_cm: Width in centimeters (per unit).
        height_cm: Height in centimeters (per unit).
        qty: Number of units.

    Returns:
        Total volume in cubic meters.
    """
    cbm_per_unit = (length_cm / 100.0) * (width_cm / 100.0) * (height_cm / 100.0)
    return cbm_per_unit * qty


def estimate_product_weight(
    category: str,
    qty: int = 1,
) -> Dict[str, Any]:
    """
    Estimate total weight and volume from product category and quantity.

    Args:
        category: Product category key (e.g. 'phone_cases', 'shoes').
        qty: Number of units.

    Returns:
        Dict with total_weight_kg, total_cbm, per_unit details.
    """
    est = PRODUCT_WEIGHT_ESTIMATES.get(category.lower(), PRODUCT_WEIGHT_ESTIMATES["default"])

    total_weight = est["weight_kg"] * qty
    dims = est["dims_cm"]
    total_cbm = calculate_cbm(dims[0], dims[1], dims[2], qty)

    return {
        "category": category,
        "qty": qty,
        "per_unit_weight_kg": est["weight_kg"],
        "per_unit_dims_cm": dims,
        "total_weight_kg": round(total_weight, 2),
        "total_cbm": round(total_cbm, 4),
        "note": est.get("note", ""),
    }


def estimate_freight_cost(
    weight_kg: float,
    cbm: float,
    mode: str,
    qty: int = 1,
) -> Dict[str, Any]:
    """
    Estimate freight cost for a given mode.

    Args:
        weight_kg: Total actual weight in kilograms.
        cbm: Total volume in cubic meters.
        mode: Freight mode key from FREIGHT_MODES.
        qty: Number of units (for per-unit cost calculation).

    Returns:
        Dict with estimated cost, breakdown, and mode details.
    """
    fm = FREIGHT_MODES.get(mode)
    if not fm:
        return {"error": f"Unknown freight mode: {mode}", "cost_low": 0, "cost_high": 0}

    cost_low = 0.0
    cost_high = 0.0
    basis = ""

    if "cost_per_kg" in fm:
        # Air or express — use max of actual weight and volumetric weight
        rate_low, rate_high = fm["cost_per_kg"]
        chargeable = weight_kg
        if "volumetric_divisor" in fm and cbm > 0:
            # Approximate volumetric from CBM
            vol_weight = (cbm * 1_000_000) / fm["volumetric_divisor"]
            chargeable = max(weight_kg, vol_weight)
        cost_low = chargeable * rate_low
        cost_high = chargeable * rate_high
        basis = f"{chargeable:.1f} kg chargeable weight"

    elif "cost_per_cbm" in fm:
        # Sea LCL
        rate_low, rate_high = fm["cost_per_cbm"]
        chargeable_cbm = max(cbm, fm.get("min_cbm", 1.0))
        cost_low = chargeable_cbm * rate_low
        cost_high = chargeable_cbm * rate_high
        basis = f"{chargeable_cbm:.2f} CBM"

    elif "cost_per_container" in fm:
        # Sea FCL
        rate_low, rate_high = fm["cost_per_container"]
        container_cbm = fm.get("capacity_cbm", 28)
        containers_needed = max(1, math.ceil(cbm / container_cbm))
        cost_low = containers_needed * rate_low
        cost_high = containers_needed * rate_high
        basis = f"{containers_needed} container(s) x {container_cbm} CBM"

    avg_cost = (cost_low + cost_high) / 2.0
    per_unit = avg_cost / max(qty, 1)

    transit_low, transit_high = fm.get("transit_days", (0, 0))

    return {
        "mode": mode,
        "mode_name": fm["name"],
        "cost_low": round(cost_low, 2),
        "cost_high": round(cost_high, 2),
        "cost_avg": round(avg_cost, 2),
        "per_unit_avg": round(per_unit, 2),
        "basis": basis,
        "transit_days_low": transit_low,
        "transit_days_high": transit_high,
        "best_for": fm.get("best_for", ""),
        "notes": fm.get("notes", ""),
    }


def recommend_freight_mode(
    total_weight_kg: float,
    total_cbm: float,
    urgency: str = "normal",
) -> List[Dict[str, Any]]:
    """
    Recommend freight modes ranked by suitability.

    Args:
        total_weight_kg: Total shipment weight in kilograms.
        total_cbm: Total shipment volume in cubic meters.
        urgency: 'urgent', 'normal', or 'flexible'.

    Returns:
        List of freight mode recommendations sorted by suitability score.
    """
    recommendations = []

    for mode_key, fm in FREIGHT_MODES.items():
        if mode_key == "rail":
            continue  # Rail is EU-only, skip for general recs

        score = 50.0  # base score
        reasons = []

        # Weight/volume fit
        min_wt = fm.get("min_weight_kg", 0)
        max_wt = fm.get("max_weight_kg")
        if max_wt and total_weight_kg > max_wt:
            score -= 40
            reasons.append(f"exceeds max weight ({max_wt}kg)")
        if total_weight_kg < min_wt:
            score -= 20
            reasons.append(f"below minimum weight ({min_wt}kg)")

        # CBM fit for container modes
        if "capacity_cbm" in fm:
            capacity = fm["capacity_cbm"]
            utilization = total_cbm / capacity if capacity else 0
            if utilization < 0.5:
                score -= 15
                reasons.append(f"low utilization ({utilization:.0%})")
            elif utilization >= 0.7:
                score += 15
                reasons.append(f"good utilization ({utilization:.0%})")

        # LCL limits
        if "max_cbm" in fm:
            if total_cbm > fm["max_cbm"]:
                score -= 30
                reasons.append(f"exceeds LCL max ({fm['max_cbm']} CBM)")

        # Urgency
        transit_low = fm.get("transit_days", (30, 30))[0]
        if urgency == "urgent":
            if transit_low <= 7:
                score += 25
                reasons.append("fast transit for urgent order")
            elif transit_low > 20:
                score -= 25
                reasons.append("too slow for urgent order")
        elif urgency == "flexible":
            # Favor cheapest options
            if "cost_per_container" in fm or mode_key == "sea_lcl":
                score += 15
                reasons.append("cost-effective for flexible timeline")

        # Get cost estimate for this mode
        cost = estimate_freight_cost(total_weight_kg, total_cbm, mode_key)

        recommendations.append({
            "mode": mode_key,
            "mode_name": fm["name"],
            "score": round(score, 1),
            "reasons": reasons,
            "cost_estimate": cost,
        })

    # Sort by score descending
    recommendations.sort(key=lambda x: x["score"], reverse=True)
    return recommendations


def check_holiday_impact(target_date_str: str) -> List[Dict[str, Any]]:
    """
    Check if a target date falls near a Chinese holiday.

    Args:
        target_date_str: Date string in YYYY-MM-DD format.

    Returns:
        List of nearby holidays with impact assessment.
    """
    try:
        target = datetime.strptime(target_date_str, "%Y-%m-%d")
    except ValueError:
        return [{"error": f"Invalid date format: {target_date_str}. Use YYYY-MM-DD."}]

    nearby = []
    target_month = target.month
    target_year = target.year

    for holiday in CHINESE_HOLIDAYS:
        h_month = holiday["typical_month"]
        # Check if within 1 month of the holiday
        month_diff = abs(target_month - h_month)
        if month_diff > 6:
            month_diff = 12 - month_diff

        if month_diff <= 1:
            # Determine if the holiday is upcoming or already passed this year
            is_upcoming = (h_month >= target_month) or (h_month == 1 and target_month == 12)
            if h_month < target_month and month_diff == 1:
                is_upcoming = False  # Holiday month already passed

            nearby.append({
                "holiday": holiday["name"],
                "typical_month": h_month,
                "duration_days": holiday["duration_days"],
                "factory_shutdown_days": holiday["factory_shutdown_days"],
                "impact": holiday["impact"],
                "planning_note": holiday["planning_note"],
                "proximity": "same_month" if month_diff == 0 else "adjacent_month",
                "is_upcoming": is_upcoming,
                "target_year": target_year,
            })

    return nearby


def get_container_recommendation(
    total_cbm: float,
    total_weight_kg: float,
) -> Dict[str, Any]:
    """
    Recommend LCL vs FCL container strategy.

    Args:
        total_cbm: Total shipment volume in cubic meters.
        total_weight_kg: Total shipment weight in kilograms.

    Returns:
        Dict with recommendation, reasoning, and cost comparison.
    """
    lcl = FREIGHT_MODES["sea_lcl"]
    fcl_20 = FREIGHT_MODES["sea_fcl_20"]
    fcl_40 = FREIGHT_MODES["sea_fcl_40"]
    fcl_40hq = FREIGHT_MODES["sea_fcl_40hq"]

    # LCL cost estimate
    lcl_rate_avg = sum(lcl["cost_per_cbm"]) / 2.0
    lcl_cost = max(total_cbm, lcl["min_cbm"]) * lcl_rate_avg

    # FCL 20ft
    fcl20_rate_avg = sum(fcl_20["cost_per_container"]) / 2.0
    containers_20 = max(1, math.ceil(total_cbm / fcl_20["capacity_cbm"]))
    fcl20_cost = containers_20 * fcl20_rate_avg

    # FCL 40ft
    fcl40_rate_avg = sum(fcl_40["cost_per_container"]) / 2.0
    containers_40 = max(1, math.ceil(total_cbm / fcl_40["capacity_cbm"]))
    fcl40_cost = containers_40 * fcl40_rate_avg

    # FCL 40HQ
    fcl40hq_rate_avg = sum(fcl_40hq["cost_per_container"]) / 2.0
    containers_40hq = max(1, math.ceil(total_cbm / fcl_40hq["capacity_cbm"]))
    fcl40hq_cost = containers_40hq * fcl40hq_rate_avg

    # Find cheapest
    options = [
        ("LCL", lcl_cost, total_cbm <= lcl.get("max_cbm", 14)),
        ("FCL 20ft", fcl20_cost, True),
        ("FCL 40ft", fcl40_cost, True),
        ("FCL 40ft HQ", fcl40hq_cost, True),
    ]

    # Filter feasible and sort by cost
    feasible = [(name, cost) for name, cost, ok in options if ok]
    feasible.sort(key=lambda x: x[1])

    recommendation = feasible[0][0] if feasible else "FCL 20ft"
    reasoning = []

    if total_cbm <= 5:
        reasoning.append("Small shipment: LCL is simpler, no minimum container commitment")
    elif total_cbm <= 14:
        # Compare LCL vs FCL 20ft
        if lcl_cost < fcl20_cost * 0.85:
            reasoning.append("LCL is significantly cheaper than a full container")
        else:
            reasoning.append("FCL 20ft is cost-competitive with LCL at this volume")
            recommendation = "FCL 20ft"
    elif total_cbm <= 28:
        reasoning.append("Volume fits a single 20ft container")
        recommendation = "FCL 20ft"
    elif total_cbm <= 56:
        reasoning.append("Volume fits a single 40ft container")
        recommendation = "FCL 40ft"
    else:
        reasoning.append("Large volume — consider 40ft HQ or multiple containers")
        recommendation = "FCL 40ft HQ"

    # Weight check
    if total_weight_kg > 21000 and recommendation == "FCL 20ft":
        reasoning.append("WARNING: Weight exceeds 20ft container limit (21MT)")
        recommendation = "FCL 40ft"
    if total_weight_kg > 26000:
        reasoning.append("WARNING: Weight exceeds single 40ft container limit (26MT)")

    return {
        "recommendation": recommendation,
        "reasoning": reasoning,
        "total_cbm": round(total_cbm, 2),
        "total_weight_kg": round(total_weight_kg, 2),
        "cost_comparison": {
            "LCL": round(lcl_cost, 2),
            "FCL_20ft": round(fcl20_cost, 2),
            "FCL_40ft": round(fcl40_cost, 2),
            "FCL_40ft_HQ": round(fcl40hq_cost, 2),
        },
    }


def is_section_321_eligible(value_usd: float) -> bool:
    """
    Check if a shipment qualifies for Section 321 de minimis entry.

    Shipments valued at or under $800 USD may be imported duty-free.

    Args:
        value_usd: Total declared value in USD.

    Returns:
        True if eligible for de minimis (duty-free) entry.
    """
    from compliance import DE_MINIMIS_THRESHOLD
    return value_usd <= DE_MINIMIS_THRESHOLD
