"""
Product tracking — list, search, inspect, and view price history.

Commands:
    product show <product_id>                   Detailed product view
    product list --supplier <supplier_id>       List products by supplier
    product search "query" [--category X]       Search products
    product prices <product_id>                 View price history
"""

import sys
from argparse import Namespace
from pathlib import Path

_TOOL_DIR = Path(__file__).resolve().parent.parent
if str(_TOOL_DIR) not in sys.path:
    sys.path.insert(0, str(_TOOL_DIR))

import db

# Terminal colours
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
BOLD = "\033[1m"
DIM = "\033[2m"
RESET = "\033[0m"


def _format_price(price_min, price_max, currency="USD"):
    """Format a price range for display."""
    if price_min is None and price_max is None:
        return f"{DIM}--{RESET}"
    sym = "$" if currency == "USD" else currency + " "
    if price_min == price_max or price_max is None:
        return f"{sym}{price_min:.2f}"
    if price_min is None:
        return f"{sym}{price_max:.2f}"
    return f"{sym}{price_min:.2f} - {sym}{price_max:.2f}"


def run_show(args: Namespace) -> int:
    """Show detailed product information."""
    product_id = args.product_id

    product = db.get_product(product_id)
    if not product:
        print(f"{RED}Product not found: {product_id}{RESET}")
        return 1

    print(f"\n{BOLD}{CYAN}Product: {product['title']}{RESET}")
    if product.get("title_cn"):
        print(f"  {DIM}{product['title_cn']}{RESET}")
    print()

    # Identity
    print(f"  {BOLD}ID:{RESET}             {product['product_id']}")
    print(f"  {BOLD}Platform:{RESET}        {product['platform']}")
    print(f"  {BOLD}URL:{RESET}             {product['url']}")
    print(f"  {BOLD}Supplier:{RESET}        {product['supplier_id']}")
    print(f"  {BOLD}Category:{RESET}        {product.get('category') or '--'}")
    print(f"  {BOLD}HS Code:{RESET}         {product.get('hs_code') or '--'}")
    print()

    # Pricing
    price = _format_price(product.get("price_min"), product.get("price_max"),
                          product.get("price_currency", "USD"))
    print(f"  {BOLD}Pricing{RESET}")
    print(f"    Price Range:      {price}")
    print(f"    MOQ:              {product.get('moq') or '--'} {product.get('moq_unit', 'pieces')}")
    print(f"    Customization:    {product.get('customization', 'unknown')}")
    print(f"    Sample Available: {'Yes' if product.get('sample_available') else 'No'}")
    if product.get("sample_price") is not None:
        print(f"    Sample Price:     ${product['sample_price']:.2f}")
    print(f"    Lead Time:        {product.get('lead_time_days') or '--'} days")
    print()

    # Specs
    specs = product.get("specs", {})
    if specs and specs != {}:
        print(f"  {BOLD}Specifications{RESET}")
        for key, val in specs.items():
            print(f"    {key}: {val}")
        print()

    # Image URLs
    images = product.get("image_urls", [])
    if images:
        print(f"  {BOLD}Images ({len(images)}){RESET}")
        for i, url in enumerate(images[:5], 1):
            print(f"    {i}. {DIM}{url[:80]}{RESET}")
        if len(images) > 5:
            print(f"    {DIM}... and {len(images) - 5} more{RESET}")
        print()

    # Notes
    if product.get("notes"):
        print(f"  {BOLD}Notes:{RESET} {product['notes']}")

    # Supplier info
    supplier = db.get_supplier(product["supplier_id"])
    if supplier:
        score = supplier.get("quality_score")
        score_str = f"{score:.1f}" if score is not None else "--"
        print(f"\n  {BOLD}Supplier:{RESET} {supplier['name']} (score: {score_str})")

    # Price history summary
    history = db.get_price_history(product_id, limit=5)
    if history:
        print(f"\n  {BOLD}Recent Prices{RESET}")
        for h in history[:5]:
            p = _format_price(h["price_min"], h["price_max"], h["price_currency"])
            moq = f"MOQ {h['moq']}" if h.get("moq") else ""
            print(f"    {h['snapshot_time']}  {p}  {moq}")

    # Timestamps
    print(f"\n  {DIM}First seen: {product['first_seen']}{RESET}")
    print(f"  {DIM}Last updated: {product['last_updated']}{RESET}")

    return 0


def run_list(args: Namespace) -> int:
    """List products by supplier."""
    supplier_id = args.supplier
    limit = getattr(args, "limit", 50)

    supplier = db.get_supplier(supplier_id)
    if not supplier:
        print(f"{RED}Supplier not found: {supplier_id}{RESET}")
        return 1

    products = db.list_products_by_supplier(supplier_id, limit=limit)

    if not products:
        print(f"{YELLOW}No products found for supplier: {supplier['name']}{RESET}")
        return 0

    print(f"\n{BOLD}{CYAN}Products from {supplier['name']} ({len(products)}){RESET}\n")

    # Header
    print(
        f"  {BOLD}{'ID':>4}  {'Title':<40} {'Price':<16} {'MOQ':<10} {'Category'}{RESET}"
    )
    print(f"  {'=' * 90}")

    for p in products:
        pid = p["product_id"]
        title = p["title"][:39]
        price = _format_price(p.get("price_min"), p.get("price_max"),
                              p.get("price_currency", "USD"))
        moq = f"{p['moq']} {p.get('moq_unit', 'pc')[:3]}" if p.get("moq") else f"{DIM}--{RESET}"
        cat = p.get("category") or f"{DIM}--{RESET}"

        print(f"  {pid:>4}  {title:<40} {price:<16} {moq:<10} {cat}")

    print()
    return 0


def run_search(args: Namespace) -> int:
    """Search products by title/category/HS code."""
    query = args.query
    category = getattr(args, "category", None)
    platform = getattr(args, "platform", None)

    results = db.search_products(query, category=category, platform=platform)

    if not results:
        print(f"{YELLOW}No products found matching \"{query}\"{RESET}")
        return 0

    print(f"\n{BOLD}{CYAN}Product Search: \"{query}\" ({len(results)} results){RESET}\n")

    for i, p in enumerate(results, 1):
        pid = p["product_id"]
        title = p["title"][:45]
        price = _format_price(p.get("price_min"), p.get("price_max"),
                              p.get("price_currency", "USD"))
        supplier = p["supplier_id"]

        print(f"  {i:>2}. [{pid}] {title}")
        print(f"      {price}  {DIM}from {supplier} ({p['platform']}){RESET}")

    print()
    return 0


def run_prices(args: Namespace) -> int:
    """Show price history for a product."""
    product_id = args.product_id

    product = db.get_product(product_id)
    if not product:
        print(f"{RED}Product not found: {product_id}{RESET}")
        return 1

    history = db.get_price_history(product_id, limit=90)

    if not history:
        print(f"{YELLOW}No price history for: {product['title']}{RESET}")
        return 0

    print(f"\n{BOLD}{CYAN}Price History: {product['title']}{RESET}")
    print(f"  {DIM}Supplier: {product['supplier_id']}{RESET}\n")

    # Header
    print(f"  {BOLD}{'Date':<22} {'Min':>8}  {'Max':>8}  {'Currency':<6}  {'MOQ':>6}  {'FX Rate'}{RESET}")
    print(f"  {'-' * 72}")

    prev_min = None
    for h in history:
        p_min = h["price_min"]
        p_max = h["price_max"]
        curr = h["price_currency"]
        moq = str(h["moq"]) if h.get("moq") else "--"
        fx = f"{h['exchange_rate']:.4f}" if h.get("exchange_rate") else "--"

        # Trend indicator
        trend = ""
        if prev_min is not None:
            if p_min < prev_min:
                trend = f" {GREEN}v{RESET}"
            elif p_min > prev_min:
                trend = f" {RED}^{RESET}"
        prev_min = p_min

        print(
            f"  {h['snapshot_time']:<22} ${p_min:>7.2f}  ${p_max:>7.2f}  "
            f"{curr:<6}  {moq:>6}  {fx}{trend}"
        )

    # Summary
    if len(history) >= 2:
        newest = history[0]
        oldest = history[-1]
        min_change = newest["price_min"] - oldest["price_min"]
        max_change = newest["price_max"] - oldest["price_max"]

        print(f"\n  {BOLD}Trend{RESET}")
        if min_change < 0:
            print(f"    Min price: {GREEN}${min_change:+.2f}{RESET} (decreasing)")
        elif min_change > 0:
            print(f"    Min price: {RED}${min_change:+.2f}{RESET} (increasing)")
        else:
            print(f"    Min price: stable")

    print()
    return 0


def run(args: Namespace) -> int:
    """Route product subcommands."""
    action = getattr(args, "product_action", None)

    if action == "show":
        return run_show(args)
    elif action == "list":
        return run_list(args)
    elif action == "search":
        return run_search(args)
    elif action == "prices":
        return run_prices(args)
    else:
        print(f"{YELLOW}Usage: product-sourcing product <show|list|search|prices>{RESET}",
              file=sys.stderr)
        return 1
