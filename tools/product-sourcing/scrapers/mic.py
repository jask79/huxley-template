"""
Made-in-China.com scraper — Sourcerer (stub)

CLI:
    python3 mic.py search "silicone phone case" --max-results 20
    python3 mic.py product "https://www.made-in-china.com/..." --output /tmp/...
    python3 mic.py supplier "https://..." --output /tmp/...

Exit codes:
    0 = success
    1 = general error
    2 = CAPTCHA / bot block detected

Status: NOT YET IMPLEMENTED. This is a structural stub that follows the same
pattern as alibaba.py, ali1688.py, and dhgate.py for future implementation.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import random
import re
import sys
import time
from pathlib import Path
from typing import Any, Optional
from urllib.parse import quote_plus

# ---------------------------------------------------------------------------
# sys.path
# ---------------------------------------------------------------------------
_SCRAPERS_DIR = Path(__file__).parent
_TOOLS_DIR = _SCRAPERS_DIR.parent
if str(_TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(_TOOLS_DIR))
if str(_SCRAPERS_DIR.parent.parent) not in sys.path:
    sys.path.insert(0, str(_SCRAPERS_DIR.parent.parent))

from scrapers import normalize_platform_id  # noqa: E402

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [mic] %(levelname)s %(message)s",
    stream=sys.stderr,
)
log = logging.getLogger("mic")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
SCREENSHOT_DIR = Path("/tmp/catalyst-screenshots")
PLATFORM = "made-in-china"

USER_AGENTS = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_5) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
]

VIEWPORTS = [
    {"width": 1440, "height": 900},
    {"width": 1920, "height": 1080},
    {"width": 1366, "height": 768},
]


# ---------------------------------------------------------------------------
# Browser helpers (same pattern as other scrapers)
# ---------------------------------------------------------------------------

def _make_browser(p, headed: bool = False):
    """Launch Chromium with stealth configuration."""
    ua = random.choice(USER_AGENTS)
    viewport = random.choice(VIEWPORTS)

    browser = p.chromium.launch(
        headless=not headed,
        args=[
            "--no-sandbox",
            "--disable-blink-features=AutomationControlled",
            "--disable-infobars",
            "--disable-dev-shm-usage",
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-extensions",
        ],
    )
    context = browser.new_context(
        user_agent=ua,
        viewport=viewport,
        locale="en-US",
        timezone_id="America/New_York",
        extra_http_headers={
            "Accept-Language": "en-US,en;q=0.9",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Dest": "document",
            "Upgrade-Insecure-Requests": "1",
        },
    )
    context.add_init_script("""
        Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
        Object.defineProperty(navigator, 'plugins', {get: () => [1,2,3,4,5]});
        Object.defineProperty(navigator, 'languages', {get: () => ['en-US', 'en']});
        window.chrome = {runtime: {}};
    """)
    return browser, context


def _save_screenshot(page, name: str) -> str:
    """Save a debug screenshot and return the path."""
    SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
    ts = int(time.time())
    path = str(SCREENSHOT_DIR / f"mic_{name}_{ts}.png")
    try:
        page.screenshot(path=path, full_page=False)
        log.info("Screenshot saved: %s", path)
    except Exception as exc:
        log.warning("Could not save screenshot: %s", exc)
    return path


def _check_blocked(page) -> bool:
    """Return True if we're on a CAPTCHA or block page."""
    content = page.content().lower()
    url = page.url.lower()
    blocked_signals = [
        "captcha", "verify you are human", "access denied",
        "robot", "security check", "challenge",
    ]
    return any(sig in content or sig in url for sig in blocked_signals)


# ---------------------------------------------------------------------------
# Stub commands
# ---------------------------------------------------------------------------

def cmd_search(args) -> list[dict]:
    """Search Made-in-China — NOT YET IMPLEMENTED."""
    query = args.query
    max_results = args.max_results
    headed = args.headed

    search_url = (
        f"https://www.made-in-china.com/products-search/"
        f"hot-china-products/{quote_plus(query)}.html"
    )

    log.info(
        "Made-in-China scraper not yet implemented. "
        "Search URL: %s. Use --headed for manual browsing.",
        search_url,
    )

    if headed:
        log.info("Headed mode: opening browser for manual browsing")
        try:
            from playwright.sync_api import sync_playwright
            with sync_playwright() as p:
                browser, context = _make_browser(p, headed=True)
                page = context.new_page()
                page.goto(search_url, wait_until="domcontentloaded")
                log.info("Browser opened. Close manually when done.")
                input("Press Enter to close browser...")
                browser.close()
        except ImportError:
            log.error("Playwright not installed. Run: pip install playwright && playwright install")
        except Exception as exc:
            log.error("Browser error: %s", exc)
    else:
        log.info("Use --headed for manual browsing of: %s", search_url)

    return []


def cmd_product(args) -> dict:
    """Scrape a Made-in-China product page — NOT YET IMPLEMENTED."""
    log.info("Made-in-China product scraper not yet implemented.")
    return {}


def cmd_supplier(args) -> dict:
    """Scrape a Made-in-China supplier page — NOT YET IMPLEMENTED."""
    log.info("Made-in-China supplier scraper not yet implemented.")
    return {}


# ---------------------------------------------------------------------------
# Output helper
# ---------------------------------------------------------------------------

def _write_output(data: Any, output_path: Optional[str]) -> None:
    """Write JSON to file or stdout."""
    json_str = json.dumps(data, indent=2, ensure_ascii=False)
    if output_path:
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json_str, encoding="utf-8")
        log.info("Output written to %s", output_path)
    else:
        print(json_str)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Made-in-China.com scraper for Sourcerer (stub)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--headed", action="store_true", help="Run browser in headed mode")
    parser.add_argument(
        "--delay", type=float, default=3.0, metavar="SECONDS",
        help="Base delay between requests (default: 3.0)",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    # search
    p_search = subparsers.add_parser("search", help="Search Made-in-China products")
    p_search.add_argument("query", help="Search query")
    p_search.add_argument("--max-results", type=int, default=20, help="Max results")
    p_search.add_argument("--output", default=None, help="Output JSON file path")

    # product
    p_product = subparsers.add_parser("product", help="Scrape a product page")
    p_product.add_argument("url", help="Product URL")
    p_product.add_argument("--output", default=None, help="Output JSON file path")

    # supplier
    p_supplier = subparsers.add_parser("supplier", help="Scrape a supplier profile")
    p_supplier.add_argument("url", help="Supplier URL")
    p_supplier.add_argument("--output", default=None, help="Output JSON file path")

    args = parser.parse_args()

    try:
        if args.command == "search":
            data = cmd_search(args)
        elif args.command == "product":
            data = cmd_product(args)
        elif args.command == "supplier":
            data = cmd_supplier(args)
        else:
            parser.error(f"Unknown command: {args.command}")
            return

        _write_output(data, args.output)

    except SystemExit:
        raise
    except Exception as exc:
        log.error("Fatal error: %s", exc)
        sys.exit(1)


if __name__ == "__main__":
    main()
