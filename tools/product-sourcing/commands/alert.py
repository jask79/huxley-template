"""
Price and score alert management commands.

Commands:
    alert create --product <id> --type price --threshold <value>  Create alert
    alert list [--active]                                         List alerts
    alert check                                                   Check all alerts
    alert deactivate <alert-id>                                   Deactivate alert
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


def run_create(args: Namespace) -> int:
    """Create a new alert."""
    product_id = getattr(args, "product", None)
    supplier_id = getattr(args, "supplier", None)
    alert_type = getattr(args, "type", "price")
    threshold = getattr(args, "threshold", None)
    condition = getattr(args, "condition", "")

    if not product_id and not supplier_id:
        print(f"{RED}Provide at least --product or --supplier.{RESET}")
        return 1

    # Build condition description
    if not condition:
        if alert_type == "price":
            if threshold:
                condition = f"Price exceeds ${threshold:.2f}"
            else:
                condition = "Price change detected"
        elif alert_type == "score":
            if threshold:
                condition = f"Score drops below {threshold:.0f}"
            else:
                condition = "Score change detected"
        else:
            condition = f"Alert type: {alert_type}"

    alert_id = db.create_alert(
        product_id=product_id,
        supplier_id=supplier_id,
        alert_type=alert_type,
        condition_desc=condition,
        threshold=threshold,
    )

    print(f"\n{GREEN}Alert created: #{alert_id}{RESET}")
    print(f"  Type: {alert_type}")
    print(f"  Condition: {condition}")
    if threshold:
        print(f"  Threshold: {threshold}")
    if product_id:
        print(f"  Product ID: {product_id}")
    if supplier_id:
        print(f"  Supplier ID: {supplier_id}")

    print()
    return 0


def run_list(args: Namespace) -> int:
    """List alerts."""
    active_only = getattr(args, "active", False)

    alerts = db.list_alerts(active_only=active_only)
    label = "Active Alerts" if active_only else "All Alerts"

    if not alerts:
        print(f"{YELLOW}No alerts found.{RESET}")
        return 0

    print(f"\n{BOLD}{CYAN}{label}{RESET} ({len(alerts)} total)\n")

    print(
        f"  {BOLD}{'ID':>4}  {'Type':<8} {'Active':<8} "
        f"{'Condition':<30} {'Threshold':>10} {'Triggered':>10}{RESET}"
    )
    print(f"  {'─' * 80}")

    for a in alerts:
        active = f"{GREEN}YES{RESET}" if a.get("active") else f"{DIM}no{RESET}"
        cond = a.get("condition_desc", "")[:29]
        threshold = f"{a['threshold']:.2f}" if a.get("threshold") is not None else "--"
        triggered = str(a.get("trigger_count", 0))

        print(
            f"  {a['id']:>4}  {a.get('alert_type', 'price'):<8} {active:<8} "
            f"{cond:<30} {threshold:>10} {triggered:>10}"
        )

    print()
    return 0


def run_check(args: Namespace) -> int:
    """Check all active alerts for trigger conditions."""
    alerts = db.get_active_alerts()

    if not alerts:
        print(f"{YELLOW}No active alerts.{RESET}")
        return 0

    print(f"\n{BOLD}{CYAN}Checking {len(alerts)} Active Alert(s){RESET}\n")

    triggered_count = 0

    for a in alerts:
        alert_id = a["id"]
        alert_type = a.get("alert_type", "price")
        threshold = a.get("threshold")
        product_id = a.get("product_id")
        supplier_id = a.get("supplier_id")

        triggered = False
        reason = ""

        if alert_type == "price" and product_id and threshold:
            product = db.get_product(product_id)
            if product and product.get("price_min") is not None:
                if product["price_min"] > threshold:
                    triggered = True
                    reason = f"Price ${product['price_min']:.2f} exceeds threshold ${threshold:.2f}"
                elif product.get("price_max") and product["price_max"] > threshold:
                    triggered = True
                    reason = f"Max price ${product['price_max']:.2f} exceeds threshold ${threshold:.2f}"

        elif alert_type == "score" and supplier_id and threshold:
            supplier = db.get_supplier(supplier_id)
            if supplier and supplier.get("quality_score") is not None:
                if supplier["quality_score"] < threshold:
                    triggered = True
                    reason = f"Score {supplier['quality_score']:.1f} below threshold {threshold:.0f}"

        if triggered:
            db.trigger_alert(alert_id)
            triggered_count += 1
            print(f"  {RED}TRIGGERED{RESET} Alert #{alert_id}: {reason}")
        else:
            print(f"  {GREEN}OK{RESET} Alert #{alert_id}: {a.get('condition_desc', '')}")

    print(f"\n  {BOLD}Result: {triggered_count} triggered, "
          f"{len(alerts) - triggered_count} OK{RESET}")

    print()
    return 0


def run_deactivate(args: Namespace) -> int:
    """Deactivate an alert."""
    alert_id = args.alert_id

    if db.deactivate_alert(alert_id):
        print(f"{GREEN}Alert #{alert_id} deactivated.{RESET}")
        return 0
    else:
        print(f"{RED}Alert #{alert_id} not found or already inactive.{RESET}")
        return 1


def run(args: Namespace) -> int:
    """Route alert subcommands."""
    action = getattr(args, "alert_action", None)

    if action == "create":
        return run_create(args)
    elif action == "list":
        return run_list(args)
    elif action == "check":
        return run_check(args)
    elif action == "deactivate":
        return run_deactivate(args)
    else:
        print(
            f"{YELLOW}Usage: product-sourcing alert "
            f"<create|list|check|deactivate>{RESET}",
            file=sys.stderr,
        )
        return 1
