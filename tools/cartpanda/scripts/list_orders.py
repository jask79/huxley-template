#!/usr/bin/env python3
"""List recent CartPanda orders.

Run from Huxley root:
    .venv/bin/python tools/cartpanda/scripts/list_orders.py
    .venv/bin/python tools/cartpanda/scripts/list_orders.py --per-page 10 --status paid

Example usage of the client — pulls a page of orders and prints a summary.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PKG_ROOT = HERE.parent
sys.path.insert(0, str(PKG_ROOT))

from dotenv import load_dotenv  # noqa: E402

ENV_PATH = PKG_ROOT / ".env"
if ENV_PATH.exists():
    load_dotenv(ENV_PATH)

from cartpanda import CartPandaClient  # noqa: E402
from cartpanda.exceptions import CartPandaAPIError  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="List recent CartPanda orders")
    parser.add_argument("--page", type=int, default=1)
    parser.add_argument("--per-page", type=int, default=20)
    parser.add_argument("--status", help='financial_status filter (e.g. "paid", "refunded")')
    args = parser.parse_args()

    try:
        with CartPandaClient() as client:
            result = client.orders.list(
                page=args.page,
                per_page=args.per_page,
                financial_status=args.status,
            )
    except CartPandaAPIError as exc:
        print(f"[error] {exc}", file=sys.stderr)
        return 1

    orders = result.orders
    if not orders:
        print("[info] No orders returned.")
        return 0

    print(f"[info] {len(orders)} order(s) returned (page {args.page}):")
    print()
    print(f"{'ORDER #':<12} {'STATUS':<12} {'TOTAL':>10}  {'CREATED':<25} EMAIL")
    print("-" * 90)
    for o in orders:
        order_number = str(o.order_number or o.id)[:11]
        fin_status = (o.financial_status or "-")[:11]
        total = f"{o.total or 0:.2f}" if o.total is not None else "-"
        created = o.created_at.isoformat() if o.created_at else "-"
        email = o.email or "-"
        print(f"{order_number:<12} {fin_status:<12} {total:>10}  {created[:25]:<25} {email}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
