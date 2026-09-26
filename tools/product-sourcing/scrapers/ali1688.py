"""
1688.com scraper — Sourcerer (Chinese domestic B2B)

1688 is Alibaba's domestic-facing platform. All content is in Mandarin Chinese.
Prices are in CNY (¥). Has aggressive anti-bot measures — extra delays applied.

CLI:
    python3 ali1688.py search "手机硅胶套" --max-results 20 --output /tmp/...
    python3 ali1688.py product "https://detail.1688.com/offer/..." --output /tmp/...
    python3 ali1688.py supplier "https://example.1688.com" --output /tmp/...

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
from urllib.parse import quote, quote_plus, urlparse

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
    format="%(asctime)s [1688] %(levelname)s %(message)s",
    stream=sys.stderr,
)
log = logging.getLogger("ali1688")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
SCREENSHOT_DIR = Path("/tmp/catalyst-screenshots")
PLATFORM = "1688"

# 1688 primarily serves Chinese users — use Chinese locale UA strings
USER_AGENTS = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_4) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.5 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36 Edg/122.0.0.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
]

VIEWPORTS = [
    {"width": 1440, "height": 900},
    {"width": 1920, "height": 1080},
    {"width": 1366, "height": 768},
    {"width": 1280, "height": 720},
]

# 1688 search URL template
SEARCH_URL = "https://s.1688.com/selloffer/offer_search.htm?keywords={}&n=y&tab=all"

# Chinese → English business type mapping (common terms)
BIZ_TYPE_MAP = {
    "工厂": "factory",
    "生产厂家": "factory",
    "厂家直销": "factory",
    "贸易商": "trading",
    "贸易公司": "trading",
    "代理商": "agent",
    "经销商": "distributor",
}

# ---------------------------------------------------------------------------
# Browser helpers
# ---------------------------------------------------------------------------

def _random_delay(base: float = 3.0, jitter: float = 4.0) -> None:
    """1688 needs longer delays due to aggressive bot detection."""
    time.sleep(base + random.random() * jitter)


def _make_browser(p, headed: bool = False):
    """Launch Chromium with stealth configuration tuned for 1688."""
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
            "--lang=zh-CN",  # Appear as Chinese browser
        ],
    )
    context = browser.new_context(
        user_agent=ua,
        viewport=viewport,
        locale="zh-CN",  # Chinese locale for 1688
        timezone_id="Asia/Shanghai",  # Chinese timezone
        extra_http_headers={
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Referer": "https://www.1688.com/",
            "Sec-Fetch-Site": "same-origin",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Dest": "document",
            "Upgrade-Insecure-Requests": "1",
        },
    )
    # Anti-detection JS
    context.add_init_script("""
        Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
        Object.defineProperty(navigator, 'plugins', {get: () => [1,2,3,4,5]});
        Object.defineProperty(navigator, 'languages', {get: () => ['zh-CN', 'zh', 'en']});
        window.chrome = {runtime: {}};
        // Override platform to Windows (common for Chinese users)
        Object.defineProperty(navigator, 'platform', {get: () => 'Win32'});
    """)
    return browser, context


def _simulate_human_behavior(page) -> None:
    """Simulate human-like reading behavior — important for 1688."""
    try:
        # Gradual scroll (simulates reading)
        for scroll_y in [200, 500, 800, 400, 0]:
            page.evaluate(f"window.scrollTo(0, {scroll_y})")
            time.sleep(random.uniform(0.3, 0.8))

        # Random mouse movements
        for _ in range(random.randint(3, 6)):
            x = random.randint(200, 1200)
            y = random.randint(100, 600)
            page.mouse.move(x, y)
            time.sleep(random.uniform(0.05, 0.15))
    except Exception:
        pass


def _save_screenshot(page, name: str) -> str:
    SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
    ts = int(time.time())
    path = str(SCREENSHOT_DIR / f"1688_{name}_{ts}.png")
    try:
        page.screenshot(path=path, full_page=False)
        log.info("Screenshot saved: %s", path)
    except Exception as exc:
        log.warning("Could not save screenshot: %s", exc)
    return path


def _check_blocked(page) -> bool:
    """Check for 1688 bot detection / CAPTCHA / Aliyun challenge."""
    content = page.content().lower()
    url = page.url.lower()

    blocked_signals = [
        "captcha",
        "验证码",           # Chinese: "verification code"
        "滑块",             # slider CAPTCHA
        "human verification",
        "access denied",
        "forbidden",
        "阿里云",           # Aliyun WAF block
        "安全验证",         # "security verification"
        "机器人",           # "robot"
        "abnormal access",
        "异常访问",
    ]
    return any(sig in content or sig in url for sig in blocked_signals)


# ---------------------------------------------------------------------------
# Text helpers for Chinese content
# ---------------------------------------------------------------------------

def _transliterate_hint(cn_text: str) -> str:
    """
    Return a minimal ASCII hint for Chinese text (not full pinyin — just a note).
    Full pinyin would require an external library (e.g. pypinyin) which we can't use.
    We store the original Chinese as title, and set title_cn = same.
    """
    return cn_text  # Return as-is; translation layer is the agent's responsibility


def _cn_parse_biz_type(text: str) -> str:
    """Detect supplier type from Chinese text."""
    for cn_term, en_type in BIZ_TYPE_MAP.items():
        if cn_term in text:
            return en_type
    return "unknown"


def _cn_parse_response_rate(text: str) -> Optional[float]:
    """Parse Chinese response rate text '回应率 95.2%' → 0.952."""
    if not text:
        return None
    m = re.search(r"(\d+(?:\.\d+)?)\s*%", text)
    return round(float(m.group(1)) / 100, 4) if m else None


def _cn_parse_transaction_count(text: str) -> Optional[int]:
    """Parse Chinese transaction count '1234笔' or '1.2万笔' → integer."""
    if not text:
        return None
    # Handle 万 (10,000) suffix
    wan_match = re.search(r"(\d+(?:\.\d+)?)\s*万", text)
    if wan_match:
        return int(float(wan_match.group(1)) * 10000)
    # Handle plain numbers
    text_clean = text.replace(",", "").replace("，", "")
    m = re.search(r"(\d+)", text_clean)
    return int(m.group(1)) if m else None


def _cn_parse_year(text: str) -> Optional[int]:
    """Parse year from Chinese text '2015年成立' → 2015."""
    if not text:
        return None
    m = re.search(r"(19|20)\d{2}", text)
    return int(m.group(0)) if m else None


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


# ---------------------------------------------------------------------------
# ID extraction
# ---------------------------------------------------------------------------

def _extract_offer_id(url: str) -> str:
    """Extract offer/product ID from 1688 URL."""
    # detail.1688.com/offer/123456789.html
    m = re.search(r"/offer/(\d+)\.html", url)
    if m:
        return m.group(1)
    # s.1688.com patterns
    m = re.search(r"offerId=(\d+)", url)
    if m:
        return m.group(1)
    nums = re.findall(r"\d{8,}", url)
    return nums[0] if nums else "unknown"


def _extract_supplier_id_1688(url: str) -> str:
    """Extract supplier ID from 1688 supplier URL."""
    parsed = urlparse(url)
    # shop.1688.com/shop/example.html or example.1688.com
    host = parsed.netloc
    host = host.replace(".1688.com", "").replace("www.", "")
    clean = re.sub(r"[^a-zA-Z0-9_-]", "", host)
    if not clean:
        # Try shop path: /shop/shopId=12345
        m = re.search(r"shopId=(\d+)", url)
        if m:
            clean = m.group(1)
    return clean or "unknown"


# ---------------------------------------------------------------------------
# Command: search
# ---------------------------------------------------------------------------

def _parse_search_card_1688(card) -> dict:
    """Parse a single 1688 product card."""
    # Product URL and title
    product_url = ""
    product_title = ""
    for sel in ["a.offer-img", ".offer-title a", "h2 a", ".title a", "a[href*='1688.com']", "a"]:
        try:
            link = card.query_selector(sel)
            if link:
                href = link.get_attribute("href") or ""
                if "1688.com" in href or href.startswith("//"):
                    product_url = href if href.startswith("http") else f"https:{href}"
                    product_title = link.inner_text().strip()
                    if not product_title:
                        product_title = link.get_attribute("title") or ""
                    if product_title:
                        break
        except Exception:
            continue

    # Price (CNY)
    price_text = ""
    for sel in [".price-num", ".price", "[class*='price']", ".offer-price"]:
        price_text = _get_text(card, sel)
        if price_text and re.search(r"\d", price_text):
            break
    price_min, price_max = parse_price_range(price_text)

    # MOQ
    moq_text = ""
    for sel in [".min-order", ".moq", "[class*='min']", "[class*='起批']"]:
        moq_text = _get_text(card, sel)
        if moq_text and re.search(r"\d", moq_text):
            break
    moq_qty, moq_unit = parse_moq(moq_text)

    # Supplier info
    supplier_name = ""
    supplier_url = ""
    for sel in [".company-name a", ".seller-name a", "[class*='seller'] a", "[class*='company'] a"]:
        try:
            supplier_el = card.query_selector(sel)
            if supplier_el:
                supplier_name = supplier_el.inner_text().strip()
                href = supplier_el.get_attribute("href") or ""
                supplier_url = href if href.startswith("http") else f"https:{href}"
                break
        except Exception:
            continue

    # 1688 verification badges (different system from Alibaba)
    verified_els = card.query_selector_all(
        "[class*='verify'], [class*='auth'], [class*='实力商家'], [class*='天猫']"
    )
    verified = len(verified_els) > 0

    # Transaction count
    trans_text = ""
    for sel in ["[class*='trans']", "[class*='deal']", "[class*='成交']"]:
        trans_text = _get_text(card, sel)
        if trans_text:
            break
    transaction_count = _cn_parse_transaction_count(trans_text)

    # Image URL
    image_url = ""
    for sel in [".offer-img img", ".img img", "img.main-img", "img"]:
        try:
            img_el = card.query_selector(sel)
            if img_el:
                src = img_el.get_attribute("src") or img_el.get_attribute("data-src") or img_el.get_attribute("data-lazy-src") or ""
                if src and not src.startswith("data:") and "1688.com" not in src.lower()[:20]:
                    image_url = src if src.startswith("http") else f"https:{src}"
                    break
        except Exception:
            continue

    supplier_raw_id = _extract_supplier_id_1688(supplier_url) if supplier_url else "unknown"
    supplier_id = normalize_platform_id(PLATFORM, supplier_raw_id)

    return {
        "supplier_id": supplier_id,
        "supplier_name": supplier_name or None,
        "supplier_name_cn": supplier_name or None,  # same on 1688 — all Chinese
        "supplier_url": supplier_url or None,
        "gold_years": 0,          # N/A on 1688
        "trade_assurance": False, # N/A on 1688
        "verified": verified,
        "response_rate": None,
        "product_title": product_title or None,
        "product_title_cn": product_title or None,
        "product_url": product_url or None,
        "price_min": price_min,
        "price_max": price_max,
        "price_currency": "CNY",
        "moq": moq_qty,
        "moq_unit": moq_unit,
        "image_url": image_url or None,
        "category": None,
    }


def cmd_search(args) -> list[dict]:
    from playwright.sync_api import sync_playwright

    query = args.query
    max_results = args.max_results
    delay = args.delay
    headed = args.headed

    # 1688 supports both Chinese and encoded queries
    encoded_query = quote(query)
    search_url = SEARCH_URL.format(encoded_query)

    log.info("Searching 1688: %s (max=%d)", query, max_results)
    log.info("Search URL: %s", search_url)

    with sync_playwright() as p:
        browser, context = _make_browser(p, headed=headed)
        page = context.new_page()
        page.set_default_timeout(30000)
        page.set_default_navigation_timeout(60000)

        try:
            # First visit homepage to build cookies (important for 1688 anti-bot)
            log.info("Warming up with homepage visit...")
            page.goto("https://www.1688.com/", wait_until="domcontentloaded")
            _random_delay(delay + 1.0, 2.0)
            _simulate_human_behavior(page)

            if _check_blocked(page):
                log.error("Blocked on 1688 homepage")
                _save_screenshot(page, "home_blocked")
                sys.exit(2)

            # Navigate to search
            log.info("Navigating to search results...")
            page.goto(search_url, wait_until="domcontentloaded")
            _random_delay(delay + 1.0, 2.0)

            if _check_blocked(page):
                log.error("Bot block / CAPTCHA detected on search page")
                _save_screenshot(page, "search_blocked")
                sys.exit(2)

            # Simulate human reading behavior
            _simulate_human_behavior(page)

            # Wait for product cards
            try:
                page.wait_for_selector(
                    ".offer-list-row-offer, .grid-offer, .offer-item, [class*='offer-card']",
                    timeout=20000,
                )
            except Exception:
                log.warning("Product card selector timed out")

            results = _scrape_search_results(page, max_results)
            log.info("Extracted %d results", len(results))

            # Pagination if needed
            page_num = 2
            while len(results) < max_results:
                # 1688 pagination: &beginPage=2
                paged_url = search_url + f"&beginPage={page_num}"
                page.goto(paged_url, wait_until="domcontentloaded")
                _random_delay(delay + 2.0, 3.0)  # Extra delay between pages on 1688

                if _check_blocked(page):
                    log.warning("Blocked on page %d — stopping", page_num)
                    break

                _simulate_human_behavior(page)
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


def _scrape_search_results(page, max_results: int) -> list[dict]:
    results = []

    cards = page.query_selector_all(
        ".offer-list-row-offer, .grid-offer, [class*='offer-card'], [class*='offer-item']"
    )
    if not cards:
        cards = page.query_selector_all("[class*='offer']")

    log.info("Found %d product cards", len(cards))

    for card in cards[:max_results]:
        try:
            result = _parse_search_card_1688(card)
            if result and result.get("product_title"):
                results.append(result)
        except Exception as exc:
            log.warning("Error parsing card: %s", exc)

    return results


# ---------------------------------------------------------------------------
# Command: product
# ---------------------------------------------------------------------------

def cmd_product(args) -> dict:
    from playwright.sync_api import sync_playwright

    url = args.url
    delay = args.delay
    headed = args.headed

    log.info("Scraping 1688 product: %s", url)

    with sync_playwright() as p:
        browser, context = _make_browser(p, headed=headed)
        page = context.new_page()
        page.set_default_timeout(30000)
        page.set_default_navigation_timeout(60000)

        try:
            page.goto(url, wait_until="domcontentloaded")
            _random_delay(delay + 1.0, 2.0)

            if _check_blocked(page):
                log.error("CAPTCHA/block on product page")
                _save_screenshot(page, "product_blocked")
                sys.exit(2)

            _simulate_human_behavior(page)

            try:
                page.wait_for_selector("h1, .d-title, [class*='title']", timeout=15000)
            except Exception:
                log.warning("Title selector timeout")

            # Title (Chinese)
            title_cn = ""
            for sel in ["h1.d-title", "h1.title", "h1", "[class*='d-title']", "[class*='offer-title']"]:
                title_cn = _get_text(page, sel)
                if title_cn:
                    break

            # Price (CNY)
            price_text = ""
            for sel in [".price-num", ".price", "[class*='price']"]:
                price_text = _get_text(page, sel)
                if price_text and re.search(r"\d", price_text):
                    break
            price_min, price_max = parse_price_range(price_text)

            # MOQ
            moq_text = ""
            for sel in [".min-order", ".moq", "[class*='min-order']", "[class*='起批']"]:
                moq_text = _get_text(page, sel)
                if moq_text and re.search(r"\d", moq_text):
                    break
            moq_qty, moq_unit = parse_moq(moq_text)

            # Specs (Chinese key-value pairs)
            specs = {}
            try:
                rows = page.query_selector_all(
                    ".attribute-list tr, .prop-list .prop-item, [class*='prop'] [class*='item']"
                )
                for row in rows:
                    cells = row.query_selector_all("td, .prop-name, .prop-value")
                    if len(cells) >= 2:
                        key = cells[0].inner_text().strip().rstrip("：:")
                        val = cells[1].inner_text().strip()
                        if key and val:
                            specs[key] = val
            except Exception as exc:
                log.warning("Spec extraction error: %s", exc)

            # Customization detection (Chinese terms)
            page_text = page.content()
            custom_lower = page_text.lower()
            custom_options = []
            cn_custom_signals = {
                "logo": ["logo", "标", "印"],
                "color": ["color", "colour", "颜色", "色"],
                "packaging": ["packag", "包装", "外包"],
            }
            for opt, signals in cn_custom_signals.items():
                if any(s in page_text for s in signals):
                    custom_options.append(opt)
            customization = ",".join(custom_options) if custom_options else "unknown"

            # Sample info
            sample_available = False
            sample_price = None
            sample_text = ""
            for sel in ["[class*='sample']", "[class*='样品']", ".sample"]:
                sample_text = _get_text(page, sel)
                if sample_text:
                    break
            if sample_text or "样品" in page_text:
                sample_available = True
                m = re.search(r"[¥￥]?\s*(\d+(?:\.\d+)?)", sample_text)
                if m:
                    sample_price = float(m.group(1))

            # Lead time (Chinese: 货期/发货期)
            lead_time_days = None
            for sel in ["[class*='lead']", "[class*='货期']", "[class*='发货']"]:
                lead_text = _get_text(page, sel)
                if lead_text:
                    m = re.search(r"(\d+)\s*[-–]\s*(\d+)\s*(?:天|日|day)", lead_text)
                    if m:
                        lead_time_days = int(m.group(2))
                        break
                    m = re.search(r"(\d+)\s*(?:天|日|day)", lead_text)
                    if m:
                        lead_time_days = int(m.group(1))
                        break

            # Image gallery
            image_urls = []
            try:
                imgs = page.query_selector_all(
                    ".detail-gallery img, .image-list img, [class*='gallery'] img, .product-img img"
                )
                for img in imgs:
                    src = img.get_attribute("src") or img.get_attribute("data-src") or ""
                    if src and not src.startswith("data:") and src not in image_urls:
                        image_url = src if src.startswith("http") else f"https:{src}"
                        image_urls.append(image_url)
            except Exception:
                pass

            # Supplier info from product page
            supplier_name = supplier_name_cn = ""
            supplier_url = ""
            for sel in [".seller-name a", ".company-name a", "[class*='seller'] a"]:
                try:
                    el = page.query_selector(sel)
                    if el:
                        supplier_name_cn = el.inner_text().strip()
                        supplier_name = supplier_name_cn
                        href = el.get_attribute("href") or ""
                        supplier_url = href if href.startswith("http") else f"https:{href}"
                        break
                except Exception:
                    continue

            offer_id = _extract_offer_id(url)
            supplier_raw_id = _extract_supplier_id_1688(supplier_url) if supplier_url else offer_id[:8]
            supplier_id = normalize_platform_id(PLATFORM, supplier_raw_id)

            return {
                "product_url": url,
                "title": title_cn or None,       # Keep Chinese as primary title on 1688
                "title_cn": title_cn or None,
                "price_min": price_min,
                "price_max": price_max,
                "price_currency": "CNY",
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

    log.info("Scraping 1688 supplier: %s", url)

    with sync_playwright() as p:
        browser, context = _make_browser(p, headed=headed)
        page = context.new_page()
        page.set_default_timeout(30000)
        page.set_default_navigation_timeout(60000)

        try:
            # Warm up with homepage first
            page.goto("https://www.1688.com/", wait_until="domcontentloaded")
            _random_delay(delay, 2.0)
            _simulate_human_behavior(page)

            page.goto(url, wait_until="domcontentloaded")
            _random_delay(delay + 1.0, 2.0)

            if _check_blocked(page):
                log.error("CAPTCHA/block on supplier page")
                _save_screenshot(page, "supplier_blocked")
                sys.exit(2)

            _simulate_human_behavior(page)

            # Company name (Chinese)
            company_name = ""
            for sel in ["h1.company-name", ".company-name", "h1", "[class*='company-title']", ".shop-name"]:
                company_name = _get_text(page, sel)
                if company_name:
                    break

            # Location
            location = ""
            for sel in ["[class*='location']", "[class*='address']", "[class*='地址']", ".region"]:
                location = _get_text(page, sel)
                if location:
                    break

            # Business type (from Chinese page text)
            page_text = page.content()
            supplier_type = _cn_parse_biz_type(page_text)

            # 1688 has its own verification badges (not Alibaba Gold Supplier)
            verified_els = page.query_selector_all(
                "[class*='verify'], [class*='auth'], [class*='实力'], [class*='认证']"
            )
            verified = len(verified_els) > 0

            # Response rate
            resp_text = ""
            for sel in ["[class*='response']", "[class*='回应率']", "[class*='reply-rate']"]:
                resp_text = _get_text(page, sel)
                if resp_text and "%" in resp_text:
                    break
            response_rate = _cn_parse_response_rate(resp_text)

            # Transaction count (成交笔数)
            trans_text = ""
            for sel in ["[class*='transaction']", "[class*='成交']", "[class*='trade-count']"]:
                trans_text = _get_text(page, sel)
                if trans_text:
                    break
            transaction_count = _cn_parse_transaction_count(trans_text)

            # On-time delivery rate
            otd_text = ""
            for sel in ["[class*='delivery']", "[class*='按时']", "[class*='on-time']"]:
                otd_text = _get_text(page, sel)
                if otd_text and "%" in otd_text:
                    break
            on_time_delivery = _cn_parse_response_rate(otd_text)  # same % parsing

            # Employee count
            employee_count = None
            for sel in ["[class*='employee']", "[class*='人员']", "[class*='人数']"]:
                emp_text = _get_text(page, sel)
                if emp_text:
                    m = re.search(r"[\d,]+-[\d,]+|[\d,]+\+?", emp_text)
                    if m:
                        employee_count = m.group(0)
                    break

            # Year established (成立年份 / 注册年份)
            year_text = ""
            for sel in ["[class*='year']", "[class*='成立']", "[class*='注册']", "[class*='established']"]:
                year_text = _get_text(page, sel)
                if year_text and re.search(r"(19|20)\d{2}", year_text):
                    break
            year_established = _cn_parse_year(year_text)

            # Main products (主营产品)
            main_products = ""
            for sel in ["[class*='main-product']", "[class*='主营']", ".main-products"]:
                main_products = _get_text(page, sel)
                if main_products:
                    break

            # Certifications
            certs = []
            cert_els = page.query_selector_all(
                "[class*='cert'], [class*='certification'], [class*='认证'], .cert-item"
            )
            for el in cert_els:
                cert_text = el.inner_text().strip()
                if cert_text and cert_text not in certs:
                    certs.append(cert_text)

            supplier_raw_id = _extract_supplier_id_1688(url)
            supplier_id = normalize_platform_id(PLATFORM, supplier_raw_id)

            return {
                "supplier_id": supplier_id,
                "supplier_name": company_name or None,
                "supplier_name_cn": company_name or None,  # Same on 1688 — all Chinese
                "url": url,
                "location": location or None,
                "supplier_type": supplier_type,
                "gold_years": 0,           # N/A on 1688
                "trade_assurance": False,  # N/A on 1688
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
        description="1688.com scraper for Sourcerer (Chinese domestic B2B)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Notes:
  - All content on 1688 is in Mandarin Chinese. Titles and names will be Chinese text.
  - Prices are always in CNY (Chinese Yuan ¥).
  - 1688 uses aggressive anti-bot measures. Use --delay 5+ if getting blocked.
  - Query can be in English or Chinese (e.g. '手机壳' or 'phone case').
        """,
    )
    parser.add_argument("--headed", action="store_true", help="Run browser in headed mode (visible)")
    parser.add_argument(
        "--delay",
        type=float,
        default=4.0,
        metavar="SECONDS",
        help="Base delay between requests (default: 4.0 — higher than Alibaba due to aggressive detection)",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    # search
    p_search = subparsers.add_parser("search", help="Search 1688 products")
    p_search.add_argument("query", help="Search query (Chinese or English, e.g. '手机壳' or 'phone case')")
    p_search.add_argument("--max-results", type=int, default=20, help="Max results to return")
    p_search.add_argument("--output", default=None, help="Output JSON file path (default: stdout)")

    # product
    p_product = subparsers.add_parser("product", help="Scrape a 1688 product detail page")
    p_product.add_argument("url", help="Full 1688 product URL (detail.1688.com/offer/...)")
    p_product.add_argument("--output", default=None, help="Output JSON file path (default: stdout)")

    # supplier
    p_supplier = subparsers.add_parser("supplier", help="Scrape a 1688 supplier/shop profile")
    p_supplier.add_argument("url", help="Full 1688 supplier URL")
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
