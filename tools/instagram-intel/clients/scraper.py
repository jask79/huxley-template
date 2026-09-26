"""Playwright-based scraper for public Instagram data (Phase 2).

Stealth-configured Chromium browser that:
  - Intercepts Instagram's internal API responses (/api/v1/*, /graphql/query/)
  - Extracts embedded JSON from page source (__NEXT_DATA__, additionalData)
  - Handles login walls gracefully (data is often in intercepted responses)
  - Respects rate limits with 2-3s delays + random jitter

Follows the exact patterns from tiktok-intel/browser.py + scrapers/base.py.
Uses SYNC Playwright (playwright.sync_api) to match the rest of the CLI.
"""

import json
import logging
import random
import re
import time
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import quote_plus

from ..config import (
    CHROMIUM_ARGS,
    LOCALE,
    PAGE_LOAD_TIMEOUT,
    SCRAPE_MAX_DELAY,
    SCRAPE_MIN_DELAY,
    SELECTOR_TIMEOUT,
    TIMEZONE,
    USER_AGENT,
    VIEWPORT,
)
from ..exceptions import (
    AntiDetectionError,
    ScraperError,
    SelectorTimeoutError,
)
from ..cache import FileCache
from ..dedup import dedup_full

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Instagram URL constants
# ---------------------------------------------------------------------------

IG_BASE = "https://www.instagram.com"
IG_REELS_URL = f"{IG_BASE}/reels/"
IG_EXPLORE_URL = f"{IG_BASE}/explore/"
IG_EXPLORE_TAGS_URL = f"{IG_BASE}/explore/tags/"

# API patterns to intercept
IG_API_PATTERNS = {
    "explore_grid": "/api/v1/discover/web/explore_grid/",
    "tags_web_info": "/api/v1/tags/web_info/",
    "topsearch": "/api/v1/web/search/topsearch/",
    "graphql": "/graphql/query/",
    "clips": "/api/v1/clips/",
    "user_info": "/api/v1/users/web_profile_info/",
    "user_media": "/api/v1/feed/user/",
    "reels_tray": "/api/v1/feed/reels_tray/",
}


from ..formatters import human_number as _fmt_count

# Instagram username validation (same as graph_api.py)
_VALID_USERNAME_RE = re.compile(r"^[a-zA-Z0-9._]{1,30}$")


def _validate_username(username: str) -> str:
    """Validate and clean an Instagram username for URL construction."""
    username = username.strip().lstrip("@")
    if not _VALID_USERNAME_RE.match(username):
        raise ValueError(
            f"Invalid Instagram username: {username!r}. "
            "Usernames must be 1-30 chars: letters, digits, periods, underscores."
        )
    return username


class InstagramScraper:
    """Playwright-based scraper for public Instagram data.

    Usage:
        scraper = InstagramScraper(headless=True)
        scraper.launch()
        try:
            results = scraper.search_users("nike", limit=5)
        finally:
            scraper.close()

    Or as a context manager:
        with InstagramScraper(headless=True) as scraper:
            results = scraper.search_users("nike", limit=5)
    """

    def __init__(
        self,
        headless: bool = True,
        cache: Optional[FileCache] = None,
        verbose: bool = False,
    ):
        self.headless = headless
        self.cache = cache
        self.verbose = verbose
        self._pw = None
        self._browser = None
        self._context = None
        self._last_nav_time: float = 0.0

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def __enter__(self):
        self.launch()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False

    def launch(self) -> None:
        """Launch Chromium with stealth settings for Instagram scraping."""
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as e:
            raise ScraperError(
                f"Missing dependency: {e}. "
                "Install with: pip3 install playwright && python3 -m playwright install chromium"
            ) from e

        try:
            self._pw = sync_playwright().start()
            self._browser = self._pw.chromium.launch(
                headless=self.headless,
                args=CHROMIUM_ARGS,
            )

            self._context = self._browser.new_context(
                user_agent=USER_AGENT,
                viewport=VIEWPORT,
                locale=LOCALE,
                timezone_id=TIMEZONE,
                color_scheme="light",
            )

            # Apply stealth patches
            try:
                from playwright_stealth import Stealth
                stealth = Stealth(
                    navigator_platform_override="MacIntel",
                    navigator_user_agent_override=USER_AGENT,
                    navigator_vendor_override="Google Inc.",
                )
                stealth.apply_stealth_sync(self._context)
            except ImportError:
                logger.warning("playwright-stealth not installed; proceeding without stealth patches")

            # Additional stealth JS injections
            self._context.add_init_script("""
                // Remove webdriver flag
                Object.defineProperty(navigator, 'webdriver', {get: () => undefined});

                // Fake plugins array
                Object.defineProperty(navigator, 'plugins', {
                    get: () => [
                        { name: 'Chrome PDF Plugin', filename: 'internal-pdf-viewer' },
                        { name: 'Chrome PDF Viewer', filename: 'mhjfbmdgcfjbbpaeojofohoefgiehjai' },
                        { name: 'Native Client', filename: 'internal-nacl-plugin' },
                    ],
                });

                // Fake chrome runtime
                if (!window.chrome) {
                    window.chrome = {
                        runtime: {},
                        loadTimes: function() { return {}; },
                        csi: function() { return {}; },
                    };
                }

                // Permissions query override
                const originalQuery = navigator.permissions.query.bind(navigator.permissions);
                navigator.permissions.query = (params) =>
                    params.name === 'notifications'
                        ? Promise.resolve({ state: 'prompt', onchange: null })
                        : originalQuery(params);

                // WebGL vendor/renderer override
                const _origGetParam = WebGLRenderingContext.prototype.getParameter;
                WebGLRenderingContext.prototype.getParameter = function(parameter) {
                    if (parameter === 37445) return 'Intel Inc.';
                    if (parameter === 37446) return 'Intel Iris OpenGL Engine';
                    return _origGetParam.apply(this, arguments);
                };
                if (typeof WebGL2RenderingContext !== 'undefined') {
                    const _origGetParam2 = WebGL2RenderingContext.prototype.getParameter;
                    WebGL2RenderingContext.prototype.getParameter = function(parameter) {
                        if (parameter === 37445) return 'Intel Inc.';
                        if (parameter === 37446) return 'Intel Iris OpenGL Engine';
                        return _origGetParam2.apply(this, arguments);
                    };
                }
            """)

            logger.debug(
                "Instagram scraper launched (headless=%s, viewport=%s)",
                self.headless, VIEWPORT,
            )

        except Exception as e:
            self.close()
            if isinstance(e, ScraperError):
                raise
            raise ScraperError(f"Failed to launch Chromium: {e}") from e

    def close(self) -> None:
        """Clean shutdown of browser, context, and Playwright."""
        for resource, name in [
            (self._context, "context"),
            (self._browser, "browser"),
        ]:
            if resource:
                try:
                    resource.close()
                except Exception:
                    pass

        if self._pw:
            try:
                self._pw.stop()
            except Exception:
                pass

        self._context = None
        self._browser = None
        self._pw = None
        logger.debug("Instagram scraper closed")

    # ------------------------------------------------------------------
    # Rate limiting & delays
    # ------------------------------------------------------------------

    def _rate_limit_delay(self) -> None:
        """Wait between navigations to respect Instagram's rate limits."""
        elapsed = time.time() - self._last_nav_time
        target = random.uniform(SCRAPE_MIN_DELAY, SCRAPE_MAX_DELAY)
        remaining = target - elapsed
        if remaining > 0:
            logger.debug("Rate limit delay: %.1fs", remaining)
            time.sleep(remaining)
        self._last_nav_time = time.time()

    @staticmethod
    def _jitter(min_s: float = 0.5, max_s: float = 1.5) -> None:
        """Random jitter between actions."""
        time.sleep(random.uniform(min_s, max_s))

    # ------------------------------------------------------------------
    # Page helpers
    # ------------------------------------------------------------------

    def _new_page(self):
        """Create a new page in the stealth context."""
        if not self._context:
            raise ScraperError("Browser not launched. Call launch() first.")
        return self._context.new_page()

    def _dismiss_overlays(self, page) -> None:
        """Dismiss cookie consent, login modals, and notification prompts."""
        dismiss_selectors = [
            # Cookie consent
            "button:has-text('Accept')",
            "button:has-text('Accept All')",
            "button:has-text('Allow All Cookies')",
            "button:has-text('Allow all cookies')",
            "button:has-text('Only allow essential cookies')",
            # Login wall / modals
            "button:has-text('Not Now')",
            "button:has-text('Not now')",
            "[aria-label='Close']",
            "[aria-label='close']",
            "button:has-text('Decline')",
            # App banner
            "button:has-text('Not Now')",
            # Notification prompt
            "button:has-text('Turn On')",  # Click away from this
        ]

        for sel in dismiss_selectors:
            try:
                btn = page.locator(sel).first
                if btn.is_visible(timeout=500):
                    btn.click(timeout=1000)
                    self._jitter(0.3, 0.6)
            except Exception:
                pass

    def _check_anti_detection(self, page) -> None:
        """Check for bot detection / challenge pages."""
        title = page.title().lower()
        indicators = [
            "just a moment",
            "attention required",
            "access denied",
            "verify you are human",
            "captcha",
            "challenge",
        ]
        for indicator in indicators:
            if indicator in title:
                raise AntiDetectionError(
                    f"Bot detection triggered: page title contains '{indicator}'"
                )

    def _gentle_scroll(self, page, scrolls: int = 3) -> None:
        """Scroll down incrementally to trigger lazy loading."""
        for _ in range(scrolls):
            page.evaluate(
                "(amount) => window.scrollBy(0, amount)",
                300 + random.randint(100, 400),
            )
            self._jitter(0.4, 0.8)

    def _navigate(self, page, url: str) -> None:
        """Navigate to URL with rate limiting and anti-detection."""
        self._rate_limit_delay()
        logger.debug("Navigating to %s", url)
        page.goto(url, wait_until="domcontentloaded", timeout=PAGE_LOAD_TIMEOUT)
        self._check_anti_detection(page)
        self._dismiss_overlays(page)

    # ------------------------------------------------------------------
    # Response interception core
    # ------------------------------------------------------------------

    def _intercept_responses(
        self,
        page_url: str,
        api_patterns: List[str],
        timeout: int = PAGE_LOAD_TIMEOUT,
        scroll_for_more: bool = False,
        max_scrolls: int = 3,
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Navigate to a page and intercept API responses matching patterns.

        Returns a dict mapping each pattern to a list of parsed JSON bodies.
        This is the primary data extraction strategy -- Instagram's web app
        fires internal API requests that return structured JSON.
        """
        collected: Dict[str, List[Dict[str, Any]]] = {p: [] for p in api_patterns}

        def _on_response(response):
            url = response.url
            for pattern in api_patterns:
                if pattern in url:
                    try:
                        body = response.json()
                        collected[pattern].append(body)
                        logger.debug(
                            "Intercepted: %s (%d bytes)",
                            url.split("?")[0][-60:],
                            len(json.dumps(body)),
                        )
                    except Exception as e:
                        logger.debug("Failed to parse response from %s: %s", url[:80], e)
                    break  # Only match the first pattern

        page = self._new_page()
        page.on("response", _on_response)

        try:
            self._rate_limit_delay()
            page.goto(page_url, wait_until="domcontentloaded", timeout=timeout)
            self._last_nav_time = time.time()

            self._check_anti_detection(page)
            self._dismiss_overlays(page)

            # Wait for API responses (much faster than fixed sleep)
            try:
                page.wait_for_response(
                    lambda r: any(p in r.url for p in api_patterns),
                    timeout=4000,
                )
            except Exception:
                pass  # No response in time, proceed with whatever was collected

            # Try scrolling to trigger lazy loads
            if scroll_for_more or not any(collected[p] for p in api_patterns):
                self._gentle_scroll(page, scrolls=2)
                try:
                    page.wait_for_response(
                        lambda r: any(p in r.url for p in api_patterns),
                        timeout=3000,
                    )
                except Exception:
                    pass

            # Additional scroll rounds for pagination
            if scroll_for_more:
                for _ in range(max_scrolls):
                    prev_total = sum(len(v) for v in collected.values())
                    self._gentle_scroll(page, scrolls=2)
                    try:
                        page.wait_for_response(
                            lambda r: any(p in r.url for p in api_patterns),
                            timeout=3000,
                        )
                    except Exception:
                        pass
                    new_total = sum(len(v) for v in collected.values())
                    if new_total == prev_total:
                        break

        except AntiDetectionError:
            raise  # Always surface bot detection to caller
        except Exception as e:
            logger.debug("Navigation error during interception: %s", e)
        finally:
            page.close()

        total = sum(len(v) for v in collected.values())
        logger.debug("Intercepted %d total responses across %d patterns", total, len(api_patterns))
        return collected

    def _extract_page_json(self, page) -> Optional[Dict[str, Any]]:
        """Extract embedded JSON from Instagram page source.

        Instagram embeds data in several ways:
          - window.__additionalDataLoaded(path, data)
          - window._sharedData = {...}
          - <script type="application/json">...</script> in __NEXT_DATA__ style

        Returns the first valid JSON blob found, or None.
        """
        # Strategy 1: __additionalDataLoaded
        additional_data = page.evaluate("""() => {
            try {
                var scripts = document.querySelectorAll('script');
                for (var i = 0; i < scripts.length; i++) {
                    var text = scripts[i].textContent || '';
                    if (text.includes('__additionalDataLoaded')) {
                        var match = text.match(/__additionalDataLoaded\\s*\\([^,]+,\\s*(\\{.+\\})\\s*\\)/);
                        if (match) return JSON.parse(match[1]);
                    }
                }
            } catch(e) {}
            return null;
        }""")
        if additional_data:
            return additional_data

        # Strategy 2: _sharedData
        shared_data = page.evaluate("""() => {
            try {
                if (window._sharedData) return window._sharedData;
            } catch(e) {}
            try {
                var scripts = document.querySelectorAll('script');
                for (var i = 0; i < scripts.length; i++) {
                    var text = scripts[i].textContent || '';
                    if (text.includes('window._sharedData')) {
                        var match = text.match(/window\\._sharedData\\s*=\\s*(\\{.+\\});/);
                        if (match) return JSON.parse(match[1]);
                    }
                }
            } catch(e) {}
            return null;
        }""")
        if shared_data:
            return shared_data

        # Strategy 3: application/json script tags
        json_data = page.evaluate("""() => {
            try {
                var scripts = document.querySelectorAll('script[type="application/json"]');
                for (var i = 0; i < scripts.length; i++) {
                    try {
                        var d = JSON.parse(scripts[i].textContent);
                        if (d && typeof d === 'object' && Object.keys(d).length > 0) {
                            return d;
                        }
                    } catch(e) {}
                }
            } catch(e) {}
            return null;
        }""")
        return json_data

    # ------------------------------------------------------------------
    # Search commands
    # ------------------------------------------------------------------

    def search_users(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Search Instagram users via topsearch API interception.

        Navigates to instagram.com and triggers a search query, intercepting
        the /api/v1/web/search/topsearch/ response.
        """
        search_url = f"{IG_BASE}/web/search/topsearch/?query={quote_plus(query)}"
        logger.debug("Searching users: %s", query)

        # The topsearch API fires when navigating with a search context.
        # We navigate to the main page and intercept the search API.
        collected = self._intercept_responses(
            page_url=f"{IG_BASE}/explore/search/",
            api_patterns=[IG_API_PATTERNS["topsearch"]],
        )

        users = []
        responses = collected.get(IG_API_PATTERNS["topsearch"], [])

        # If no topsearch responses, try direct URL approach
        if not responses:
            collected = self._intercept_responses(
                page_url=f"{IG_BASE}",
                api_patterns=[IG_API_PATTERNS["topsearch"]],
            )
            responses = collected.get(IG_API_PATTERNS["topsearch"], [])

        # If still nothing, try injecting search via the search bar
        if not responses:
            responses = self._search_via_input(query)

        for resp in responses:
            for user_data in resp.get("users", []):
                if len(users) >= limit:
                    break
                user = user_data.get("user", user_data)
                follower_count = user.get("follower_count", 0) or 0
                users.append({
                    "username": user.get("username", ""),
                    "full_name": user.get("full_name", ""),
                    "followers": follower_count,
                    "is_verified": user.get("is_verified", False),
                    "is_private": user.get("is_private", False),
                    "profile_pic_url": user.get("profile_pic_url", ""),
                    "followers_fmt": _fmt_count(follower_count),
                })

        return users[:limit]

    def search_hashtags(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Search Instagram hashtags via topsearch API interception."""
        logger.debug("Searching hashtags: %s", query)

        responses = self._search_via_input(query)

        hashtags = []
        for resp in responses:
            for ht_data in resp.get("hashtags", []):
                if len(hashtags) >= limit:
                    break
                ht = ht_data.get("hashtag", ht_data)
                media_count = ht.get("media_count", 0) or 0
                hashtags.append({
                    "name": ht.get("name", ""),
                    "media_count": media_count,
                    "media_count_fmt": _fmt_count(media_count),
                })

        return hashtags[:limit]

    def search_content(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Search Instagram content (posts/reels) by keyword.

        Uses explore/tags endpoint as a proxy since Instagram doesn't have
        a public content search API. Falls back to hashtag-based search.
        """
        logger.debug("Searching content: %s", query)

        # Try searching for the query as a hashtag first (most content-like)
        tag = query.strip().replace(" ", "").replace("#", "")
        tag_url = f"{IG_EXPLORE_TAGS_URL}{quote_plus(tag)}/"

        collected = self._intercept_responses(
            page_url=tag_url,
            api_patterns=[
                IG_API_PATTERNS["tags_web_info"],
                IG_API_PATTERNS["graphql"],
            ],
            scroll_for_more=True,
            max_scrolls=2,
        )

        content = []

        # Extract from tags web info
        for resp in collected.get(IG_API_PATTERNS["tags_web_info"], []):
            content.extend(self._extract_media_from_tag_response(resp, limit))

        # Extract from graphql responses
        for resp in collected.get(IG_API_PATTERNS["graphql"], []):
            content.extend(self._extract_media_from_graphql(resp, limit - len(content)))

        return content[:limit]

    def _search_via_input(self, query: str) -> List[Dict[str, Any]]:
        """Perform search by typing into the Instagram search bar.

        This triggers the topsearch API call that we intercept.
        Returns a list of raw topsearch response bodies.
        """
        collected_responses: List[Dict[str, Any]] = []

        def _on_response(response):
            if IG_API_PATTERNS["topsearch"] in response.url:
                try:
                    body = response.json()
                    collected_responses.append(body)
                    logger.debug("Intercepted topsearch response")
                except Exception as e:
                    logger.debug("Failed to parse topsearch response: %s", e)

        page = self._new_page()
        page.on("response", _on_response)

        try:
            self._rate_limit_delay()
            page.goto(IG_BASE, wait_until="domcontentloaded", timeout=PAGE_LOAD_TIMEOUT)
            self._last_nav_time = time.time()
            self._check_anti_detection(page)
            self._dismiss_overlays(page)
            self._jitter(0.8, 1.5)

            # Find and click the search input
            search_clicked = False
            search_selectors = [
                "a[href='/explore/']",
                "[aria-label='Search']",
                "svg[aria-label='Search']",
                "a:has-text('Search')",
                "[role='link']:has-text('Search')",
            ]
            for sel in search_selectors:
                try:
                    elem = page.locator(sel).first
                    if elem.is_visible(timeout=2000):
                        elem.click(timeout=2000)
                        search_clicked = True
                        self._jitter(0.5, 1.0)
                        break
                except Exception:
                    continue

            if not search_clicked:
                logger.debug("Could not find search element on Instagram")
                return collected_responses

            # Type the query into the search input
            input_selectors = [
                "input[aria-label='Search input']",
                "input[placeholder='Search']",
                "input[type='text']",
            ]
            typed = False
            for sel in input_selectors:
                try:
                    inp = page.locator(sel).first
                    if inp.is_visible(timeout=2000):
                        inp.fill("")
                        self._jitter(0.2, 0.4)
                        inp.type(query, delay=random.randint(50, 120))
                        typed = True
                        break
                except Exception:
                    continue

            if not typed:
                logger.debug("Could not find search input on Instagram")
                return collected_responses

            # Wait for topsearch API to fire
            try:
                page.wait_for_response(
                    lambda r: IG_API_PATTERNS["topsearch"] in r.url,
                    timeout=4000,
                )
            except Exception:
                pass  # Proceed with whatever was collected

        except AntiDetectionError:
            raise
        except Exception as e:
            logger.debug("Search via input error: %s", e)
        finally:
            page.close()

        return collected_responses

    # ------------------------------------------------------------------
    # Trending commands
    # ------------------------------------------------------------------

    def get_trending_reels(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Get trending reels from instagram.com/reels/.

        Intercepts the clips/reels API responses.
        """
        logger.debug("Fetching trending reels (limit=%d)", limit)

        collected = self._intercept_responses(
            page_url=IG_REELS_URL,
            api_patterns=[
                IG_API_PATTERNS["clips"],
                IG_API_PATTERNS["graphql"],
            ],
            scroll_for_more=True,
            max_scrolls=3,
        )

        reels = []

        # Extract from clips API responses
        for resp in collected.get(IG_API_PATTERNS["clips"], []):
            reels.extend(self._extract_reels_from_clips(resp))

        # Extract from graphql responses
        for resp in collected.get(IG_API_PATTERNS["graphql"], []):
            reels.extend(self._extract_reels_from_graphql(resp))

        # Full dedup: exact IDs + fuzzy captions (#7)
        unique_reels = dedup_full(reels, fuzzy_threshold=0.7, caption_field="caption")

        return unique_reels[:limit]

    def get_trending_audio(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Get trending audio from Reels.

        First fetches trending reels, then aggregates audio tracks
        by frequency of appearance, sorted by usage count.
        """
        logger.debug("Fetching trending audio (limit=%d)", limit)

        # Get more reels than the limit to have good audio aggregation
        reels = self.get_trending_reels(limit=max(limit * 3, 50))

        # Aggregate audio by name/id
        audio_map: Dict[str, Dict[str, Any]] = {}
        for reel in reels:
            audio_name = reel.get("audio_name", "")
            audio_id = reel.get("audio_id", "")
            if not audio_name and not audio_id:
                continue

            key = audio_id or audio_name
            if key not in audio_map:
                audio_map[key] = {
                    "audio_id": audio_id,
                    "name": audio_name,
                    "artist": reel.get("audio_artist", ""),
                    "usage_count": 0,
                    "reels_using": [],
                }
            audio_map[key]["usage_count"] += 1
            permalink = reel.get("permalink", "")
            if permalink:
                audio_map[key]["reels_using"].append(permalink)

        # Sort by usage count descending
        sorted_audio = sorted(
            audio_map.values(),
            key=lambda x: x["usage_count"],
            reverse=True,
        )

        return sorted_audio[:limit]

    def get_explore(self, topic: str = "", limit: int = 20) -> List[Dict[str, Any]]:
        """Get Explore page content, optionally filtered by topic.

        If topic is provided, navigates to a hashtag search first,
        otherwise scrapes the general explore grid.
        """
        logger.debug("Fetching explore (topic=%s, limit=%d)", topic, limit)

        if topic:
            # Search for the topic via tags
            tag = topic.strip().replace(" ", "").replace("#", "")
            url = f"{IG_EXPLORE_TAGS_URL}{quote_plus(tag)}/"
        else:
            url = IG_EXPLORE_URL

        collected = self._intercept_responses(
            page_url=url,
            api_patterns=[
                IG_API_PATTERNS["explore_grid"],
                IG_API_PATTERNS["tags_web_info"],
                IG_API_PATTERNS["graphql"],
            ],
            scroll_for_more=True,
            max_scrolls=3,
        )

        items = []

        # Extract from explore grid
        for resp in collected.get(IG_API_PATTERNS["explore_grid"], []):
            items.extend(self._extract_explore_items(resp))

        # Extract from tags
        for resp in collected.get(IG_API_PATTERNS["tags_web_info"], []):
            items.extend(self._extract_media_from_tag_response(resp, limit))

        # Extract from graphql
        for resp in collected.get(IG_API_PATTERNS["graphql"], []):
            items.extend(self._extract_media_from_graphql(resp, limit - len(items)))

        # Full dedup: exact IDs + fuzzy captions (#7)
        unique = dedup_full(items, fuzzy_threshold=0.7, caption_field="caption")

        return unique[:limit]

    # ------------------------------------------------------------------
    # User profile commands
    # ------------------------------------------------------------------

    def get_user_profile(self, username: str) -> Optional[Dict[str, Any]]:
        """Get any public user's profile data.

        Navigates to instagram.com/{username}/ and extracts profile data
        from embedded JSON or intercepted API responses.
        """
        username = _validate_username(username)
        logger.debug("Fetching user profile: @%s", username)

        profile_url = f"{IG_BASE}/{username}/"

        # Try API interception first
        collected = self._intercept_responses(
            page_url=profile_url,
            api_patterns=[
                IG_API_PATTERNS["user_info"],
                IG_API_PATTERNS["graphql"],
            ],
        )

        profile = None

        # Check user_info API responses
        for resp in collected.get(IG_API_PATTERNS["user_info"], []):
            profile = self._extract_profile_from_api(resp)
            if profile:
                return profile

        # Check graphql responses
        for resp in collected.get(IG_API_PATTERNS["graphql"], []):
            profile = self._extract_profile_from_graphql(resp)
            if profile:
                return profile

        # Fallback: extract from embedded page JSON
        page = self._new_page()
        try:
            self._rate_limit_delay()
            page.goto(profile_url, wait_until="domcontentloaded", timeout=PAGE_LOAD_TIMEOUT)
            self._last_nav_time = time.time()
            self._check_anti_detection(page)
            self._dismiss_overlays(page)
            self._jitter(0.8, 1.5)

            json_data = self._extract_page_json(page)
            if json_data:
                profile = self._extract_profile_from_page_json(json_data, username)
                if profile:
                    return profile

            # Last resort: try meta tags
            profile = self._extract_profile_from_meta(page, username)
            return profile

        except AntiDetectionError:
            raise
        except Exception as e:
            logger.debug("Profile extraction error for @%s: %s", username, e)
            return None
        finally:
            page.close()

    def get_user_reels(self, username: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Get a user's reels from instagram.com/{username}/reels/.

        Intercepts the media feed API responses on the reels tab.
        """
        username = _validate_username(username)
        logger.debug("Fetching reels for @%s (limit=%d)", username, limit)

        reels_url = f"{IG_BASE}/{username}/reels/"

        collected = self._intercept_responses(
            page_url=reels_url,
            api_patterns=[
                IG_API_PATTERNS["clips"],
                IG_API_PATTERNS["graphql"],
                IG_API_PATTERNS["user_media"],
            ],
            scroll_for_more=True,
            max_scrolls=3,
        )

        reels = []

        # Extract from clips
        for resp in collected.get(IG_API_PATTERNS["clips"], []):
            reels.extend(self._extract_reels_from_clips(resp))

        # Extract from user_media
        for resp in collected.get(IG_API_PATTERNS["user_media"], []):
            reels.extend(self._extract_reels_from_user_media(resp))

        # Extract from graphql
        for resp in collected.get(IG_API_PATTERNS["graphql"], []):
            reels.extend(self._extract_reels_from_graphql(resp))

        # Full dedup: exact IDs + fuzzy captions (#7)
        unique = dedup_full(reels, fuzzy_threshold=0.7, caption_field="caption")

        return unique[:limit]

    # ------------------------------------------------------------------
    # Hashtag deep
    # ------------------------------------------------------------------

    def get_hashtag_deep(self, hashtag: str, limit: int = 50) -> Optional[Dict[str, Any]]:
        """Deep hashtag analysis from instagram.com/explore/tags/{hashtag}/.

        No 30/week API limit. Intercepts tags/web_info and graphql responses.
        """
        hashtag = hashtag.strip().lstrip("#")
        logger.debug("Fetching hashtag deep: #%s (limit=%d)", hashtag, limit)

        tag_url = f"{IG_EXPLORE_TAGS_URL}{quote_plus(hashtag)}/"

        collected = self._intercept_responses(
            page_url=tag_url,
            api_patterns=[
                IG_API_PATTERNS["tags_web_info"],
                IG_API_PATTERNS["graphql"],
            ],
            scroll_for_more=True,
            max_scrolls=3,
        )

        result = {
            "name": hashtag,
            "media_count": 0,
            "media_count_fmt": "0",
            "top_posts": [],
            "recent_posts": [],
        }

        # Extract from tags web info
        for resp in collected.get(IG_API_PATTERNS["tags_web_info"], []):
            tag_info = self._extract_tag_info(resp)
            if tag_info:
                result["media_count"] = tag_info.get("media_count", 0)
                result["media_count_fmt"] = _fmt_count(tag_info.get("media_count", 0))
                result["top_posts"] = tag_info.get("top_posts", [])[:limit]
                result["recent_posts"] = tag_info.get("recent_posts", [])[:limit]

        # Supplement from graphql
        for resp in collected.get(IG_API_PATTERNS["graphql"], []):
            extra_posts = self._extract_media_from_graphql(resp, limit)
            if extra_posts and not result["top_posts"]:
                result["top_posts"] = extra_posts[:limit]

        return result

    # ------------------------------------------------------------------
    # Data extraction helpers
    # ------------------------------------------------------------------

    def _extract_reels_from_clips(self, resp: Dict) -> List[Dict[str, Any]]:
        """Extract reel items from a clips API response."""
        reels = []
        # Instagram clips API structures: items[], reels_media[]
        items = resp.get("items", [])
        if not items:
            items = resp.get("reels_media", [])
        if not items:
            # Try nested under 'data'
            data = resp.get("data", {})
            if isinstance(data, dict):
                items = data.get("items", []) or data.get("reels_media", [])

        for item in items:
            media = item.get("media", item)
            reel = self._parse_media_to_reel(media)
            if reel:
                reels.append(reel)

        return reels

    def _extract_reels_from_graphql(self, resp: Dict) -> List[Dict[str, Any]]:
        """Extract reel items from a GraphQL response."""
        reels = []

        # GraphQL responses have varying structures
        data = resp.get("data", {})
        if not isinstance(data, dict):
            return reels

        # Try xdt_api__v1__clips__home__connection_v2 (common for reels)
        for key in data:
            node = data[key]
            if not isinstance(node, dict):
                continue
            edges = node.get("edges", [])
            if not edges and "items" in node:
                for item in node["items"]:
                    media = item.get("media", item)
                    reel = self._parse_media_to_reel(media)
                    if reel:
                        reels.append(reel)
            for edge in edges:
                media_node = edge.get("node", edge)
                media = media_node.get("media", media_node)
                reel = self._parse_media_to_reel(media)
                if reel:
                    reels.append(reel)

        return reels

    def _extract_reels_from_user_media(self, resp: Dict) -> List[Dict[str, Any]]:
        """Extract reels from user media feed response."""
        reels = []
        items = resp.get("items", [])
        for item in items:
            media = item.get("media", item) if isinstance(item, dict) else item
            reel = self._parse_media_to_reel(media)
            if reel:
                reels.append(reel)
        return reels

    def _parse_media_to_reel(self, media: Dict) -> Optional[Dict[str, Any]]:
        """Parse a single media dict into a reel data dict."""
        if not isinstance(media, dict):
            return None

        media_id = str(media.get("pk", "") or media.get("id", "") or "")
        if not media_id:
            return None

        # Caption
        caption_obj = media.get("caption", {})
        caption = ""
        if isinstance(caption_obj, dict):
            caption = caption_obj.get("text", "")
        elif isinstance(caption_obj, str):
            caption = caption_obj

        # Author
        user = media.get("user", {}) or {}
        author = user.get("username", "")

        # Counts
        like_count = media.get("like_count", 0) or 0
        comment_count = media.get("comment_count", 0) or 0
        view_count = (
            media.get("play_count", 0)
            or media.get("view_count", 0)
            or media.get("video_view_count", 0)
            or 0
        )

        # Audio
        audio_name = ""
        audio_id = ""
        audio_artist = ""
        music_metadata = media.get("music_metadata", {})
        if isinstance(music_metadata, dict):
            music_info = music_metadata.get("music_info", {})
            if isinstance(music_info, dict):
                audio_name = music_info.get("music_asset_info", {}).get("title", "")
                audio_id = str(music_info.get("music_asset_info", {}).get("audio_cluster_id", ""))
                audio_artist = music_info.get("music_asset_info", {}).get("display_artist", "")

        # Permalink
        code = media.get("code", "")
        permalink = f"https://www.instagram.com/reel/{code}/" if code else ""

        # Thumbnail
        image_versions = media.get("image_versions2", {})
        candidates = image_versions.get("candidates", []) if isinstance(image_versions, dict) else []
        thumbnail = candidates[0].get("url", "") if candidates else ""

        return {
            "reel_id": media_id,
            "author": author,
            "caption": caption[:200],
            "likes": like_count,
            "comments": comment_count,
            "views": view_count,
            "audio_name": audio_name,
            "audio_id": audio_id,
            "audio_artist": audio_artist,
            "permalink": permalink,
            "thumbnail_url": thumbnail,
            "likes_fmt": _fmt_count(like_count),
            "views_fmt": _fmt_count(view_count),
        }

    def _extract_explore_items(self, resp: Dict) -> List[Dict[str, Any]]:
        """Extract media items from explore grid API response."""
        items = []
        # Explore grid: sectional_items[] -> layout_content -> medias[]
        sections = resp.get("sectional_items", [])
        if not sections:
            sections = resp.get("items", [])

        for section in sections:
            if not isinstance(section, dict):
                continue
            layout = section.get("layout_content", {})
            medias = layout.get("medias", []) if isinstance(layout, dict) else []
            if not medias:
                # Try direct media in section
                media = section.get("media", None)
                if media:
                    medias = [{"media": media}]

            for media_wrapper in medias:
                if not isinstance(media_wrapper, dict):
                    continue
                media = media_wrapper.get("media", media_wrapper)
                item = self._parse_media_to_explore_item(media)
                if item:
                    items.append(item)

        return items

    def _parse_media_to_explore_item(self, media: Dict) -> Optional[Dict[str, Any]]:
        """Parse a single media dict into an explore item."""
        if not isinstance(media, dict):
            return None

        media_id = str(media.get("pk", "") or media.get("id", "") or "")
        if not media_id:
            return None

        # Media type
        media_type_int = media.get("media_type", 0)
        media_type_map = {1: "IMAGE", 2: "VIDEO", 8: "CAROUSEL"}
        media_type = media_type_map.get(media_type_int, "UNKNOWN")

        user = media.get("user", {}) or {}
        author = user.get("username", "")

        caption_obj = media.get("caption", {})
        caption = ""
        if isinstance(caption_obj, dict):
            caption = caption_obj.get("text", "")
        elif isinstance(caption_obj, str):
            caption = caption_obj

        like_count = media.get("like_count", 0) or 0
        comment_count = media.get("comment_count", 0) or 0

        code = media.get("code", "")
        permalink = f"https://www.instagram.com/p/{code}/" if code else ""

        image_versions = media.get("image_versions2", {})
        candidates = image_versions.get("candidates", []) if isinstance(image_versions, dict) else []
        thumbnail = candidates[0].get("url", "") if candidates else ""

        return {
            "media_id": media_id,
            "media_type": media_type,
            "author": author,
            "caption": caption[:200],
            "likes": like_count,
            "comments": comment_count,
            "permalink": permalink,
            "thumbnail_url": thumbnail,
            "likes_fmt": _fmt_count(like_count),
            "comments_fmt": _fmt_count(comment_count),
        }

    def _extract_media_from_tag_response(
        self, resp: Dict, limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Extract media items from a tags/web_info API response."""
        items = []
        data = resp.get("data", resp)
        if not isinstance(data, dict):
            return items

        # Top posts
        top_section = data.get("top", {})
        if isinstance(top_section, dict):
            sections = top_section.get("sections", [])
            for section in sections:
                medias = section.get("layout_content", {}).get("medias", [])
                for media_wrapper in medias:
                    media = media_wrapper.get("media", media_wrapper)
                    item = self._parse_media_to_explore_item(media)
                    if item and len(items) < limit:
                        items.append(item)

        # Recent posts
        recent_section = data.get("recent", {})
        if isinstance(recent_section, dict):
            sections = recent_section.get("sections", [])
            for section in sections:
                medias = section.get("layout_content", {}).get("medias", [])
                for media_wrapper in medias:
                    media = media_wrapper.get("media", media_wrapper)
                    item = self._parse_media_to_explore_item(media)
                    if item and len(items) < limit:
                        items.append(item)

        return items

    def _extract_media_from_graphql(
        self, resp: Dict, limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Extract media items from a GraphQL response."""
        items = []
        data = resp.get("data", {})
        if not isinstance(data, dict):
            return items

        # Walk through all top-level keys looking for edge structures
        for key, value in data.items():
            if not isinstance(value, dict):
                continue

            # Look for edge_*_media patterns
            for edge_key in list(value.keys()):
                if "edge" in edge_key.lower() or "media" in edge_key.lower():
                    edge_data = value[edge_key]
                    if isinstance(edge_data, dict):
                        edges = edge_data.get("edges", [])
                        for edge in edges:
                            node = edge.get("node", {})
                            item = self._parse_graphql_media_node(node)
                            if item and len(items) < limit:
                                items.append(item)

        return items

    def _parse_graphql_media_node(self, node: Dict) -> Optional[Dict[str, Any]]:
        """Parse a GraphQL media node into an explore-style item."""
        if not isinstance(node, dict):
            return None

        media_id = str(node.get("id", "") or node.get("pk", "") or "")
        if not media_id:
            return None

        typename = node.get("__typename", "")
        if "Video" in typename or node.get("is_video", False):
            media_type = "VIDEO"
        elif "Sidecar" in typename:
            media_type = "CAROUSEL"
        else:
            media_type = "IMAGE"

        owner = node.get("owner", {}) or {}
        author = owner.get("username", "")

        caption_edges = node.get("edge_media_to_caption", {})
        caption = ""
        if isinstance(caption_edges, dict):
            edges = caption_edges.get("edges", [])
            if edges:
                caption = edges[0].get("node", {}).get("text", "")

        like_count = 0
        likes_edge = node.get("edge_liked_by", {}) or node.get("edge_media_preview_like", {})
        if isinstance(likes_edge, dict):
            like_count = likes_edge.get("count", 0) or 0

        comment_count = 0
        comments_edge = node.get("edge_media_to_comment", {}) or node.get("edge_media_preview_comment", {})
        if isinstance(comments_edge, dict):
            comment_count = comments_edge.get("count", 0) or 0

        shortcode = node.get("shortcode", "")
        permalink = f"https://www.instagram.com/p/{shortcode}/" if shortcode else ""

        thumbnail = node.get("thumbnail_src", "") or node.get("display_url", "")

        return {
            "media_id": media_id,
            "media_type": media_type,
            "author": author,
            "caption": caption[:200] if caption else "",
            "likes": like_count,
            "comments": comment_count,
            "permalink": permalink,
            "thumbnail_url": thumbnail,
            "likes_fmt": _fmt_count(like_count),
            "comments_fmt": _fmt_count(comment_count),
        }

    def _extract_tag_info(self, resp: Dict) -> Optional[Dict[str, Any]]:
        """Extract tag info from tags/web_info response."""
        data = resp.get("data", resp)
        if not isinstance(data, dict):
            return None

        media_count = data.get("media_count", 0) or 0

        top_posts = []
        top_section = data.get("top", {})
        if isinstance(top_section, dict):
            sections = top_section.get("sections", [])
            for section in sections:
                medias = section.get("layout_content", {}).get("medias", [])
                for media_wrapper in medias:
                    media = media_wrapper.get("media", media_wrapper)
                    item = self._parse_media_to_explore_item(media)
                    if item:
                        top_posts.append(item)

        recent_posts = []
        recent_section = data.get("recent", {})
        if isinstance(recent_section, dict):
            sections = recent_section.get("sections", [])
            for section in sections:
                medias = section.get("layout_content", {}).get("medias", [])
                for media_wrapper in medias:
                    media = media_wrapper.get("media", media_wrapper)
                    item = self._parse_media_to_explore_item(media)
                    if item:
                        recent_posts.append(item)

        return {
            "media_count": media_count,
            "top_posts": top_posts,
            "recent_posts": recent_posts,
        }

    def _extract_profile_from_api(self, resp: Dict) -> Optional[Dict[str, Any]]:
        """Extract profile from web_profile_info API response."""
        data = resp.get("data", {})
        if not isinstance(data, dict):
            return None

        user = data.get("user", {})
        if not user:
            return None

        return self._build_profile_dict(user)

    def _extract_profile_from_graphql(self, resp: Dict) -> Optional[Dict[str, Any]]:
        """Extract profile from GraphQL response."""
        data = resp.get("data", {})
        if not isinstance(data, dict):
            return None

        # Look for user data under common graphql keys
        for key in ["user", "xdt_api__v1__users__web_profile_info"]:
            user = data.get(key, {})
            if isinstance(user, dict) and user.get("username"):
                return self._build_profile_dict(user)

        return None

    def _extract_profile_from_page_json(
        self, json_data: Dict, username: str
    ) -> Optional[Dict[str, Any]]:
        """Extract profile from embedded page JSON."""
        # Try entry_data -> ProfilePage
        entry_data = json_data.get("entry_data", {})
        profile_pages = entry_data.get("ProfilePage", [])
        if profile_pages:
            graphql = profile_pages[0].get("graphql", {})
            user = graphql.get("user", {})
            if user:
                return self._build_profile_dict(user)

        # Try walking the JSON for user data
        user = self._find_user_in_json(json_data, username)
        if user:
            return self._build_profile_dict(user)

        return None

    def _extract_profile_from_meta(self, page, username: str) -> Optional[Dict[str, Any]]:
        """Extract basic profile from meta tags as last resort."""
        try:
            description = page.evaluate("""() => {
                var meta = document.querySelector('meta[property="og:description"]');
                return meta ? meta.getAttribute('content') : '';
            }""") or ""

            title = page.evaluate("""() => {
                var meta = document.querySelector('meta[property="og:title"]');
                return meta ? meta.getAttribute('content') : '';
            }""") or ""

            # Parse "1.2M Followers, 500 Following, 3,000 Posts" from description
            followers = 0
            following = 0
            posts = 0

            # Match patterns like "1.2M Followers"
            f_match = re.search(r"([\d,.]+[KMB]?)\s*Followers", description, re.IGNORECASE)
            if f_match:
                from ..formatters import parse_human_number
                followers = parse_human_number(f_match.group(1))

            fw_match = re.search(r"([\d,.]+[KMB]?)\s*Following", description, re.IGNORECASE)
            if fw_match:
                from ..formatters import parse_human_number
                following = parse_human_number(fw_match.group(1))

            p_match = re.search(r"([\d,.]+[KMB]?)\s*Posts", description, re.IGNORECASE)
            if p_match:
                from ..formatters import parse_human_number
                posts = parse_human_number(p_match.group(1))

            # Extract full name from title: "Full Name (@username)"
            full_name = ""
            name_match = re.search(r"^(.+?)\s*\(@", title)
            if name_match:
                full_name = name_match.group(1).strip()

            if followers or following or posts or full_name:
                return {
                    "username": username,
                    "full_name": full_name,
                    "biography": "",
                    "followers": followers,
                    "following": following,
                    "media_count": posts,
                    "is_verified": False,
                    "is_private": False,
                    "is_business": False,
                    "category": "",
                    "external_url": "",
                    "profile_pic_url": "",
                    "followers_fmt": _fmt_count(followers),
                    "following_fmt": _fmt_count(following),
                }
        except Exception as e:
            logger.debug("Meta tag extraction failed: %s", e)

        return None

    def _build_profile_dict(self, user: Dict) -> Dict[str, Any]:
        """Build a standardized profile dict from IG user data."""
        follower_count = (
            user.get("edge_followed_by", {}).get("count", 0)
            if isinstance(user.get("edge_followed_by"), dict)
            else user.get("follower_count", 0) or 0
        )
        following_count = (
            user.get("edge_follow", {}).get("count", 0)
            if isinstance(user.get("edge_follow"), dict)
            else user.get("following_count", 0) or 0
        )
        media_count = (
            user.get("edge_owner_to_timeline_media", {}).get("count", 0)
            if isinstance(user.get("edge_owner_to_timeline_media"), dict)
            else user.get("media_count", 0) or 0
        )

        return {
            "username": user.get("username", ""),
            "full_name": user.get("full_name", ""),
            "biography": user.get("biography", "") or user.get("bio", ""),
            "followers": follower_count,
            "following": following_count,
            "media_count": media_count,
            "is_verified": user.get("is_verified", False),
            "is_private": user.get("is_private", False),
            "is_business": user.get("is_business_account", False) or user.get("is_business", False),
            "category": user.get("category_name", "") or user.get("category", ""),
            "external_url": user.get("external_url", "") or (user.get("bio_link", {}).get("url", "") if isinstance(user.get("bio_link"), dict) else ""),
            "profile_pic_url": user.get("profile_pic_url_hd", "") or user.get("profile_pic_url", ""),
            "followers_fmt": _fmt_count(follower_count),
            "following_fmt": _fmt_count(following_count),
        }

    def _find_user_in_json(self, data: Any, username: str, depth: int = 0) -> Optional[Dict]:
        """Recursively search JSON structure for user data matching username."""
        if depth > 5:
            return None
        if isinstance(data, dict):
            if data.get("username") == username and ("follower_count" in data or "edge_followed_by" in data):
                return data
            for v in data.values():
                result = self._find_user_in_json(v, username, depth + 1)
                if result:
                    return result
        elif isinstance(data, list):
            for item in data[:20]:  # Limit list traversal
                result = self._find_user_in_json(item, username, depth + 1)
                if result:
                    return result
        return None
