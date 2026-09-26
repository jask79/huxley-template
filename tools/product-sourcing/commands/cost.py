"""
Landed cost calculations — duties, freight, insurance, and total landed cost.

Enhanced with compliance module (Section 301 tariff data) and logistics module
(weight/dimension-based freight estimation) for more accurate calculations.

Commands:
    cost calculate --product-id <id> --qty <N> [--freight-mode sea|air|express]
    cost history <product_id>
    cost hs-lookup "product description"
    cost exchange <from> <to>
"""

import sys
from argparse import Namespace
from pathlib import Path
from typing import Optional

_TOOL_DIR = Path(__file__).resolve().parent.parent
if str(_TOOL_DIR) not in sys.path:
    sys.path.insert(0, str(_TOOL_DIR))

import db
from client import (
    EasyshipClient,
    FreightosClient,
    ExchangeRateClient,
    CredentialError,
    APIError,
)
from compliance import get_total_duty_rate, DE_MINIMIS_THRESHOLD
from logistics import (
    estimate_freight_cost as logistics_estimate_freight,
    estimate_product_weight,
    FREIGHT_MODES,
)

# Terminal colours
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
BOLD = "\033[1m"
DIM = "\033[2m"
RESET = "\033[0m"

# Default cost assumptions (when API calls fail or are unavailable)
DEFAULT_DUTY_RATE = 0.05        # 5% default duty
DEFAULT_INSURANCE_RATE = 0.01   # 1% of goods value
DEFAULT_CUSTOMS_FEE = 25.00     # Flat customs broker fee (USD)

# Freight cost estimates per kg (fallback when API unavailable)
FREIGHT_ESTIMATES = {
    "sea": 0.30,     # $/kg ocean LCL
    "air": 4.50,     # $/kg air freight
    "express": 8.00,  # $/kg express courier
}


def _try_easyship():
    """Try to initialize EasyshipClient, return None if credentials missing."""
    try:
        return EasyshipClient()
    except CredentialError:
        return None


def _try_freightos():
    """Initialize FreightosClient (no auth needed)."""
    return FreightosClient()


def _try_exchange():
    """Initialize ExchangeRateClient (no auth needed)."""
    return ExchangeRateClient()


def run_calculate(args: Namespace) -> int:
    """Calculate full landed cost for a product."""
    product_id = getattr(args, "product_id", None)
    unit_cost = getattr(args, "unit_cost", None)
    qty = args.qty
    hs_code = getattr(args, "hs_code", None)
    origin = getattr(args, "origin", "CN")
    dest = getattr(args, "dest", "US")
    freight_mode = getattr(args, "freight_mode", None)
    sell_price = getattr(args, "sell_price", None)
    category = getattr(args, "category", None)
    weight_kg = getattr(args, "weight", None)
    dims_str = getattr(args, "dims", None)

    product = None
    product_title = "Custom Product"

    # Get product data if product_id provided
    if product_id:
        product = db.get_product(product_id)
        if not product:
            print(f"{RED}Product not found: {product_id}{RESET}")
            return 1
        product_title = product["title"]
        if unit_cost is None and product.get("price_min") is not None:
            # Use average of min/max as unit cost
            p_min = product["price_min"]
            p_max = product.get("price_max", p_min)
            unit_cost = (p_min + p_max) / 2.0
        if hs_code is None and product.get("hs_code"):
            hs_code = product["hs_code"]
        if category is None and product.get("category"):
            category = product["category"]

    if unit_cost is None:
        print(f"{RED}Unit cost required. Use --unit-cost or provide --product-id with pricing data.{RESET}")
        return 1

    total_goods = unit_cost * qty

    # --- Duty calculation (enhanced with compliance module) ---
    duty_rate = DEFAULT_DUTY_RATE
    duty_amount = 0.0
    section_301_rate = 0.0
    section_301_amount = 0.0
    mfn_rate = DEFAULT_DUTY_RATE
    used_compliance_data = False

    easyship = _try_easyship()
    if easyship and hs_code:
        print(f"{DIM}Looking up duty rate for HS {hs_code} ({origin} -> {dest})...{RESET}")
        try:
            duty_data = easyship.calculate_duties(origin, dest, hs_code, total_goods)
            # Parse duty info from response
            taxes = duty_data.get("taxes_and_duties", {})
            rate = taxes.get("import_duty_rate")
            if rate is not None:
                duty_rate = float(rate)
            amount = taxes.get("import_duty")
            if amount is not None:
                duty_amount = float(amount)
            else:
                duty_amount = total_goods * duty_rate
        except APIError as e:
            print(f"  {YELLOW}Easyship API error: {e}. Falling back to compliance database.{RESET}")
            easyship = None  # Fall through to compliance module

    if not easyship and hs_code:
        # Use compliance module for tariff data
        rate_data = get_total_duty_rate(hs_code, origin, dest)
        mfn_rate = rate_data["mfn_rate"]
        section_301_rate = rate_data["section_301_rate"]
        duty_rate = rate_data["total_rate"]
        duty_amount = total_goods * duty_rate
        section_301_amount = total_goods * section_301_rate
        used_compliance_data = True
        if duty_rate > 0:
            print(f"  {DIM}Using compliance database: HS {hs_code} -> {duty_rate:.1%} total duty{RESET}")
        else:
            print(f"  {DIM}HS chapter not in compliance database. Using default {DEFAULT_DUTY_RATE:.1%} rate.{RESET}")
            duty_rate = DEFAULT_DUTY_RATE
            duty_amount = total_goods * duty_rate
    elif not easyship and not hs_code:
        print(f"  {DIM}No HS code provided. Using default {duty_rate:.1%} duty rate.{RESET}")
        duty_amount = total_goods * duty_rate

    # --- Freight calculation (enhanced with logistics module) ---
    freight_cost = 0.0
    freight_label = freight_mode or "sea"

    # Determine weight/volume using explicit args, category, or fallback
    if weight_kg is not None:
        estimated_weight_kg = weight_kg * qty
        if dims_str:
            try:
                dims = [float(d.strip()) for d in dims_str.split("x")]
                if len(dims) == 3:
                    from logistics import calculate_cbm
                    estimated_cbm = calculate_cbm(dims[0], dims[1], dims[2], qty)
                else:
                    estimated_cbm = estimated_weight_kg * 0.003
            except (ValueError, IndexError):
                estimated_cbm = estimated_weight_kg * 0.003
        else:
            estimated_cbm = estimated_weight_kg * 0.003
    elif category:
        weight_est = estimate_product_weight(category, qty)
        estimated_weight_kg = weight_est["total_weight_kg"]
        estimated_cbm = weight_est["total_cbm"]
        print(f"  {DIM}Weight estimate ({category}): {estimated_weight_kg:.1f}kg, {estimated_cbm:.3f}CBM{RESET}")
    else:
        # Legacy fallback: 100g per unit
        estimated_weight_kg = qty * 0.1
        estimated_cbm = estimated_weight_kg * 0.003

    # Map CLI freight modes to logistics module keys
    mode_map = {
        "sea": "sea_lcl",
        "air": "air",
        "express": "express",
    }

    if freight_mode:
        # Try Freightos API first
        freightos = _try_freightos()
        try:
            print(f"{DIM}Estimating {freight_label} freight ({origin} -> {dest})...{RESET}")
            freight_data = freightos.estimate_freight(origin, dest, estimated_weight_kg)
            rate = freight_data.get("rate") or freight_data.get("cost")
            if rate is not None:
                freight_cost = float(rate)
            else:
                raise APIError("No rate returned")
        except (APIError, ConnectionError, TimeoutError, ValueError):
            # Fallback to logistics module
            logistics_mode = mode_map.get(freight_mode, freight_mode)
            est = logistics_estimate_freight(estimated_weight_kg, estimated_cbm, logistics_mode, qty)
            freight_cost = est.get("cost_avg", 0)
            freight_label = f"{freight_mode} (est.)"
            print(f"  {DIM}Using logistics estimate: ${freight_cost:.2f} ({est.get('basis', '')}){RESET}")
    else:
        # Default to sea freight via logistics module
        freight_label = "sea LCL (est.)"
        est = logistics_estimate_freight(estimated_weight_kg, estimated_cbm, "sea_lcl", qty)
        freight_cost = est.get("cost_avg", 0)

    # --- Insurance ---
    insurance = total_goods * DEFAULT_INSURANCE_RATE

    # --- Customs broker fee ---
    customs_fee = DEFAULT_CUSTOMS_FEE

    # --- Total landed cost ---
    total_landed = total_goods + duty_amount + freight_cost + insurance + customs_fee
    per_unit_landed = total_landed / qty

    # --- Margin calculation ---
    margin = None
    if sell_price is not None and sell_price > 0:
        margin = (sell_price - per_unit_landed) / sell_price * 100.0

    # --- Store in DB ---
    calc_id = db.log_cost_calc(
        quantity=qty,
        unit_cost_usd=unit_cost,
        total_landed_usd=total_landed,
        per_unit_landed_usd=per_unit_landed,
        product_id=product_id,
        hs_code=hs_code,
        duty_rate=duty_rate,
        duty_amount_usd=duty_amount,
        freight_mode=freight_label,
        freight_cost_usd=freight_cost,
        insurance_usd=insurance,
        customs_fee_usd=customs_fee,
        margin_at_price=margin,
    )

    # --- Display ---
    print(f"\n{BOLD}{CYAN}Landed Cost Breakdown — {product_title}{RESET}\n")
    print(f"  Unit cost (FOB):      ${unit_cost:.2f} x {qty:,} units = ${total_goods:,.2f}")
    if hs_code:
        print(f"  HS Code:              {hs_code}")

    # Show Section 301 breakdown when using compliance data
    if used_compliance_data and section_301_rate > 0:
        print(f"  MFN Duty ({mfn_rate:.1%}):      ${total_goods * mfn_rate:,.2f}")
        print(f"  Section 301 ({section_301_rate:.1%}): ${section_301_amount:,.2f}")
        print(f"  Total Duty ({duty_rate:.1%}):   ${duty_amount:,.2f}")
    else:
        print(f"  Import Duty ({duty_rate:.1%}):  ${duty_amount:,.2f}")

    print(f"  Freight ({freight_label}):  ${freight_cost:,.2f}")
    print(f"  Insurance:            ${insurance:,.2f}")
    print(f"  Customs broker fee:   ${customs_fee:,.2f}")
    print(f"  {'─' * 45}")
    print(f"  {BOLD}Total landed:         ${total_landed:,.2f}{RESET}")
    print(f"  {BOLD}Per unit landed:      ${per_unit_landed:,.2f}{RESET}")

    if margin is not None:
        margin_color = GREEN if margin >= 50 else (YELLOW if margin >= 25 else RED)
        print(f"\n  At retail ${sell_price:.2f}:      {margin_color}{margin:.1f}% margin{RESET}")

    # De minimis note
    if total_goods <= DE_MINIMIS_THRESHOLD:
        print(f"\n  {GREEN}Note: Goods value under ${DE_MINIMIS_THRESHOLD} may qualify for Section 321 de minimis (duty-free).{RESET}")

    print(f"\n  {DIM}Calculation saved as #{calc_id}{RESET}")

    return 0


def run_history(args: Namespace) -> int:
    """Show cost calculation history for a product."""
    product_id = args.product_id

    product = db.get_product(product_id)
    if not product:
        print(f"{RED}Product not found: {product_id}{RESET}")
        return 1

    history = db.get_cost_history(product_id, limit=20)

    if not history:
        print(f"{YELLOW}No cost calculations for: {product['title']}{RESET}")
        return 0

    print(f"\n{BOLD}{CYAN}Cost History: {product['title']}{RESET}\n")

    print(
        f"  {BOLD}{'Date':<22} {'Qty':>6}  {'Unit':>7}  {'Duty':>7}  "
        f"{'Freight':>8}  {'Landed':>8}  {'Per Unit':>8}  {'Margin':>7}{RESET}"
    )
    print(f"  {'-' * 90}")

    for c in history:
        margin_str = f"{c['margin_at_price']:.1f}%" if c.get("margin_at_price") is not None else "--"
        mode = c.get("freight_mode") or "--"
        print(
            f"  {c['calculated_at']:<22} {c['quantity']:>6,}  "
            f"${c['unit_cost_usd']:>6.2f}  ${c.get('duty_amount_usd', 0):>6.2f}  "
            f"${c.get('freight_cost_usd', 0):>7.2f}  "
            f"${c['total_landed_usd']:>7.2f}  ${c['per_unit_landed_usd']:>7.2f}  "
            f"{margin_str:>7}"
        )

    print()
    return 0


def run_hs_lookup(args: Namespace) -> int:
    """Look up HS codes by product description."""
    query = args.query

    easyship = _try_easyship()
    if not easyship:
        print(f"{RED}Easyship API credentials not configured.{RESET}")
        print(f"{DIM}Add token: security add-generic-password "
              f"-s 'product-sourcing-easyship-token' -a huxley -w '<token>' -U{RESET}")
        return 1

    print(f"{DIM}Looking up HS codes for \"{query}\"...{RESET}")

    try:
        results = easyship.lookup_hs_code(query)
    except APIError as e:
        print(f"{RED}Easyship API error: {e}{RESET}")
        return 1

    if not results:
        print(f"{YELLOW}No HS codes found for \"{query}\"{RESET}")
        return 0

    print(f"\n{BOLD}{CYAN}HS Code Results for \"{query}\"{RESET}\n")

    for i, r in enumerate(results, 1):
        code = r.get("hs_code", r.get("code", "?"))
        desc = r.get("description", "")[:60]
        duty = r.get("duty_rate")
        duty_str = f"{float(duty):.1%}" if duty is not None else "--"

        print(f"  {i:>2}. {BOLD}{code}{RESET}")
        print(f"      {desc}")
        if duty is not None:
            print(f"      Duty rate: {duty_str}")
        print()

    return 0


def run_exchange(args: Namespace) -> int:
    """Show exchange rate between two currencies."""
    from_curr = args.from_currency.upper()
    to_curr = args.to_currency.upper()

    exchange = _try_exchange()

    try:
        rate = exchange.get_rate(from_curr, to_curr)
    except APIError as e:
        print(f"{RED}Exchange rate error: {e}{RESET}")
        return 1

    print(f"\n{BOLD}{CYAN}Exchange Rate{RESET}")
    print(f"  1 {from_curr} = {GREEN}{rate:.6f}{RESET} {to_curr}")

    # Show some common conversions
    amounts = [1, 10, 100, 1000, 10000]
    print(f"\n  {BOLD}{'':>10}{from_curr:>12}  {'=':>3}  {to_curr}{RESET}")
    for amt in amounts:
        converted = amt * rate
        print(f"  {'':<10}{amt:>12,.2f}  {'=':>3}  {converted:,.2f}")

    # Show cached info
    pair = f"{from_curr}_{to_curr}"
    cached = db.get_exchange_rate(pair)
    if cached:
        print(f"\n  {DIM}Cached at: {cached['fetched_at']} (4hr TTL){RESET}")

    return 0


def run(args: Namespace) -> int:
    """Route cost subcommands."""
    action = getattr(args, "cost_action", None)

    if action == "calculate":
        return run_calculate(args)
    elif action == "history":
        return run_history(args)
    elif action == "hs-lookup":
        return run_hs_lookup(args)
    elif action == "exchange":
        return run_exchange(args)
    else:
        print(f"{YELLOW}Usage: product-sourcing cost <calculate|history|hs-lookup|exchange>{RESET}",
              file=sys.stderr)
        return 1
