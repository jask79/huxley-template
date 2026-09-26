"""
Comparison commands — side-by-side supplier, product, and quote comparisons.

Commands:
    compare suppliers <id1> <id2> [id3...]   Side-by-side supplier comparison
    compare products <id1> <id2> [id3...]    Side-by-side product comparison
    compare quotes <rfq1> <rfq2> [rfq3...]   Multi-quote comparison matrix
"""

import sys
from argparse import Namespace
from pathlib import Path
from typing import Any, Dict, List

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


def _highlight_best(values: List, reverse: bool = False) -> List[str]:
    """
    Return formatted strings highlighting the best value in GREEN.

    Args:
        values: List of comparable values (float, int, or None).
        reverse: If True, lower is better (e.g. price, risk).
    """
    numeric = [(i, v) for i, v in enumerate(values) if v is not None and isinstance(v, (int, float))]
    if not numeric:
        return [f"{DIM}--{RESET}" if v is None else str(v) for v in values]

    if reverse:
        best_val = min(v for _, v in numeric)
    else:
        best_val = max(v for _, v in numeric)

    result = []
    for i, v in enumerate(values):
        if v is None:
            result.append(f"{DIM}--{RESET}")
        elif isinstance(v, (int, float)) and v == best_val:
            if isinstance(v, float):
                result.append(f"{GREEN}{BOLD}{v:.2f}{RESET}")
            else:
                result.append(f"{GREEN}{BOLD}{v}{RESET}")
        else:
            if isinstance(v, float):
                result.append(f"{v:.2f}")
            else:
                result.append(str(v))
    return result


def _pct_format(val, highlight_vals=None, best_high=True) -> str:
    """Format a percentage value with optional highlighting."""
    if val is None:
        return f"{DIM}--{RESET}"
    return f"{val:.0%}"


def run_suppliers(args: Namespace) -> int:
    """Side-by-side supplier comparison."""
    supplier_ids = args.supplier_ids

    if len(supplier_ids) < 2:
        print(f"{RED}Provide at least 2 supplier IDs to compare.{RESET}")
        return 1

    suppliers = []
    for sid in supplier_ids:
        s = db.get_supplier(sid)
        if not s:
            print(f"{YELLOW}Supplier not found: {sid}{RESET}")
            continue
        # Score it
        score, breakdown, red_flags = score_supplier(s)
        s["_score"] = score
        s["_interpretation"] = interpret_score(score)
        s["_red_flags"] = red_flags
        suppliers.append(s)

    if len(suppliers) < 2:
        print(f"{RED}Need at least 2 valid suppliers to compare.{RESET}")
        return 1

    # Display comparison
    print(f"\n{BOLD}{CYAN}Supplier Comparison{RESET}\n")

    # Column headers
    col_w = 22
    label_w = 22
    header = f"  {'':<{label_w}}"
    for s in suppliers:
        name = s["name"][:col_w - 1]
        header += f" {BOLD}{name:<{col_w}}{RESET}"
    print(header)
    print(f"  {'─' * (label_w + col_w * len(suppliers))}")

    # Rows
    rows = [
        ("ID", [s["supplier_id"] for s in suppliers], False),
        ("Platform", [s["platform"] for s in suppliers], False),
        ("Type", [s.get("supplier_type", "--") for s in suppliers], False),
        ("Location", [(s.get("location") or "--")[:20] for s in suppliers], False),
        ("Quality Score", [s["_score"] for s in suppliers], True),
        ("Interpretation", [s["_interpretation"] for s in suppliers], False),
        ("Gold Years", [s.get("gold_years", 0) for s in suppliers], True),
        ("Trade Assurance", ["Yes" if s.get("trade_assurance") else "No" for s in suppliers], False),
        ("Verified", ["Yes" if s.get("verified") else "No" for s in suppliers], False),
        ("Response Rate", [s.get("response_rate") for s in suppliers], True),
        ("Transactions", [s.get("transaction_count", 0) for s in suppliers], True),
        ("On-Time Delivery", [s.get("on_time_delivery") for s in suppliers], True),
        ("Year Est.", [s.get("year_established") for s in suppliers], True),
        ("Employees", [s.get("employee_count", "--") for s in suppliers], False),
        ("Red Flags", [len(s.get("_red_flags", [])) for s in suppliers], False),
    ]

    for label, values, is_numeric in rows:
        row = f"  {label:<{label_w}}"

        if is_numeric and all(isinstance(v, (int, float)) or v is None for v in values):
            formatted = _highlight_best(values, reverse=(label in ("Red Flags",)))
            for f in formatted:
                row += f" {f:<{col_w}}"
        else:
            for v in values:
                if v is None:
                    v_str = f"{DIM}--{RESET}"
                elif isinstance(v, float):
                    v_str = f"{v:.2f}"
                else:
                    v_str = str(v)[:col_w - 1]
                row += f" {v_str:<{col_w}}"
        print(row)

    # Red flag details
    print(f"\n  {BOLD}Red Flag Details:{RESET}")
    for s in suppliers:
        flags = s.get("_red_flags", [])
        if flags:
            print(f"    {s['name'][:25]}:")
            for f in flags:
                sev = f.get("severity", "WARNING")
                color = RED if sev == "CRITICAL" else YELLOW
                print(f"      {color}[{sev}]{RESET} {f.get('desc', f.get('name', ''))}")
        else:
            print(f"    {s['name'][:25]}: {GREEN}No red flags{RESET}")

    print()
    return 0


def run_products(args: Namespace) -> int:
    """Side-by-side product comparison."""
    product_ids = args.product_ids

    if len(product_ids) < 2:
        print(f"{RED}Provide at least 2 product IDs to compare.{RESET}")
        return 1

    products = []
    for pid in product_ids:
        p = db.get_product(pid)
        if not p:
            print(f"{YELLOW}Product not found: {pid}{RESET}")
            continue
        products.append(p)

    if len(products) < 2:
        print(f"{RED}Need at least 2 valid products to compare.{RESET}")
        return 1

    print(f"\n{BOLD}{CYAN}Product Comparison{RESET}\n")

    col_w = 24
    label_w = 20

    header = f"  {'':<{label_w}}"
    for p in products:
        name = p["title"][:col_w - 1]
        header += f" {BOLD}{name:<{col_w}}{RESET}"
    print(header)
    print(f"  {'─' * (label_w + col_w * len(products))}")

    def _price_str(p):
        if p.get("price_min") is not None:
            if p.get("price_max") and p["price_max"] != p["price_min"]:
                return f"${p['price_min']:.2f}-{p['price_max']:.2f}"
            return f"${p['price_min']:.2f}"
        return "--"

    rows = [
        ("ID", [str(p["product_id"]) for p in products]),
        ("Supplier", [p["supplier_id"][:22] for p in products]),
        ("Platform", [p["platform"] for p in products]),
        ("Category", [(p.get("category") or "--")[:22] for p in products]),
        ("Price Range", [_price_str(p) for p in products]),
        ("Currency", [p.get("price_currency", "USD") for p in products]),
        ("MOQ", [str(p.get("moq") or "--") for p in products]),
        ("Lead Time", [f"{p['lead_time_days']}d" if p.get("lead_time_days") else "--" for p in products]),
        ("Sample Price", [f"${p['sample_price']:.2f}" if p.get("sample_price") else "--" for p in products]),
        ("Customization", [(p.get("customization") or "--")[:22] for p in products]),
        ("HS Code", [(p.get("hs_code") or "--") for p in products]),
    ]

    for label, values in rows:
        row = f"  {label:<{label_w}}"
        for v in values:
            row += f" {v:<{col_w}}"
        print(row)

    # Highlight cheapest
    prices_min = [(i, p.get("price_min")) for i, p in enumerate(products) if p.get("price_min") is not None]
    if prices_min:
        cheapest_idx = min(prices_min, key=lambda x: x[1])[0]
        print(f"\n  {GREEN}Lowest price: {products[cheapest_idx]['title'][:40]}{RESET}")

    print()
    return 0


def run_quotes(args: Namespace) -> int:
    """Multi-quote comparison from RFQs."""
    rfq_ids = args.rfq_ids

    if len(rfq_ids) < 2:
        print(f"{RED}Provide at least 2 RFQ IDs to compare.{RESET}")
        return 1

    rfqs = []
    for rid in rfq_ids:
        r = db.get_rfq(rid)
        if not r:
            print(f"{YELLOW}RFQ not found: {rid}{RESET}")
            continue
        # Enrich with supplier data
        s = db.get_supplier(r["supplier_id"])
        if s:
            r["_supplier_name"] = s["name"]
            r["_quality_score"] = s.get("quality_score")
        else:
            r["_supplier_name"] = r["supplier_id"]
            r["_quality_score"] = None
        rfqs.append(r)

    if len(rfqs) < 2:
        print(f"{RED}Need at least 2 valid RFQs to compare.{RESET}")
        return 1

    print(f"\n{BOLD}{CYAN}Quote Comparison{RESET}\n")

    col_w = 22
    label_w = 20

    header = f"  {'':<{label_w}}"
    for r in rfqs:
        name = f"RFQ#{r['rfq_id']}"
        header += f" {BOLD}{name:<{col_w}}{RESET}"
    print(header)
    print(f"  {'─' * (label_w + col_w * len(rfqs))}")

    rows = [
        ("Supplier", [r["_supplier_name"][:20] for r in rfqs]),
        ("Status", [r["status"] for r in rfqs]),
        ("Description", [r["description"][:20] for r in rfqs]),
        ("Quantity", [str(r.get("quantity") or "--") for r in rfqs]),
        ("Target Price", [f"${r['target_price']:.2f}" if r.get("target_price") else "--" for r in rfqs]),
        ("Quoted Price", [f"${r['supplier_quote']:.2f}" if r.get("supplier_quote") else "--" for r in rfqs]),
        ("Lead Time", [f"{r['lead_time_quoted']}d" if r.get("lead_time_quoted") else "--" for r in rfqs]),
        ("Supplier Score", [f"{r['_quality_score']:.1f}" if r.get("_quality_score") else "--" for r in rfqs]),
    ]

    for label, values in rows:
        row = f"  {label:<{label_w}}"
        for v in values:
            row += f" {v:<{col_w}}"
        print(row)

    # Highlight best quote
    quoted = [(i, r.get("supplier_quote")) for i, r in enumerate(rfqs) if r.get("supplier_quote") is not None]
    if quoted:
        best_idx = min(quoted, key=lambda x: x[1])[0]
        print(f"\n  {GREEN}Best quoted price: RFQ#{rfqs[best_idx]['rfq_id']} "
              f"({rfqs[best_idx]['_supplier_name']}) — "
              f"${rfqs[best_idx]['supplier_quote']:.2f}{RESET}")

    print()
    return 0


def run(args: Namespace) -> int:
    """Route compare subcommands."""
    action = getattr(args, "compare_action", None)

    if action == "suppliers":
        return run_suppliers(args)
    elif action == "products":
        return run_products(args)
    elif action == "quotes":
        return run_quotes(args)
    else:
        print(
            f"{YELLOW}Usage: product-sourcing compare "
            f"<suppliers|products|quotes>{RESET}",
            file=sys.stderr,
        )
        return 1
