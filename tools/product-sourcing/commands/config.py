"""
Configuration management — show config, check credentials, database stats.

Commands:
    config show     Show current configuration and credential status
    config check    Verify API credentials and database connectivity
    config stats    Show database statistics
"""

import sys
from argparse import Namespace
from pathlib import Path

_TOOL_DIR = Path(__file__).resolve().parent.parent
if str(_TOOL_DIR) not in sys.path:
    sys.path.insert(0, str(_TOOL_DIR))

import db
from client import _keychain_get, EasyshipClient

# Terminal colours
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
BOLD = "\033[1m"
DIM = "\033[2m"
RESET = "\033[0m"


def _check_icon(ok: bool) -> str:
    """Return colored check/cross icon."""
    return f"{GREEN}OK{RESET}" if ok else f"{RED}MISSING{RESET}"


def run_show(args: Namespace) -> int:
    """Show current configuration."""
    print(f"\n{BOLD}{CYAN}Product Sourcing — Configuration{RESET}\n")

    # Database
    print(f"  {BOLD}Database{RESET}")
    print(f"    Path:     {db.DB_PATH}")
    print(f"    Exists:   {_check_icon(db.DB_PATH.exists())}")
    print()

    # API Credentials
    print(f"  {BOLD}API Credentials{RESET}")

    easyship_token = _keychain_get(EasyshipClient.KC_SERVICE)
    print(f"    Easyship:   {_check_icon(bool(easyship_token))}")
    if easyship_token:
        print(f"                {DIM}Token: {easyship_token[:8]}...{RESET}")
    else:
        print(f"                {DIM}Add: security add-generic-password "
              f"-s '{EasyshipClient.KC_SERVICE}' -a huxley -w '<token>' -U{RESET}")

    print(f"    Freightos:  {GREEN}No auth needed{RESET}")
    print(f"    ExchangeRate: {GREEN}No auth needed{RESET}")
    print()

    # Supported platforms
    print(f"  {BOLD}Supported Platforms{RESET}")
    platforms = ["alibaba", "1688", "dhgate", "made-in-china"]
    scrapers_dir = _TOOL_DIR / "scrapers"
    scraper_map = {
        "alibaba": "alibaba.py",
        "1688": "ali1688.py",
        "dhgate": "dhgate.py",
        "made-in-china": "mic.py",
    }
    for plat in platforms:
        script = scraper_map.get(plat, "")
        exists = (scrapers_dir / script).exists() if script else False
        status = f"{GREEN}ready{RESET}" if exists else f"{DIM}scraper pending{RESET}"
        print(f"    {plat:<16} {status}")

    print()
    return 0


def run_check(args: Namespace) -> int:
    """Verify API credentials and database connectivity."""
    print(f"\n{BOLD}{CYAN}Product Sourcing — Credential Check{RESET}\n")

    all_ok = True

    # Database connectivity
    print(f"  {BOLD}Database{RESET}")
    try:
        conn = db.get_connection()
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )
        tables = [row["name"] for row in cursor.fetchall()]
        conn.close()
        expected = {"suppliers", "products", "price_snapshots", "search_history",
                    "rfqs", "supplier_scores", "cost_calculations", "exchange_rates"}
        missing = expected - set(tables)
        if missing:
            print(f"    {RED}Missing tables: {', '.join(missing)}{RESET}")
            all_ok = False
        else:
            print(f"    {GREEN}All {len(expected)} tables present{RESET}")
    except Exception as e:
        print(f"    {RED}Connection failed: {e}{RESET}")
        all_ok = False

    # Easyship
    print(f"\n  {BOLD}Easyship API{RESET}")
    easyship_token = _keychain_get(EasyshipClient.KC_SERVICE)
    if easyship_token:
        print(f"    Token:   {GREEN}Found ({len(easyship_token)} chars){RESET}")
        # Optionally test the API
        try:
            client = EasyshipClient(token=easyship_token)
            # Lightweight test — just init succeeds
            print(f"    Client:  {GREEN}Initialized{RESET}")
        except Exception as e:
            print(f"    Client:  {RED}Init failed: {e}{RESET}")
            all_ok = False
    else:
        print(f"    Token:   {RED}Not found in Keychain{RESET}")
        print(f"    {DIM}Add: security add-generic-password "
              f"-s '{EasyshipClient.KC_SERVICE}' -a huxley -w '<token>' -U{RESET}")
        # Not a hard failure — tool works without Easyship
        print(f"    {YELLOW}(Optional: cost calculations will use default duty rates){RESET}")

    # Exchange Rate API (no auth, just connectivity)
    print(f"\n  {BOLD}Exchange Rate API{RESET}")
    print(f"    Auth:    {GREEN}None required{RESET}")
    print(f"    Source:  open.er-api.com")

    # Freightos
    print(f"\n  {BOLD}Freightos API{RESET}")
    print(f"    Auth:    {GREEN}None required{RESET}")

    # Summary
    print()
    if all_ok:
        print(f"  {GREEN}{BOLD}All checks passed{RESET}")
    else:
        print(f"  {YELLOW}{BOLD}Some checks failed — see above{RESET}")

    return 0 if all_ok else 1


def run_stats(args: Namespace) -> int:
    """Show database statistics."""
    print(f"\n{BOLD}{CYAN}Product Sourcing — Database Statistics{RESET}\n")

    conn = db.get_connection()
    try:
        # Table counts
        tables = {
            "suppliers": "Suppliers",
            "products": "Products",
            "price_snapshots": "Price Snapshots",
            "search_history": "Searches",
            "rfqs": "RFQs",
            "supplier_scores": "Score Records",
            "cost_calculations": "Cost Calculations",
            "exchange_rates": "Exchange Rates",
        }

        print(f"  {BOLD}Table Counts{RESET}")
        total_rows = 0
        for table, label in tables.items():
            try:
                count = conn.execute(
                    f"SELECT COUNT(*) as c FROM {table}"
                ).fetchone()["c"]
                total_rows += count
                print(f"    {label:<20} {count:>6,}")
            except Exception:
                print(f"    {label:<20} {RED}error{RESET}")

        print(f"    {'─' * 28}")
        print(f"    {'Total':<20} {total_rows:>6,}")

        # Platform breakdown
        plat_rows = conn.execute(
            "SELECT platform, COUNT(*) as c FROM suppliers GROUP BY platform ORDER BY c DESC"
        ).fetchall()
        if plat_rows:
            print(f"\n  {BOLD}Suppliers by Platform{RESET}")
            for r in plat_rows:
                print(f"    {r['platform']:<16} {r['c']:>6,}")

        # Score distribution
        score_rows = conn.execute("""
            SELECT
                CASE
                    WHEN quality_score >= 90 THEN 'Excellent (90+)'
                    WHEN quality_score >= 75 THEN 'Good (75-89)'
                    WHEN quality_score >= 60 THEN 'Fair (60-74)'
                    WHEN quality_score >= 40 THEN 'Marginal (40-59)'
                    WHEN quality_score >= 20 THEN 'Poor (20-39)'
                    WHEN quality_score IS NOT NULL THEN 'Critical (0-19)'
                    ELSE 'Unscored'
                END as tier,
                COUNT(*) as c
            FROM suppliers
            GROUP BY tier
            ORDER BY MIN(COALESCE(quality_score, -1)) DESC
        """).fetchall()
        if score_rows:
            print(f"\n  {BOLD}Score Distribution{RESET}")
            for r in score_rows:
                print(f"    {r['tier']:<20} {r['c']:>6,}")

        # RFQ status breakdown
        rfq_rows = conn.execute(
            "SELECT status, COUNT(*) as c FROM rfqs GROUP BY status ORDER BY c DESC"
        ).fetchall()
        if rfq_rows:
            print(f"\n  {BOLD}RFQ Status{RESET}")
            for r in rfq_rows:
                print(f"    {r['status']:<16} {r['c']:>6,}")

        # Recent activity
        recent_search = conn.execute(
            "SELECT searched_at FROM search_history ORDER BY searched_at DESC LIMIT 1"
        ).fetchone()
        if recent_search:
            print(f"\n  {BOLD}Last Activity{RESET}")
            print(f"    Last search: {recent_search['searched_at']}")

        recent_score = conn.execute(
            "SELECT scored_at FROM supplier_scores ORDER BY scored_at DESC LIMIT 1"
        ).fetchone()
        if recent_score:
            print(f"    Last score:  {recent_score['scored_at']}")

        # Database file size
        if db.DB_PATH.exists():
            size_bytes = db.DB_PATH.stat().st_size
            if size_bytes >= 1_048_576:
                size_str = f"{size_bytes / 1_048_576:.1f} MB"
            elif size_bytes >= 1024:
                size_str = f"{size_bytes / 1024:.1f} KB"
            else:
                size_str = f"{size_bytes} bytes"
            print(f"\n  {DIM}Database size: {size_str}{RESET}")

    finally:
        conn.close()

    print()
    return 0


def run(args: Namespace) -> int:
    """Route config subcommands."""
    action = getattr(args, "config_action", None)

    if action == "show":
        return run_show(args)
    elif action == "check":
        return run_check(args)
    elif action == "stats":
        return run_stats(args)
    else:
        print(f"{YELLOW}Usage: product-sourcing config <show|check|stats>{RESET}",
              file=sys.stderr)
        return 1
