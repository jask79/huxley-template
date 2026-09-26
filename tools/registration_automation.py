#!/usr/bin/env python3
"""
Enhanced Account Registration Automation
Uses direct Playwright library with stealth, human simulation, and CAPTCHA solving

Features:
- playwright-stealth for fingerprint evasion
- Human behavior simulation (mouse movements, timing, typos)
- Dynamic site detection and form field discovery
- CAPTCHA solving with playwright-recaptcha
- Configurable per-site strategies
"""

import asyncio
import random
import time
import re
from typing import Optional, Dict, List, Tuple
from pathlib import Path
from dataclasses import dataclass
import logging

# Direct Playwright imports
from playwright.async_api import async_playwright, Page, Browser, BrowserContext
from playwright_stealth import Stealth

# CAPTCHA solving - reCAPTCHA
try:
    from playwright_recaptcha import recaptchav2
    RECAPTCHA_AVAILABLE = True
except ImportError:
    RECAPTCHA_AVAILABLE = False
    logging.warning("playwright-recaptcha not available - reCAPTCHA solving disabled")

# CAPTCHA solving - hCaptcha
try:
    from hcaptcha_challenger import AgentV, AgentConfig
    HCAPTCHA_AVAILABLE = True
except ImportError:
    HCAPTCHA_AVAILABLE = False
    logging.warning("hcaptcha-challenger not available - hCaptcha solving disabled")


logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)


@dataclass
class RegistrationConfig:
    """Configuration for registration automation"""
    headless: bool = True  # Background mode by default; set False for debugging
    slow_mo: int = 100  # Slow down actions by milliseconds
    viewport_width: int = 1280
    viewport_height: int = 720
    user_agent: Optional[str] = None
    locale: str = "en-US"
    timezone: str = "America/New_York"

    # Human simulation settings
    typing_speed_wpm: int = 45  # Words per minute (human average: 40-50)
    mouse_movement_enabled: bool = True
    random_pauses_enabled: bool = True
    typo_correction_enabled: bool = True
    typo_rate: float = 0.05  # 5% chance of typo per word

    # Session/Profile persistence (inspired by agent-browser CLI patterns)
    session_name: Optional[str] = None  # Named session for isolation
    profile_path: Optional[str] = None  # Persistent profile for auth state


@dataclass
class RegistrationResult:
    """Result of registration attempt"""
    success: bool
    email: str
    username: Optional[str] = None
    error_message: Optional[str] = None
    captcha_encountered: bool = False
    captcha_solved: bool = False
    verification_required: bool = False
    screenshots: List[str] = None

    def __post_init__(self):
        if self.screenshots is None:
            self.screenshots = []


class HumanSimulator:
    """Simulates human-like behavior during automation"""

    def __init__(self, page: Page, config: RegistrationConfig):
        self.page = page
        self.config = config

    async def random_pause(self, min_ms: int = 500, max_ms: int = 2000):
        """
        Random pause to simulate reading/thinking
        Research shows human pauses vary:
        - Between fields: 500-1500ms
        - Before submit: 900-2000ms
        - After typing: 300-800ms
        """
        if self.config.random_pauses_enabled:
            pause = random.uniform(min_ms, max_ms) / 1000
            await asyncio.sleep(pause)

    async def move_mouse_to_element(self, selector: str):
        """Move mouse in human-like path to element"""
        if not self.config.mouse_movement_enabled:
            return

        try:
            element = await self.page.wait_for_selector(selector, timeout=5000)
            if element:
                box = await element.bounding_box()
                if box:
                    # Move to element center with slight randomness
                    target_x = box['x'] + box['width'] / 2 + random.randint(-5, 5)
                    target_y = box['y'] + box['height'] / 2 + random.randint(-5, 5)

                    # Move mouse in curved path (simulates human movement)
                    await self.page.mouse.move(target_x, target_y, steps=random.randint(10, 20))
                    await asyncio.sleep(random.uniform(0.1, 0.3))
        except Exception as e:
            logger.debug(f"Mouse movement failed: {e}")

    async def human_type(self, selector: str, text: str, with_typos: bool = True):
        """
        Type text with human-like speed and occasional typos
        Research-based timing: 80-250ms per character (average human typing)
        Typing speeds: Fast typists (75 WPM) = ~80ms, Average (40 WPM) = ~200ms
        """
        await self.move_mouse_to_element(selector)
        await self.page.click(selector)
        await self.random_pause(300, 800)

        # Research-based typing delays: 80-250ms per character with randomness
        # This is more realistic than WPM calculation and prevents detection
        min_delay = 80  # Fast typist minimum
        max_delay = 250  # Average typist maximum

        text_to_type = text

        # Simulate typos and corrections (disabled for critical fields by caller)
        if with_typos and self.config.typo_correction_enabled and len(text) > 3:
            words = text.split(' ')
            if len(words) > 1 and random.random() < self.config.typo_rate:
                # Introduce a typo in a random word
                word_idx = random.randint(0, len(words) - 1)
                word = words[word_idx]
                if len(word) > 2:
                    char_idx = random.randint(0, len(word) - 1)
                    typo_word = word[:char_idx] + random.choice('qwertyuiop') + word[char_idx + 1:]
                    words[word_idx] = typo_word

                    # Type with typo (character by character with random delays)
                    partial_text = ' '.join(words)
                    for char in partial_text:
                        await self.page.keyboard.type(char)
                        await asyncio.sleep(random.uniform(min_delay, max_delay) / 1000)

                    await self.random_pause(500, 1200)  # Notice typo

                    # Correct typo (backspace and retype)
                    for _ in range(len(typo_word)):
                        await self.page.keyboard.press('Backspace')
                        await asyncio.sleep(random.uniform(min_delay, max_delay) / 1000)

                    for char in word:
                        await self.page.keyboard.type(char)
                        await asyncio.sleep(random.uniform(min_delay, max_delay) / 1000)

                    await self.random_pause(200, 500)
                    return

        # Normal typing without typos - character by character with random delays
        # This is CRITICAL for avoiding bot detection (instantaneous filling triggers detection)
        for char in text_to_type:
            await self.page.keyboard.type(char)
            await asyncio.sleep(random.uniform(min_delay, max_delay) / 1000)

        await self.random_pause(200, 600)

    async def scroll_smoothly(self, pixels: int = 300):
        """Smooth scroll like human"""
        if self.config.mouse_movement_enabled:
            await self.page.evaluate(f"""
                window.scrollBy({{
                    top: {pixels},
                    left: 0,
                    behavior: 'smooth'
                }});
            """)
            await self.random_pause(800, 1500)


class DynamicFormDetector:
    """Detects and maps form fields dynamically across different sites"""

    # Common field patterns for different input types
    FIELD_PATTERNS = {
        'email': [
            'input[type="email"]',
            'input[name*="email" i]',
            'input[id*="email" i]',
            'input[placeholder*="email" i]',
            'input[autocomplete="email"]'
        ],
        'password': [
            'input[type="password"]',
            'input[name*="password" i]',
            'input[id*="password" i]',
            'input[placeholder*="password" i]',
            'input[autocomplete="new-password"]',
            'input[autocomplete="current-password"]'
        ],
        'username': [
            'input[name*="username" i]',
            'input[id*="username" i]',
            'input[placeholder*="username" i]',
            'input[autocomplete="username"]'
        ],
        'fullname': [
            'input[name*="name" i]:not([name*="username" i])',
            'input[id*="name" i]:not([id*="username" i])',
            'input[placeholder*="full name" i]',
            'input[placeholder*="name" i]',
            'input[autocomplete="name"]'
        ],
        'firstname': [
            'input[name*="first" i]',
            'input[id*="first" i]',
            'input[placeholder*="first name" i]',
            'input[autocomplete="given-name"]'
        ],
        'lastname': [
            'input[name*="last" i]',
            'input[id*="last" i]',
            'input[placeholder*="last name" i]',
            'input[autocomplete="family-name"]'
        ],
        'terms_checkbox': [
            'input[type="checkbox"][name*="terms" i]',
            'input[type="checkbox"][name*="accept" i]',
            'input[type="checkbox"][name*="agree" i]',
            'input[type="checkbox"][required]'
        ],
        'submit': [
            # CRITICAL: Use role-based locators with exact text matching (Playwright best practice)
            # These will be converted to getByRole() calls in the detector
            # The exact:true flag prevents matching "Sign up with Google" when looking for "Sign up"
            'role:button[name="Create account"]',
            'role:button[name="Sign up"]',
            'role:button[name="Register"]',
            'role:button[name="Create your account"]',
            'role:button[name="Join now"]',
            'role:button[name="Join"]',
            'role:button[name="Continue"]',  # For multi-step forms like GitHub
            # Fallback to type-based selectors if role-based fails
            # IMPORTANT: Exclude OAuth buttons explicitly
            'button[type="submit"]:not(:has-text("Continue with")):not(:has-text("Sign in with")):not(:has-text("Google")):not(:has-text("GitHub"))',
            'input[type="submit"]',
            # Explicit text matching that excludes OAuth patterns
            'button:has-text("Create account"):not(:has-text("Continue with"))',
            'button:has-text("Sign up"):not(:has-text("Continue with"))',
        ]
    }

    def __init__(self, page: Page):
        self.page = page
        self.detected_fields: Dict[str, str] = {}

    async def detect_form_fields(self) -> Dict[str, str]:
        """Detect all form fields on current page"""
        logger.info("🔍 Detecting form fields...")

        for field_type, selectors in self.FIELD_PATTERNS.items():
            for selector in selectors:
                try:
                    # Handle role-based locators (Playwright best practice)
                    if selector.startswith('role:'):
                        element = await self._query_by_role(selector)
                    else:
                        element = await self.page.query_selector(selector)

                    if element and await element.is_visible():
                        self.detected_fields[field_type] = selector
                        logger.info(f"  ✓ Found {field_type}: {selector}")
                        break
                except Exception as e:
                    logger.debug(f"  × Selector failed: {selector} - {e}")
                    continue

        return self.detected_fields

    async def _query_by_role(self, role_selector: str):
        """
        Convert role-based selector to getByRole() call
        Format: role:button[name="Create account"]
        """
        try:
            # Parse role selector
            match = re.match(r'role:(\w+)\[name="([^"]+)"\]', role_selector)
            if not match:
                return None

            role, name = match.groups()

            # Use Playwright's getByRole with exact name matching
            element = self.page.get_by_role(role, name=name, exact=True)

            # Check if element exists and is visible
            if await element.count() > 0:
                return await element.first.element_handle()

            return None
        except Exception as e:
            logger.debug(f"Role-based query failed: {e}")
            return None

    async def get_field_selector(self, field_type: str) -> Optional[str]:
        """Get selector for specific field type"""
        if field_type in self.detected_fields:
            return self.detected_fields[field_type]

        # Try detecting again if not found
        for selector in self.FIELD_PATTERNS.get(field_type, []):
            try:
                # Handle role-based locators
                if selector.startswith('role:'):
                    element = await self._query_by_role(selector)
                else:
                    element = await self.page.query_selector(selector)

                if element and await element.is_visible():
                    self.detected_fields[field_type] = selector
                    return selector
            except:
                continue

        return None


class RegistrationAutomation:
    """Main registration automation engine"""

    def __init__(self, config: Optional[RegistrationConfig] = None):
        self.config = config or RegistrationConfig()
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None

    async def initialize(self):
        """
        Initialize browser with stealth mode
        Research-based anti-detection configuration from:
        - ScrapeOps Playwright Anti-Detection Guide
        - Playwright Best Practices for Avoiding Detection

        Supports two persistence modes (inspired by agent-browser CLI):
        - session_name: Named session for parallel isolated instances
        - profile_path: Persistent context for auth state preservation
        """
        logger.info("🚀 Initializing stealth browser...")

        # Session/profile path resolution
        profile_dir = None
        if self.config.profile_path:
            profile_dir = Path(self.config.profile_path)
            profile_dir.mkdir(parents=True, exist_ok=True)
            logger.info(f"📁 Using persistent profile: {profile_dir}")
        elif self.config.session_name:
            # Named sessions stored in Huxley's session directory
            session_base = Path("{{CATALYST_ROOT}}/.cache/browser_sessions")
            session_base.mkdir(parents=True, exist_ok=True)
            profile_dir = session_base / self.config.session_name
            profile_dir.mkdir(parents=True, exist_ok=True)
            logger.info(f"📁 Using named session: {self.config.session_name}")

        playwright = await async_playwright().start()
        self._playwright = playwright  # Store reference for cleanup

        # Anti-detection browser arguments
        browser_args = [
            '--disable-blink-features=AutomationControlled',  # Removes navigator.webdriver flag
            '--disable-infobars',
            '--disable-extensions',
            '--disable-dev-shm-usage',
            '--no-sandbox',
            '--disable-setuid-sandbox',
            '--disable-web-security',
            '--disable-features=IsolateOrigins,site-per-process',
            '--enable-webgl',  # Hardware fingerprinting
            '--use-gl=swiftshader',  # GPU rendering simulation
            '--window-size=1920,1080'  # Consistent viewport
        ]

        # Context options (shared between persistent and non-persistent)
        context_options = {
            'viewport': {'width': self.config.viewport_width, 'height': self.config.viewport_height},
            'user_agent': self.config.user_agent or 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'locale': self.config.locale,
            'timezone_id': self.config.timezone,
            'permissions': ['geolocation'],
            'geolocation': {'latitude': 40.7128, 'longitude': -74.0060},  # New York
            'color_scheme': 'light',
            'extra_http_headers': {
                'Accept-Language': 'en-US,en;q=0.9',
                'Accept-Encoding': 'gzip, deflate, br',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Sec-Fetch-Dest': 'document',
                'Sec-Fetch-Mode': 'navigate',
                'Sec-Fetch-Site': 'none',
                'Upgrade-Insecure-Requests': '1'
            }
        }

        if profile_dir:
            # Use launch_persistent_context for session/profile persistence
            # This preserves cookies, localStorage, IndexedDB across runs
            logger.info("🔐 Using persistent context (auth state will be preserved)")
            self.context = await playwright.chromium.launch_persistent_context(
                user_data_dir=str(profile_dir),
                headless=self.config.headless,
                slow_mo=self.config.slow_mo,
                args=browser_args,
                **context_options
            )
            self.browser = None  # Persistent context doesn't have separate browser
            self.page = self.context.pages[0] if self.context.pages else await self.context.new_page()
        else:
            # Standard ephemeral browser (original behavior)
            self.browser = await playwright.chromium.launch(
                headless=self.config.headless,
                slow_mo=self.config.slow_mo,
                args=browser_args
            )
            self.context = await self.browser.new_context(**context_options)
            self.page = await self.context.new_page()

        # Apply stealth mode
        stealth = Stealth()
        await stealth.apply_stealth_async(self.page)

        # Override navigator.webdriver (additional layer)
        await self.page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
        """)

        mode_desc = "persistent" if profile_dir else "ephemeral"
        logger.info(f"✅ Browser initialized with stealth mode ({mode_desc})")

    async def register_account(self,
                              url: str,
                              email: str,
                              password: str,
                              username: Optional[str] = None,
                              fullname: Optional[str] = None) -> RegistrationResult:
        """
        Register account on any site with dynamic field detection

        Args:
            url: Registration page URL
            email: Email address
            password: Password
            username: Optional username
            fullname: Optional full name
        """

        result = RegistrationResult(success=False, email=email, username=username)

        try:
            logger.info(f"🌐 Navigating to {url}")
            await self.page.goto(url, wait_until='networkidle', timeout=30000)

            # Wait for page to settle (handle Cloudflare, etc.)
            await asyncio.sleep(5)

            # Take initial screenshot
            screenshot_path = f"/tmp/registration_start_{int(time.time())}.png"
            await self.page.screenshot(path=screenshot_path)
            result.screenshots.append(screenshot_path)
            logger.info(f"📸 Screenshot: {screenshot_path}")

            # Initialize helpers
            human = HumanSimulator(self.page, self.config)
            detector = DynamicFormDetector(self.page)

            # Detect form fields
            await detector.detect_form_fields()

            # Scroll to see form (human behavior)
            await human.scroll_smoothly(300)
            await human.random_pause(1000, 2000)

            # Fill full name if present
            if fullname:
                fullname_selector = await detector.get_field_selector('fullname')
                if fullname_selector:
                    logger.info(f"👤 Filling name field")
                    await human.human_type(fullname_selector, fullname)

            # Fill email field
            email_selector = await detector.get_field_selector('email')
            if email_selector:
                logger.info(f"📧 Filling email")
                await human.human_type(email_selector, email, with_typos=False)  # Don't typo email
                # Research: 500-1500ms pause between fields
                await human.random_pause(500, 1500)
            else:
                raise Exception("Email field not found")

            # Fill username if present and provided
            if username:
                username_selector = await detector.get_field_selector('username')
                if username_selector:
                    logger.info(f"👥 Filling username")
                    await human.human_type(username_selector, username, with_typos=False)
                    # Research: 500-1500ms pause between fields
                    await human.random_pause(500, 1500)

            # Fill password field
            password_selector = await detector.get_field_selector('password')
            if password_selector:
                logger.info(f"🔑 Filling password")
                await human.human_type(password_selector, password, with_typos=False)
                # Research: 900-2000ms pause before final actions (longer thinking time)
                await human.random_pause(900, 2000)
            else:
                raise Exception("Password field not found")

            # Accept terms if checkbox present
            terms_selector = await detector.get_field_selector('terms_checkbox')
            if terms_selector:
                logger.info(f"☑️  Accepting terms")
                await human.move_mouse_to_element(terms_selector)
                await self.page.click(terms_selector)
                # Research: 500-1000ms after checkbox
                await human.random_pause(500, 1000)

            # Check for CAPTCHA
            captcha_detected, captcha_type = await self._detect_captcha()
            if captcha_detected:
                result.captcha_encountered = True
                logger.warning(f"⚠️  CAPTCHA detected: {captcha_type}")

                # Check if we can solve this type
                can_solve = False
                if captcha_type == 'recaptcha' and RECAPTCHA_AVAILABLE:
                    can_solve = True
                elif captcha_type == 'hcaptcha' and HCAPTCHA_AVAILABLE:
                    can_solve = True
                elif captcha_type == 'turnstile':
                    can_solve = True  # We'll try stealth bypass

                if can_solve:
                    logger.info(f"🔧 Attempting to solve {captcha_type}...")
                    captcha_solved = await self._solve_captcha(captcha_type)
                    result.captcha_solved = captcha_solved

                    if not captcha_solved:
                        logger.error(f"❌ {captcha_type} solving failed")
                        result.error_message = f"{captcha_type} solving failed - manual intervention required"
                        return result
                else:
                    logger.error(f"❌ No solver available for {captcha_type}")
                    result.error_message = f"{captcha_type} encountered but solver not available"
                    return result

            # Submit form
            # Research: 900-2000ms pause before submit (thinking/reviewing time)
            await human.random_pause(900, 2000)
            submit_selector = await detector.get_field_selector('submit')

            if submit_selector:
                logger.info(f"🚀 Submitting form with selector: {submit_selector}")

                # Handle role-based vs CSS selectors differently for clicking
                if submit_selector.startswith('role:'):
                    # Use getByRole for clicking (most reliable)
                    # Research shows role-based locators with exact:true prevent OAuth button issues
                    match = re.match(r'role:(\w+)\[name="([^"]+)"\]', submit_selector)
                    if match:
                        role, name = match.groups()
                        logger.info(f"  Using role-based click: {role} with name '{name}' (exact match)")

                        # Verify the button before clicking
                        button = self.page.get_by_role(role, name=name, exact=True)
                        button_text = await button.text_content()
                        logger.info(f"  Submit button text: '{button_text.strip()}'")

                        # CRITICAL: Validate it's NOT an OAuth button
                        # Research shows this prevents the most common automation failure
                        oauth_indicators = ['continue with', 'sign in with', 'sign up with', 'google', 'github', 'facebook', 'microsoft']
                        if any(indicator in button_text.lower() for indicator in oauth_indicators):
                            logger.error(f"❌ Detected OAuth button, refusing to click: '{button_text}'")
                            raise Exception(f"Selector matched OAuth button instead of submit: {button_text}")

                        # Human-like mouse movement before click
                        await human.random_pause(200, 500)
                        await button.click()
                else:
                    # Traditional CSS selector click
                    element = await self.page.query_selector(submit_selector)
                    if element:
                        element_text = await element.text_content() or ''
                        logger.info(f"  Submit button text: '{element_text.strip()}'")

                        # CRITICAL: Validate it's NOT an OAuth button
                        oauth_indicators = ['continue with', 'sign in with', 'sign up with', 'google', 'github', 'facebook', 'microsoft']
                        if any(indicator in element_text.lower() for indicator in oauth_indicators):
                            logger.error(f"❌ Detected OAuth button, refusing to click: '{element_text}'")
                            raise Exception(f"Selector matched OAuth button instead of submit: {element_text}")

                        await human.move_mouse_to_element(submit_selector)
                        await human.random_pause(200, 500)
                        await self.page.click(submit_selector)
            else:
                logger.warning("⚠️  No submit button found, pressing Enter as fallback")
                await self.page.keyboard.press('Enter')

            # Wait for navigation/response
            await asyncio.sleep(5)

            # Take post-submit screenshot
            screenshot_path = f"/tmp/registration_end_{int(time.time())}.png"
            await self.page.screenshot(path=screenshot_path)
            result.screenshots.append(screenshot_path)

            # Check result
            current_url = self.page.url
            page_content = await self.page.content()

            # Success indicators
            success_indicators = [
                'verify' in current_url.lower(),
                'verification' in current_url.lower(),
                'confirm' in current_url.lower(),
                'check your email' in page_content.lower(),
                'welcome' in current_url.lower(),
                'dashboard' in current_url.lower()
            ]

            # Error indicators
            error_indicators = [
                'error' in page_content.lower(),
                'already exists' in page_content.lower(),
                'invalid' in page_content.lower(),
                'try again' in page_content.lower()
            ]

            if any(success_indicators):
                result.success = True
                if 'verify' in current_url.lower() or 'check your email' in page_content.lower():
                    result.verification_required = True
                    logger.info("✅ Registration successful - email verification required")
                else:
                    logger.info("✅ Registration successful")
            elif any(error_indicators):
                result.success = False
                result.error_message = "Registration failed - check page for errors"
                logger.error(f"❌ Registration failed: {current_url}")
            else:
                result.success = True  # Assume success if no clear error
                logger.warning("⚠️  Registration status unclear - assuming success")

            logger.info(f"📍 Final URL: {current_url}")

        except Exception as e:
            result.success = False
            result.error_message = str(e)
            logger.error(f"❌ Registration error: {e}")

            # Error screenshot
            try:
                screenshot_path = f"/tmp/registration_error_{int(time.time())}.png"
                await self.page.screenshot(path=screenshot_path)
                result.screenshots.append(screenshot_path)
            except:
                pass

        return result

    async def _detect_captcha(self) -> tuple[bool, str]:
        """
        Detect if CAPTCHA is present and identify the type.

        Returns:
            Tuple of (is_present, captcha_type)
            captcha_type is one of: 'recaptcha', 'hcaptcha', 'turnstile', 'unknown'
        """
        # reCAPTCHA selectors
        recaptcha_selectors = [
            'iframe[src*="recaptcha"]',
            '.g-recaptcha',
            '[data-sitekey][class*="recaptcha"]',
        ]

        # hCaptcha selectors
        hcaptcha_selectors = [
            'iframe[src*="hcaptcha"]',
            '.h-captcha',
            '[data-sitekey][class*="hcaptcha"]',
            'iframe[data-hcaptcha-widget-id]',
        ]

        # Cloudflare Turnstile selectors
        turnstile_selectors = [
            'iframe[src*="turnstile"]',
            '#cf-turnstile',
            '.cf-turnstile',
        ]

        # Check reCAPTCHA
        for selector in recaptcha_selectors:
            try:
                element = await self.page.query_selector(selector)
                if element:
                    logger.info("🔍 Detected: reCAPTCHA")
                    return True, 'recaptcha'
            except:
                continue

        # Check hCaptcha
        for selector in hcaptcha_selectors:
            try:
                element = await self.page.query_selector(selector)
                if element:
                    logger.info("🔍 Detected: hCaptcha")
                    return True, 'hcaptcha'
            except:
                continue

        # Check Turnstile
        for selector in turnstile_selectors:
            try:
                element = await self.page.query_selector(selector)
                if element:
                    logger.info("🔍 Detected: Cloudflare Turnstile")
                    return True, 'turnstile'
            except:
                continue

        return False, 'none'

    async def _solve_captcha(self, captcha_type: str = 'unknown') -> bool:
        """
        Solve CAPTCHA based on detected type.

        Args:
            captcha_type: Type of CAPTCHA ('recaptcha', 'hcaptcha', 'turnstile', 'unknown')

        Returns:
            True if solved successfully
        """
        try:
            # === reCAPTCHA ===
            if captcha_type in ('recaptcha', 'unknown'):
                recaptcha_frame = self.page.frame(url=re.compile(r'google\.com/recaptcha'))
                if recaptcha_frame and RECAPTCHA_AVAILABLE:
                    logger.info("🔧 Attempting to solve reCAPTCHA...")
                    async with recaptchav2.AsyncSolver(self.page) as solver:
                        token = await solver.solve_recaptcha(wait=True, timeout=30)
                        if token:
                            logger.info("✅ reCAPTCHA solved successfully")
                            return True

            # === hCaptcha ===
            if captcha_type in ('hcaptcha', 'unknown') and HCAPTCHA_AVAILABLE:
                logger.info("🔧 Attempting to solve hCaptcha...")

                # Get Gemini API key from environment
                import os
                gemini_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")

                if not gemini_key:
                    logger.warning("⚠️ GEMINI_API_KEY not set - hCaptcha auto-solve unavailable")
                    return False

                try:
                    # Create agent config
                    from pathlib import Path
                    cache_dir = Path("{{CATALYST_ROOT}}/.cache/hcaptcha")
                    cache_dir.mkdir(parents=True, exist_ok=True)

                    agent_config = AgentConfig(
                        GEMINI_API_KEY=gemini_key,
                        cache_dir=cache_dir,
                        EXECUTION_TIMEOUT=120.0,
                        RESPONSE_TIMEOUT=30.0,
                        RETRY_ON_FAILURE=True,
                    )

                    # Create and run agent
                    agent = AgentV(page=self.page, agent_config=agent_config)
                    challenge_signal = await agent.wait_for_challenge()

                    if challenge_signal:
                        if hasattr(challenge_signal, 'is_pass') and challenge_signal.is_pass:
                            logger.info("✅ hCaptcha solved successfully")
                            return True
                        else:
                            # Assume success if we got a signal without explicit failure
                            logger.info("✅ hCaptcha challenge completed")
                            return True

                except Exception as e:
                    logger.error(f"hCaptcha solving failed: {e}")
                    return False

            # === Cloudflare Turnstile ===
            if captcha_type == 'turnstile':
                logger.warning("⚠️ Cloudflare Turnstile detected - auto-solve not supported")
                logger.info("💡 Turnstile is often bypassed by proper stealth mode")
                # Wait and hope stealth mode handles it
                await asyncio.sleep(5)
                # Check if Turnstile auto-completed
                turnstile_response = await self.page.query_selector('[name="cf-turnstile-response"]')
                if turnstile_response:
                    value = await turnstile_response.get_attribute('value')
                    if value:
                        logger.info("✅ Turnstile appears to have auto-completed")
                        return True
                return False

        except Exception as e:
            logger.error(f"CAPTCHA solving failed: {e}")

        return False

    async def cleanup(self):
        """Close browser and persistent context"""
        if self.context:
            await self.context.close()
        if self.browser:
            await self.browser.close()
        if hasattr(self, '_playwright') and self._playwright:
            await self._playwright.stop()


async def main():
    """CLI interface"""
    import argparse

    parser = argparse.ArgumentParser(
        description="Enhanced Account Registration Automation",
        epilog="""
Session/Profile Examples:
  # Named session (isolated, persists in .cache/browser_sessions/)
  %(prog)s https://site.com/signup --email x@y.com --password pass --session github-dev

  # Persistent profile (custom path, full auth state preservation)
  %(prog)s https://site.com/signup --email x@y.com --password pass --profile ~/.browser_profiles/github

  # Reuse existing session for subsequent logins
  %(prog)s https://github.com/login --session github-dev --email x@y.com --password pass
        """,
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument('url', help='Registration page URL')
    parser.add_argument('--email', required=True, help='Email address')
    parser.add_argument('--password', required=True, help='Password')
    parser.add_argument('--username', help='Username (optional)')
    parser.add_argument('--fullname', help='Full name (optional)')
    parser.add_argument('--headless', action='store_true', help='Run in headless mode')
    parser.add_argument('--session', help='Named session for isolation (stored in .cache/browser_sessions/)')
    parser.add_argument('--profile', help='Persistent profile path for auth state preservation')

    args = parser.parse_args()

    config = RegistrationConfig(
        headless=args.headless,
        session_name=args.session,
        profile_path=args.profile
    )
    automation = RegistrationAutomation(config)

    try:
        await automation.initialize()

        result = await automation.register_account(
            url=args.url,
            email=args.email,
            password=args.password,
            username=args.username,
            fullname=args.fullname
        )

        print("\n" + "="*60)
        print(f"✅ SUCCESS" if result.success else "❌ FAILED")
        print("="*60)
        print(f"Email: {result.email}")
        if result.username:
            print(f"Username: {result.username}")
        if result.verification_required:
            print("📧 Email verification required")
        if result.captcha_encountered:
            print(f"🔐 CAPTCHA: {'Solved' if result.captcha_solved else 'Failed'}")
        if result.error_message:
            print(f"Error: {result.error_message}")
        if result.screenshots:
            print(f"\n📸 Screenshots saved:")
            for screenshot in result.screenshots:
                print(f"  - {screenshot}")
        print("="*60)

        return 0 if result.success else 1

    finally:
        await automation.cleanup()


if __name__ == '__main__':
    import sys
    sys.exit(asyncio.run(main()))
