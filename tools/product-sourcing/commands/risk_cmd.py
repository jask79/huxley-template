"""
Supply chain risk assessment commands.

Commands:
    risk assess <supplier-id>    Full risk assessment for a supplier
    risk report                  Portfolio-wide risk summary
    risk concentration           Supplier concentration analysis
    risk scams <supplier-id>     Check for scam indicators
"""

import sys
from argparse import Namespace
from pathlib import Path

_TOOL_DIR = Path(__file__).resolve().parent.parent
if str(_TOOL_DIR) not in sys.path:
    sys.path.insert(0, str(_TOOL_DIR))

import db
from risk import (
    assess_supplier_risk,
    assess_concentration_risk,
    get_scam_indicators,
    SOURCING_SCAMS,
)

# Terminal colours
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
BOLD = "\033[1m"
DIM = "\033[2m"
RESET = "\033[0m"


def _risk_color(score: float) -> str:
    """Return ANSI color for a risk score."""
    if score < 30:
        return GREEN
    elif score < 60:
        return YELLOW
    elif score < 80:
        return RED
    else:
        return f"{RED}{BOLD}"


def run_assess(args: Namespace) -> int:
    """Full risk assessment for a supplier."""
    supplier_id = args.supplier_id

    supplier = db.get_supplier(supplier_id)
    if not supplier:
        print(f"{RED}Supplier not found: {supplier_id}{RESET}")
        return 1

    assessment = assess_supplier_risk(supplier)
    overall = assessment["overall_risk"]
    level = assessment["risk_level"]
    factors = assessment["factors"]
    recommendations = assessment["recommendations"]

    color = _risk_color(overall)

    print(f"\n{BOLD}{CYAN}Risk Assessment: {supplier['name']}{RESET}")
    print(f"  {DIM}ID: {supplier_id} | Platform: {supplier['platform']}{RESET}\n")

    print(f"  {BOLD}Overall Risk Score: {color}{overall:.1f}/100 ({level}){RESET}\n")

    # Factor breakdown
    print(f"  {BOLD}{'Factor':<22} {'Score':>7}  {'Level':<12}{RESET}")
    print(f"  {'─' * 45}")

    for factor_name, score in sorted(factors.items()):
        fc = _risk_color(score)
        factor_label = factor_name.replace("_", " ").title()
        factor_level = "LOW" if score < 30 else ("MODERATE" if score < 60 else ("HIGH" if score < 80 else "CRITICAL"))
        print(f"  {factor_label:<22} {fc}{score:>6.1f}{RESET}  {factor_level:<12}")

    # Recommendations
    if recommendations:
        print(f"\n  {BOLD}Recommendations:{RESET}")
        for i, rec in enumerate(recommendations, 1):
            print(f"    {i}. {rec}")

    # Store assessment
    assessment_id = db.log_risk_assessment(
        supplier_id=supplier_id,
        overall_risk=overall,
        breakdown=factors,
        recommendations=recommendations,
        geographic_risk=factors.get("geographic"),
        financial_risk=factors.get("financial"),
        quality_risk=factors.get("quality"),
        lead_time_risk=factors.get("lead_time"),
        compliance_risk=factors.get("compliance"),
    )
    print(f"\n  {DIM}Assessment saved as #{assessment_id}{RESET}")

    print()
    return 0


def run_report(args: Namespace) -> int:
    """Portfolio-wide risk summary across all suppliers."""
    suppliers = db.list_suppliers(limit=200)

    if not suppliers:
        print(f"{YELLOW}No suppliers in database.{RESET}")
        return 0

    print(f"\n{BOLD}{CYAN}Portfolio Risk Report{RESET}")
    print(f"  {DIM}{len(suppliers)} suppliers tracked{RESET}\n")

    # Assess each supplier
    risk_data = []
    for s in suppliers:
        assessment = assess_supplier_risk(s)
        risk_data.append({
            "supplier_id": s["supplier_id"],
            "name": s["name"],
            "platform": s["platform"],
            "overall_risk": assessment["overall_risk"],
            "risk_level": assessment["risk_level"],
        })

    # Sort by risk (highest first)
    risk_data.sort(key=lambda x: x["overall_risk"], reverse=True)

    # Summary stats
    risk_scores = [r["overall_risk"] for r in risk_data]
    avg_risk = sum(risk_scores) / len(risk_scores)
    critical = sum(1 for s in risk_scores if s >= 80)
    high = sum(1 for s in risk_scores if 60 <= s < 80)
    moderate = sum(1 for s in risk_scores if 30 <= s < 60)
    low = sum(1 for s in risk_scores if s < 30)

    avg_color = _risk_color(avg_risk)
    print(f"  Average Risk Score: {avg_color}{avg_risk:.1f}{RESET}")
    print(f"  {RED}Critical: {critical}{RESET}  |  "
          f"{RED}High: {high}{RESET}  |  "
          f"{YELLOW}Moderate: {moderate}{RESET}  |  "
          f"{GREEN}Low: {low}{RESET}\n")

    # Table
    print(f"  {BOLD}{'#':>3}  {'Risk':>5}  {'Level':<10} {'Supplier':<30} {'Platform':<10}{RESET}")
    print(f"  {'─' * 65}")

    for i, r in enumerate(risk_data[:20], 1):
        color = _risk_color(r["overall_risk"])
        name = r["name"][:29]
        print(
            f"  {i:>3}  {color}{r['overall_risk']:>5.1f}{RESET}  "
            f"{r['risk_level']:<10} {name:<30} {r['platform']:<10}"
        )

    if len(risk_data) > 20:
        print(f"  {DIM}... and {len(risk_data) - 20} more{RESET}")

    print()
    return 0


def run_concentration(args: Namespace) -> int:
    """Supplier concentration analysis."""
    suppliers = db.list_suppliers(limit=200)

    if not suppliers:
        print(f"{YELLOW}No suppliers in database.{RESET}")
        return 0

    analysis = assess_concentration_risk(suppliers)

    print(f"\n{BOLD}{CYAN}Supplier Concentration Analysis{RESET}\n")

    conc_risk = analysis["concentration_risk"]
    color = _risk_color(conc_risk)
    print(f"  Concentration Risk: {color}{conc_risk:.1f}/100 ({analysis['risk_level']}){RESET}")
    print(f"  HHI Index: {analysis['hhi']:.4f}")
    print(f"  Total Suppliers: {analysis['total_suppliers']}")

    # Geographic concentration
    geo = analysis.get("geographic_concentration", {})
    if geo:
        print(f"\n  {BOLD}Geographic Distribution:{RESET}")
        for region, share in sorted(geo.items(), key=lambda x: x[1], reverse=True):
            bar_len = int(share * 40)
            bar = "█" * bar_len
            pct = share * 100
            print(f"    {region[:20]:<20} {bar} {pct:.0f}%")

    # Recommendations
    recs = analysis.get("recommendations", [])
    if recs:
        print(f"\n  {BOLD}Recommendations:{RESET}")
        for rec in recs:
            print(f"    {YELLOW}!{RESET} {rec}")

    print()
    return 0


def run_scams(args: Namespace) -> int:
    """Check a supplier against known scam patterns."""
    supplier_id = args.supplier_id

    supplier = db.get_supplier(supplier_id)
    if not supplier:
        print(f"{RED}Supplier not found: {supplier_id}{RESET}")
        return 1

    indicators = get_scam_indicators(supplier)

    print(f"\n{BOLD}{CYAN}Scam Indicator Check: {supplier['name']}{RESET}")
    print(f"  {DIM}ID: {supplier_id} | Platform: {supplier['platform']}{RESET}\n")

    if not indicators:
        print(f"  {GREEN}No scam indicators detected.{RESET}")
        print(f"  {DIM}This does not guarantee safety — always do due diligence.{RESET}")
    else:
        print(f"  {RED}{BOLD}{len(indicators)} indicator(s) found:{RESET}\n")
        for i, ind in enumerate(indicators, 1):
            conf = ind.get("confidence", "low")
            if conf == "high":
                conf_color = RED
            elif conf == "medium":
                conf_color = YELLOW
            else:
                conf_color = DIM

            print(f"  {i}. {BOLD}{ind['scam_type'].replace('_', ' ').title()}{RESET}")
            print(f"     Confidence: {conf_color}{conf}{RESET}")
            print(f"     Reason: {ind['reason']}")
            print(f"     Prevention: {ind['prevention']}")
            print()

    # Also show the scam pattern reference
    print(f"\n  {BOLD}Common Sourcing Scams Reference:{RESET}")
    for scam in SOURCING_SCAMS:
        print(f"    {BOLD}{scam['name'].replace('_', ' ').title()}{RESET}: {scam['description']}")

    print()
    return 0


def run(args: Namespace) -> int:
    """Route risk subcommands."""
    action = getattr(args, "risk_action", None)

    if action == "assess":
        return run_assess(args)
    elif action == "report":
        return run_report(args)
    elif action == "concentration":
        return run_concentration(args)
    elif action == "scams":
        return run_scams(args)
    else:
        print(
            f"{YELLOW}Usage: product-sourcing risk "
            f"<assess|report|concentration|scams>{RESET}",
            file=sys.stderr,
        )
        return 1
