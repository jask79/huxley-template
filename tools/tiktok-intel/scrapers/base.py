"""Abstract base class for TikTok Creative Center scrapers.

Provides shared functionality:
  - Rate limiting between navigations
  - Anti-detection checks (CAPTCHA, challenge pages)
  - Gentle scroll to trigger lazy loading
  - Overlay/banner dismissal
  - Navigation with retry
  - API response interception (primary data extraction strategy)
"""

import logging
import random
import time
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Tuple

from ..browser import BrowserManager
from ..config import (
    API_INTERCEPT_TIMEOUT,
    MAX_DELAY,
    MIN_DELAY,
    PAGE_LOAD_TIMEOUT,
    SELECTOR_TIMEOUT,
    TIKTOK_BASE,
    TIKTOK_MAX_DELAY,
    TIKTOK_MIN_DELAY,
)
from ..exceptions import AntiDetectionError, SelectorTimeoutError
from ..models import ScrapeResult

logger = logging.getLogger(__name__)


class BaseScraper(ABC):
    """Abstract base scraper with anti-detection, rate limiting, and API interception."""

    name: str = "base"

    def __init__(self, browser_manager: BrowserManager, verbose: bool = False):
        self.bm = browser_manager
        self.verbose = verbose
        self._last_nav_time = 0.0
        self._warmed_up = False

    # ------------------------------------------------------------------
    # Abstract interface
    # ------------------------------------------------------------------

    @abstractmethod
    def scrape(self, filters: Dict[str, Any], limit: int = 20) -> ScrapeResult:
        """Execute the scrape with given filters. Must return ScrapeResult."""
        ...

    # ------------------------------------------------------------------
    # Rate limiting
    # ------------------------------------------------------------------

    def _rate_limit_delay(self) -> None:
        """Wait a random interval between navigations for anti-detection."""
        elapsed = time.time() - self._last_nav_time
        target_delay = random.uniform(MIN_DELAY, MAX_DELAY)
        remaining = target_delay - elapsed
        if remaining > 0:
            logger.debug("Rate limit delay: %.1fs", remaining)
            time.sleep(remaining)
        self._last_nav_time = time.time()

    # ------------------------------------------------------------------
    # Navigation
    # ------------------------------------------------------------------

    def _navigate(self, page, url: str, wait_selector: str = None) -> None:
        """Navigate to URL with rate limiting and anti-detection check.

        Args:
            page: Playwright page object.
            url: Target URL.
            wait_selector: Optional CSS selector to wait for after load.
        """
        self._rate_limit_delay()

        logger.debug("Navigating to %s", url)
        page.goto(url, wait_until="domcontentloaded", timeout=PAGE_LOAD_TIMEOUT)

        # Check for anti-detection triggers
        self._check_anti_detection(page)

        # Dismiss overlays before waiting for content
        self._dismiss_overlays(page)

        # Wait for specific selector if provided
        if wait_selector:
            try:
                page.wait_for_selector(wait_selector, timeout=SELECTOR_TIMEOUT)
            except Exception:
                raise SelectorTimeoutError(wait_selector, SELECTOR_TIMEOUT)

    # ------------------------------------------------------------------
    # API response interception
    # ------------------------------------------------------------------

    def _intercept_api(
        self,
        page_url: str,
        api_pattern: str,
        timeout: int = API_INTERCEPT_TIMEOUT,
    ) -> List[Dict[str, Any]]:
        """Navigate to a page and intercept matching API responses.

        The Creative Center frontend loads data via internal REST endpoints
        (creative_radar_api/v1/*) that return clean JSON. Instead of parsing
        the React DOM (unreliable due to dynamic class names), we:
          1. Open a new page with a response listener
          2. Navigate to the CC page (establishes session cookies + headers)
          3. Collect all API responses whose URL contains `api_pattern`
          4. Return the parsed JSON bodies

        Args:
            page_url: The Creative Center page URL to navigate to.
            api_pattern: Substring to match against response URLs.
            timeout: Max time (ms) to wait for page + API responses.

        Returns:
            List of parsed JSON response bodies matching the pattern.
        """
        collected: List[Dict[str, Any]] = []

        def _on_response(response):
            if api_pattern in response.url:
                try:
                    body = response.json()
                    collected.append(body)
                    self._log(
                        "Intercepted API response: %s (code=%s)",
                        response.url.split("?")[0],
                        body.get("code", "?"),
                    )
                except Exception as e:
                    self._log("Failed to parse API response: %s", e)

        page = self.bm.new_page()
        page.on("response", _on_response)

        # Warm up with homepage visit before hitting deep URLs (enhanced only)
        self._warmup_navigation(page)

        try:
            max_attempts = 2
            for attempt in range(1, max_attempts + 1):
                try:
                    self._rate_limit_delay()

                    logger.debug(
                        "Navigating for API intercept (attempt %d): %s",
                        attempt, page_url,
                    )
                    page.goto(
                        page_url,
                        wait_until="networkidle",
                        timeout=timeout + 5000,
                    )
                    self._last_nav_time = time.time()

                    # Check for bot detection after page load
                    self._check_anti_detection(page)

                    # Dismiss any overlays
                    self._dismiss_overlays(page)

                    # Extra wait for lazy/deferred API calls
                    time.sleep(2)

                    # If no responses captured yet, try scrolling to trigger lazy loads
                    if not collected:
                        self._log("No API responses yet, scrolling to trigger lazy loads")
                        self._gentle_scroll(page, scrolls=2)
                        time.sleep(2)

                    # If still nothing and we have retries left, reload the page
                    if not collected and attempt < max_attempts:
                        self._log(
                            "No API responses after attempt %d, retrying navigation",
                            attempt,
                        )
                        continue

                    # Got responses or exhausted retries
                    break

                except Exception as e:
                    self._log("Navigation error during API intercept: %s", e)
                    break
        finally:
            page.close()

        self._log(
            "Intercepted %d API responses matching '%s'",
            len(collected),
            api_pattern,
        )
        return collected

    def _intercept_api_paginated(
        self,
        page_url: str,
        api_pattern: str,
        max_pages: int = 3,
        scroll_pause: float = 2.0,
        timeout: int = API_INTERCEPT_TIMEOUT,
    ) -> List[Dict[str, Any]]:
        """Navigate to a page and intercept matching API responses with pagination.

        Extends `_intercept_api` with scroll-based pagination. After the initial
        page load, scrolls down to trigger additional API calls (up to `max_pages`
        rounds).

        Args:
            page_url: The page URL to navigate to.
            api_pattern: Substring to match against response URLs.
            max_pages: Maximum number of scroll rounds for pagination.
            scroll_pause: Seconds to pause after each scroll for API responses.
            timeout: Max time (ms) to wait for page + API responses.

        Returns:
            List of parsed JSON response bodies matching the pattern.
        """
        collected: List[Dict[str, Any]] = []

        def _on_response(response):
            if api_pattern in response.url:
                try:
                    body = response.json()
                    collected.append(body)
                    self._log(
                        "Intercepted paginated API response: %s (keys=%s)",
                        response.url.split("?")[0],
                        list(body.keys())[:5] if isinstance(body, dict) else "?",
                    )
                except Exception as e:
                    self._log("Failed to parse paginated API response: %s", e)

        page = self.bm.new_page()
        page.on("response", _on_response)

        # Warm up with homepage visit before hitting deep URLs (enhanced only)
        self._warmup_navigation(page)

        try:
            self._tiktok_rate_limit_delay()

            logger.debug("Navigating for paginated API intercept: %s", page_url)
            page.goto(
                page_url,
                wait_until="networkidle",
                timeout=timeout + 5000,
            )
            self._last_nav_time = time.time()

            # Check for bot detection after page load
            self._check_anti_detection(page)

            # Dismiss any overlays
            self._dismiss_overlays(page)

            # Wait for initial API responses
            time.sleep(2)

            # If no responses captured yet, try a light scroll
            if not collected:
                self._log("No API responses yet, scrolling to trigger loads")
                self._gentle_scroll(page, scrolls=2)
                time.sleep(scroll_pause)

            # Paginate: scroll down to trigger more API calls
            if collected:
                pages_scrolled = 0
                while pages_scrolled < max_pages:
                    prev_count = len(collected)
                    self._gentle_scroll(page, scrolls=2)
                    time.sleep(scroll_pause)

                    if len(collected) == prev_count:
                        self._log(
                            "No new API responses after scroll %d, stopping pagination",
                            pages_scrolled + 1,
                        )
                        break
                    pages_scrolled += 1
                    self._log(
                        "Pagination scroll %d: %d total responses",
                        pages_scrolled,
                        len(collected),
                    )

        except Exception as e:
            self._log("Navigation error during paginated API intercept: %s", e)
        finally:
            page.close()

        self._log(
            "Paginated intercept complete: %d API responses matching '%s'",
            len(collected),
            api_pattern,
        )
        return collected

    # ------------------------------------------------------------------
    # Enhanced stealth helpers
    # ------------------------------------------------------------------

    @property
    def _is_enhanced(self) -> bool:
        """Check if the browser manager is using enhanced stealth."""
        return getattr(self.bm, "stealth_level", "standard") == "enhanced"

    def _tiktok_rate_limit_delay(self) -> None:
        """Rate limit using wider delays when in enhanced (tiktok.com) mode."""
        if self._is_enhanced:
            elapsed = time.time() - self._last_nav_time
            target_delay = random.uniform(TIKTOK_MIN_DELAY, TIKTOK_MAX_DELAY)
            remaining = target_delay - elapsed
            if remaining > 0:
                logger.debug("TikTok rate limit delay: %.1fs", remaining)
                time.sleep(remaining)
            self._last_nav_time = time.time()
        else:
            self._rate_limit_delay()

    def _warmup_navigation(self, page=None) -> None:
        """Navigate to tiktok.com homepage before the real target URL.

        Establishes cookies and browsing history so the subsequent navigation
        to search/shop pages looks like organic browsing rather than a direct
        bot hit to a deep URL. Only runs once per browser session and only in
        enhanced stealth mode.

        Args:
            page: Playwright page object to reuse for the warmup visit.
                  If None, a new page is created internally and closed after
                  the warmup so that cookies persist in the shared context.
        """
        if self._warmed_up or not self._is_enhanced:
            return

        # If no page was provided (called from scrape() before any page exists),
        # create a temporary page. Cookies persist in the browser context.
        _owned_page = False
        if page is None:
            page = self.bm.new_page()
            _owned_page = True

        self._log("Warm-up: navigating to TikTok homepage to establish cookies")
        try:
            self._tiktok_rate_limit_delay()
            page.goto(
                TIKTOK_BASE,
                wait_until="domcontentloaded",
                timeout=PAGE_LOAD_TIMEOUT,
            )
            self._last_nav_time = time.time()

            # Dismiss cookie consent / overlays
            self._dismiss_overlays(page)

            # Simulate reading the homepage for 2-4 seconds
            self._random_delay(2.0, 4.0)

            # Gentle scroll 1-2 times to look organic
            scroll_count = random.randint(1, 2)
            self._gentle_scroll(page, scrolls=scroll_count)

            self._random_delay(0.5, 1.0)

            self._warmed_up = True
            self._log("Warm-up complete (scrolled %d times)", scroll_count)

        except Exception as e:
            # Warm-up failure is non-fatal — log and continue to real target
            self._log("Warm-up navigation failed (non-fatal): %s", e)
            self._warmed_up = True  # Don't retry on next call
        finally:
            if _owned_page:
                try:
                    page.close()
                except Exception:
                    pass

    @staticmethod
    def _extract_api_data(
        response: Dict[str, Any],
        data_key: Optional[str] = None,
    ) -> Tuple[bool, Any, str]:
        """Extract data from a standard Creative Center API response.

        The API envelope is: {"code": 0, "msg": "OK", "data": {...}}
        Success is code == 0. The actual list is under data[data_key].

        Args:
            response: Parsed JSON response body.
            data_key: Key within the "data" dict to extract (e.g., "materials",
                      "sound_list"). If None, returns the entire "data" dict.

        Returns:
            Tuple of (success: bool, items: list|dict, error_msg: str).
            On success, items is the extracted data. On failure, items is [].
        """
        code = response.get("code", -1)
        msg = response.get("msg", "")

        if code != 0:
            return False, [], f"API error code={code}: {msg}"

        data = response.get("data", {})
        if data_key:
            items = data.get(data_key, [])
            # Some endpoints use alternative keys — try common fallbacks
            if not items and isinstance(data, dict):
                for fallback_key in ("list", "rank_list", "items"):
                    items = data.get(fallback_key, [])
                    if items:
                        break
            return True, items, ""

        return True, data, ""

    # ------------------------------------------------------------------
    # Anti-detection
    # ------------------------------------------------------------------

    def _check_anti_detection(self, page) -> None:
        """Check if we've been detected as a bot."""
        # Check page title/content for common challenge indicators
        title = page.title().lower()
        challenge_indicators = [
            "just a moment",      # Cloudflare challenge
            "attention required",  # Cloudflare
            "access denied",       # Generic block
            "verify you are human",
            "captcha",
        ]

        for indicator in challenge_indicators:
            if indicator in title:
                raise AntiDetectionError(
                    f"Bot detection triggered: page title contains '{indicator}'"
                )

        # Check for CAPTCHA iframes
        captcha_check = page.evaluate(
            """
            () => {
                const iframes = document.querySelectorAll('iframe');
                for (const iframe of iframes) {
                    const src = (iframe.src || '').toLowerCase();
                    if (src.includes('captcha') || src.includes('challenge')
                        || src.includes('recaptcha') || src.includes('hcaptcha')) {
                        return true;
                    }
                }
                return false;
            }
            """
        )
        if captcha_check:
            raise AntiDetectionError("CAPTCHA iframe detected on page")

    # ------------------------------------------------------------------
    # Overlay dismissal (mirrors poshmark.py _dismiss_banner)
    # ------------------------------------------------------------------

    def _dismiss_overlays(self, page) -> None:
        """Try to dismiss cookie consent, promos, or other overlays."""
        dismiss_selectors = [
            # Cookie consent
            "button:has-text('Accept')",
            "button:has-text('Accept All')",
            "button:has-text('Got it')",
            "button:has-text('OK')",
            "button:has-text('I agree')",
            # TikTok-specific
            "button:has-text('Accept all cookies')",
            "[data-testid='cookie-banner-accept']",
            # Generic close buttons
            "button[aria-label='close']",
            "button[aria-label='Close']",
            "[class*='close-btn']",
            "[class*='modal-close']",
        ]

        for sel in dismiss_selectors:
            try:
                btn = page.locator(sel).first
                if btn.is_visible(timeout=500):
                    btn.click(timeout=1000)
                    self._random_delay(0.3, 0.6)
            except Exception:
                pass

    # ------------------------------------------------------------------
    # Gentle scroll (mirrors poshmark.py _gentle_scroll)
    # ------------------------------------------------------------------

    def _gentle_scroll(self, page, scrolls: int = 3) -> None:
        """Scroll down incrementally to trigger lazy loading."""
        for _ in range(scrolls):
            page.evaluate(
                "(amount) => window.scrollBy(0, amount)",
                300 + random.randint(100, 400),
            )
            self._random_delay(0.4, 0.8)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _random_delay(min_s: float = 0.5, max_s: float = 1.5) -> None:
        """Sleep for a random duration."""
        time.sleep(random.uniform(min_s, max_s))

    @staticmethod
    def _format_count(value: Any) -> str:
        """Format a raw numeric value into a human-readable count string.

        Converts large numbers to K/M/B suffixed strings.
        Passes through strings unchanged.
        """
        if isinstance(value, str):
            return value
        if not isinstance(value, (int, float)):
            return str(value) if value else ""

        num = float(value)
        if num >= 1_000_000_000:
            return f"{num / 1_000_000_000:.1f}B"
        if num >= 1_000_000:
            return f"{num / 1_000_000:.1f}M"
        if num >= 1_000:
            return f"{num / 1_000:.1f}K"
        return str(int(num))

    @staticmethod
    def _rank_diff_to_string(diff: Any, diff_type: Any) -> str:
        """Convert API rank_diff + rank_diff_type into human-readable string.

        diff_type: 0=unchanged, 1=up, 2=same, 3=new
        API may return null for these fields.
        """
        diff = diff or 0
        diff_type = diff_type or 0
        if diff_type == 3:
            return "new"
        if diff == 0:
            return ""
        if diff > 0:
            return f"+{diff}"
        return str(diff)

    def _log(self, msg: str, *args) -> None:
        """Log a debug message (visible with --verbose)."""
        logger.debug(msg, *args)
