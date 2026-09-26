"""
Trade compliance commands — tariff lookup, requirements, and Incoterms reference.

Commands:
    compliance check <product-id>       Show stored compliance status for a product
    compliance requirements <category>  Show US import requirements for a product category
    compliance tariff <hs-code>         Look up tariff rate including Section 301
    compliance incoterms [term]         Show Incoterms reference (all or specific)
"""

import sys
from argparse import Namespace
from pathlib import Path

_TOOL_DIR = Path(__file__).resolve().parent.parent
if str(_TOOL_DIR) not in sys.path:
    sys.path.insert(0, str(_TOOL_DIR))

import db
from compliance import (
    get_total_duty_rate,
    get_compliance_requirements,
    get_incoterm,
    estimate_total_duties,
    PRODUCT_COMPLIANCE,
    INCOTERMS,
    DE_MINIMIS_THRESHOLD,
)

# Terminal colours
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
BOLD = "\033[1m"
DIM = "\033[2m"
RESET = "\033[0m"


def run_check(args: Namespace) -> int:
    """Show stored compliance checks for a product."""
    product_id = args.product_id

    product = db.get_product(product_id)
    if not product:
        print(f"{RED}Product not found: {product_id}{RESET}")
        return 1

    checks = db.get_compliance_checks(product_id)

    if not checks:
        print(f"{YELLOW}No compliance checks recorded for: {product['title']}{RESET}")
        print(f"{DIM}Use 'compliance requirements <category>' to see what's needed.{RESET}")
        return 0

    print(f"\n{BOLD}{CYAN}Compliance Status: {product['title']}{RESET}\n")

    print(f"  {BOLD}{'Agency':<10} {'Requirement':<35} {'Status':<12} {'Est Cost':>10}  {'Actual':>10}{RESET}")
    print(f"  {'─' * 85}")

    for c in checks:
        status = c["status"]
        if status == "passed":
            status_color = GREEN
        elif status == "failed":
            status_color = RED
        elif status == "in_progress":
            status_color = YELLOW
        else:
            status_color = DIM

        est = f"${c['estimated_cost']:,.0f}" if c.get("estimated_cost") else "--"
        actual = f"${c['actual_cost']:,.0f}" if c.get("actual_cost") else "--"
        agency = (c.get("agency") or "--")[:9]
        req = c["requirement"][:34]

        print(
            f"  {agency:<10} {req:<35} "
            f"{status_color}{status:<12}{RESET} "
            f"{est:>10}  {actual:>10}"
        )

    print()
    return 0


def run_requirements(args: Namespace) -> int:
    """Show US import compliance requirements for a product category."""
    category = args.category.lower()

    reqs = get_compliance_requirements(category)
    if not reqs:
        print(f"{YELLOW}Category '{category}' not found.{RESET}")
        print(f"\n{DIM}Available categories:{RESET}")
        for cat in sorted(PRODUCT_COMPLIANCE.keys()):
            print(f"  - {cat}")
        return 1

    print(f"\n{BOLD}{CYAN}US Import Requirements: {category.replace('_', ' ').title()}{RESET}\n")

    # Requirements table
    requirements = reqs.get("requirements", [])
    if requirements:
        print(f"  {BOLD}{'Agency':<10} {'Type':<40} {'Cost':<18} {'Timeline':<14} {'Req?'}{RESET}")
        print(f"  {'─' * 95}")

        for r in requirements:
            agency = r.get("agency", "--")[:9]
            rtype = r.get("type", "--")[:39]
            cost = r.get("cost_range", "--")[:17]
            timeline = r.get("timeline_weeks", (0, 0))
            if isinstance(timeline, tuple):
                if timeline[0] == 0 and timeline[1] == 0:
                    tl = "none"
                else:
                    tl = f"{timeline[0]}-{timeline[1]} weeks"
            else:
                tl = str(timeline)
            mandatory = f"{RED}YES{RESET}" if r.get("mandatory") else f"{DIM}opt{RESET}"

            print(f"  {agency:<10} {rtype:<40} {cost:<18} {tl:<14} {mandatory}")

    # Labeling requirements
    labeling = reqs.get("labeling", [])
    if labeling:
        print(f"\n  {BOLD}Labeling Requirements:{RESET}")
        for label in labeling:
            print(f"    - {label}")

    # Warnings
    warnings = reqs.get("warnings", [])
    if warnings:
        print(f"\n  {BOLD}{YELLOW}Warnings:{RESET}")
        for warn in warnings:
            print(f"    {YELLOW}!{RESET} {warn}")

    print()
    return 0


def run_tariff(args: Namespace) -> int:
    """Look up tariff rate for an HS code including Section 301."""
    hs_code = args.hs_code
    origin = getattr(args, "origin", "CN")
    dest = getattr(args, "dest", "US")
    value = getattr(args, "value", 10000.0)

    rates = get_total_duty_rate(hs_code, origin, dest)
    duties = estimate_total_duties(hs_code, value, origin, dest)

    chapter = rates.get("chapter", hs_code[:2])
    desc = rates.get("mfn_description", "Unknown chapter")

    print(f"\n{BOLD}{CYAN}Tariff Lookup: HS {hs_code} ({desc}){RESET}\n")

    mfn_pct = rates["mfn_rate"] * 100
    s301_pct = rates["section_301_rate"] * 100
    total_pct = rates["total_rate"] * 100

    print(f"  MFN Duty Rate:        {mfn_pct:.1f}%")

    if rates["section_301_rate"] > 0:
        s301_list = rates.get("section_301_list", "?")
        print(f"  Section 301 (List {s301_list}): {s301_pct:.1f}%")
    else:
        print(f"  Section 301:          {DIM}Not applicable{RESET}")

    print(f"  {'─' * 35}")
    total_color = RED if total_pct > 20 else (YELLOW if total_pct > 10 else GREEN)
    print(f"  {BOLD}Total Estimated Duty: {total_color}{total_pct:.1f}%{RESET}")

    # Show dollar amounts
    print(f"\n  On ${value:,.2f} goods value ({origin} -> {dest}):")
    print(f"    MFN Duty:           ${duties['mfn_duty']:,.2f}")
    if duties["section_301_duty"] > 0:
        print(f"    Section 301:        ${duties['section_301_duty']:,.2f}")
    print(f"    {BOLD}Total Duty:         ${duties['total_duty']:,.2f}{RESET}")

    # De minimis note
    if value <= DE_MINIMIS_THRESHOLD:
        print(f"\n  {GREEN}Section 321 de minimis: Shipment under ${DE_MINIMIS_THRESHOLD} may be duty-free.{RESET}")

    # Notes
    if rates.get("notes"):
        print(f"\n  {DIM}Notes: {rates['notes']}{RESET}")

    print()
    return 0


def run_incoterms(args: Namespace) -> int:
    """Show Incoterms reference."""
    term = getattr(args, "term", None)

    if term:
        info = get_incoterm(term)
        if not info:
            print(f"{RED}Incoterm '{term}' not found.{RESET}")
            print(f"{DIM}Valid terms: {', '.join(sorted(INCOTERMS.keys()))}{RESET}")
            return 1

        print(f"\n{BOLD}{CYAN}{term.upper()} — {info['name']}{RESET}\n")
        print(f"  Risk transfers:  {info['risk_transfers']}")
        print(f"  Seller pays:     {info['seller_pays']}")
        print(f"  Buyer pays:      {info['buyer_pays']}")
        print(f"  Transport modes: {info['modes']}")
        print(f"  Use when:        {info['use_when']}")
        print(f"  Risk level:      {info['risk_level']}")
        print()
        return 0

    # Show all Incoterms
    print(f"\n{BOLD}{CYAN}Incoterms 2020 Reference{RESET}\n")

    print(f"  {BOLD}{'Code':<6} {'Name':<35} {'Risk Level':<20} {'Modes'}{RESET}")
    print(f"  {'─' * 85}")

    for code in ["EXW", "FCA", "FAS", "FOB", "CFR", "CIF", "CPT", "CIP", "DAP", "DPU", "DDP"]:
        info = INCOTERMS[code]
        risk = info["risk_level"]
        if "very_low" in risk:
            risk_color = GREEN
        elif "low" in risk:
            risk_color = GREEN
        elif "moderate" in risk:
            risk_color = YELLOW
        else:
            risk_color = RED

        print(
            f"  {BOLD}{code:<6}{RESET} {info['name']:<35} "
            f"{risk_color}{risk:<20}{RESET} {info['modes']}"
        )

    print(f"\n  {DIM}Use 'compliance incoterms <CODE>' for full details on a specific term.{RESET}")
    print()
    return 0


def run(args: Namespace) -> int:
    """Route compliance subcommands."""
    action = getattr(args, "compliance_action", None)

    if action == "check":
        return run_check(args)
    elif action == "requirements":
        return run_requirements(args)
    elif action == "tariff":
        return run_tariff(args)
    elif action == "incoterms":
        return run_incoterms(args)
    else:
        print(
            f"{YELLOW}Usage: product-sourcing compliance "
            f"<check|requirements|tariff|incoterms>{RESET}",
            file=sys.stderr,
        )
        return 1
