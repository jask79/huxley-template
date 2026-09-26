"""Playwright browser lifecycle management.

Provides a context manager that launches Chromium with stealth patches,
reuses the browser context across multiple page navigations, and tears
down cleanly on exit.

Pattern follows the shared marketplace-searcher browser pattern.
"""

import logging
import random
from typing import Optional

from .config import (
    CHROMIUM_ARGS,
    ENHANCED_CHROMIUM_ARGS,
    ENHANCED_GEOLOCATION,
    ENHANCED_HTTP_HEADERS,
    ENHANCED_USER_AGENTS,
    LOCALE,
    TIMEZONE,
    USER_AGENT,
    VIEWPORT,
)
from .exceptions import BrowserLaunchError

logger = logging.getLogger(__name__)


class BrowserManager:
    """Context manager for stealth Chromium via Playwright.

    Usage:
        with BrowserManager(headless=True) as bm:
            page = bm.new_page()
            page.goto("https://example.com")
    """

    def __init__(self, headless: bool = True, stealth_level: str = "standard"):
        self.headless = headless
        self.stealth_level = stealth_level
        self._pw = None
        self._browser = None
        self._context = None

    def __enter__(self):
        self._launch()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False  # don't suppress exceptions

    def _launch(self) -> None:
        """Launch Chromium with playwright-stealth patches."""
        try:
            from playwright.sync_api import sync_playwright
            from playwright_stealth import Stealth
        except ImportError as e:
            raise BrowserLaunchError(
                f"Missing dependency: {e}. "
                "Install with: pip install playwright playwright-stealth"
            ) from e

        try:
            self._pw = sync_playwright().start()

            is_enhanced = self.stealth_level == "enhanced"

            # Enhanced stealth: random UA + randomized viewport + extra args
            if is_enhanced:
                ua = random.choice(ENHANCED_USER_AGENTS)
                viewport = {
                    "width": random.randint(1800, 1920),
                    "height": random.randint(900, 1080),
                }
                launch_args = ENHANCED_CHROMIUM_ARGS
            else:
                ua = USER_AGENT
                viewport = VIEWPORT
                launch_args = CHROMIUM_ARGS

            # Match platform to user agent to avoid fingerprint mismatch
            if "Windows" in ua:
                platform = "Win32"
            elif "Linux" in ua:
                platform = "Linux x86_64"
            else:
                platform = "MacIntel"

            stealth = Stealth(
                navigator_platform_override=platform,
                navigator_user_agent_override=ua,
                navigator_vendor_override="Google Inc.",
            )

            self._browser = self._pw.chromium.launch(
                headless=self.headless,
                args=launch_args,
            )

            # Build context options — enhanced mode adds headers + geolocation
            context_opts = dict(
                user_agent=ua,
                viewport=viewport,
                locale=LOCALE,
                timezone_id=TIMEZONE,
                color_scheme="light",
            )
            if is_enhanced:
                context_opts["extra_http_headers"] = ENHANCED_HTTP_HEADERS
                context_opts["geolocation"] = ENHANCED_GEOLOCATION
                context_opts["permissions"] = ["geolocation"]

            self._context = self._browser.new_context(**context_opts)

            stealth.apply_stealth_sync(self._context)

            # Enhanced stealth: inject extra JS overrides for tiktok.com
            if is_enhanced:
                self._context.add_init_script("""
                    // -------------------------------------------------------
                    // Double-layer webdriver removal (on top of playwright-stealth)
                    // -------------------------------------------------------
                    Object.defineProperty(navigator, 'webdriver', {
                        get: () => undefined,
                    });

                    // -------------------------------------------------------
                    // navigator.permissions.query — resolve 'prompt'
                    // -------------------------------------------------------
                    const originalQuery = navigator.permissions.query.bind(navigator.permissions);
                    navigator.permissions.query = (params) =>
                        params.name === 'notifications'
                            ? Promise.resolve({ state: 'prompt', onchange: null })
                            : originalQuery(params);

                    // -------------------------------------------------------
                    // navigator.plugins — non-empty array
                    // -------------------------------------------------------
                    Object.defineProperty(navigator, 'plugins', {
                        get: () => [
                            { name: 'Chrome PDF Plugin', filename: 'internal-pdf-viewer' },
                            { name: 'Chrome PDF Viewer', filename: 'mhjfbmdgcfjbbpaeojofohoefgiehjai' },
                            { name: 'Native Client', filename: 'internal-nacl-plugin' },
                        ],
                    });

                    // -------------------------------------------------------
                    // window.chrome — truthy object
                    // -------------------------------------------------------
                    if (!window.chrome) {
                        window.chrome = {
                            runtime: {},
                            loadTimes: function() { return {}; },
                            csi: function() { return {}; },
                        };
                    }

                    // -------------------------------------------------------
                    // Canvas fingerprint noise injection
                    // Adds subtle per-pixel noise so every toDataURL call
                    // produces a unique hash — defeats canvas fingerprinting.
                    // -------------------------------------------------------
                    const _origToDataURL = HTMLCanvasElement.prototype.toDataURL;
                    HTMLCanvasElement.prototype.toDataURL = function(type) {
                        if (type === 'image/png' || type === undefined) {
                            const ctx = this.getContext('2d');
                            if (ctx) {
                                try {
                                    const imageData = ctx.getImageData(0, 0, this.width, this.height);
                                    for (let i = 0; i < imageData.data.length; i += 4) {
                                        imageData.data[i] += Math.floor(Math.random() * 2);
                                    }
                                    ctx.putImageData(imageData, 0, 0);
                                } catch (e) {
                                    // SecurityError on tainted canvas — skip noise
                                }
                            }
                        }
                        return _origToDataURL.apply(this, arguments);
                    };

                    // -------------------------------------------------------
                    // WebGL vendor/renderer override
                    // Reports Intel Iris instead of SwiftShader/Mesa to look
                    // like a real Mac or common Intel laptop.
                    // -------------------------------------------------------
                    const _origGetParam = WebGLRenderingContext.prototype.getParameter;
                    WebGLRenderingContext.prototype.getParameter = function(parameter) {
                        // UNMASKED_VENDOR_WEBGL
                        if (parameter === 37445) return 'Intel Inc.';
                        // UNMASKED_RENDERER_WEBGL
                        if (parameter === 37446) return 'Intel Iris OpenGL Engine';
                        return _origGetParam.apply(this, arguments);
                    };
                    // Also patch WebGL2
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
                "Browser launched (headless=%s, viewport=%s, stealth=%s, args=%d)",
                self.headless,
                viewport,
                self.stealth_level,
                len(launch_args),
            )

        except Exception as e:
            # Clean up partial state on launch failure
            self.close()
            if isinstance(e, BrowserLaunchError):
                raise
            raise BrowserLaunchError(f"Failed to launch Chromium: {e}") from e

    def new_page(self):
        """Create a new page in the stealth context."""
        if not self._context:
            raise BrowserLaunchError("Browser not launched — use as context manager")
        return self._context.new_page()

    @property
    def context(self):
        """Access the browser context (for advanced usage)."""
        return self._context

    def close(self) -> None:
        """Tear down browser, context, and Playwright."""
        if self._context:
            try:
                self._context.close()
            except Exception:
                pass
            self._context = None

        if self._browser:
            try:
                self._browser.close()
            except Exception:
                pass
            self._browser = None

        if self._pw:
            try:
                self._pw.stop()
            except Exception:
                pass
            self._pw = None

        logger.debug("Browser closed")
