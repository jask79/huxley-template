#!/usr/bin/env python3
"""Verify CartPanda API connectivity.

Run from Huxley root:
    .venv/bin/python tools/cartpanda/scripts/test_connection.py

Reads CARTPANDA_API_KEY + CARTPANDA_BASE_URL from tools/cartpanda/.env (or
process env). Hits a lightweight endpoint to confirm auth + reachability.

Exit codes:
    0 — connection OK
    1 — missing config
    2 — API returned an error
    3 — network error
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

# Allow running as a script without installing the package: prepend tools/cartpanda
HERE = Path(__file__).resolve().parent
PKG_ROOT = HERE.parent
sys.path.insert(0, str(PKG_ROOT))

from dotenv import load_dotenv  # noqa: E402

ENV_PATH = PKG_ROOT / ".env"
if ENV_PATH.exists():
    load_dotenv(ENV_PATH)
else:
    print(f"[warn] No .env found at {ENV_PATH} — using process env only.")

from cartpanda import CartPandaClient, CartPandaSettings  # noqa: E402
from cartpanda.exceptions import (  # noqa: E402
    CartPandaAPIError,
    CartPandaAuthError,
)


def main() -> int:
    settings = CartPandaSettings()
    if not settings.api_key:
        print("[fail] CARTPANDA_API_KEY is not set.")
        print(f"       Copy {PKG_ROOT}/.env.example to {PKG_ROOT}/.env and fill in real values.")
        return 1

    print(f"[info] Base URL : {settings.base_url}")
    print(f"[info] Shop slug: {settings.shop_slug or '(unset)'}")
    print(f"[info] API key  : {settings.api_key[:6]}…{settings.api_key[-4:]} ({len(settings.api_key)} chars)")
    print()

    try:
        with CartPandaClient(settings=settings) as client:
            # Try a few lightweight read endpoints — the first one that returns
            # 2xx wins. If they all 404, the base URL is wrong.
            probes = [
                ("GET", "/products", {"per_page": 1}),
                ("GET", "/shop", None),
                ("GET", "/orders", {"per_page": 1}),
            ]
            for method, path, params in probes:
                try:
                    print(f"[probe] {method} {settings.base_url}{path} …")
                    client.request(method, path, params=params)
                    print(f"[ok]    {method} {path} returned 2xx.")
                    print()
                    print("[done] CartPanda connection looks healthy.")
                    return 0
                except CartPandaAuthError as exc:
                    print(f"[fail] {exc}")
                    print("       Auth header is wrong. Confirm:")
                    print("       - CARTPANDA_API_KEY is the correct token")
                    print("       - Authorization scheme is 'Bearer' (default) vs 'X-API-Key'")
                    print("         (edit cartpanda/client.py _default_headers if needed)")
                    return 2
                except CartPandaAPIError as exc:
                    print(f"[skip] {exc}")
                    continue
        print()
        print("[fail] All probe endpoints returned errors. Confirm CARTPANDA_BASE_URL.")
        return 2
    except Exception as exc:  # noqa: BLE001
        print(f"[error] Unexpected: {exc}")
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
