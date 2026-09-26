"""
Product search orchestration across sourcing platforms.

Commands:
    search "query"                      Search all platforms
    search "query" --platform alibaba   Search specific platform
    search "query" --limit 10           Limit results

Scraper integration: Calls platform-specific scraper scripts via subprocess,
parses their JSON output, upserts results into the database, and displays
a formatted results table with auto-scored suppliers.
"""

import json
import subprocess
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

# Platform-to-scraper mapping
SCRAPER_MAP = {
    "alibaba": "alibaba.py",
    "1688": "ali1688.py",
    "dhgate": "dhgate.py",
    "made-in-china": "mic.py",
}

SCRAPERS_DIR = _TOOL_DIR / "scrapers"


def _run_scraper(platform: str, query: str, limit: int) -> List[Dict[str, Any]]:
    """
    Run a platform scraper script and return parsed JSON results.

    Each scraper script is expected to accept:
        python3 scrapers/<script> search "query" --limit N --json

    And output a JSON array of product/supplier dicts to stdout.
    Returns empty list if scraper is not found or fails.
    """
    script_name = SCRAPER_MAP.get(platform)
    if not script_name:
        print(f"  {YELLOW}No scraper available for platform: {platform}{RESET}")
        return []

    script_path = SCRAPERS_DIR / script_name
    if not script_path.exists():
        print(f"  {DIM}Scraper not yet implemented: {script_path.name}{RESET}")
        print(f"  {DIM}(Bowser delegation templates in templates/ can be used to build scrapers){RESET}")
        return []

    try:
        result = subprocess.run(
            [sys.executable, str(script_path), "search", query,
             "--max-results", str(limit)],
            capture_output=True, text=True, timeout=120,
            cwd=str(SCRAPERS_DIR),
        )
        if result.returncode != 0:
            stderr = result.stderr.strip()
            if stderr:
                print(f"  {RED}Scraper error ({platform}): {stderr[:200]}{RESET}")
            return []

        output = result.stdout.strip()
        if not output:
            return []

        return json.loads(output)

    except subprocess.TimeoutExpired:
        print(f"  {RED}Scraper timeout ({platform}): exceeded 120s{RESET}")
        return []
    except json.JSONDecodeError as e:
        print(f"  {RED}Scraper output parse error ({platform}): {e}{RESET}")
        return []
    except Exception as e:
        print(f"  {RED}Scraper failed ({platform}): {e}{RESET}")
        return []


def _process_results(
    platform: str, raw_results: List[Dict[str, Any]], query: str,
) -> List[Dict[str, Any]]:
    """
    Process raw scraper results: upsert into DB, score suppliers, log search.

    Returns a list of enriched result dicts for display.
    """
    processed = []

    for item in raw_results:
        # Upsert supplier
        supplier_id = item.get("supplier_id", "")
        if not supplier_id:
            continue

        supplier_data = {
            "supplier_id": supplier_id,
            "platform": platform,
            "name": item.get("supplier_name", "Unknown"),
            "url": item.get("supplier_url", ""),
            "name_cn": item.get("supplier_name_cn"),
            "location": item.get("location"),
            "supplier_type": item.get("supplier_type", "unknown"),
            "gold_years": item.get("gold_years", 0),
            "trade_assurance": item.get("trade_assurance", 0),
            "verified": item.get("verified", 0),
            "response_rate": item.get("response_rate"),
            "transaction_count": item.get("transaction_count", 0),
            "on_time_delivery": item.get("on_time_delivery"),
            "employee_count": item.get("employee_count"),
            "year_established": item.get("year_established"),
            "main_products": item.get("main_products"),
        }

        # Score the supplier
        score, breakdown, red_flags = score_supplier(supplier_data)
        supplier_data["quality_score"] = score
        supplier_data["red_flags"] = [f["name"] for f in red_flags]

        db.upsert_supplier(**supplier_data)
        db.update_supplier_score(supplier_id, score)
        db.log_score(supplier_id, score, breakdown)

        # Upsert product
        product_data = {
            "supplier_id": supplier_id,
            "platform": platform,
            "url": item.get("product_url", item.get("url", "")),
            "title": item.get("product_title", item.get("title", "Unknown Product")),
            "title_cn": item.get("title_cn"),
            "category": item.get("category"),
            "moq": item.get("moq"),
            "moq_unit": item.get("moq_unit", "pieces"),
            "price_min": item.get("price_min"),
            "price_max": item.get("price_max"),
            "price_currency": item.get("price_currency", "USD"),
        }
        product_id = db.upsert_product(**product_data)

        # Add price snapshot if prices available
        if product_data["price_min"] is not None and product_data["price_max"] is not None:
            db.add_price_snapshot(
                product_id,
                product_data["price_min"],
                product_data["price_max"],
                product_data.get("price_currency", "USD"),
                moq=product_data.get("moq"),
            )

        # Enrich for display
        item["_score"] = score
        item["_interpretation"] = interpret_score(score)
        item["_red_flags"] = red_flags
        item["_product_id"] = product_id
        processed.append(item)

    # Log the search
    top_results = [
        {"title": r.get("title", ""), "score": r.get("_score", 0)}
        for r in processed[:10]
    ]
    db.log_search(
        query=query,
        platform=platform,
        result_count=len(processed),
        top_results=top_results,
    )

    return processed


def _format_price(price_min, price_max, currency="USD"):
    """Format a price range for display."""
    if price_min is None and price_max is None:
        return f"{DIM}--{RESET}"
    sym = "$" if currency == "USD" else currency + " "
    if price_min == price_max or price_max is None:
        return f"{sym}{price_min:.2f}"
    if price_min is None:
        return f"{sym}{price_max:.2f}"
    return f"{sym}{price_min:.2f}-{price_max:.2f}"


def _format_moq(moq, moq_unit="pieces"):
    """Format MOQ for display."""
    if moq is None:
        return f"{DIM}--{RESET}"
    unit_abbr = {"pieces": "pc", "sets": "set", "units": "u",
                 "pairs": "pr", "boxes": "bx", "cartons": "ctn"}
    u = unit_abbr.get(moq_unit, moq_unit[:3])
    return f"{moq}{u}"


def _score_color(score):
    """Return ANSI color code for a score value."""
    if score >= 75:
        return GREEN
    elif score >= 50:
        return YELLOW
    else:
        return RED


def _format_flags(red_flags):
    """Format red flags as compact icons."""
    if not red_flags:
        return ""
    critical = [f for f in red_flags if f.get("severity") == "CRITICAL"]
    warnings = [f for f in red_flags if f.get("severity") == "WARNING"]
    parts = []
    if critical:
        parts.append(f"{RED}x{len(critical)}{RESET}")
    if warnings:
        parts.append(f"{YELLOW}!{len(warnings)}{RESET}")
    return " ".join(parts)


def _display_results(platform: str, query: str, results: List[Dict[str, Any]]) -> None:
    """Display search results as a formatted terminal table."""
    if not results:
        print(f"\n  {YELLOW}No results found for \"{query}\" on {platform}{RESET}")
        return

    print(f"\n{CYAN}Search results for \"{query}\" on {platform} ({len(results)} results){RESET}\n")

    # Header
    header = (
        f"  {BOLD}{'#':>3}  {'Score':>5}  {'Supplier':<28} {'Type':<10} "
        f"{'Gold':>4}  {'TA':>2}  {'Price':<14} {'MOQ':<8} {'Flags'}{RESET}"
    )
    print(header)
    print(f"  {'=' * 100}")

    for i, r in enumerate(results, 1):
        score = r.get("_score", 0)
        sc = _score_color(score)
        name = r.get("supplier_name", "Unknown")[:27]
        s_type = r.get("supplier_type", "?")[:9]
        gold = r.get("gold_years", 0)
        gold_str = f"{gold}yr" if gold > 0 else f"{DIM}--{RESET}"
        ta = f"{GREEN}Y{RESET}" if r.get("trade_assurance") else f"{RED}N{RESET}"
        price = _format_price(r.get("price_min"), r.get("price_max"),
                              r.get("price_currency", "USD"))
        moq = _format_moq(r.get("moq"), r.get("moq_unit", "pieces"))
        flags = _format_flags(r.get("_red_flags", []))

        print(
            f"  {i:>3}  {sc}{score:>5.1f}{RESET}  {name:<28} {s_type:<10} "
            f"{gold_str:>4}  {ta:>2}  {price:<14} {moq:<8} {flags}"
        )

    print()


def run(args: Namespace) -> int:
    """Run the search command."""
    query = args.query
    platform = getattr(args, "platform", None)
    limit = getattr(args, "limit", 20)

    if platform:
        platforms = [platform]
    else:
        platforms = list(SCRAPER_MAP.keys())

    all_results = []

    for plat in platforms:
        print(f"{DIM}Searching {plat} for \"{query}\"...{RESET}")
        raw = _run_scraper(plat, query, limit)

        if raw:
            processed = _process_results(plat, raw, query)
            # Sort by score descending
            processed.sort(key=lambda x: x.get("_score", 0), reverse=True)
            _display_results(plat, query, processed)
            all_results.extend(processed)
        else:
            _display_results(plat, query, [])

    # Summary for multi-platform search
    if len(platforms) > 1 and all_results:
        all_results.sort(key=lambda x: x.get("_score", 0), reverse=True)
        print(f"\n{BOLD}{CYAN}Combined Results Summary{RESET}")
        print(f"  Total results: {len(all_results)}")
        if all_results:
            top = all_results[0]
            print(
                f"  Top scored: {GREEN}{top.get('supplier_name', '?')}{RESET} "
                f"({top.get('_score', 0):.1f} - {top.get('_interpretation', '?')})"
            )
        scored = [r for r in all_results if r.get("_score", 0) >= 75]
        print(f"  Good+ suppliers (75+): {len(scored)}")

    return 0
