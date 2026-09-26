"""
Negotiation intelligence commands — templates, payment terms, strategy advice.

Commands:
    negotiate template <stage>                         Get message template
    negotiate terms <order-value>                      Payment terms recommendation
    negotiate strategy <scenario>                      Get strategy advice
    negotiate discount <base-price> --quantities "..."  Volume discount estimate
"""

import sys
from argparse import Namespace
from pathlib import Path

_TOOL_DIR = Path(__file__).resolve().parent.parent
if str(_TOOL_DIR) not in sys.path:
    sys.path.insert(0, str(_TOOL_DIR))

from negotiation import (
    get_template,
    get_payment_recommendation,
    get_negotiation_strategy,
    estimate_volume_discount,
    MESSAGE_TEMPLATES,
    PAYMENT_TERMS,
    NEGOTIATION_STRATEGIES,
)

# Terminal colours
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
BOLD = "\033[1m"
DIM = "\033[2m"
RESET = "\033[0m"


def run_template(args: Namespace) -> int:
    """Get a negotiation message template."""
    stage = args.stage

    template = get_template(stage)
    if template.startswith("Template '"):
        # Not found — show available
        print(f"{YELLOW}{template}{RESET}")
        return 1

    print(f"\n{BOLD}{CYAN}Template: {stage.replace('_', ' ').title()}{RESET}\n")
    print(f"{DIM}{'─' * 60}{RESET}")
    print(template)
    print(f"{DIM}{'─' * 60}{RESET}")
    print(f"\n{DIM}Replace {{placeholders}} with your actual values.{RESET}")
    print(f"{DIM}Available templates: {', '.join(sorted(MESSAGE_TEMPLATES.keys()))}{RESET}")

    print()
    return 0


def run_terms(args: Namespace) -> int:
    """Payment terms recommendation based on order value."""
    order_value = args.order_value
    supplier_score = getattr(args, "supplier_score", 50.0)
    first_order = getattr(args, "first_order", True)

    rec = get_payment_recommendation(order_value, supplier_score, first_order)

    print(f"\n{BOLD}{CYAN}Payment Terms Recommendation{RESET}")
    print(f"  Order Value: ${order_value:,.2f}")
    print(f"  Supplier Score: {supplier_score:.0f}/100")
    print(f"  First Order: {'Yes' if first_order else 'No'}\n")

    # Recommended
    details = rec.get("recommended_details", {})
    print(f"  {GREEN}{BOLD}Recommended: {details.get('name', rec['recommended'])}{RESET}")
    print(f"  {details.get('description', '')}")
    print(f"  Risk: {details.get('risk', '--')}")
    print(f"  Use when: {details.get('use_when', '--')}")
    if details.get("notes"):
        print(f"  {DIM}Note: {details['notes']}{RESET}")

    # Reasoning
    print(f"\n  {BOLD}Reasoning:{RESET}")
    for r in rec.get("reasoning", []):
        print(f"    - {r}")

    # Alternatives
    alts = rec.get("alternatives", [])
    if alts:
        print(f"\n  {BOLD}Alternatives:{RESET}")
        for alt in alts:
            alt_name = alt.get("name", alt.get("term", "?"))
            print(f"    - {alt_name}: {alt.get('description', '')}")

    # Full payment terms reference
    print(f"\n  {BOLD}All Payment Terms:{RESET}")
    for key, term in PAYMENT_TERMS.items():
        risk = term.get("risk", "?")
        if "high" in risk:
            rc = RED
        elif "moderate" in risk:
            rc = YELLOW
        elif "low" in risk:
            rc = GREEN
        else:
            rc = DIM
        print(f"    {term['name']:<30} {rc}risk: {risk}{RESET}")

    print()
    return 0


def run_strategy(args: Namespace) -> int:
    """Get negotiation strategy advice for a scenario."""
    scenario = args.scenario

    strat = get_negotiation_strategy(scenario)
    if not strat:
        print(f"{YELLOW}Scenario '{scenario}' not found.{RESET}")
        print(f"\n{DIM}Available scenarios:{RESET}")
        for s in NEGOTIATION_STRATEGIES:
            print(f"  - {s['scenario']}")
        return 1

    print(f"\n{BOLD}{CYAN}Negotiation Strategy: {scenario.replace('_', ' ').title()}{RESET}\n")

    print(f"  {BOLD}Strategy:{RESET}")
    print(f"  {strat['strategy']}")

    print(f"\n  {BOLD}Leverage Points:{RESET}")
    for point in strat.get("leverage_points", []):
        print(f"    {GREEN}+{RESET} {point}")

    mistakes = strat.get("common_mistakes", [])
    if mistakes:
        print(f"\n  {BOLD}{RED}Common Mistakes to Avoid:{RESET}")
        for mistake in mistakes:
            print(f"    {RED}x{RESET} {mistake}")

    print()
    return 0


def run_discount(args: Namespace) -> int:
    """Estimate volume discounts."""
    base_price = args.base_price
    quantities_str = getattr(args, "quantities", "")

    if not quantities_str:
        print(f"{RED}Provide quantities with --quantities (comma-separated).{RESET}")
        return 1

    try:
        quantities = [int(q.strip()) for q in quantities_str.split(",")]
    except ValueError:
        print(f"{RED}Invalid quantities. Use comma-separated integers: --quantities \"100,500,1000\"{RESET}")
        return 1

    estimates = estimate_volume_discount(base_price, quantities)

    print(f"\n{BOLD}{CYAN}Volume Discount Estimate{RESET}")
    print(f"  Base price: ${base_price:.4f}/unit\n")

    print(f"  {BOLD}{'Quantity':>10}  {'Unit Price':>12}  {'Discount':>10}  {'Total':>12}  {'Savings':>10}{RESET}")
    print(f"  {'─' * 60}")

    for est in estimates:
        discount_color = GREEN if est["discount_pct"] >= 10 else (YELLOW if est["discount_pct"] >= 5 else DIM)
        print(
            f"  {est['quantity']:>10,}  "
            f"${est['estimated_price']:>11.4f}  "
            f"{discount_color}{est['discount_pct']:>9.1f}%{RESET}  "
            f"${est['total_cost']:>11,.2f}  "
            f"${est['savings_vs_base']:>9,.2f}"
        )

    print(f"\n  {DIM}Estimates based on typical China manufacturing discount curves.{RESET}")
    print(f"  {DIM}Actual discounts vary by product, supplier, and relationship.{RESET}")

    print()
    return 0


def run(args: Namespace) -> int:
    """Route negotiate subcommands."""
    action = getattr(args, "negotiate_action", None)

    if action == "template":
        return run_template(args)
    elif action == "terms":
        return run_terms(args)
    elif action == "strategy":
        return run_strategy(args)
    elif action == "discount":
        return run_discount(args)
    else:
        print(
            f"{YELLOW}Usage: product-sourcing negotiate "
            f"<template|terms|strategy|discount>{RESET}",
            file=sys.stderr,
        )
        return 1
