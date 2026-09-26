"""
DHgate.com scraper — Sourcerer

DHgate is an international B2B/B2C wholesale platform. English language, USD prices.
Lighter bot detection than 1688 — standard stealth measures are sufficient.

CLI:
    python3 dhgate.py search "silicone phone case" --max-results 20 --output /tmp/...
    python3 dhgate.py product "https://www.dhgate.com/product/..." --output /tmp/...
    python3 dhgate.py supplier "https://www.dhgate.com/store/..." --output /tmp/...

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
from urllib.parse import quote_plus, urlparse

# ---------------------------------------------------------------------------
# sys.path setup
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
    format="%(asctime)s [dhgate] %(levelname)s %(message)s",
    stream=sys.stderr,
)
log = logging.getLogger("dhgate")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
SCREENSHOT_DIR = Path("/tmp/catalyst-screenshots")
PLATFORM = "dhgate"

USER_AGENTS = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_5) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:124.0) Gecko/20100101 Firefox/124.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
]

VIEWPORTS = [
    {"width": 1440, "height": 900},
    {"width": 1920, "height": 1080},
    {"width": 1366, "height": 768},
    {"width": 1280, "height": 800},
    {"width": 1536, "height": 864},
]

# DHgate search URL
SEARCH_URL = "https://www.dhgate.com/wholesale/search.do?searchkey={}&catalog=&pt=Y"

# DHgate Top Merchant / trusted seller badge classes (changes frequently)
TRUSTED_BADGE_SELECTORS = [
    "[class*='top-merchant']",
    "[class*='topm']",
    "[class*='trusted']",
    "[class*='verified-seller']",
    "[class*='vip-seller']",
    "[class*='gold-seller']",
    ".seller-level",
]

# ---------------------------------------------------------------------------
# Browser helpers
# ---------------------------------------------------------------------------

def _random_delay(base: float = 2.0, jitter: float = 3.0) -> None:
    time.sleep(base + random.random() * jitter)


def _make_browser(p, headed: bool = False):
    """Launch Chromium with stealth configuration for DHgate."""
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
        timezone_id="America/Chicago",
        extra_http_headers={
            "Accept-Language": "en-US,en;q=0.9",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Dest": "document",
            "Upgrade-Insecure-Requests": "1",
        },
    )
    context.add_init_script("""
        Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
        Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});
        Object.defineProperty(navigator, 'languages', {get: () => ['en-US', 'en']});
        window.chrome = {runtime: {}};
    """)
    return browser, context


def _simulate_mouse_movement(page) -> None:
    try:
        for _ in range(random.randint(2, 4)):
            x = random.randint(100, 1300)
            y = random.randint(100, 700)
            page.mouse.move(x, y)
            time.sleep(random.uniform(0.05, 0.2))
    except Exception:
        pass


def _save_screenshot(page, name: str) -> str:
    SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
    ts = int(time.time())
    path = str(SCREENSHOT_DIR / f"dhgate_{name}_{ts}.png")
    try:
        page.screenshot(path=path, full_page=False)
        log.info("Screenshot saved: %s", path)
    except Exception as exc:
        log.warning("Could not save screenshot: %s", exc)
    return path


def _check_blocked(page) -> bool:
    """Check for DHgate bot detection or CAPTCHA."""
    content = page.content().lower()
    url = page.url.lower()

    blocked_signals = [
        "captcha",
        "verify you are human",
        "access denied",
        "robot",
        "security check",
        "unusual traffic",
        "we're sorry",
        "403 forbidden",
        "blocked",
    ]
    return any(sig in content or sig in url for sig in blocked_signals)


# ---------------------------------------------------------------------------
# Text helpers
# ---------------------------------------------------------------------------

def _get_text(el, selector: str) -> str:
    try:
        child = el.query_selector(selector)
        return child.inner_text().strip() if child else ""
    except Exception:
        return ""


def _get_attr(el, selector: str, attr: str) -> str:
    try:
        child = el.query_selector(selector)
        return (child.get_attribute(attr) or "").strip() if child else ""
    except Exception:
        return ""


def _parse_response_rate(text: str) -> Optional[float]:
    if not text:
        return None
    m = re.search(r"(\d+(?:\.\d+)?)\s*%", text)
    return round(float(m.group(1)) / 100, 4) if m else None


def _parse_transaction_count(text: str) -> Optional[int]:
    if not text:
        return None
    text = text.replace(",", "")
    # Handle "1.2k", "2.5K" patterns
    k_match = re.search(r"(\d+(?:\.\d+)?)\s*[kK]", text)
    if k_match:
        return int(float(k_match.group(1)) * 1000)
    m = re.search(r"(\d+)", text)
    return int(m.group(1)) if m else None


def _parse_year(text: str) -> Optional[int]:
    if not text:
        return None
    m = re.search(r"(19|20)\d{2}", text)
    return int(m.group(0)) if m else None


def _parse_lead_time(text: str) -> Optional[int]:
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


def _extract_dhgate_product_id(url: str) -> str:
    """Extract DHgate product ID from URL."""
    # dhgate.com/product/name/p-xxxxxxxxxxxx.html
    m = re.search(r"p-([a-f0-9]{32})", url)
    if m:
        return m.group(1)[:12]  # Truncate for ID use
    # Alternative: numeric ID in path
    m = re.search(r"/(\d{6,})", url)
    if m:
        return m.group(1)
    return "unknown"


def _extract_dhgate_store_id(url: str) -> str:
    """Extract DHgate store ID from URL or seller profile."""
    # dhgate.com/store/info/ID.html
    m = re.search(r"/store/(?:info/)?([^/?.]+)", url)
    if m:
        return re.sub(r"[^a-zA-Z0-9_-]", "", m.group(1))
    # dhgate.com/store/products/ID.html
    m = re.search(r"seller=([^&]+)", url)
    if m:
        return re.sub(r"[^a-zA-Z0-9_-]", "", m.group(1))
    return "unknown"


# ---------------------------------------------------------------------------
# Command: search
# ---------------------------------------------------------------------------

def _parse_search_card_dhgate(card) -> dict:
    """Parse a single DHgate product card element."""
    # Product URL and title
    product_url = ""
    product_title = ""
    for sel in [".gallery-main-title a", ".title a", "a.item-main-title", "h2 a", "a[href*='dhgate.com/product']", "a"]:
        try:
            link = card.query_selector(sel)
            if link:
                href = link.get_attribute("href") or ""
                if "dhgate.com" in href or href.startswith("/"):
                    product_url = href if href.startswith("http") else f"https://www.dhgate.com{href}"
                    product_title = link.inner_text().strip() or link.get_attribute("title") or ""
                    if product_title:
                        break
        except Exception:
            continue

    if not product_title:
        for sel in [".gallery-main-title", ".item-title", ".title", "h2", "[class*='title']"]:
            product_title = _get_text(card, sel)
            if product_title:
                break

    # Price
    price_text = ""
    for sel in [".item-price", ".price-num", ".price", "[class*='price']"]:
        price_text = _get_text(card, sel)
        if price_text and re.search(r"\d", price_text):
            break
    price_min, price_max = parse_price_range(price_text)

    # MOQ
    moq_text = ""
    for sel in [".min-order", ".moq", "[class*='min-order']", "[class*='moq']"]:
        moq_text = _get_text(card, sel)
        if moq_text and re.search(r"\d", moq_text):
            break
    moq_qty, moq_unit = parse_moq(moq_text)

    # Supplier/seller info
    supplier_name = ""
    supplier_url = ""
    for sel in [".seller-info a", ".store-name a", "[class*='seller'] a", "[class*='store'] a"]:
        try:
            seller_el = card.query_selector(sel)
            if seller_el:
                supplier_name = seller_el.inner_text().strip()
                href = seller_el.get_attribute("href") or ""
                supplier_url = href if href.startswith("http") else f"https://www.dhgate.com{href}"
                break
        except Exception:
            continue

    # DHgate Top Merchant / verification badges
    verified = False
    for sel in TRUSTED_BADGE_SELECTORS:
        try:
            badge_els = card.query_selector_all(sel)
            if badge_els:
                verified = True
                break
        except Exception:
            continue

    # Feedback / rating
    feedback_text = ""
    for sel in ["[class*='feedback']", "[class*='rating']", "[class*='score']"]:
        feedback_text = _get_text(card, sel)
        if feedback_text:
            break
    response_rate = _parse_response_rate(feedback_text)

    # Transaction count / sold count
    trans_text = ""
    for sel in ["[class*='sold']", "[class*='order']", "[class*='transaction']"]:
        trans_text = _get_text(card, sel)
        if trans_text:
            break

    # Image URL
    image_url = ""
    for sel in [".gallery-main-pic img", ".item-img img", "img.main-img", "img"]:
        try:
            img_el = card.query_selector(sel)
            if img_el:
                src = img_el.get_attribute("src") or img_el.get_attribute("data-src") or img_el.get_attribute("data-lazy") or ""
                if src and not src.startswith("data:") and src not in ("", "undefined"):
                    image_url = src if src.startswith("http") else f"https:{src}"
                    break
        except Exception:
            continue

    # Category from card (usually not present — leave None)
    supplier_raw_id = _extract_dhgate_store_id(supplier_url) if supplier_url else "unknown"
    supplier_id = normalize_platform_id(PLATFORM, supplier_raw_id)

    return {
        "supplier_id": supplier_id,
        "supplier_name": supplier_name or None,
        "supplier_name_cn": None,
        "supplier_url": supplier_url or None,
        "gold_years": 0,       # DHgate doesn't use gold years
        "trade_assurance": False,  # DHgate doesn't have Trade Assurance (Alibaba-specific)
        "verified": verified,
        "response_rate": response_rate,
        "product_title": product_title or None,
        "product_title_cn": None,
        "product_url": product_url or None,
        "price_min": price_min,
        "price_max": price_max,
        "price_currency": "USD",
        "moq": moq_qty,
        "moq_unit": moq_unit,
        "image_url": image_url or None,
        "category": None,
    }


def _scrape_search_results(page, max_results: int) -> list[dict]:
    results = []

    try:
        page.wait_for_selector(
            ".gallery-item, .item-wrap, [class*='product-item'], [class*='gallery-main']",
            timeout=25000,
        )
    except Exception:
        log.warning("Product card selector timed out — trying fallback")

    # Scroll to trigger lazy loading
    page.evaluate("window.scrollTo(0, document.body.scrollHeight * 0.5)")
    _random_delay(0.8, 0.8)
    page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
    _random_delay(0.8, 0.8)
    page.evaluate("window.scrollTo(0, 0)")

    cards = page.query_selector_all(
        ".gallery-item, .item-wrap, [class*='product-item'], [class*='gallery-main']"
    )
    if not cards:
        cards = page.query_selector_all("[class*='item']:has(a[href*='dhgate.com/product'])")

    log.info("Found %d product cards", len(cards))

    for card in cards[:max_results]:
        try:
            result = _parse_search_card_dhgate(card)
            if result and result.get("product_title"):
                results.append(result)
        except Exception as exc:
            log.warning("Error parsing card: %s", exc)

    return results


def cmd_search(args) -> list[dict]:
    from playwright.sync_api import sync_playwright

    query = args.query
    max_results = args.max_results
    delay = args.delay
    headed = args.headed

    search_url = SEARCH_URL.format(quote_plus(query))
    log.info("Searching DHgate: %s (max=%d)", query, max_results)

    with sync_playwright() as p:
        browser, context = _make_browser(p, headed=headed)
        page = context.new_page()
        page.set_default_timeout(30000)
        page.set_default_navigation_timeout(60000)

        try:
            page.goto(search_url, wait_until="domcontentloaded")
            _random_delay(delay, 2.0)

            if _check_blocked(page):
                log.error("Bot block / CAPTCHA detected on search page")
                _save_screenshot(page, "search_blocked")
                sys.exit(2)

            _simulate_mouse_movement(page)

            results = _scrape_search_results(page, max_results)
            log.info("Extracted %d results", len(results))

            # Pagination
            page_num = 2
            while len(results) < max_results:
                # DHgate pagination uses &page= or &pageNum=
                paged_url = search_url + f"&page={page_num}"
                page.goto(paged_url, wait_until="domcontentloaded")
                _random_delay(delay, 2.0)

                if _check_blocked(page):
                    log.warning("Blocked on page %d — stopping", page_num)
                    break

                _simulate_mouse_movement(page)
                page_results = _scrape_search_results(page, max_results - len(results))
                if not page_results:
                    break
                results.extend(page_results)
                page_num += 1

            return results[:max_results]

        except SystemExit:
            raise
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

def _parse_specs_dhgate(page) -> dict:
    """Extract product specifications from DHgate product page."""
    specs = {}
    try:
        # DHgate uses a property table format
        rows = page.query_selector_all(
            ".product-info-property tr, .property-list li, [class*='spec'] tr, [class*='param'] tr"
        )
        for row in rows:
            cells = row.query_selector_all("td, th, li")
            if len(cells) >= 2:
                key = cells[0].inner_text().strip().rstrip(":")
                val = cells[1].inner_text().strip()
                if key and val:
                    specs[key] = val
            elif len(cells) == 1:
                # Single-cell rows sometimes have "key: value" format
                text = cells[0].inner_text().strip()
                if ":" in text:
                    parts = text.split(":", 1)
                    specs[parts[0].strip()] = parts[1].strip()
    except Exception as exc:
        log.warning("Spec extraction error: %s", exc)

    # Fallback: definition lists
    if not specs:
        try:
            dls = page.query_selector_all(".property dt, [class*='prop-name']")
            dds = page.query_selector_all(".property dd, [class*='prop-val']")
            for dt, dd in zip(dls, dds):
                key = dt.inner_text().strip().rstrip(":")
                val = dd.inner_text().strip()
                if key and val:
                    specs[key] = val
        except Exception:
            pass

    return specs


def _parse_image_gallery_dhgate(page) -> list[str]:
    """Extract DHgate product image URLs."""
    urls = []
    try:
        imgs = page.query_selector_all(
            ".gallery-thumb img, .product-gallery img, [class*='thumbnail'] img, .swiper-slide img"
        )
        for img in imgs:
            src = img.get_attribute("src") or img.get_attribute("data-src") or img.get_attribute("data-zoom-image") or ""
            if src and not src.startswith("data:") and src not in urls:
                # Upgrade to full-size if possible (replace thumbnail suffix)
                src = re.sub(r"_(\d+)x(\d+)\.", "_350x350.", src)
                full_src = src if src.startswith("http") else f"https:{src}"
                urls.append(full_src)
    except Exception as exc:
        log.warning("Gallery extraction error: %s", exc)
    return urls


def cmd_product(args) -> dict:
    from playwright.sync_api import sync_playwright

    url = args.url
    delay = args.delay
    headed = args.headed

    log.info("Scraping DHgate product: %s", url)

    with sync_playwright() as p:
        browser, context = _make_browser(p, headed=headed)
        page = context.new_page()
        page.set_default_timeout(30000)
        page.set_default_navigation_timeout(60000)

        try:
            page.goto(url, wait_until="domcontentloaded")
            _random_delay(delay, 2.0)

            if _check_blocked(page):
                log.error("CAPTCHA/block on product page")
                _save_screenshot(page, "product_blocked")
                sys.exit(2)

            try:
                page.wait_for_selector("h1, .product-title, [class*='product-name']", timeout=15000)
            except Exception:
                log.warning("Title selector timeout")

            _simulate_mouse_movement(page)

            # Title
            title = ""
            for sel in ["h1.product-name", "h1.title", "h1", "[class*='product-title']", "[class*='product-name']"]:
                title = _get_text(page, sel)
                if title:
                    break

            # Price
            price_text = ""
            for sel in [".item-price", ".price-range", ".price", "[class*='price-num']", "[class*='product-price']"]:
                price_text = _get_text(page, sel)
                if price_text and re.search(r"\d", price_text):
                    break
            price_min, price_max = parse_price_range(price_text)

            # MOQ
            moq_text = ""
            for sel in [".min-order-count", ".moq", "[class*='min-order']"]:
                moq_text = _get_text(page, sel)
                if moq_text and re.search(r"\d", moq_text):
                    break
            moq_qty, moq_unit = parse_moq(moq_text)

            # Specs
            specs = _parse_specs_dhgate(page)

            # Customization
            page_text = page.content()
            custom_options = []
            custom_signals = {
                "logo": ["logo", "custom logo", "your logo"],
                "color": ["color", "colour", "custom color"],
                "packaging": ["custom packaging", "custom package", "oem packaging"],
            }
            for opt, signals in custom_signals.items():
                if any(s.lower() in page_text.lower() for s in signals):
                    custom_options.append(opt)
            customization = ",".join(custom_options) if custom_options else "unknown"

            # Sample info
            sample_available = False
            sample_price = None
            sample_text = ""
            for sel in ["[class*='sample']", ".sample-price", "[class*='sample-price']"]:
                sample_text = _get_text(page, sel)
                if sample_text:
                    break
            if sample_text or "sample" in page_text.lower():
                sample_available = True
                m = re.search(r"\$\s*(\d+(?:\.\d+)?)", sample_text)
                if m:
                    sample_price = float(m.group(1))

            # Lead time
            lead_text = ""
            for sel in ["[class*='lead-time']", "[class*='processing']", ".shipping-time", "[class*='days-to-ship']"]:
                lead_text = _get_text(page, sel)
                if lead_text:
                    break
            lead_time_days = _parse_lead_time(lead_text)

            # Image gallery
            image_urls = _parse_image_gallery_dhgate(page)

            # Supplier info from product page
            supplier_name = ""
            supplier_url = ""
            for sel in [".store-name a", ".seller-name a", "[class*='store'] a", "[class*='seller'] a"]:
                try:
                    el = page.query_selector(sel)
                    if el:
                        supplier_name = el.inner_text().strip()
                        href = el.get_attribute("href") or ""
                        supplier_url = href if href.startswith("http") else f"https://www.dhgate.com{href}"
                        break
                except Exception:
                    continue

            supplier_raw_id = _extract_dhgate_store_id(supplier_url) if supplier_url else "unknown"
            supplier_id = normalize_platform_id(PLATFORM, supplier_raw_id)

            # Category — try breadcrumbs
            category = ""
            for sel in [".breadcrumb li:last-child", "[class*='category']", ".nav-breadcrumb li:last-child"]:
                category = _get_text(page, sel)
                if category and category.lower() not in ("home", "dhgate"):
                    break

            return {
                "product_url": url,
                "title": title or None,
                "title_cn": None,
                "price_min": price_min,
                "price_max": price_max,
                "price_currency": "USD",
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

        except SystemExit:
            raise
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

def cmd_supplier(args) -> dict:
    from playwright.sync_api import sync_playwright

    url = args.url
    delay = args.delay
    headed = args.headed

    log.info("Scraping DHgate supplier: %s", url)

    with sync_playwright() as p:
        browser, context = _make_browser(p, headed=headed)
        page = context.new_page()
        page.set_default_timeout(30000)
        page.set_default_navigation_timeout(60000)

        try:
            page.goto(url, wait_until="domcontentloaded")
            _random_delay(delay, 2.0)

            if _check_blocked(page):
                log.error("CAPTCHA/block on supplier page")
                _save_screenshot(page, "supplier_blocked")
                sys.exit(2)

            _simulate_mouse_movement(page)
            _random_delay(1.0, 1.0)

            # Scroll to load more content
            page.evaluate("window.scrollTo(0, 600)")
            _random_delay(0.5, 0.5)
            page.evaluate("window.scrollTo(0, 0)")

            # Company name
            company_name = ""
            for sel in ["h1.store-name", ".store-name", "h1", "[class*='store-title']", ".seller-store-name"]:
                company_name = _get_text(page, sel)
                if company_name:
                    break

            # Location
            location = ""
            for sel in ["[class*='location']", "[class*='country']", ".seller-location", "[class*='ship-from']"]:
                location = _get_text(page, sel)
                if location:
                    break

            # Business type
            page_text = page.content()
            supplier_type = "unknown"
            type_lower = page_text.lower()
            if "manufacturer" in type_lower or "factory" in type_lower:
                supplier_type = "factory"
            elif "trading" in type_lower or "wholesaler" in type_lower or "reseller" in type_lower:
                supplier_type = "trading"

            # DHgate Top Merchant / verification
            verified = False
            for sel in TRUSTED_BADGE_SELECTORS:
                try:
                    badge_els = page.query_selector_all(sel)
                    if badge_els:
                        verified = True
                        break
                except Exception:
                    continue

            # Feedback / response rate
            resp_text = ""
            for sel in ["[class*='response']", "[class*='feedback']", ".seller-feedback", "[class*='positive-rate']"]:
                resp_text = _get_text(page, sel)
                if resp_text and "%" in resp_text:
                    break
            response_rate = _parse_response_rate(resp_text)

            # Transaction count (total orders / sales)
            trans_text = ""
            for sel in ["[class*='transaction']", "[class*='total-order']", "[class*='sales']", ".order-count"]:
                trans_text = _get_text(page, sel)
                if trans_text:
                    break
            transaction_count = _parse_transaction_count(trans_text)

            # On-time delivery rate
            otd_text = ""
            for sel in ["[class*='on-time']", "[class*='delivery-rate']", "[class*='ship-on-time']"]:
                otd_text = _get_text(page, sel)
                if otd_text and "%" in otd_text:
                    break
            on_time_delivery = _parse_response_rate(otd_text)

            # Employee count (less commonly shown on DHgate)
            employee_count = None
            for sel in ["[class*='employee']", "[class*='staff']", "[class*='team-size']"]:
                emp_text = _get_text(page, sel)
                if emp_text:
                    m = re.search(r"[\d,]+-[\d,]+|[\d,]+\+?", emp_text)
                    if m:
                        employee_count = m.group(0)
                    break

            # Year / member since
            year_text = ""
            for sel in ["[class*='member-since']", "[class*='year']", "[class*='since']", ".join-time"]:
                year_text = _get_text(page, sel)
                if year_text and re.search(r"(19|20)\d{2}", year_text):
                    break
            year_established = _parse_year(year_text)

            # Main products / categories
            main_products = ""
            for sel in ["[class*='main-product']", "[class*='product-category']", ".seller-categories", "[class*='category-list']"]:
                main_products = _get_text(page, sel)
                if main_products:
                    break

            # Certifications (rare on DHgate but check)
            certs = []
            cert_els = page.query_selector_all(
                "[class*='cert'], [class*='certification'], [class*='badge']"
            )
            for el in cert_els:
                cert_text = el.inner_text().strip()
                if cert_text and len(cert_text) < 50 and cert_text not in certs:
                    certs.append(cert_text)

            supplier_raw_id = _extract_dhgate_store_id(url)
            supplier_id = normalize_platform_id(PLATFORM, supplier_raw_id)

            return {
                "supplier_id": supplier_id,
                "supplier_name": company_name or None,
                "supplier_name_cn": None,
                "url": url,
                "location": location or None,
                "supplier_type": supplier_type,
                "gold_years": 0,           # Not applicable on DHgate
                "trade_assurance": False,  # Not applicable on DHgate
                "verified": verified,
                "response_rate": response_rate,
                "transaction_count": transaction_count,
                "on_time_delivery": on_time_delivery,
                "employee_count": employee_count,
                "year_established": year_established,
                "main_products": main_products or None,
                "certifications": certs,
            }

        except SystemExit:
            raise
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
        description="DHgate.com scraper for Sourcerer",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Notes:
  - DHgate prices are in USD. International shipping from Chinese suppliers.
  - DHgate Top Merchant badge is the primary trust signal (not Gold Supplier).
  - Lighter bot detection than 1688 — standard delay settings usually suffice.
  - Store URLs: dhgate.com/store/info/STOREID.html
        """,
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
    p_search = subparsers.add_parser("search", help="Search DHgate products")
    p_search.add_argument("query", help="Search query (e.g. 'silicone phone case')")
    p_search.add_argument("--max-results", type=int, default=20, help="Max results to return")
    p_search.add_argument("--output", default=None, help="Output JSON file path (default: stdout)")

    # product
    p_product = subparsers.add_parser("product", help="Scrape a DHgate product detail page")
    p_product.add_argument("url", help="Full DHgate product URL")
    p_product.add_argument("--output", default=None, help="Output JSON file path (default: stdout)")

    # supplier
    p_supplier = subparsers.add_parser("supplier", help="Scrape a DHgate store/supplier profile")
    p_supplier.add_argument("url", help="Full DHgate store URL (e.g. dhgate.com/store/info/ID.html)")
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
