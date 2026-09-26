"""
RFQ (Request for Quotation) lifecycle tracking.

Commands:
    rfq create --supplier <id> --desc "description" [--product-id N] [--qty N]
    rfq update <rfq_id> --status <status> [--quote X] [--lead-time N] [--notes "..."]
    rfq list [--status X] [--supplier X]
    rfq show <rfq_id>
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

# Status display colors
STATUS_COLORS = {
    "draft": DIM,
    "sent": CYAN,
    "quoted": YELLOW,
    "negotiating": YELLOW,
    "accepted": GREEN,
    "rejected": RED,
}


def _status_display(status: str) -> str:
    """Format a status string with color."""
    color = STATUS_COLORS.get(status, RESET)
    return f"{color}{status}{RESET}"


def run_create(args: Namespace) -> int:
    """Create a new RFQ."""
    supplier_id = args.supplier
    description = args.desc
    product_id = getattr(args, "product_id", None)
    qty = getattr(args, "qty", None)
    target_price = getattr(args, "target_price", None)

    # Verify supplier exists
    supplier = db.get_supplier(supplier_id)
    if not supplier:
        print(f"{RED}Supplier not found: {supplier_id}{RESET}")
        print(f"{DIM}Use 'product-sourcing supplier list' to see tracked suppliers.{RESET}")
        return 1

    # Verify product exists if provided
    if product_id is not None:
        product = db.get_product(product_id)
        if not product:
            print(f"{RED}Product not found: {product_id}{RESET}")
            return 1

    rfq_id = db.create_rfq(
        supplier_id=supplier_id,
        description=description,
        product_id=product_id,
        quantity=qty,
        target_price=target_price,
    )

    print(f"\n{GREEN}{BOLD}RFQ created successfully{RESET}")
    print(f"  {BOLD}RFQ ID:{RESET}        {rfq_id}")
    print(f"  {BOLD}Supplier:{RESET}      {supplier['name']} ({supplier_id})")
    print(f"  {BOLD}Description:{RESET}   {description}")
    if product_id is not None:
        print(f"  {BOLD}Product:{RESET}       #{product_id}")
    if qty is not None:
        print(f"  {BOLD}Quantity:{RESET}      {qty:,}")
    if target_price is not None:
        print(f"  {BOLD}Target Price:{RESET} ${target_price:.2f}")
    print(f"  {BOLD}Status:{RESET}        {_status_display('draft')}")
    print(f"\n  {DIM}Update: product-sourcing rfq update {rfq_id} --status sent{RESET}")

    return 0


def run_update(args: Namespace) -> int:
    """Update an existing RFQ."""
    rfq_id = args.rfq_id
    status = getattr(args, "status", None)
    quote = getattr(args, "quote", None)
    lead_time = getattr(args, "lead_time", None)
    notes = getattr(args, "notes", None)

    # Verify RFQ exists
    rfq = db.get_rfq(rfq_id)
    if not rfq:
        print(f"{RED}RFQ not found: {rfq_id}{RESET}")
        return 1

    if status is None and quote is None and lead_time is None and notes is None:
        print(f"{YELLOW}No updates specified. Use --status, --quote, --lead-time, or --notes.{RESET}")
        return 1

    updated = db.update_rfq(
        rfq_id=rfq_id,
        status=status,
        supplier_quote=quote,
        lead_time_quoted=lead_time,
        notes=notes,
    )

    if not updated:
        print(f"{RED}Failed to update RFQ {rfq_id}{RESET}")
        return 1

    # Fetch updated RFQ
    rfq = db.get_rfq(rfq_id)

    print(f"\n{GREEN}{BOLD}RFQ #{rfq_id} updated{RESET}")
    print(f"  {BOLD}Status:{RESET}     {_status_display(rfq['status'])}")
    if rfq.get("supplier_quote") is not None:
        print(f"  {BOLD}Quote:{RESET}      ${rfq['supplier_quote']:.2f} {rfq.get('quote_currency', 'USD')}")
    if rfq.get("lead_time_quoted") is not None:
        print(f"  {BOLD}Lead Time:{RESET} {rfq['lead_time_quoted']} days")
    if rfq.get("notes"):
        print(f"  {BOLD}Notes:{RESET}     {rfq['notes']}")

    return 0


def run_list(args: Namespace) -> int:
    """List RFQs with optional filters."""
    status = getattr(args, "status", None)
    supplier_id = getattr(args, "supplier", None)

    rfqs = db.list_rfqs(status=status, supplier_id=supplier_id)

    if not rfqs:
        msg = "No RFQs found"
        if status:
            msg += f" with status '{status}'"
        if supplier_id:
            msg += f" for supplier {supplier_id}"
        print(f"{YELLOW}{msg}.{RESET}")
        return 0

    title = f"RFQs ({len(rfqs)})"
    if status:
        title += f" — status: {status}"
    if supplier_id:
        title += f" — supplier: {supplier_id}"
    print(f"\n{BOLD}{CYAN}{title}{RESET}\n")

    # Header
    print(
        f"  {BOLD}{'ID':>4}  {'Status':<12}  {'Supplier':<20} "
        f"{'Qty':>8}  {'Target':>8}  {'Quote':>8}  {'Description'}{RESET}"
    )
    print(f"  {'=' * 95}")

    for r in rfqs:
        rid = r["rfq_id"]
        st = _status_display(r["status"])
        sup = r["supplier_id"][:19]
        qty = f"{r['quantity']:,}" if r.get("quantity") else "--"
        target = f"${r['target_price']:.2f}" if r.get("target_price") is not None else "--"
        quote = f"${r['supplier_quote']:.2f}" if r.get("supplier_quote") is not None else "--"
        desc = r["description"][:30]

        print(
            f"  {rid:>4}  {st:<12}  {sup:<20} "
            f"{qty:>8}  {target:>8}  {quote:>8}  {desc}"
        )

    print()
    return 0


def run_show(args: Namespace) -> int:
    """Show detailed RFQ information."""
    rfq_id = args.rfq_id

    rfq = db.get_rfq(rfq_id)
    if not rfq:
        print(f"{RED}RFQ not found: {rfq_id}{RESET}")
        return 1

    print(f"\n{BOLD}{CYAN}RFQ #{rfq['rfq_id']}{RESET}")
    print(f"  {BOLD}Status:{RESET}          {_status_display(rfq['status'])}")
    print()

    # Supplier info
    print(f"  {BOLD}Supplier:{RESET}        {rfq['supplier_id']}")
    supplier = db.get_supplier(rfq["supplier_id"])
    if supplier:
        print(f"                     {supplier['name']}")
        score = supplier.get("quality_score")
        if score is not None:
            print(f"                     Score: {score:.1f}")

    # Product link
    if rfq.get("product_id"):
        product = db.get_product(rfq["product_id"])
        if product:
            print(f"  {BOLD}Product:{RESET}         [{rfq['product_id']}] {product['title'][:40]}")
        else:
            print(f"  {BOLD}Product:{RESET}         #{rfq['product_id']}")

    print()

    # Request details
    print(f"  {BOLD}Description:{RESET}     {rfq['description']}")
    if rfq.get("quantity"):
        print(f"  {BOLD}Quantity:{RESET}        {rfq['quantity']:,}")
    if rfq.get("target_price") is not None:
        print(f"  {BOLD}Target Price:{RESET}   ${rfq['target_price']:.2f}")

    # Quote details
    if rfq.get("supplier_quote") is not None:
        print(f"\n  {BOLD}Supplier Quote{RESET}")
        print(f"    Unit Price:      ${rfq['supplier_quote']:.2f} {rfq.get('quote_currency', 'USD')}")
        if rfq.get("quote_moq"):
            print(f"    Quote MOQ:       {rfq['quote_moq']:,}")
        if rfq.get("lead_time_quoted"):
            print(f"    Lead Time:       {rfq['lead_time_quoted']} days")

    # Samples
    if rfq.get("sample_requested"):
        print(f"\n  {BOLD}Sample{RESET}")
        print(f"    Requested:       Yes")
        if rfq.get("sample_cost") is not None:
            print(f"    Sample Cost:     ${rfq['sample_cost']:.2f}")

    # Notes
    if rfq.get("notes"):
        print(f"\n  {BOLD}Notes:{RESET}           {rfq['notes']}")

    # Timestamps
    print(f"\n  {DIM}Created: {rfq['created_at']}{RESET}")
    print(f"  {DIM}Updated: {rfq['updated_at']}{RESET}")

    # Suggest next action
    status = rfq["status"]
    if status == "draft":
        print(f"\n  {DIM}Next: product-sourcing rfq update {rfq_id} --status sent{RESET}")
    elif status == "sent":
        print(f"\n  {DIM}Next: product-sourcing rfq update {rfq_id} --status quoted --quote <price>{RESET}")
    elif status == "quoted":
        print(f"\n  {DIM}Next: product-sourcing rfq update {rfq_id} --status negotiating{RESET}")
        print(f"  {DIM}  or: product-sourcing rfq update {rfq_id} --status accepted{RESET}")

    return 0


def run(args: Namespace) -> int:
    """Route RFQ subcommands."""
    action = getattr(args, "rfq_action", None)

    if action == "create":
        return run_create(args)
    elif action == "update":
        return run_update(args)
    elif action == "list":
        return run_list(args)
    elif action == "show":
        return run_show(args)
    else:
        print(f"{YELLOW}Usage: product-sourcing rfq <create|update|list|show>{RESET}",
              file=sys.stderr)
        return 1
