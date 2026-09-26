#!/usr/bin/env python3
"""
Product Sourcing CLI — E-commerce supplier intelligence toolkit.

Search suppliers, compare products, calculate landed costs, manage RFQs,
and track supplier quality scores across sourcing platforms.

Usage:
    python3 tools/product-sourcing/cli.py search "silicone phone case"
    python3 tools/product-sourcing/cli.py supplier list
    python3 tools/product-sourcing/cli.py product show 42
    python3 tools/product-sourcing/cli.py cost calculate --product-id 42 --qty 1000
    python3 tools/product-sourcing/cli.py rfq create --supplier ali:abc123 --desc "Custom logo"
    python3 tools/product-sourcing/cli.py export suppliers --format csv
    python3 tools/product-sourcing/cli.py config show

Dependencies: None (stdlib only)
Auth: Easyship API token via macOS Keychain.
"""

import argparse
import os
import subprocess
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Huxley root detection (same pattern as tiktok.py)
# ---------------------------------------------------------------------------

def _find_catalyst_root() -> Path:
    """Resolve Huxley root reliably, even when invoked through symlinks."""
    # 1. Explicit env var (highest priority)
    env = os.environ.get("CATALYST_ROOT")
    if env:
        return Path(env)
    # 2. git rev-parse (works from any depth inside the repo)
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0:
            return Path(result.stdout.strip())
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    # 3. Walk up from this file
    return Path(__file__).resolve().parent.parent.parent


CATALYST_ROOT = _find_catalyst_root()

# Ensure the tool directory is on the path so sibling imports work
TOOL_DIR = Path(__file__).resolve().parent
if str(TOOL_DIR) not in sys.path:
    sys.path.insert(0, str(TOOL_DIR))

# Terminal colours
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
BOLD = "\033[1m"
DIM = "\033[2m"
RESET = "\033[0m"

VERSION = "0.2.0"


def _build_parser() -> argparse.ArgumentParser:
    """Build the top-level argument parser with all subcommand groups."""
    parser = argparse.ArgumentParser(
        prog="product-sourcing",
        description=(
            f"{BOLD}Sourcerer{RESET} "
            f"— E-commerce supplier intelligence toolkit"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"""\
{DIM}Version {VERSION}
Auth: Easyship token via macOS Keychain (product-sourcing-easyship-token).
Database: monitoring/product-sourcing.db{RESET}
""",
    )
    parser.add_argument(
        "--debug", action="store_true",
        help="Enable debug output",
    )
    parser.add_argument(
        "--version", action="version",
        version=f"%(prog)s {VERSION}",
    )

    subparsers = parser.add_subparsers(
        dest="command",
        title="commands",
        metavar="<command>",
    )

    # --- search ---
    search_parser = subparsers.add_parser(
        "search",
        help="Search for products across sourcing platforms",
        description="Search supplier platforms for products matching a query.",
    )
    search_parser.add_argument("query", help="Product search query")
    search_parser.add_argument(
        "--platform", choices=["alibaba", "1688", "dhgate", "made-in-china"],
        default=None, help="Limit search to a specific platform",
    )
    search_parser.add_argument(
        "--limit", type=int, default=20,
        help="Maximum results to return (default: 20)",
    )

    # --- supplier ---
    supplier_parser = subparsers.add_parser(
        "supplier",
        help="Manage and inspect suppliers",
        description="List, search, inspect, and score suppliers.",
    )
    supplier_sub = supplier_parser.add_subparsers(
        dest="supplier_action", metavar="<action>",
    )

    # supplier list
    sup_list = supplier_sub.add_parser("list", help="List all tracked suppliers")
    sup_list.add_argument(
        "--platform", default=None, help="Filter by platform",
    )
    sup_list.add_argument(
        "--limit", type=int, default=50, help="Max results (default: 50)",
    )

    # supplier show <id>
    sup_show = supplier_sub.add_parser("show", help="Show supplier details")
    sup_show.add_argument("supplier_id", help="Supplier ID (e.g. ali:abc123)")

    # supplier search <query>
    sup_search = supplier_sub.add_parser("search", help="Search suppliers by name")
    sup_search.add_argument("query", help="Search term")
    sup_search.add_argument(
        "--platform", default=None, help="Filter by platform",
    )

    # supplier score <id>
    sup_score = supplier_sub.add_parser("score", help="View supplier score history")
    sup_score.add_argument("supplier_id", help="Supplier ID")

    # --- product ---
    product_parser = subparsers.add_parser(
        "product",
        help="Manage and inspect products",
        description="List, search, and inspect sourced products.",
    )
    product_sub = product_parser.add_subparsers(
        dest="product_action", metavar="<action>",
    )

    # product show <id>
    prod_show = product_sub.add_parser("show", help="Show product details")
    prod_show.add_argument("product_id", type=int, help="Product ID")

    # product list --supplier <id>
    prod_list = product_sub.add_parser("list", help="List products by supplier")
    prod_list.add_argument("--supplier", required=True, help="Supplier ID")
    prod_list.add_argument(
        "--limit", type=int, default=50, help="Max results (default: 50)",
    )

    # product search <query>
    prod_search = product_sub.add_parser("search", help="Search products")
    prod_search.add_argument("query", help="Search term")
    prod_search.add_argument("--category", default=None, help="Filter by category")
    prod_search.add_argument("--platform", default=None, help="Filter by platform")

    # product prices <id>
    prod_prices = product_sub.add_parser("prices", help="View price history")
    prod_prices.add_argument("product_id", type=int, help="Product ID")

    # --- cost ---
    cost_parser = subparsers.add_parser(
        "cost",
        help="Landed cost calculations",
        description="Calculate total landed cost including duties, freight, and fees.",
    )
    cost_sub = cost_parser.add_subparsers(
        dest="cost_action", metavar="<action>",
    )

    # cost calculate
    cost_calc = cost_sub.add_parser("calculate", help="Calculate landed cost")
    cost_calc.add_argument(
        "--product-id", type=int, default=None,
        help="Product ID (uses stored price if set)",
    )
    cost_calc.add_argument("--unit-cost", type=float, help="Unit cost in USD")
    cost_calc.add_argument("--qty", type=int, required=True, help="Order quantity")
    cost_calc.add_argument("--hs-code", default=None, help="HS code for duty lookup")
    cost_calc.add_argument(
        "--origin", default="CN", help="Origin country code (default: CN)",
    )
    cost_calc.add_argument(
        "--dest", default="US", help="Destination country code (default: US)",
    )
    cost_calc.add_argument(
        "--freight-mode", choices=["sea", "air", "express"],
        default=None, help="Freight mode",
    )
    cost_calc.add_argument(
        "--sell-price", type=float, default=None,
        help="Retail sell price for margin calculation",
    )
    cost_calc.add_argument(
        "--category", default=None,
        help="Product category for weight estimation (e.g. phone_cases, shoes)",
    )
    cost_calc.add_argument(
        "--weight", type=float, default=None,
        help="Per-unit weight in kg (overrides category estimate)",
    )
    cost_calc.add_argument(
        "--dims", default=None,
        help="Per-unit dimensions in cm (LxWxH, e.g. '30x20x10')",
    )

    # cost history <product-id>
    cost_hist = cost_sub.add_parser("history", help="View cost calculation history")
    cost_hist.add_argument("product_id", type=int, help="Product ID")

    # cost hs-lookup <query>
    cost_hs = cost_sub.add_parser("hs-lookup", help="Look up HS code by description")
    cost_hs.add_argument("query", help="Product description for HS code lookup")

    # cost exchange <from> <to>
    cost_fx = cost_sub.add_parser("exchange", help="Get exchange rate")
    cost_fx.add_argument("from_currency", help="Source currency (e.g. CNY)")
    cost_fx.add_argument("to_currency", help="Target currency (e.g. USD)")

    # --- rfq ---
    rfq_parser = subparsers.add_parser(
        "rfq",
        help="Request for Quotation management",
        description="Create, update, and track RFQs sent to suppliers.",
    )
    rfq_sub = rfq_parser.add_subparsers(
        dest="rfq_action", metavar="<action>",
    )

    # rfq create
    rfq_create = rfq_sub.add_parser("create", help="Create a new RFQ")
    rfq_create.add_argument("--supplier", required=True, help="Supplier ID")
    rfq_create.add_argument("--desc", required=True, help="Product/requirement description")
    rfq_create.add_argument("--product-id", type=int, default=None, help="Link to product")
    rfq_create.add_argument("--qty", type=int, default=None, help="Requested quantity")
    rfq_create.add_argument("--target-price", type=float, default=None, help="Target unit price")

    # rfq update
    rfq_update = rfq_sub.add_parser("update", help="Update an existing RFQ")
    rfq_update.add_argument("rfq_id", type=int, help="RFQ ID to update")
    rfq_update.add_argument(
        "--status", choices=["draft", "sent", "quoted", "negotiating", "accepted", "rejected"],
        default=None, help="New status",
    )
    rfq_update.add_argument("--quote", type=float, default=None, help="Supplier's quoted price")
    rfq_update.add_argument("--lead-time", type=int, default=None, help="Quoted lead time (days)")
    rfq_update.add_argument("--notes", default=None, help="Additional notes")

    # rfq list
    rfq_list = rfq_sub.add_parser("list", help="List RFQs")
    rfq_list.add_argument(
        "--status", default=None,
        help="Filter by status (draft, sent, quoted, negotiating, accepted, rejected)",
    )
    rfq_list.add_argument("--supplier", default=None, help="Filter by supplier ID")

    # rfq show
    rfq_show = rfq_sub.add_parser("show", help="Show RFQ details")
    rfq_show.add_argument("rfq_id", type=int, help="RFQ ID")

    # --- export ---
    export_parser = subparsers.add_parser(
        "export",
        help="Export data to CSV or JSON",
        description="Export suppliers, products, or cost data for spreadsheets.",
    )
    export_sub = export_parser.add_subparsers(
        dest="export_action", metavar="<action>",
    )

    # export suppliers
    exp_sup = export_sub.add_parser("suppliers", help="Export supplier list")
    exp_sup.add_argument(
        "--format", choices=["csv", "json", "md"], default="csv",
        help="Output format (default: csv)",
    )
    exp_sup.add_argument("--output", default=None, help="Output file path")

    # export products
    exp_prod = export_sub.add_parser("products", help="Export product list")
    exp_prod.add_argument(
        "--format", choices=["csv", "json", "md"], default="csv",
        help="Output format (default: csv)",
    )
    exp_prod.add_argument("--supplier", default=None, help="Filter by supplier ID")
    exp_prod.add_argument("--output", default=None, help="Output file path")

    # export costs
    exp_cost = export_sub.add_parser("costs", help="Export cost calculations")
    exp_cost.add_argument(
        "--format", choices=["csv", "json", "md"], default="csv",
        help="Output format (default: csv)",
    )
    exp_cost.add_argument("--output", default=None, help="Output file path")

    # --- config ---
    config_parser = subparsers.add_parser(
        "config",
        help="Configuration and status",
        description="Show configuration, check API credentials, and database stats.",
    )
    config_sub = config_parser.add_subparsers(
        dest="config_action", metavar="<action>",
    )

    # config show
    config_sub.add_parser("show", help="Show current configuration and credential status")

    # config check
    config_sub.add_parser("check", help="Verify API credentials and database connectivity")

    # config stats
    config_sub.add_parser("stats", help="Show database statistics")

    # --- compliance ---
    compliance_parser = subparsers.add_parser(
        "compliance",
        help="Trade compliance, tariffs, and Incoterms",
        description="Look up tariff rates, compliance requirements, and Incoterms.",
    )
    compliance_sub = compliance_parser.add_subparsers(
        dest="compliance_action", metavar="<action>",
    )

    # compliance check <product-id>
    comp_check = compliance_sub.add_parser("check", help="Show compliance status for a product")
    comp_check.add_argument("product_id", type=int, help="Product ID")

    # compliance requirements <category>
    comp_reqs = compliance_sub.add_parser("requirements", help="Show US import requirements")
    comp_reqs.add_argument(
        "category",
        help="Product category (electronics, toys, textiles, cosmetics, etc.)",
    )

    # compliance tariff <hs-code>
    comp_tariff = compliance_sub.add_parser("tariff", help="Look up tariff rate for HS code")
    comp_tariff.add_argument("hs_code", help="HS code (e.g. 8507, 6110)")
    comp_tariff.add_argument("--origin", default="CN", help="Origin country (default: CN)")
    comp_tariff.add_argument("--dest", default="US", help="Destination country (default: US)")
    comp_tariff.add_argument(
        "--value", type=float, default=10000.0,
        help="Goods value for duty estimate (default: $10,000)",
    )

    # compliance incoterms [term]
    comp_inco = compliance_sub.add_parser("incoterms", help="Show Incoterms 2020 reference")
    comp_inco.add_argument("term", nargs="?", default=None, help="Specific Incoterm (e.g. FOB, CIF, DDP)")

    # --- compare ---
    compare_parser = subparsers.add_parser(
        "compare",
        help="Side-by-side comparisons",
        description="Compare suppliers, products, or quotes side by side.",
    )
    compare_sub = compare_parser.add_subparsers(
        dest="compare_action", metavar="<action>",
    )

    # compare suppliers <id1> <id2> [id3...]
    cmp_sup = compare_sub.add_parser("suppliers", help="Compare suppliers side by side")
    cmp_sup.add_argument("supplier_ids", nargs="+", help="Supplier IDs to compare")

    # compare products <id1> <id2> [id3...]
    cmp_prod = compare_sub.add_parser("products", help="Compare products side by side")
    cmp_prod.add_argument("product_ids", nargs="+", type=int, help="Product IDs to compare")

    # compare quotes <rfq1> <rfq2> [rfq3...]
    cmp_quotes = compare_sub.add_parser("quotes", help="Compare RFQ quotes")
    cmp_quotes.add_argument("rfq_ids", nargs="+", type=int, help="RFQ IDs to compare")

    # --- risk ---
    risk_parser = subparsers.add_parser(
        "risk",
        help="Supply chain risk assessment",
        description="Assess supplier risk, portfolio concentration, and scam indicators.",
    )
    risk_sub = risk_parser.add_subparsers(
        dest="risk_action", metavar="<action>",
    )

    # risk assess <supplier-id>
    risk_assess = risk_sub.add_parser("assess", help="Full risk assessment for a supplier")
    risk_assess.add_argument("supplier_id", help="Supplier ID")

    # risk report
    risk_sub.add_parser("report", help="Portfolio-wide risk summary")

    # risk concentration
    risk_sub.add_parser("concentration", help="Supplier concentration analysis")

    # risk scams <supplier-id>
    risk_scams = risk_sub.add_parser("scams", help="Check for scam indicators")
    risk_scams.add_argument("supplier_id", help="Supplier ID")

    # --- negotiate ---
    negotiate_parser = subparsers.add_parser(
        "negotiate",
        help="Negotiation intelligence and templates",
        description="Message templates, payment terms, strategy advice, and discount estimates.",
    )
    negotiate_sub = negotiate_parser.add_subparsers(
        dest="negotiate_action", metavar="<action>",
    )

    # negotiate template <stage>
    neg_template = negotiate_sub.add_parser("template", help="Get message template")
    neg_template.add_argument(
        "stage",
        help="Template stage (initial_inquiry, sample_request, price_negotiation, "
             "counter_offer, order_confirmation, quality_complaint, reorder, rfq_followup)",
    )

    # negotiate terms <order-value>
    neg_terms = negotiate_sub.add_parser("terms", help="Payment terms recommendation")
    neg_terms.add_argument("order_value", type=float, help="Order value in USD")
    neg_terms.add_argument(
        "--supplier-score", type=float, default=50.0,
        help="Supplier quality score (default: 50)",
    )
    neg_terms.add_argument(
        "--repeat", dest="first_order", action="store_false",
        help="This is a repeat order (not first order)",
    )

    # negotiate strategy <scenario>
    neg_strat = negotiate_sub.add_parser("strategy", help="Get strategy advice")
    neg_strat.add_argument(
        "scenario",
        help="Scenario (first_order, price_too_high, reorder_negotiation, "
             "quality_issue, urgent_order, switching_supplier)",
    )

    # negotiate discount <base-price>
    neg_disc = negotiate_sub.add_parser("discount", help="Estimate volume discounts")
    neg_disc.add_argument("base_price", type=float, help="Base unit price at MOQ")
    neg_disc.add_argument(
        "--quantities", required=True,
        help="Comma-separated quantities (e.g. \"100,500,1000,5000\")",
    )

    # --- alert ---
    alert_parser = subparsers.add_parser(
        "alert",
        help="Price and score alerts",
        description="Create, list, check, and manage alerts for price/score changes.",
    )
    alert_sub = alert_parser.add_subparsers(
        dest="alert_action", metavar="<action>",
    )

    # alert create
    alert_create = alert_sub.add_parser("create", help="Create a new alert")
    alert_create.add_argument("--product", type=int, default=None, help="Product ID")
    alert_create.add_argument("--supplier", default=None, help="Supplier ID")
    alert_create.add_argument(
        "--type", choices=["price", "score", "custom"], default="price",
        help="Alert type (default: price)",
    )
    alert_create.add_argument("--threshold", type=float, default=None, help="Threshold value")
    alert_create.add_argument("--condition", default="", help="Custom condition description")

    # alert list
    alert_list = alert_sub.add_parser("list", help="List alerts")
    alert_list.add_argument("--active", action="store_true", help="Show only active alerts")

    # alert check
    alert_sub.add_parser("check", help="Check all active alerts for triggers")

    # alert deactivate <alert-id>
    alert_deact = alert_sub.add_parser("deactivate", help="Deactivate an alert")
    alert_deact.add_argument("alert_id", type=int, help="Alert ID to deactivate")

    return parser


def main() -> int:
    """Main entry point."""
    parser = _build_parser()
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 0

    # Initialize DB (auto-creates tables on first run)
    try:
        from db import get_connection
        conn = get_connection()
        conn.close()
    except Exception as e:
        print(f"{RED}Failed to initialize database: {e}{RESET}", file=sys.stderr)
        return 1

    if args.debug:
        import logging
        logging.basicConfig(level=logging.DEBUG)
        print(f"{DIM}Debug mode enabled{RESET}")

    # Route to command handler
    try:
        if args.command == "search":
            from commands import search as cmd_search
            return cmd_search.run(args)
        elif args.command == "supplier":
            from commands import supplier as cmd_supplier
            return cmd_supplier.run(args)
        elif args.command == "product":
            from commands import product as cmd_product
            return cmd_product.run(args)
        elif args.command == "cost":
            from commands import cost as cmd_cost
            return cmd_cost.run(args)
        elif args.command == "rfq":
            from commands import rfq as cmd_rfq
            return cmd_rfq.run(args)
        elif args.command == "export":
            from commands import export as cmd_export
            return cmd_export.run(args)
        elif args.command == "config":
            from commands import config as cmd_config
            return cmd_config.run(args)
        elif args.command == "compliance":
            from commands import compliance as cmd_compliance
            return cmd_compliance.run(args)
        elif args.command == "compare":
            from commands import compare as cmd_compare
            return cmd_compare.run(args)
        elif args.command == "risk":
            from commands import risk_cmd as cmd_risk
            return cmd_risk.run(args)
        elif args.command == "negotiate":
            from commands import negotiate as cmd_negotiate
            return cmd_negotiate.run(args)
        elif args.command == "alert":
            from commands import alert as cmd_alert
            return cmd_alert.run(args)
        else:
            parser.print_help()
            return 1

    except KeyboardInterrupt:
        print(f"\n{DIM}Interrupted.{RESET}")
        return 0
    except Exception as e:
        if args.debug:
            import traceback
            traceback.print_exc()
        else:
            print(f"\n{RED}{BOLD}Unexpected error{RESET}: {e}", file=sys.stderr)
            print(
                f"{DIM}Run with --debug for full traceback.{RESET}",
                file=sys.stderr,
            )
        return 1


if __name__ == "__main__":
    sys.exit(main())
