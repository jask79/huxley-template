"""
Alibaba.com scraper — Sourcerer

CLI:
    python3 alibaba.py search "silicone phone case" --max-results 20 --output /tmp/...
    python3 alibaba.py product "https://www.alibaba.com/product-detail/..." --output /tmp/...
    python3 alibaba.py supplier "https://example.en.alibaba.com" --output /tmp/...

Exit codes:
    0 = success
    1 = general error
    2 = CAPTCHA / bot block detected
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
from urllib.parse import quote_plus, urljoin, urlparse

# ---------------------------------------------------------------------------
# sys.path: allow both `python3 alibaba.py` and `from scrapers.alibaba import`
# ---------------------------------------------------------------------------
_SCRAPERS_DIR = Path(__file__).parent
_TOOLS_DIR = _SCRAPERS_DIR.parent
if str(_TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(_TOOLS_DIR))
if str(_SCRAPERS_DIR.parent.parent) not in sys.path:
    sys.path.insert(0, str(_SCRAPERS_DIR.parent.parent))

from scrapers import normalize_platform_id, parse_moq, parse_price_range  # noqa: E402

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [alibaba] %(levelname)s %(message)s",
    stream=sys.stderr,
)
log = logging.getLogger("alibaba")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
SCREENSHOT_DIR = Path("/tmp/catalyst-screenshots")
PLATFORM = "alibaba"

USER_AGENTS = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_5) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36 Edg/123.0.0.0",
]

VIEWPORTS = [
    {"width": 1440, "height": 900},
    {"width": 1920, "height": 1080},
    {"width": 1366, "height": 768},
    {"width": 1280, "height": 800},
    {"width": 1536, "height": 864},
]

# ---------------------------------------------------------------------------
# Browser helpers
# ---------------------------------------------------------------------------

def _random_delay(base: float = 2.0, jitter: float = 3.0) -> None:
    time.sleep(base + random.random() * jitter)


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
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Dest": "document",
            "Upgrade-Insecure-Requests": "1",
        },
    )
    # Disable webdriver flag
    context.add_init_script("""
        Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
        Object.defineProperty(navigator, 'plugins', {get: () => [1,2,3,4,5]});
        Object.defineProperty(navigator, 'languages', {get: () => ['en-US', 'en']});
        window.chrome = {runtime: {}};
    """)
    return browser, context


def _simulate_mouse_movement(page) -> None:
    """Simulate human-like random mouse movement."""
    try:
        for _ in range(random.randint(2, 5)):
            x = random.randint(100, 1200)
            y = random.randint(100, 700)
            page.mouse.move(x, y)
            time.sleep(random.uniform(0.05, 0.2))
    except Exception:
        pass


def _save_screenshot(page, name: str) -> str:
    """Save a debug screenshot and return the path."""
    SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
    ts = int(time.time())
    path = str(SCREENSHOT_DIR / f"alibaba_{name}_{ts}.png")
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
        "captcha",
        "verify you are human",
        "access denied",
        "robot",
        "security check",
        "verify your identity",
        "challenge",
    ]
    return any(sig in content or sig in url for sig in blocked_signals)


# ---------------------------------------------------------------------------
# Parsers — search results
# ---------------------------------------------------------------------------

def _extract_supplier_id_from_url(url: str) -> str:
    """Extract a stable ID from a supplier/store URL."""
    parsed = urlparse(url)
    # e.g. example.en.alibaba.com → "example"
    host = parsed.netloc or parsed.path
    host = host.replace(".en.alibaba.com", "").replace("www.", "").replace("alibaba.com", "")
    clean = re.sub(r"[^a-zA-Z0-9_-]", "", host)
    return clean or "unknown"


def _extract_product_id_from_url(url: str) -> str:
    """Extract product ID from Alibaba product URL."""
    m = re.search(r"/product-detail/[^/]+-(\d+)\.html", url)
    if m:
        return m.group(1)
    # fallback — use last numeric segment
    nums = re.findall(r"\d{6,}", url)
    return nums[-1] if nums else "unknown"


def _parse_gold_years(text: str) -> int:
    """Parse '5 YRS' or '5 Year(s)' → 5."""
    if not text:
        return 0
    m = re.search(r"(\d+)\s*(?:yr|year)", text, re.IGNORECASE)
    return int(m.group(1)) if m else 0


def _parse_response_rate(text: str) -> Optional[float]:
    """Parse '95.2% Response Rate' → 0.952."""
    if not text:
        return None
    m = re.search(r"(\d+(?:\.\d+)?)\s*%", text)
    return round(float(m.group(1)) / 100, 4) if m else None


def _scrape_search_results(page, max_results: int) -> list[dict]:
    """Extract product cards from the current Alibaba search results page."""
    results = []

    # Wait for product cards to appear
    try:
        page.wait_for_selector(
            ".organic-gallery-offer-outter, .list-no-v2-main, .m-gallery-product-item-v2",
            timeout=30000,
        )
    except Exception:
        log.warning("Product card selector timed out — attempting fallback selectors")

    _simulate_mouse_movement(page)
    _random_delay(1.0, 1.5)

    # Scroll to load lazy images
    page.evaluate("window.scrollTo(0, document.body.scrollHeight / 2)")
    _random_delay(1.0, 1.0)
    page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
    _random_delay(1.0, 1.0)
    page.evaluate("window.scrollTo(0, 0)")

    cards = page.query_selector_all(
        ".organic-gallery-offer-outter, .list-no-v2-main, .m-gallery-product-item-v2"
    )
    if not cards:
        # Try broader fallback
        cards = page.query_selector_all("[class*='offer'], [class*='product-item']")

    log.info("Found %d product cards", len(cards))

    for card in cards[:max_results]:
        try:
            result = _parse_search_card(card)
            if result and result.get("product_title"):
                results.append(result)
        except Exception as exc:
            log.warning("Error parsing card: %s", exc)

    return results


def _get_text(el, selector: str) -> str:
    """Safe inner_text() from a child selector."""
    try:
        child = el.query_selector(selector)
        return child.inner_text().strip() if child else ""
    except Exception:
        return ""


def _get_attr(el, selector: str, attr: str) -> str:
    """Safe get_attribute() from a child selector."""
    try:
        child = el.query_selector(selector)
        return (child.get_attribute(attr) or "").strip() if child else ""
    except Exception:
        return ""


def _parse_search_card(card) -> dict:
    """Parse a single product card element into a result dict."""
    # Product link and title
    product_url = ""
    product_title = ""
    for sel in ["a.organic-gallery-offer__img", "a[class*='product']", "h2 a", ".title a", "a"]:
        try:
            link = card.query_selector(sel)
            if link:
                href = link.get_attribute("href") or ""
                if "alibaba.com" in href or href.startswith("/"):
                    product_url = href if href.startswith("http") else f"https:{href}"
                    product_title = link.inner_text().strip() or _get_attr(card, sel, "title")
                    break
        except Exception:
            continue

    # Product title via dedicated element if not found above
    if not product_title:
        for sel in [".organic-gallery-offer__title", ".title", "h2", "[class*='title']"]:
            product_title = _get_text(card, sel)
            if product_title:
                break

    # Price
    price_text = ""
    for sel in [".price-range", ".price", "[class*='price']"]:
        price_text = _get_text(card, sel)
        if price_text:
            break
    price_min, price_max = parse_price_range(price_text)

    # Currency
    currency = "USD"
    if "¥" in price_text or "CNY" in price_text.upper() or "RMB" in price_text.upper():
        currency = "CNY"
    elif "€" in price_text:
        currency = "EUR"

    # MOQ
    moq_text = ""
    for sel in [".moq", "[class*='moq']", ".min-order"]:
        moq_text = _get_text(card, sel)
        if moq_text:
            break
    moq_qty, moq_unit = parse_moq(moq_text)

    # Supplier info
    supplier_name = ""
    supplier_url = ""
    for sel in [".supplier-name a", ".company-name a", "[class*='supplier'] a", "[class*='company'] a"]:
        try:
            supplier_el = card.query_selector(sel)
            if supplier_el:
                supplier_name = supplier_el.inner_text().strip()
                href = supplier_el.get_attribute("href") or ""
                supplier_url = href if href.startswith("http") else f"https:{href}"
                break
        except Exception:
            continue

    # Gold years
    gold_text = ""
    for sel in ["[class*='gold']", "[class*='yrs']", "[class*='year']"]:
        gold_text = _get_text(card, sel)
        if gold_text:
            break
    gold_years = _parse_gold_years(gold_text)

    # Trade assurance
    ta_indicators = card.query_selector_all("[class*='trade-assurance'], [class*='trade_assurance']")
    trade_assurance = len(ta_indicators) > 0
    if not trade_assurance:
        card_text = card.inner_text()
        trade_assurance = "trade assurance" in card_text.lower()

    # Verified
    verified_els = card.query_selector_all("[class*='verified'], [class*='assess']")
    verified = len(verified_els) > 0

    # Response rate
    response_text = ""
    for sel in ["[class*='response']", "[class*='reply']"]:
        response_text = _get_text(card, sel)
        if response_text:
            break
    response_rate = _parse_response_rate(response_text)

    # Image URL
    image_url = ""
    for sel in ["img.main-img", ".product-img img", "[class*='img'] img", "img"]:
        try:
            img_el = card.query_selector(sel)
            if img_el:
                src = img_el.get_attribute("src") or img_el.get_attribute("data-src") or ""
                if src and not src.startswith("data:"):
                    image_url = src
                    break
        except Exception:
            continue

    # Category
    category = ""
    for sel in ["[class*='category']", "[class*='breadcrumb']"]:
        category = _get_text(card, sel)
        if category:
            break

    # Derive supplier ID
    supplier_raw_id = _extract_supplier_id_from_url(supplier_url) if supplier_url else "unknown"
    supplier_id = normalize_platform_id(PLATFORM, supplier_raw_id)

    return {
        "supplier_id": supplier_id,
        "supplier_name": supplier_name or None,
        "supplier_name_cn": None,
        "supplier_url": supplier_url or None,
        "gold_years": gold_years,
        "trade_assurance": trade_assurance,
        "verified": verified,
        "response_rate": response_rate,
        "product_title": product_title or None,
        "product_title_cn": None,
        "product_url": product_url or None,
        "price_min": price_min,
        "price_max": price_max,
        "price_currency": currency,
        "moq": moq_qty,
        "moq_unit": moq_unit,
        "image_url": image_url or None,
        "category": category or None,
    }


# ---------------------------------------------------------------------------
# Command: search
# ---------------------------------------------------------------------------

def cmd_search(args) -> list[dict]:
    from playwright.sync_api import sync_playwright

    query = args.query
    max_results = args.max_results
    delay = args.delay
    headed = args.headed

    search_url = f"https://www.alibaba.com/trade/search?SearchText={quote_plus(query)}&IndexArea=product_en"

    log.info("Searching Alibaba: %s (max=%d)", query, max_results)

    with sync_playwright() as p:
        browser, context = _make_browser(p, headed=headed)
        page = context.new_page()
        page.set_default_timeout(30000)
        page.set_default_navigation_timeout(60000)

        try:
            # Navigate to search
            page.goto(search_url, wait_until="domcontentloaded")
            _random_delay(delay, 2.0)

            if _check_blocked(page):
                log.error("Bot block / CAPTCHA detected on search page")
                _save_screenshot(page, "search_blocked")
                sys.exit(2)

            results = _scrape_search_results(page, max_results)
            log.info("Extracted %d results", len(results))

            # If we need more and there are more pages, paginate
            page_num = 2
            while len(results) < max_results:
                paginated_url = f"{search_url}&page={page_num}"
                page.goto(paginated_url, wait_until="domcontentloaded")
                _random_delay(delay, 2.0)

                if _check_blocked(page):
                    log.warning("Blocked on page %d — stopping pagination", page_num)
                    break

                page_results = _scrape_search_results(page, max_results - len(results))
                if not page_results:
                    break
                results.extend(page_results)
                page_num += 1

            return results[:max_results]

        except Exception as exc:
            log.error("Search failed: %s", exc)
            try:
                _save_screenshot(page, "search_error")
            except Exception:
                pass
            raise
        finally:
            browser.close()


# ---------------------------------------------------------------------------
# Command: product
# ---------------------------------------------------------------------------

def _parse_specs_table(page) -> dict:
    """Extract key-value pairs from product specification tables."""
    specs = {}
    try:
        rows = page.query_selector_all(".attribute-list tr, .product-prop-list tr, [class*='spec'] tr")
        for row in rows:
            cells = row.query_selector_all("td, th")
            if len(cells) >= 2:
                key = cells[0].inner_text().strip().rstrip(":")
                val = cells[1].inner_text().strip()
                if key and val:
                    specs[key] = val
    except Exception as exc:
        log.warning("Spec table extraction error: %s", exc)

    # Also try definition list format
    if not specs:
        try:
            dts = page.query_selector_all(".attributes-list dt, [class*='prop-name']")
            dds = page.query_selector_all(".attributes-list dd, [class*='prop-value']")
            for dt, dd in zip(dts, dds):
                key = dt.inner_text().strip().rstrip(":")
                val = dd.inner_text().strip()
                if key and val:
                    specs[key] = val
        except Exception:
            pass

    return specs


def _parse_image_gallery(page) -> list[str]:
    """Extract all product image URLs from gallery."""
    urls = []
    try:
        imgs = page.query_selector_all(
            ".detail-gallery-img, .images-view-item img, [class*='gallery'] img, .detail-img-list img"
        )
        for img in imgs:
            src = img.get_attribute("src") or img.get_attribute("data-src") or ""
            if src and not src.startswith("data:") and src not in urls:
                urls.append(src)
    except Exception as exc:
        log.warning("Gallery extraction error: %s", exc)
    return urls


def _parse_lead_time(text: str) -> Optional[int]:
    """Parse '15-20 days' or '3 weeks' → days (returns max)."""
    if not text:
        return None
    m = re.search(r"(\d+)\s*[-–]\s*(\d+)\s*day", text, re.IGNORECASE)
    if m:
        return int(m.group(2))
    m = re.search(r"(\d+)\s*day", text, re.IGNORECASE)
    if m:
        return int(m.group(1))
    m = re.search(r"(\d+)\s*week", text, re.IGNORECASE)
    if m:
        return int(m.group(1)) * 7
    return None


def cmd_product(args) -> dict:
    from playwright.sync_api import sync_playwright

    url = args.url
    delay = args.delay
    headed = args.headed

    log.info("Scraping Alibaba product: %s", url)

    with sync_playwright() as p:
        browser, context = _make_browser(p, headed=headed)
        page = context.new_page()
        page.set_default_timeout(30000)
        page.set_default_navigation_timeout(60000)

        try:
            page.goto(url, wait_until="domcontentloaded")
            _random_delay(delay, 2.0)

            if _check_blocked(page):
                log.error("Bot block / CAPTCHA on product page")
                _save_screenshot(page, "product_blocked")
                sys.exit(2)

            try:
                page.wait_for_selector(".module-pdp-title, h1, .product-title", timeout=15000)
            except Exception:
                log.warning("Title selector timeout — proceeding with partial data")

            _simulate_mouse_movement(page)

            # Title
            title = ""
            for sel in [".module-pdp-title", "h1.title", "h1", "[class*='product-name']"]:
                title = _get_text(page, sel)
                if title:
                    break

            # Price
            price_text = ""
            for sel in [".price-range", ".price", "[class*='price']"]:
                price_text = _get_text(page, sel)
                if price_text:
                    break
            price_min, price_max = parse_price_range(price_text)

            currency = "USD"
            if "¥" in price_text or "CNY" in price_text.upper():
                currency = "CNY"

            # MOQ
            moq_text = ""
            for sel in [".moq-info", ".min-order", "[class*='moq']"]:
                moq_text = _get_text(page, sel)
                if moq_text:
                    break
            moq_qty, moq_unit = parse_moq(moq_text)

            # Specs
            specs = _parse_specs_table(page)

            # Customization
            custom_text = ""
            for sel in ["[class*='customiz']", "[class*='oem']", ".custom-service"]:
                custom_text = _get_text(page, sel)
                if custom_text:
                    break
            # Heuristic: detect common options
            custom_options = []
            custom_lower = custom_text.lower() + page.content().lower()[:5000]
            if "logo" in custom_lower:
                custom_options.append("logo")
            if "color" in custom_lower or "colour" in custom_lower:
                custom_options.append("color")
            if "packag" in custom_lower:
                custom_options.append("packaging")
            customization = ",".join(custom_options) if custom_options else "unknown"

            # Sample info
            sample_price = None
            sample_available = False
            sample_text = ""
            for sel in ["[class*='sample']", ".sample-price"]:
                sample_text = _get_text(page, sel)
                if sample_text:
                    break
            if sample_text:
                sample_available = True
                m = re.search(r"[\$¥€]?\s*(\d+(?:\.\d+)?)", sample_text)
                if m:
                    sample_price = float(m.group(1))

            # Lead time
            lead_text = ""
            for sel in ["[class*='lead-time']", "[class*='leadtime']", ".lead-time"]:
                lead_text = _get_text(page, sel)
                if lead_text:
                    break
            lead_time_days = _parse_lead_time(lead_text)

            # Image gallery
            image_urls = _parse_image_gallery(page)

            # Supplier info (basic from product page)
            supplier_name = ""
            supplier_url = ""
            for sel in [".supplier-name a", ".company-name a", "[class*='supplier'] a"]:
                try:
                    el = page.query_selector(sel)
                    if el:
                        supplier_name = el.inner_text().strip()
                        href = el.get_attribute("href") or ""
                        supplier_url = href if href.startswith("http") else f"https:{href}"
                        break
                except Exception:
                    continue

            supplier_raw_id = _extract_supplier_id_from_url(supplier_url) if supplier_url else "unknown"
            product_id = _extract_product_id_from_url(url)
            supplier_id = normalize_platform_id(PLATFORM, supplier_raw_id)

            return {
                "product_url": url,
                "title": title or None,
                "title_cn": None,
                "price_min": price_min,
                "price_max": price_max,
                "price_currency": currency,
                "moq": moq_qty,
                "moq_unit": moq_unit,
                "customization": customization,
                "sample_price": sample_price,
                "sample_available": sample_available,
                "lead_time_days": lead_time_days,
                "specs": specs,
                "image_urls": image_urls,
                "supplier_id": supplier_id,
                "supplier_name": supplier_name or None,
            }

        except Exception as exc:
            log.error("Product scrape failed: %s", exc)
            try:
                _save_screenshot(page, "product_error")
            except Exception:
                pass
            raise
        finally:
            browser.close()


# ---------------------------------------------------------------------------
# Command: supplier
# ---------------------------------------------------------------------------

def _parse_transaction_count(text: str) -> Optional[int]:
    """Parse '1,234 Transactions' or '847' → integer."""
    if not text:
        return None
    text = text.replace(",", "")
    m = re.search(r"(\d+)", text)
    return int(m.group(1)) if m else None


def _parse_on_time_delivery(text: str) -> Optional[float]:
    """Parse '92.1%' → 0.921."""
    if not text:
        return None
    m = re.search(r"(\d+(?:\.\d+)?)\s*%", text)
    return round(float(m.group(1)) / 100, 4) if m else None


def _parse_year_established(text: str) -> Optional[int]:
    """Parse 'Est. 2015' or 'Since 2012' → integer."""
    if not text:
        return None
    m = re.search(r"(19|20)\d{2}", text)
    return int(m.group(0)) if m else None


def cmd_supplier(args) -> dict:
    from playwright.sync_api import sync_playwright

    url = args.url
    delay = args.delay
    headed = args.headed

    log.info("Scraping Alibaba supplier: %s", url)

    with sync_playwright() as p:
        browser, context = _make_browser(p, headed=headed)
        page = context.new_page()
        page.set_default_timeout(30000)
        page.set_default_navigation_timeout(60000)

        try:
            page.goto(url, wait_until="domcontentloaded")
            _random_delay(delay, 2.0)

            if _check_blocked(page):
                log.error("Bot block / CAPTCHA on supplier page")
                _save_screenshot(page, "supplier_blocked")
                sys.exit(2)

            _simulate_mouse_movement(page)
            _random_delay(1.0, 1.0)

            # Company name
            company_name = ""
            for sel in ["h1.company-name", ".company-name", "h1", "[class*='company'] h1"]:
                company_name = _get_text(page, sel)
                if company_name:
                    break

            # Location
            location = ""
            for sel in ["[class*='location']", "[class*='address']", ".country"]:
                location = _get_text(page, sel)
                if location:
                    break

            # Business type
            biz_type_text = page.content().lower()
            supplier_type = "unknown"
            if "manufacturer" in biz_type_text or "factory" in biz_type_text:
                supplier_type = "factory"
            elif "trading" in biz_type_text or "trader" in biz_type_text:
                supplier_type = "trading"
            elif "agent" in biz_type_text:
                supplier_type = "agent"

            # Gold years
            gold_text = ""
            for sel in ["[class*='gold-supplier']", "[class*='gold']"]:
                gold_text = _get_text(page, sel)
                if gold_text:
                    break
            gold_years = _parse_gold_years(gold_text)

            # Trade assurance
            ta_els = page.query_selector_all("[class*='trade-assurance'], [class*='tradeassurance']")
            trade_assurance = len(ta_els) > 0

            # Verified
            verified_els = page.query_selector_all("[class*='verified'], [class*='assess']")
            verified = len(verified_els) > 0

            # Response rate
            resp_text = ""
            for sel in ["[class*='response-rate']", "[class*='response']"]:
                resp_text = _get_text(page, sel)
                if resp_text:
                    break
            response_rate = _parse_response_rate(resp_text)

            # Transaction count
            trans_text = ""
            for sel in ["[class*='transaction']", "[class*='trade-count']"]:
                trans_text = _get_text(page, sel)
                if trans_text:
                    break
            transaction_count = _parse_transaction_count(trans_text)

            # On-time delivery
            otd_text = ""
            for sel in ["[class*='on-time']", "[class*='ontime']", "[class*='delivery']"]:
                otd_text = _get_text(page, sel)
                if otd_text and "%" in otd_text:
                    break
            on_time_delivery = _parse_on_time_delivery(otd_text)

            # Employee count
            employee_count = None
            for sel in ["[class*='employee']", "[class*='staff']"]:
                emp_text = _get_text(page, sel)
                if emp_text:
                    m = re.search(r"[\d,]+-[\d,]+|[\d,]+\+?", emp_text)
                    if m:
                        employee_count = m.group(0)
                    break

            # Year established
            year_text = ""
            for sel in ["[class*='year']", "[class*='established']", "[class*='founded']"]:
                year_text = _get_text(page, sel)
                if year_text and re.search(r"(19|20)\d{2}", year_text):
                    break
            year_established = _parse_year_established(year_text)

            # Main products
            main_products = ""
            for sel in ["[class*='main-products']", "[class*='main-product']", "[class*='product-category']"]:
                main_products = _get_text(page, sel)
                if main_products:
                    break

            # Certifications
            certs = []
            cert_els = page.query_selector_all(
                "[class*='cert'], [class*='certification'], .cert-item, .certification-list li"
            )
            for el in cert_els:
                cert_text = el.inner_text().strip()
                if cert_text and cert_text not in certs:
                    certs.append(cert_text)

            # Derive supplier ID from URL
            supplier_raw_id = _extract_supplier_id_from_url(url)
            supplier_id = normalize_platform_id(PLATFORM, supplier_raw_id)

            return {
                "supplier_id": supplier_id,
                "supplier_name": company_name or None,
                "supplier_name_cn": None,
                "url": url,
                "location": location or None,
                "supplier_type": supplier_type,
                "gold_years": gold_years,
                "trade_assurance": trade_assurance,
                "verified": verified,
                "response_rate": response_rate,
                "transaction_count": transaction_count,
                "on_time_delivery": on_time_delivery,
                "employee_count": employee_count,
                "year_established": year_established,
                "main_products": main_products or None,
                "certifications": certs,
            }

        except Exception as exc:
            log.error("Supplier scrape failed: %s", exc)
            try:
                _save_screenshot(page, "supplier_error")
            except Exception:
                pass
            raise
        finally:
            browser.close()


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
        description="Alibaba.com scraper for Sourcerer",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--headed", action="store_true", help="Run browser in headed mode (visible)")
    parser.add_argument(
        "--delay",
        type=float,
        default=3.0,
        metavar="SECONDS",
        help="Base delay between requests (default: 3.0)",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    # search
    p_search = subparsers.add_parser("search", help="Search Alibaba products")
    p_search.add_argument("query", help="Search query (e.g. 'silicone phone case')")
    p_search.add_argument("--max-results", type=int, default=20, help="Max results to return")
    p_search.add_argument("--output", default=None, help="Output JSON file path (default: stdout)")

    # product
    p_product = subparsers.add_parser("product", help="Scrape a product detail page")
    p_product.add_argument("url", help="Full Alibaba product URL")
    p_product.add_argument("--output", default=None, help="Output JSON file path (default: stdout)")

    # supplier
    p_supplier = subparsers.add_parser("supplier", help="Scrape a supplier profile")
    p_supplier.add_argument("url", help="Full Alibaba supplier URL (e.g. example.en.alibaba.com)")
    p_supplier.add_argument("--output", default=None, help="Output JSON file path (default: stdout)")

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
