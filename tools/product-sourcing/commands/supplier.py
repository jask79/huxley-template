"""
Supplier intelligence — list, search, inspect, and score suppliers.

Commands:
    supplier list [--platform X] [--limit N]    List tracked suppliers
    supplier show <supplier_id>                 Detailed supplier view
    supplier search "query" [--platform X]      Search by name/products
    supplier score <supplier_id>                Re-score and show history
"""

import sys
from argparse import Namespace
from pathlib import Path

_TOOL_DIR = Path(__file__).resolve().parent.parent
if str(_TOOL_DIR) not in sys.path:
    sys.path.insert(0, str(_TOOL_DIR))

import db
from scoring import score_supplier, interpret_score

# Terminal colours
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
BOLD = "\033[1m"
DIM = "\033[2m"
RESET = "\033[0m"


def _score_color(score):
    """Return ANSI color for a score value."""
    if score is None:
        return DIM
    if score >= 75:
        return GREEN
    elif score >= 50:
        return YELLOW
    return RED


def _yn(val):
    """Format boolean-ish value as Y/N."""
    return f"{GREEN}Y{RESET}" if val else f"{RED}N{RESET}"


def _fmt_rate(val):
    """Format a rate (0-1) as percentage."""
    if val is None:
        return f"{DIM}--{RESET}"
    return f"{val:.0%}"


def run_list(args: Namespace) -> int:
    """List tracked suppliers."""
    platform = getattr(args, "platform", None)
    limit = getattr(args, "limit", 50)

    suppliers = db.list_suppliers(platform=platform, limit=limit)

    if not suppliers:
        print(f"{YELLOW}No suppliers tracked yet.{RESET}")
        print(f"{DIM}Run a search first: product-sourcing search \"your query\"{RESET}")
        return 0

    title = f"Tracked Suppliers ({len(suppliers)})"
    if platform:
        title += f" — {platform}"
    print(f"\n{BOLD}{CYAN}{title}{RESET}\n")

    # Header
    print(
        f"  {BOLD}{'#':>3}  {'Score':>5}  {'Supplier':<30} {'Platform':<10} "
        f"{'Type':<12} {'Gold':>4}  {'TA':>2}  {'Txns':>6}{RESET}"
    )
    print(f"  {'=' * 90}")

    for i, s in enumerate(suppliers, 1):
        score = s.get("quality_score")
        sc = _score_color(score)
        score_str = f"{score:.1f}" if score is not None else "--"
        name = s["name"][:29]
        plat = s["platform"][:9]
        stype = s.get("supplier_type", "?")[:11]
        gold = s.get("gold_years", 0)
        gold_str = f"{gold}yr" if gold > 0 else f"{DIM}--{RESET}"
        ta = _yn(s.get("trade_assurance"))
        txns = s.get("transaction_count", 0)
        txn_str = f"{txns:,}" if txns > 0 else f"{DIM}0{RESET}"

        print(
            f"  {i:>3}  {sc}{score_str:>5}{RESET}  {name:<30} {plat:<10} "
            f"{stype:<12} {gold_str:>4}  {ta:>2}  {txn_str:>6}"
        )

    print()
    return 0


def run_show(args: Namespace) -> int:
    """Show detailed supplier information."""
    supplier_id = args.supplier_id

    supplier = db.get_supplier(supplier_id)
    if not supplier:
        print(f"{RED}Supplier not found: {supplier_id}{RESET}")
        return 1

    score = supplier.get("quality_score")
    sc = _score_color(score)
    interp = interpret_score(score) if score is not None else "Unscored"

    print(f"\n{BOLD}{CYAN}Supplier: {supplier['name']}{RESET}")
    if supplier.get("name_cn"):
        print(f"  {DIM}{supplier['name_cn']}{RESET}")
    print()

    # Identity
    print(f"  {BOLD}ID:{RESET}            {supplier['supplier_id']}")
    print(f"  {BOLD}Platform:{RESET}       {supplier['platform']}")
    print(f"  {BOLD}URL:{RESET}            {supplier['url']}")
    print(f"  {BOLD}Location:{RESET}       {supplier.get('location') or '--'}")
    print(f"  {BOLD}Type:{RESET}           {supplier.get('supplier_type', 'unknown')}")
    print(f"  {BOLD}Established:{RESET}    {supplier.get('year_established') or '--'}")
    print(f"  {BOLD}Employees:{RESET}      {supplier.get('employee_count') or '--'}")
    print()

    # Trust metrics
    print(f"  {BOLD}Trust Metrics{RESET}")
    print(f"    Gold Supplier:    {supplier.get('gold_years', 0)} years")
    print(f"    Trade Assurance:  {_yn(supplier.get('trade_assurance'))}")
    print(f"    Verified:         {_yn(supplier.get('verified'))}")
    print(f"    Transactions:     {supplier.get('transaction_count', 0):,}")
    print(f"    Response Rate:    {_fmt_rate(supplier.get('response_rate'))}")
    print(f"    On-Time Delivery: {_fmt_rate(supplier.get('on_time_delivery'))}")
    print()

    # Score
    score_str = f"{score:.1f}" if score is not None else "--"
    print(f"  {BOLD}Quality Score:{RESET}  {sc}{score_str}{RESET} ({interp})")

    # Red flags
    flags = supplier.get("red_flags", [])
    if flags:
        print(f"\n  {BOLD}Red Flags:{RESET}")
        for f in flags:
            icon = f"{RED}x{RESET}" if isinstance(f, str) else f"{RED}x{RESET}"
            print(f"    {icon} {f}")
    print()

    # Main products
    if supplier.get("main_products"):
        print(f"  {BOLD}Main Products:{RESET} {supplier['main_products']}")

    # Notes
    if supplier.get("notes"):
        print(f"  {BOLD}Notes:{RESET} {supplier['notes']}")

    # Products from this supplier
    products = db.list_products_by_supplier(supplier_id, limit=10)
    if products:
        print(f"\n  {BOLD}Products ({len(products)}){RESET}")
        for p in products:
            price_str = ""
            if p.get("price_min") is not None:
                if p.get("price_max") and p["price_max"] != p["price_min"]:
                    price_str = f"${p['price_min']:.2f}-${p['price_max']:.2f}"
                else:
                    price_str = f"${p['price_min']:.2f}"
            moq_str = f"MOQ {p['moq']}" if p.get("moq") else ""
            print(f"    [{p['product_id']}] {p['title'][:50]}  {price_str}  {moq_str}")

    # Recent RFQs
    rfqs = db.list_rfqs(supplier_id=supplier_id, limit=5)
    if rfqs:
        print(f"\n  {BOLD}Recent RFQs ({len(rfqs)}){RESET}")
        for r in rfqs:
            status_color = GREEN if r["status"] == "accepted" else (
                RED if r["status"] == "rejected" else YELLOW)
            print(
                f"    [RFQ-{r['rfq_id']}] {status_color}{r['status']}{RESET} "
                f"— {r['description'][:40]}"
            )

    # Timestamps
    print(f"\n  {DIM}First seen: {supplier['first_seen']}{RESET}")
    print(f"  {DIM}Last updated: {supplier['last_updated']}{RESET}")

    return 0


def run_search(args: Namespace) -> int:
    """Search suppliers by name or products."""
    query = args.query
    platform = getattr(args, "platform", None)

    results = db.search_suppliers(query, platform=platform)

    if not results:
        print(f"{YELLOW}No suppliers found matching \"{query}\"{RESET}")
        return 0

    print(f"\n{BOLD}{CYAN}Supplier Search: \"{query}\" ({len(results)} results){RESET}\n")

    for i, s in enumerate(results, 1):
        score = s.get("quality_score")
        sc = _score_color(score)
        score_str = f"{score:.1f}" if score is not None else "--"
        name = s["name"][:35]
        plat = s["platform"]
        stype = s.get("supplier_type", "?")

        print(f"  {i:>2}. {sc}{score_str:>5}{RESET}  {name}  {DIM}({plat}, {stype}){RESET}")
        if s.get("main_products"):
            print(f"      {DIM}{s['main_products'][:60]}{RESET}")

    print()
    return 0


def run_score(args: Namespace) -> int:
    """Re-score a supplier and show score history."""
    supplier_id = args.supplier_id

    supplier = db.get_supplier(supplier_id)
    if not supplier:
        print(f"{RED}Supplier not found: {supplier_id}{RESET}")
        return 1

    # Re-score
    score, breakdown, red_flags = score_supplier(supplier)
    db.update_supplier_score(supplier_id, score)
    db.log_score(supplier_id, score, breakdown)

    sc = _score_color(score)
    interp = interpret_score(score)

    print(f"\n{BOLD}{CYAN}Scoring: {supplier['name']}{RESET}")
    print(f"  {BOLD}Overall Score:{RESET}  {sc}{score:.1f}{RESET} ({interp})")
    print(f"  {BOLD}Confidence:{RESET}     {breakdown['confidence_level']}")
    print(f"  {BOLD}Factors Used:{RESET}   {breakdown['available_count']}/{breakdown['total_factors']}")
    print()

    # Factor breakdown
    print(f"  {BOLD}Factor Breakdown{RESET}")
    print(f"  {'Factor':<24} {'Score':>6}  {'Weight':>6}  {'Adj.Wt':>6}")
    print(f"  {'-' * 50}")

    factors = breakdown.get("factors", {})
    for name, detail in factors.items():
        raw = detail.get("raw_score")
        raw_str = f"{raw:.1f}" if raw is not None else f"{DIM}N/A{RESET}"
        wt = f"{detail['weight']:.3f}"
        adj = f"{detail['adjusted_weight']:.3f}"
        label = name.replace("_", " ").title()
        print(f"  {label:<24} {raw_str:>6}  {wt:>6}  {adj:>6}")

    print(f"\n  {DIM}Raw: {breakdown['raw_score']:.1f} "
          f"-> Confidence ({breakdown['confidence_penalty']:.2f}): {breakdown['after_confidence']:.1f} "
          f"-> Red flags (-{breakdown['red_flag_penalty']:.1f}): {breakdown['final_score']:.1f}{RESET}")

    # Red flags
    if red_flags:
        print(f"\n  {BOLD}Red Flags ({len(red_flags)}){RESET}")
        for f in red_flags:
            sev = f["severity"]
            icon = f"{RED}CRITICAL{RESET}" if sev == "CRITICAL" else f"{YELLOW}WARNING{RESET}"
            print(f"    [{f['code']}] {icon} {f['desc']} (-{f['penalty']:.1f})")

    # Score history
    history = db.get_score_history(supplier_id, limit=10)
    if len(history) > 1:
        print(f"\n  {BOLD}Score History{RESET}")
        for h in history[:10]:
            print(f"    {h['scored_at']}  {h['overall_score']:.1f}")

    print()
    return 0


def run(args: Namespace) -> int:
    """Route supplier subcommands."""
    action = getattr(args, "supplier_action", None)

    if action == "list":
        return run_list(args)
    elif action == "show":
        return run_show(args)
    elif action == "search":
        return run_search(args)
    elif action == "score":
        return run_score(args)
    else:
        print(f"{YELLOW}Usage: product-sourcing supplier <list|show|search|score>{RESET}",
              file=sys.stderr)
        return 1
