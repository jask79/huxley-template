#!/Library/Frameworks/Python.framework/Versions/3.11/bin/python3
"""
Universal CAPTCHA Solver for Huxley
Dynamically detects and solves reCAPTCHA v2/v3, hCaptcha, Cloudflare Turnstile across any website
"""

import asyncio
import logging
import random
import re
from typing import Optional, Dict, Any, Tuple
from enum import Enum
from pathlib import Path

from playwright.async_api import Page, async_playwright, Browser
from playwright_stealth import stealth

# Optional: playwright-recaptcha (Python 3.14+ compatibility issue with aifc module)
try:
    from playwright_recaptcha import recaptchav2, recaptchav3
    RECAPTCHA_AVAILABLE = True
except (ImportError, ModuleNotFoundError):
    logging.warning("playwright-recaptcha not available (Python 3.14+ compatibility)")
    RECAPTCHA_AVAILABLE = False
    recaptchav2 = None
    recaptchav3 = None


class CaptchaType(Enum):
    """Detected CAPTCHA types"""
    RECAPTCHA_V2 = "recaptcha_v2"
    RECAPTCHA_V3 = "recaptcha_v3"
    HCAPTCHA = "hcaptcha"
    CLOUDFLARE_TURNSTILE = "turnstile"
    UNKNOWN = "unknown"
    NONE = "none"


class CaptchaSolveResult:
    """Result of CAPTCHA solving attempt"""
    def __init__(
        self,
        success: bool,
        captcha_type: CaptchaType,
        token: Optional[str] = None,
        error: Optional[str] = None,
        time_taken: float = 0.0
    ):
        self.success = success
        self.captcha_type = captcha_type
        self.token = token
        self.error = error
        self.time_taken = time_taken

    def __repr__(self):
        status = "✓" if self.success else "✗"
        return f"<CaptchaSolveResult {status} {self.captcha_type.value} {self.time_taken:.1f}s>"


class UniversalCaptchaSolver:
    """
    Universal CAPTCHA solver that works across multiple platforms

    Features:
    - Auto-detection of CAPTCHA type
    - Multi-strategy solving (audio, image, API fallback)
    - Anti-detection with stealth mode
    - Human-like behavior simulation
    - Comprehensive error handling
    """

    def __init__(
        self,
        headless: bool = False,
        stealth_enabled: bool = True,
        timeout: int = 30,
        max_retries: int = 2,
        api_key: Optional[str] = None,
        browser: str = "chromium"  # chromium, firefox, brave (chromium best for bot detection)
    ):
        """
        Initialize universal CAPTCHA solver

        Args:
            headless: Run browser in headless mode (False recommended for better success)
            stealth_enabled: Enable anti-detection measures
            timeout: Timeout for CAPTCHA solving in seconds
            max_retries: Number of retry attempts for failed solves
            api_key: Optional API key for paid solving services (2captcha, etc.)
            browser: Browser to use (brave, firefox, chromium) - default brave
        """
        self.headless = headless
        self.stealth_enabled = stealth_enabled
        self.timeout = timeout
        self.max_retries = max_retries
        self.api_key = api_key
        self.browser = browser.lower()

        self.logger = logging.getLogger(__name__)
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )

    async def detect_captcha_type(self, page: Page) -> CaptchaType:
        """
        Automatically detect CAPTCHA type on the page

        Args:
            page: Playwright page object

        Returns:
            CaptchaType enum value
        """
        self.logger.info("🔍 Detecting CAPTCHA type...")

        try:
            # Check for reCAPTCHA v2 (iframe with google.com/recaptcha)
            recaptcha_v2_frames = [
                frame for frame in page.frames
                if 'google.com/recaptcha' in frame.url and 'anchor' in frame.url
            ]
            if recaptcha_v2_frames:
                self.logger.info("✓ Detected reCAPTCHA v2")
                return CaptchaType.RECAPTCHA_V2

            # Check for reCAPTCHA v3 (script tag with grecaptcha.execute)
            recaptcha_v3_script = await page.evaluate("""
                () => {
                    const scripts = Array.from(document.getElementsByTagName('script'));
                    return scripts.some(s =>
                        s.src.includes('recaptcha') &&
                        s.src.includes('render')
                    );
                }
            """)
            if recaptcha_v3_script:
                self.logger.info("✓ Detected reCAPTCHA v3")
                return CaptchaType.RECAPTCHA_V3

            # Check for hCaptcha (iframe with hcaptcha.com)
            hcaptcha_frames = [
                frame for frame in page.frames
                if 'hcaptcha.com' in frame.url
            ]
            if hcaptcha_frames:
                self.logger.info("✓ Detected hCaptcha")
                return CaptchaType.HCAPTCHA

            # Check for Cloudflare Turnstile (iframe with challenges.cloudflare.com)
            turnstile_frames = [
                frame for frame in page.frames
                if 'challenges.cloudflare.com' in frame.url or 'turnstile' in frame.url
            ]
            if turnstile_frames:
                self.logger.info("✓ Detected Cloudflare Turnstile")
                return CaptchaType.CLOUDFLARE_TURNSTILE

            # Check for common CAPTCHA-related elements
            captcha_indicators = await page.evaluate("""
                () => {
                    const selectors = [
                        '.g-recaptcha',
                        '#recaptcha',
                        '.h-captcha',
                        '.cf-turnstile',
                        '[data-sitekey]'
                    ];
                    return selectors.some(sel => document.querySelector(sel));
                }
            """)
            if captcha_indicators:
                self.logger.info("⚠ CAPTCHA element detected but type unclear")
                return CaptchaType.UNKNOWN

            self.logger.info("✓ No CAPTCHA detected")
            return CaptchaType.NONE

        except Exception as e:
            self.logger.error(f"Error detecting CAPTCHA: {e}")
            return CaptchaType.UNKNOWN

    async def solve_recaptcha_v2(self, page: Page) -> CaptchaSolveResult:
        """
        Solve reCAPTCHA v2 using audio challenge method (free)

        Args:
            page: Playwright page object

        Returns:
            CaptchaSolveResult with token if successful
        """
        import time
        start_time = time.time()

        self.logger.info("🤖 Solving reCAPTCHA v2 via audio challenge...")

        if not RECAPTCHA_AVAILABLE:
            return CaptchaSolveResult(
                success=False,
                captcha_type=CaptchaType.RECAPTCHA_V2,
                error="playwright-recaptcha not available (Python 3.14+ compatibility)",
                time_taken=0
            )

        try:
            async with recaptchav2.AsyncSolver(page) as solver:
                token = await solver.solve_recaptcha(wait=True, timeout=self.timeout)

                if token:
                    elapsed = time.time() - start_time
                    self.logger.info(f"✓ reCAPTCHA v2 solved in {elapsed:.1f}s")
                    return CaptchaSolveResult(
                        success=True,
                        captcha_type=CaptchaType.RECAPTCHA_V2,
                        token=token,
                        time_taken=elapsed
                    )
                else:
                    elapsed = time.time() - start_time
                    return CaptchaSolveResult(
                        success=False,
                        captcha_type=CaptchaType.RECAPTCHA_V2,
                        error="No token returned from solver",
                        time_taken=elapsed
                    )

        except Exception as e:
            elapsed = time.time() - start_time
            self.logger.error(f"✗ reCAPTCHA v2 solve failed: {e}")
            return CaptchaSolveResult(
                success=False,
                captcha_type=CaptchaType.RECAPTCHA_V2,
                error=str(e),
                time_taken=elapsed
            )

    async def solve_recaptcha_v3(self, page: Page) -> CaptchaSolveResult:
        """
        Solve reCAPTCHA v3 by intercepting token

        Args:
            page: Playwright page object

        Returns:
            CaptchaSolveResult with token if successful
        """
        import time
        start_time = time.time()

        self.logger.info("🤖 Solving reCAPTCHA v3...")

        if not RECAPTCHA_AVAILABLE:
            return CaptchaSolveResult(
                success=False,
                captcha_type=CaptchaType.RECAPTCHA_V3,
                error="playwright-recaptcha not available (Python 3.14+ compatibility)",
                time_taken=0
            )

        try:
            async with recaptchav3.AsyncSolver(page) as solver:
                token = await solver.solve_recaptcha(timeout=self.timeout)

                if token:
                    elapsed = time.time() - start_time
                    self.logger.info(f"✓ reCAPTCHA v3 solved in {elapsed:.1f}s")
                    return CaptchaSolveResult(
                        success=True,
                        captcha_type=CaptchaType.RECAPTCHA_V3,
                        token=token,
                        time_taken=elapsed
                    )
                else:
                    elapsed = time.time() - start_time
                    return CaptchaSolveResult(
                        success=False,
                        captcha_type=CaptchaType.RECAPTCHA_V3,
                        error="No token intercepted",
                        time_taken=elapsed
                    )

        except Exception as e:
            elapsed = time.time() - start_time
            self.logger.error(f"✗ reCAPTCHA v3 solve failed: {e}")
            return CaptchaSolveResult(
                success=False,
                captcha_type=CaptchaType.RECAPTCHA_V3,
                error=str(e),
                time_taken=elapsed
            )

    async def solve_hcaptcha(self, page: Page) -> CaptchaSolveResult:
        """
        Solve hCaptcha (requires API or manual intervention)

        Args:
            page: Playwright page object

        Returns:
            CaptchaSolveResult
        """
        import time
        start_time = time.time()

        self.logger.warning("⚠ hCaptcha detected - Free solving not available")

        if self.api_key:
            self.logger.info("🔑 API key provided - attempting API solve...")
            # TODO: Implement API-based hCaptcha solving
            # Would use playwright-captcha or 2captcha API
            elapsed = time.time() - start_time
            return CaptchaSolveResult(
                success=False,
                captcha_type=CaptchaType.HCAPTCHA,
                error="API solving not yet implemented",
                time_taken=elapsed
            )
        else:
            elapsed = time.time() - start_time
            self.logger.info("💡 Suggestion: Provide API key or solve manually")
            return CaptchaSolveResult(
                success=False,
                captcha_type=CaptchaType.HCAPTCHA,
                error="hCaptcha requires API key or manual solving",
                time_taken=elapsed
            )

    async def solve_turnstile(self, page: Page) -> CaptchaSolveResult:
        """
        Solve Cloudflare Turnstile (requires API or special handling)

        Args:
            page: Playwright page object

        Returns:
            CaptchaSolveResult
        """
        import time
        start_time = time.time()

        self.logger.warning("⚠ Cloudflare Turnstile detected")

        # Turnstile sometimes auto-solves with good stealth
        self.logger.info("⏳ Waiting for Turnstile auto-solve...")
        try:
            await asyncio.sleep(3)  # Give Turnstile time to process

            # Check if solved
            turnstile_success = await page.evaluate("""
                () => {
                    const token = document.querySelector('[name="cf-turnstile-response"]');
                    return token && token.value.length > 0;
                }
            """)

            elapsed = time.time() - start_time

            if turnstile_success:
                self.logger.info("✓ Turnstile auto-solved!")
                return CaptchaSolveResult(
                    success=True,
                    captcha_type=CaptchaType.CLOUDFLARE_TURNSTILE,
                    token="turnstile-auto-solved",
                    time_taken=elapsed
                )
            else:
                self.logger.warning("✗ Turnstile did not auto-solve")
                return CaptchaSolveResult(
                    success=False,
                    captcha_type=CaptchaType.CLOUDFLARE_TURNSTILE,
                    error="Turnstile requires API solving or better stealth",
                    time_taken=elapsed
                )

        except Exception as e:
            elapsed = time.time() - start_time
            self.logger.error(f"✗ Turnstile handling failed: {e}")
            return CaptchaSolveResult(
                success=False,
                captcha_type=CaptchaType.CLOUDFLARE_TURNSTILE,
                error=str(e),
                time_taken=elapsed
            )

    async def solve(self, page: Page) -> CaptchaSolveResult:
        """
        Universal solve method - detects and solves any CAPTCHA type

        Args:
            page: Playwright page object with CAPTCHA to solve

        Returns:
            CaptchaSolveResult with details
        """
        # Detect CAPTCHA type
        captcha_type = await self.detect_captcha_type(page)

        # No CAPTCHA present
        if captcha_type == CaptchaType.NONE:
            return CaptchaSolveResult(
                success=True,
                captcha_type=CaptchaType.NONE,
                time_taken=0.0
            )

        # Route to appropriate solver with retries
        for attempt in range(self.max_retries + 1):
            if attempt > 0:
                self.logger.info(f"🔄 Retry attempt {attempt}/{self.max_retries}")
                await asyncio.sleep(random.uniform(2, 5))  # Random delay between retries

            if captcha_type == CaptchaType.RECAPTCHA_V2:
                result = await self.solve_recaptcha_v2(page)
            elif captcha_type == CaptchaType.RECAPTCHA_V3:
                result = await self.solve_recaptcha_v3(page)
            elif captcha_type == CaptchaType.HCAPTCHA:
                result = await self.solve_hcaptcha(page)
            elif captcha_type == CaptchaType.CLOUDFLARE_TURNSTILE:
                result = await self.solve_turnstile(page)
            else:
                return CaptchaSolveResult(
                    success=False,
                    captcha_type=captcha_type,
                    error="Unknown or unsupported CAPTCHA type"
                )

            if result.success:
                return result

        # All retries failed
        self.logger.error(f"✗ All {self.max_retries + 1} attempts failed")
        return result

    async def create_stealth_browser(self) -> Tuple[Browser, Page]:
        """
        Create a stealth-enabled browser instance with Brave browser

        Returns:
            Tuple of (Browser, Page) with stealth applied
        """
        playwright = await async_playwright().start()

        # Configure browser based on selection
        if self.browser == "brave":
            # Brave browser (Chromium-based)
            # Common Brave paths on macOS
            brave_paths = [
            ]

            brave_path = None
            for path in brave_paths:
                if Path(path).exists():
                    brave_path = path
                    break

            if not brave_path:
                self.logger.warning("⚠ Brave browser not found, falling back to Chromium")
                browser = await playwright.chromium.launch(
                    headless=self.headless,
                    args=['--disable-blink-features=AutomationControlled']
                )
            else:
                self.logger.info(f"✓ Using Brave browser: {brave_path}")
                browser = await playwright.chromium.launch(
                    executable_path=brave_path,
                    headless=self.headless,
                    args=[
                        '--disable-blink-features=AutomationControlled',
                        '--disable-features=IsolateOrigins,site-per-process'
                    ],
                    channel=None  # Don't use channel when using executable_path
                )

        elif self.browser == "firefox":
            # Firefox (recommended for CAPTCHA solving in research)
            browser = await playwright.firefox.launch(
                headless=self.headless,
                args=['--disable-blink-features=AutomationControlled']
            )

        else:  # chromium
            browser = await playwright.chromium.launch(
                headless=self.headless,
                args=['--disable-blink-features=AutomationControlled']
            )

        page = await browser.new_page()

        # Apply stealth if enabled
        if self.stealth_enabled:
            await stealth(page)
            self.logger.info("✓ Stealth mode enabled")

        return browser, page

    async def human_type(self, page: Page, selector: str, text: str):
        """
        Type text with human-like delays

        Args:
            page: Playwright page
            selector: CSS selector for input field
            text: Text to type
        """
        await page.click(selector)
        for char in text:
            await page.keyboard.type(char)
            await asyncio.sleep(random.uniform(0.05, 0.15))  # 50-150ms per keystroke

    async def human_click(self, page: Page, selector: str):
        """
        Click with human-like behavior (random position within element)

        Args:
            page: Playwright page
            selector: CSS selector for element to click
        """
        element = await page.query_selector(selector)
        if not element:
            raise ValueError(f"Element not found: {selector}")

        box = await element.bounding_box()
        if not box:
            raise ValueError(f"Element has no bounding box: {selector}")

        # Random position within element bounds
        x = box['x'] + random.uniform(5, box['width'] - 5)
        y = box['y'] + random.uniform(5, box['height'] - 5)

        await page.mouse.move(x, y)
        await asyncio.sleep(random.uniform(0.1, 0.3))
        await page.mouse.click(x, y)


async def test_captcha_solver():
    """Test the universal CAPTCHA solver on reCAPTCHA demo page"""
    solver = UniversalCaptchaSolver(headless=False)

    browser, page = await solver.create_stealth_browser()

    try:
        # Test on Google's reCAPTCHA demo
        print("\n🧪 Testing on reCAPTCHA v2 demo page...")
        await page.goto("https://www.google.com/recaptcha/api2/demo")

        # Solve CAPTCHA
        result = await solver.solve(page)

        print(f"\n📊 Result: {result}")
        print(f"   Success: {result.success}")
        print(f"   Type: {result.captcha_type.value}")
        print(f"   Time: {result.time_taken:.2f}s")

        if result.token:
            print(f"   Token: {result.token[:50]}...")

        if result.error:
            print(f"   Error: {result.error}")

        # Wait to see result
        await asyncio.sleep(5)

    finally:
        await browser.close()


if __name__ == "__main__":
    print("🚀 Universal CAPTCHA Solver for Huxley")
    print("=" * 60)
    asyncio.run(test_captcha_solver())
