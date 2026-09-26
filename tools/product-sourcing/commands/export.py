"""
Data export — suppliers, products, and cost calculations to CSV, JSON, or Markdown.

Commands:
    export suppliers [--format csv|json|md] [--output FILE]
    export products [--format csv|json|md] [--supplier X] [--output FILE]
    export costs [--format csv|json|md] [--output FILE]
"""

import csv
import io
import json
import sys
from argparse import Namespace
from pathlib import Path
from typing import Any, Dict, List

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


def _write_output(content: str, output_path: str = None, fmt: str = "csv") -> None:
    """Write content to file or stdout."""
    if output_path:
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        print(f"{GREEN}Exported to: {path}{RESET}")
    else:
        print(content)


def _to_csv(rows: List[Dict[str, Any]], columns: List[str]) -> str:
    """Convert list of dicts to CSV string."""
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=columns, extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        # Flatten JSON fields to strings
        flat = {}
        for k, v in row.items():
            if isinstance(v, (list, dict)):
                flat[k] = json.dumps(v)
            else:
                flat[k] = v
        writer.writerow(flat)
    return output.getvalue()


def _to_json(rows: List[Dict[str, Any]]) -> str:
    """Convert list of dicts to pretty JSON string."""
    return json.dumps(rows, indent=2, default=str)


def _to_markdown(rows: List[Dict[str, Any]], columns: List[str], title: str) -> str:
    """Convert list of dicts to Markdown table."""
    if not rows:
        return f"# {title}\n\n_No data_\n"

    lines = [f"# {title}\n"]

    # Header
    header = "| " + " | ".join(columns) + " |"
    separator = "| " + " | ".join(["---"] * len(columns)) + " |"
    lines.append(header)
    lines.append(separator)

    for row in rows:
        cells = []
        for col in columns:
            val = row.get(col, "")
            if isinstance(val, (list, dict)):
                val = json.dumps(val)
            elif val is None:
                val = ""
            cells.append(str(val).replace("|", "\\|")[:50])
        lines.append("| " + " | ".join(cells) + " |")

    return "\n".join(lines) + "\n"


def run_suppliers(args: Namespace) -> int:
    """Export supplier list."""
    fmt = getattr(args, "format", "csv")
    output = getattr(args, "output", None)

    suppliers = db.list_suppliers(limit=10000)

    if not suppliers:
        print(f"{YELLOW}No suppliers to export.{RESET}")
        return 0

    columns = [
        "supplier_id", "platform", "name", "name_cn", "url", "location",
        "supplier_type", "gold_years", "trade_assurance", "verified",
        "response_rate", "transaction_count", "on_time_delivery",
        "employee_count", "year_established", "main_products",
        "quality_score", "red_flags", "first_seen", "last_updated",
    ]

    if fmt == "csv":
        content = _to_csv(suppliers, columns)
    elif fmt == "json":
        content = _to_json(suppliers)
    elif fmt == "md":
        # Markdown uses a subset of columns for readability
        md_cols = [
            "supplier_id", "name", "platform", "supplier_type",
            "gold_years", "quality_score", "transaction_count",
        ]
        content = _to_markdown(suppliers, md_cols, "Supplier Export")
    else:
        content = _to_csv(suppliers, columns)

    _write_output(content, output, fmt)
    print(f"{DIM}Exported {len(suppliers)} suppliers ({fmt}){RESET}")

    return 0


def run_products(args: Namespace) -> int:
    """Export product list."""
    fmt = getattr(args, "format", "csv")
    output = getattr(args, "output", None)
    supplier_id = getattr(args, "supplier", None)

    if supplier_id:
        products = db.list_products_by_supplier(supplier_id, limit=10000)
    else:
        products = db.search_products("", limit=10000)

    if not products:
        print(f"{YELLOW}No products to export.{RESET}")
        return 0

    columns = [
        "product_id", "supplier_id", "platform", "url", "title", "title_cn",
        "category", "hs_code", "moq", "moq_unit", "price_min", "price_max",
        "price_currency", "customization", "sample_price", "sample_available",
        "lead_time_days", "specs", "first_seen", "last_updated",
    ]

    if fmt == "csv":
        content = _to_csv(products, columns)
    elif fmt == "json":
        content = _to_json(products)
    elif fmt == "md":
        md_cols = [
            "product_id", "title", "supplier_id", "price_min",
            "price_max", "moq", "category",
        ]
        content = _to_markdown(products, md_cols, "Product Export")
    else:
        content = _to_csv(products, columns)

    _write_output(content, output, fmt)
    print(f"{DIM}Exported {len(products)} products ({fmt}){RESET}")

    return 0


def run_costs(args: Namespace) -> int:
    """Export cost calculations."""
    fmt = getattr(args, "format", "csv")
    output = getattr(args, "output", None)

    # Get all cost calculations (no product_id filter in this path)
    conn = db.get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM cost_calculations ORDER BY calculated_at DESC LIMIT 10000"
        ).fetchall()
        costs = [dict(r) for r in rows]
    finally:
        conn.close()

    if not costs:
        print(f"{YELLOW}No cost calculations to export.{RESET}")
        return 0

    columns = [
        "id", "product_id", "quantity", "unit_cost_usd", "hs_code",
        "duty_rate", "duty_amount_usd", "freight_mode", "freight_cost_usd",
        "insurance_usd", "customs_fee_usd", "total_landed_usd",
        "per_unit_landed_usd", "margin_at_price", "calculated_at",
    ]

    if fmt == "csv":
        content = _to_csv(costs, columns)
    elif fmt == "json":
        content = _to_json(costs)
    elif fmt == "md":
        md_cols = [
            "id", "product_id", "quantity", "unit_cost_usd",
            "total_landed_usd", "per_unit_landed_usd", "margin_at_price",
        ]
        content = _to_markdown(costs, md_cols, "Cost Calculation Export")
    else:
        content = _to_csv(costs, columns)

    _write_output(content, output, fmt)
    print(f"{DIM}Exported {len(costs)} cost calculations ({fmt}){RESET}")

    return 0


def run(args: Namespace) -> int:
    """Route export subcommands."""
    action = getattr(args, "export_action", None)

    if action == "suppliers":
        return run_suppliers(args)
    elif action == "products":
        return run_products(args)
    elif action == "costs":
        return run_costs(args)
    else:
        print(f"{YELLOW}Usage: product-sourcing export <suppliers|products|costs>{RESET}",
              file=sys.stderr)
        return 1
