"""
Negotiation intelligence and templates for Sourcerer.

Provides payment term recommendations, message templates for supplier
communication, negotiation strategies, and volume discount estimation.

All functions are pure (no side effects, no database access, no network calls).

Dependencies: None (stdlib only).
"""

from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# Payment Terms Reference
# ---------------------------------------------------------------------------

PAYMENT_TERMS: Dict[str, Dict[str, Any]] = {
    "tt_30_70": {
        "name": "30/70 T/T",
        "description": "30% deposit via wire transfer, 70% before shipment",
        "risk": "moderate",
        "use_when": "Standard for new relationships. Most common for China sourcing.",
        "buyer_leverage": "moderate",
        "notes": "Never pay 70% without pre-shipment inspection approval.",
    },
    "tt_100_advance": {
        "name": "100% T/T Advance",
        "description": "Full payment before production begins",
        "risk": "high",
        "use_when": "NEVER for new suppliers. Only with trusted long-term partners.",
        "buyer_leverage": "none",
        "notes": "Maximum risk. Only acceptable if supplier is deeply trusted.",
    },
    "trade_assurance": {
        "name": "Alibaba Trade Assurance",
        "description": "Escrow via Alibaba platform — payment released after delivery confirmation",
        "risk": "low",
        "use_when": "First orders with Alibaba suppliers. Payment released after delivery confirmation.",
        "buyer_leverage": "high",
        "notes": "Best protection for Alibaba orders. Dispute resolution included.",
    },
    "lc": {
        "name": "Letter of Credit (L/C)",
        "description": "Bank-guaranteed payment — bank verifies documents before releasing payment",
        "risk": "low",
        "use_when": "Large orders ($50K+). Bank verifies documents before releasing payment.",
        "buyer_leverage": "high",
        "notes": "Bank fees typically 1-3% of order value. Need to specify terms precisely.",
    },
    "tt_30_70_delivery": {
        "name": "30/70 T/T Against Delivery",
        "description": "30% deposit, 70% after delivery confirmed at destination",
        "risk": "low",
        "use_when": "Negotiation goal for established suppliers. Strong buyer position.",
        "buyer_leverage": "very high",
        "notes": "Most suppliers will only agree after 3+ successful orders.",
    },
    "open_account": {
        "name": "Open Account (Net 30/60)",
        "description": "Pay after receiving goods, with 30 or 60 day terms",
        "risk": "very low for buyer",
        "use_when": "Only for very established relationships (years). Rare for China sourcing.",
        "buyer_leverage": "maximum",
        "notes": "Extremely rare. Only large buyers with leverage can negotiate this.",
    },
    "dp": {
        "name": "Documents Against Payment (D/P)",
        "description": "Pay bank to release shipping documents that enable cargo pickup",
        "risk": "moderate",
        "use_when": "Alternative to LC for mid-size orders. Simpler than LC.",
        "buyer_leverage": "moderate",
        "notes": "Bank holds documents until buyer pays. Buyer can inspect docs before paying.",
    },
}

# ---------------------------------------------------------------------------
# Message Templates
# ---------------------------------------------------------------------------

MESSAGE_TEMPLATES: Dict[str, str] = {
    "initial_inquiry": (
        "Subject: Inquiry for {product_name} - {quantity} units\n"
        "\n"
        "Dear {supplier_name},\n"
        "\n"
        "We are {company_desc} interested in sourcing {product_name}.\n"
        "\n"
        "Requirements:\n"
        "- Quantity: {quantity} units\n"
        "- Customization: {customization_details}\n"
        "- Target price: {target_price} per unit ({incoterm})\n"
        "- Delivery: {delivery_timeline}\n"
        "\n"
        "Please provide:\n"
        "1. Unit price for {quantity} units\n"
        "2. MOQ and price tiers (100, 500, 1000, 5000 units)\n"
        "3. Sample availability and cost\n"
        "4. Production lead time\n"
        "5. Available certifications\n"
        "6. Customization options (logo, color, packaging)\n"
        "\n"
        "Best regards,\n"
        "{buyer_name}"
    ),

    "sample_request": (
        "Subject: Sample Request - {product_name}\n"
        "\n"
        "Dear {supplier_name},\n"
        "\n"
        "Thank you for the quotation. We would like to proceed with samples.\n"
        "\n"
        "Sample order:\n"
        "- Product: {product_name}\n"
        "- Quantity: {sample_qty} sample(s)\n"
        "- Specifications: {specifications}\n"
        "- Shipping: Express (DHL/FedEx) to {shipping_address}\n"
        "\n"
        "Please confirm:\n"
        "1. Sample cost and shipping fee\n"
        "2. Sample lead time\n"
        "3. Will sample cost be deducted from bulk order?\n"
        "\n"
        "We plan to place a bulk order of {bulk_quantity} units if samples meet "
        "our quality standards.\n"
        "\n"
        "Best regards,\n"
        "{buyer_name}"
    ),

    "price_negotiation": (
        "Subject: Re: Price Discussion - {product_name}\n"
        "\n"
        "Dear {supplier_name},\n"
        "\n"
        "Thank you for the quote of {quoted_price}/unit for {quantity} units.\n"
        "\n"
        "We have received competitive quotes from other qualified suppliers in "
        "the range of {competitor_price_range}/unit for similar specifications.\n"
        "\n"
        "We are interested in a long-term partnership and plan to order "
        "{annual_volume} units per year. Could you review the pricing considering:\n"
        "\n"
        "1. Our commitment to ongoing orders\n"
        "2. Volume discount for {quantity}+ units\n"
        "3. Simplified specifications: {simplification_details}\n"
        "\n"
        "Our target price is {target_price}/unit ({incoterm}). Please let us know "
        "if this is workable.\n"
        "\n"
        "Best regards,\n"
        "{buyer_name}"
    ),

    "counter_offer": (
        "Subject: Re: Revised Quotation - {product_name}\n"
        "\n"
        "Dear {supplier_name},\n"
        "\n"
        "Thank you for revising the price to {revised_price}/unit.\n"
        "\n"
        "We appreciate the adjustment, but our budget allows a maximum of "
        "{max_budget}/unit ({incoterm}) for this order.\n"
        "\n"
        "To help bridge the gap, we can offer:\n"
        "- Larger initial order: {increased_qty} units\n"
        "- Faster payment: {payment_terms}\n"
        "- Simplified packaging/specs: {simplifications}\n"
        "\n"
        "Can we meet at {counter_price}/unit? This would allow us to proceed "
        "immediately.\n"
        "\n"
        "Best regards,\n"
        "{buyer_name}"
    ),

    "order_confirmation": (
        "Subject: Purchase Order Confirmation - PO#{po_number}\n"
        "\n"
        "Dear {supplier_name},\n"
        "\n"
        "Please find below our purchase order details:\n"
        "\n"
        "PO Number: {po_number}\n"
        "Product: {product_name}\n"
        "Quantity: {quantity} units\n"
        "Unit Price: {unit_price} ({incoterm})\n"
        "Total: {total_value}\n"
        "Payment Terms: {payment_terms}\n"
        "Delivery Date: {delivery_date}\n"
        "Shipping: {shipping_method} to {shipping_destination}\n"
        "\n"
        "Quality requirements:\n"
        "- AQL 2.5 for major defects, AQL 4.0 for minor\n"
        "- Pre-shipment inspection required before 70% payment\n"
        "- All units must match approved sample\n"
        "\n"
        "Please confirm acceptance and share:\n"
        "1. Production schedule\n"
        "2. Bank details for 30% deposit\n"
        "\n"
        "Best regards,\n"
        "{buyer_name}"
    ),

    "quality_complaint": (
        "Subject: URGENT - Quality Issue - PO#{po_number}\n"
        "\n"
        "Dear {supplier_name},\n"
        "\n"
        "We have received order PO#{po_number} and discovered the following "
        "quality issues:\n"
        "\n"
        "Issues found:\n"
        "{issue_description}\n"
        "\n"
        "Evidence:\n"
        "- Photos attached showing defects\n"
        "- Affected quantity: {affected_qty} out of {total_qty} units ({defect_rate}%)\n"
        "- Reference: Approved sample dated {sample_date}\n"
        "\n"
        "We request:\n"
        "1. Root cause analysis within 3 business days\n"
        "2. {resolution_request}\n"
        "3. Prevention plan for future orders\n"
        "\n"
        "Please respond within 24 hours. This affects our ability to place "
        "future orders.\n"
        "\n"
        "Best regards,\n"
        "{buyer_name}"
    ),

    "reorder": (
        "Subject: Reorder - {product_name} - {quantity} units\n"
        "\n"
        "Dear {supplier_name},\n"
        "\n"
        "We are pleased with the quality of the previous order and would like "
        "to place a repeat order:\n"
        "\n"
        "Product: {product_name}\n"
        "Quantity: {quantity} units (previous order: {prev_quantity})\n"
        "Specifications: Same as PO#{prev_po_number}\n"
        "\n"
        "Given our ongoing partnership and increased volume, we would like to "
        "discuss:\n"
        "1. Price adjustment for {quantity} units (previous: {prev_price}/unit)\n"
        "2. Improved payment terms\n"
        "3. Priority production slot\n"
        "\n"
        "Please provide updated quotation.\n"
        "\n"
        "Best regards,\n"
        "{buyer_name}"
    ),

    "rfq_followup": (
        "Subject: Follow-up - Inquiry for {product_name}\n"
        "\n"
        "Dear {supplier_name},\n"
        "\n"
        "I sent an inquiry regarding {product_name} on {inquiry_date} but "
        "haven't received a response yet.\n"
        "\n"
        "We are actively sourcing this product and plan to place an order of "
        "{quantity} units within {timeline}.\n"
        "\n"
        "Could you kindly provide a quotation at your earliest convenience?\n"
        "\n"
        "Best regards,\n"
        "{buyer_name}"
    ),
}

# ---------------------------------------------------------------------------
# Negotiation Strategies
# ---------------------------------------------------------------------------

NEGOTIATION_STRATEGIES: List[Dict[str, Any]] = [
    {
        "scenario": "first_order",
        "strategy": (
            "Start with a sample order. Use Trade Assurance if on Alibaba. "
            "Don't reveal your full volume plans yet — suppliers price based on "
            "perceived opportunity. Get 3+ quotes before committing."
        ),
        "leverage_points": [
            "future volume potential",
            "quick payment (faster than competitors)",
            "long-term partnership opportunity",
            "willingness to provide testimonials/references",
        ],
        "common_mistakes": [
            "Revealing your maximum budget upfront",
            "Ordering too large on the first order",
            "Paying 100% upfront to a new supplier",
        ],
    },
    {
        "scenario": "price_too_high",
        "strategy": (
            "Get 3+ quotes to establish market price. Show competitor pricing "
            "(redact names). Ask for volume tiers. Consider simplifying specs, "
            "materials, or packaging to reduce cost."
        ),
        "leverage_points": [
            "competitive quotes from other suppliers",
            "larger quantity commitment",
            "simplified specifications or materials",
            "longer lead time acceptance",
            "off-season ordering (avoid peak season premiums)",
        ],
        "common_mistakes": [
            "Pressuring too hard (damages relationship)",
            "Comparing quotes with different Incoterms",
            "Not accounting for quality differences",
        ],
    },
    {
        "scenario": "reorder_negotiation",
        "strategy": (
            "Reference previous order quality and volume. Push for 5-10% price "
            "reduction on reorders. Negotiate better payment terms (e.g. 30/70 "
            "against delivery instead of before shipment)."
        ),
        "leverage_points": [
            "proven track record with this supplier",
            "repeat business guarantee",
            "referral potential to other buyers",
            "increased order quantity",
        ],
        "common_mistakes": [
            "Assuming the same price is fair forever",
            "Not benchmarking against new quotes periodically",
        ],
    },
    {
        "scenario": "quality_issue",
        "strategy": (
            "Document everything with photos and measurements. Reference the "
            "original spec sheet and approved sample. Request remake, credit, "
            "or partial refund. Escalate to Trade Assurance dispute if needed."
        ),
        "leverage_points": [
            "Trade Assurance dispute mechanism",
            "documented evidence (photos, specs, inspection reports)",
            "future orders at risk if not resolved",
            "negative review impact on supplier's platform rating",
        ],
        "common_mistakes": [
            "Accepting a small discount instead of proper resolution",
            "Not documenting defects thoroughly enough",
            "Waiting too long to file a dispute (time limits apply)",
        ],
    },
    {
        "scenario": "urgent_order",
        "strategy": (
            "Be transparent about the deadline. Offer to pay a rush fee (10-20% "
            "premium is typical). Accept simplified QC if timeline is very tight. "
            "Consider air freight instead of sea to recover time."
        ),
        "leverage_points": [
            "willingness to pay rush premium",
            "simplified inspection requirements",
            "guaranteed future orders at standard timeline",
        ],
        "common_mistakes": [
            "Expecting rush delivery at standard price",
            "Skipping quality inspection entirely",
            "Not building buffer time for unexpected delays",
        ],
    },
    {
        "scenario": "switching_supplier",
        "strategy": (
            "Run parallel production with old and new supplier for at least "
            "one order cycle. Qualify new supplier with sample + small order "
            "before fully transitioning. Never burn bridges with old supplier "
            "until new one is proven."
        ),
        "leverage_points": [
            "volume up for grabs",
            "competitive tension between old and new supplier",
            "clear quality expectations from existing relationship",
        ],
        "common_mistakes": [
            "Cutting off old supplier too quickly",
            "Not qualifying new supplier thoroughly",
            "Revealing to new supplier that you're desperate to switch",
        ],
    },
]


# ---------------------------------------------------------------------------
# Functions
# ---------------------------------------------------------------------------

def get_template(
    stage: str,
    context: Optional[Dict[str, str]] = None,
) -> str:
    """
    Get a negotiation message template, optionally filled with context.

    Args:
        stage: Template key (e.g. 'initial_inquiry', 'sample_request').
        context: Optional dict of placeholder values to fill in.

    Returns:
        Template string (with placeholders filled if context provided).
    """
    template = MESSAGE_TEMPLATES.get(stage)
    if not template:
        available = ", ".join(sorted(MESSAGE_TEMPLATES.keys()))
        return f"Template '{stage}' not found. Available: {available}"

    if context:
        try:
            return template.format(**{
                k: context.get(k, f"{{{k}}}")
                for k in _extract_placeholders(template)
            })
        except (KeyError, IndexError):
            return template

    return template


def get_payment_recommendation(
    order_value: float,
    supplier_score: float = 50.0,
    is_first_order: bool = True,
) -> Dict[str, Any]:
    """
    Recommend payment terms based on order context.

    Args:
        order_value: Order value in USD.
        supplier_score: Supplier quality score (0-100).
        is_first_order: Whether this is the first order with this supplier.

    Returns:
        Dict with recommended terms, alternatives, and reasoning.
    """
    recommended = ""
    reasoning = []
    alternatives = []

    if is_first_order:
        if order_value < 500:
            recommended = "trade_assurance"
            reasoning.append("First order + small value: Trade Assurance provides best protection")
            alternatives = ["tt_30_70"]
        elif order_value < 5000:
            recommended = "trade_assurance"
            reasoning.append("First order: Trade Assurance is safest for initial relationship")
            alternatives = ["tt_30_70"]
        elif order_value < 50000:
            recommended = "tt_30_70"
            reasoning.append("Mid-size first order: 30/70 T/T is industry standard")
            if supplier_score >= 75:
                alternatives = ["trade_assurance"]
            else:
                alternatives = ["trade_assurance", "lc"]
                reasoning.append("Consider LC for additional bank protection")
        else:
            recommended = "lc"
            reasoning.append("Large first order ($50K+): Letter of Credit provides bank guarantee")
            alternatives = ["tt_30_70"]
    else:
        # Repeat order
        if supplier_score >= 80:
            recommended = "tt_30_70_delivery"
            reasoning.append("High-scoring repeat supplier: negotiate 70% against delivery")
            alternatives = ["tt_30_70"]
        elif supplier_score >= 60:
            recommended = "tt_30_70"
            reasoning.append("Good repeat supplier: standard 30/70 T/T")
            alternatives = ["tt_30_70_delivery"]
        else:
            recommended = "trade_assurance"
            reasoning.append("Below-average supplier score: maintain Trade Assurance protection")
            alternatives = ["tt_30_70"]

    return {
        "recommended": recommended,
        "recommended_details": PAYMENT_TERMS.get(recommended, {}),
        "alternatives": [
            {"term": t, **PAYMENT_TERMS.get(t, {})}
            for t in alternatives
        ],
        "reasoning": reasoning,
        "order_value": order_value,
        "supplier_score": supplier_score,
        "is_first_order": is_first_order,
    }


def get_negotiation_strategy(scenario: str) -> Dict[str, Any]:
    """
    Get negotiation strategy advice for a scenario.

    Args:
        scenario: Scenario key (e.g. 'first_order', 'price_too_high').

    Returns:
        Strategy dict with advice, leverage points, and common mistakes.
        Empty dict if scenario not found.
    """
    for strat in NEGOTIATION_STRATEGIES:
        if strat["scenario"] == scenario:
            return strat
    return {}


def estimate_volume_discount(
    base_price: float,
    quantities: List[int],
) -> List[Dict[str, Any]]:
    """
    Estimate typical volume discount curve.

    Based on industry averages for China manufacturing:
      - MOQ: base price
      - 2x MOQ: ~5% discount
      - 5x MOQ: ~10% discount
      - 10x MOQ: ~15% discount
      - 20x+ MOQ: ~20% discount (negotiable)

    Args:
        base_price: Base unit price at MOQ.
        quantities: List of quantity levels to estimate.

    Returns:
        List of dicts with quantity, estimated_price, discount_pct, total_cost.
    """
    if not quantities:
        return []

    # Filter out invalid quantities
    quantities = [q for q in quantities if q > 0]
    if not quantities:
        return []

    # Sort quantities ascending
    sorted_qtys = sorted(quantities)
    base_qty = sorted_qtys[0]

    results = []
    for qty in sorted_qtys:
        if base_qty <= 0:
            ratio = 1.0
        else:
            ratio = qty / base_qty

        # Discount curve (logarithmic)
        if ratio <= 1.0:
            discount = 0.0
        elif ratio <= 2.0:
            discount = 0.05
        elif ratio <= 5.0:
            discount = 0.05 + (ratio - 2.0) / 3.0 * 0.05  # 5-10%
        elif ratio <= 10.0:
            discount = 0.10 + (ratio - 5.0) / 5.0 * 0.05  # 10-15%
        elif ratio <= 20.0:
            discount = 0.15 + (ratio - 10.0) / 10.0 * 0.05  # 15-20%
        else:
            discount = 0.20  # Cap at 20% for estimates

        estimated_price = round(base_price * (1.0 - discount), 4)
        total_cost = round(estimated_price * qty, 2)

        results.append({
            "quantity": qty,
            "estimated_price": estimated_price,
            "discount_pct": round(discount * 100, 1),
            "total_cost": total_cost,
            "savings_vs_base": round((base_price - estimated_price) * qty, 2),
        })

    return results


def _extract_placeholders(template: str) -> List[str]:
    """Extract {placeholder} names from a template string."""
    import re
    return re.findall(r"\{(\w+)\}", template)
