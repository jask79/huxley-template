#!/usr/bin/env python3
"""
Hybrid Browser Automation Wrapper
Combines Playwright (via MCP) and SeleniumBase for optimal automation

Strategy:
- Playwright: Fast, modern, good for cooperative sites
- SeleniumBase: Stealth mode, CAPTCHA solving, anti-detection for challenging sites
"""

import subprocess
import json
import os
import tempfile
from typing import Optional, Dict, List, Literal
from pathlib import Path
from dataclasses import dataclass
import logging

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)


@dataclass
class BrowserConfig:
    """Browser automation configuration"""
    mode: Literal["playwright", "seleniumbase"] = "playwright"
    headless: bool = True
    stealth: bool = False  # UC mode for SeleniumBase
    captcha_service: Optional[str] = None  # "2captcha", etc.
    captcha_api_key: Optional[str] = None
    user_agent: Optional[str] = None
    proxy: Optional[str] = None


class HybridBrowser:
    """Unified interface for Playwright and SeleniumBase"""

    # Sites that typically need stealth/anti-detection
    STEALTH_SITES = {
        'instagram.com',
        'facebook.com',
        'twitter.com',
        'x.com',
        'linkedin.com',
        'tiktok.com',
        'reddit.com',
        'amazon.com',
        'cloudflare.com'
    }

    def __init__(self, config: Optional[BrowserConfig] = None):
        self.config = config or BrowserConfig()
        self.catalyst_root = Path("{{CATALYST_ROOT}}")

    def should_use_stealth(self, url: str) -> bool:
        """Determine if URL needs stealth mode"""
        from urllib.parse import urlparse
        domain = urlparse(url).netloc

        # Remove www. prefix
        domain = domain.replace('www.', '')

        return any(stealth_domain in domain for stealth_domain in self.STEALTH_SITES)

    def auto_select_mode(self, url: str, force_mode: Optional[str] = None) -> str:
        """Auto-select best browser mode for URL"""
        if force_mode:
            return force_mode

        if self.should_use_stealth(url):
            logger.info(f"🔒 Stealth mode recommended for {url}")
            return "seleniumbase"
        else:
            logger.info(f"⚡ Playwright mode selected for {url}")
            return "playwright"

    def create_seleniumbase_script(self, task: str, url: str,
                                   script_path: Path) -> None:
        """
        Generate SeleniumBase Python script for automation task

        Tasks:
        - navigate: Just open URL
        - fill_form: Fill out form fields
        - solve_captcha: Handle CAPTCHA challenges
        - create_account: Full account creation workflow
        """

        if task == "navigate":
            script = f'''
from seleniumbase import SB

with SB(uc=True, headless=False) as sb:
    sb.open("{url}")
    sb.sleep(3)
    print("NAVIGATION_SUCCESS")
'''

        elif task == "solve_captcha":
            # SeleniumBase has built-in CAPTCHA solving
            script = f'''
from seleniumbase import SB

with SB(uc=True, headless=False) as sb:
    sb.open("{url}")

    # Wait for CAPTCHA iframe or elements
    if sb.is_element_visible("iframe[src*='recaptcha']"):
        print("CAPTCHA_DETECTED")
        # SeleniumBase can auto-solve with 2Captcha integration
        # Requires CAPTCHA_API_KEY environment variable
        sb.sleep(5)  # Manual solve for now
        print("CAPTCHA_WAITING")
    else:
        print("NO_CAPTCHA")
'''

        elif task == "create_account":
            script = f'''
from seleniumbase import SB
import sys
import json
import time
import random

# Load account details from stdin
account_data = json.loads(sys.stdin.read())

def human_pause(min_sec=0.5, max_sec=2.0):
    """Simulate human thinking/reading time"""
    time.sleep(random.uniform(min_sec, max_sec))

with SB(uc=True, headless=False) as sb:
    print("🚀 Opening signup page...")
    sb.open("{url}")

    # Wait for page load and Cloudflare
    sb.sleep(8)

    try:
        # Strategy: Try multiple selector patterns for each field
        # This works across different sites dynamically

        # === FULL NAME / NAME FIELD ===
        name_selectors = [
            '#fullname', '#full_name', '#full-name',
            'input[name="fullname"]', 'input[name="full_name"]',
            'input[name="name"]', 'input[placeholder*="name" i]',
            'input[placeholder*="Name" i]'
        ]

        for selector in name_selectors:
            try:
                if sb.is_element_visible(selector):
                    print(f"👤 Filling name field: {{selector}}")
                    sb.slow_click(selector)
                    human_pause(0.3, 0.6)
                    sb.type(selector, account_data.get('fullname', 'Huxley'), timeout=5)
                    human_pause(0.8, 1.5)
                    break
            except:
                continue

        # === EMAIL FIELD ===
        email_selectors = [
            '#email', '#Email', 'input[type="email"]',
            'input[name="email"]', 'input[placeholder*="email" i]',
            'input[placeholder*="Email" i]'
        ]

        for selector in email_selectors:
            try:
                if sb.is_element_visible(selector):
                    print(f"📧 Filling email: {{selector}}")
                    sb.slow_click(selector)
                    human_pause(0.3, 0.6)
                    sb.type(selector, account_data['email'], timeout=5)
                    human_pause(0.9, 1.8)
                    break
            except:
                continue

        # === PASSWORD FIELD ===
        password_selectors = [
            '#password', '#Password', 'input[type="password"]',
            'input[name="password"]', 'input[placeholder*="password" i]'
        ]

        for selector in password_selectors:
            try:
                if sb.is_element_visible(selector):
                    print(f"🔑 Filling password: {{selector}}")
                    sb.slow_click(selector)
                    human_pause(0.3, 0.6)
                    sb.type(selector, account_data['password'], timeout=5)
                    human_pause(0.7, 1.3)
                    break
            except:
                continue

        # === USERNAME FIELD (if present) ===
        if account_data.get('username'):
            username_selectors = [
                '#username', 'input[name="username"]',
                'input[placeholder*="username" i]'
            ]

            for selector in username_selectors:
                try:
                    if sb.is_element_visible(selector):
                        print(f"👥 Filling username: {{selector}}")
                        sb.slow_click(selector)
                        human_pause(0.3, 0.6)
                        sb.type(selector, account_data['username'], timeout=5)
                        human_pause(0.7, 1.3)
                        break
                except:
                    continue

        # === TERMS/PRIVACY CHECKBOX ===
        checkbox_selectors = [
            '#accept-terms-and-privacy', 'input[type="checkbox"][name*="terms"]',
            'input[type="checkbox"][name*="accept"]', 'input[type="checkbox"][required]'
        ]

        for selector in checkbox_selectors:
            try:
                if sb.is_element_visible(selector):
                    print(f"☑️  Checking terms: {{selector}}")
                    sb.slow_click(selector)
                    human_pause(0.5, 1.0)
                    break
            except:
                continue

        # Handle CAPTCHA if present (UC mode usually bypasses)
        if sb.is_element_visible("iframe[src*='recaptcha']"):
            print("⚠️  CAPTCHA detected - waiting...")
            sb.sleep(15)  # UC mode should handle it

        # === SUBMIT BUTTON ===
        submit_selectors = [
            'button[type="submit"]',
            'input[type="submit"]',
            'button:contains("Sign up")',
            'button:contains("Register")',
            'button:contains("Create")'
        ]

        human_pause(0.8, 1.5)

        for selector in submit_selectors:
            try:
                if sb.is_element_visible(selector):
                    print(f"🚀 Submitting form: {{selector}}")
                    sb.slow_click(selector)
                    break
            except:
                continue

        # Wait for response
        sb.sleep(8)

        current_url = sb.get_current_url()
        print(f"📍 Result URL: {{current_url}}")

        if 'verification' in current_url or 'verify' in current_url:
            print("✅ SIGNUP_SUCCESS_EMAIL_VERIFICATION_REQUIRED")
        elif 'dashboard' in current_url or 'home' in current_url:
            print("✅ SIGNUP_SUCCESS_LOGGED_IN")
        else:
            print("⚠️  SIGNUP_COMPLETED_STATUS_UNCLEAR")

        # Keep browser open briefly
        sb.sleep(10)

    except Exception as e:
        print(f"❌ ERROR: {{e}}")
        sb.save_screenshot("signup_error.png")
        sys.exit(1)
'''

        else:
            raise ValueError(f"Unknown task: {task}")

        # Write script to file
        with open(script_path, 'w') as f:
            f.write(script)

    def run_seleniumbase(self, task: str, url: str,
                        data: Optional[Dict] = None) -> Dict:
        """
        Execute SeleniumBase automation task

        Returns:
            Dict with status, output, and any extracted data
        """

        # Create temporary script
        with tempfile.NamedTemporaryFile(
            mode='w', suffix='.py', delete=False
        ) as f:
            script_path = Path(f.name)

        try:
            # Generate script
            self.create_seleniumbase_script(task, url, script_path)

            # Run script
            cmd = ['python3', str(script_path)]

            # Pass data via stdin if provided
            input_data = json.dumps(data) if data else None

            result = subprocess.run(
                cmd,
                input=input_data,
                capture_output=True,
                text=True,
                timeout=120
            )

            return {
                'success': result.returncode == 0,
                'output': result.stdout,
                'error': result.stderr,
                'returncode': result.returncode
            }

        finally:
            # Cleanup
            if script_path.exists():
                script_path.unlink()

    def run_playwright_mcp(self, task: str, url: str,
                          data: Optional[Dict] = None) -> Dict:
        """
        Execute Playwright automation via MCP

        Note: This is a placeholder - actual implementation should use
        Claude Code's Playwright MCP tools directly
        """

        logger.info("🎭 Playwright MCP automation (use Claude Code's mcp__playwright tools)")

        return {
            'success': False,
            'message': 'Use Playwright MCP tools directly in Claude Code',
            'note': 'Call mcp__playwright__browser_navigate, mcp__playwright__browser_click, etc.'
        }

    def navigate(self, url: str, mode: Optional[str] = None) -> Dict:
        """Navigate to URL using appropriate browser"""
        mode = mode or self.auto_select_mode(url)

        if mode == "seleniumbase":
            return self.run_seleniumbase("navigate", url)
        else:
            return self.run_playwright_mcp("navigate", url)

    def create_account(self, url: str, account_data: Dict,
                      mode: Optional[str] = None) -> Dict:
        """
        Create account on service

        Args:
            url: Account creation page URL
            account_data: Dict with email, password, username, etc.
            mode: Force specific browser mode
        """
        mode = mode or self.auto_select_mode(url)

        logger.info(f"🔐 Creating account on {url} using {mode}")

        if mode == "seleniumbase":
            return self.run_seleniumbase("create_account", url, account_data)
        else:
            return self.run_playwright_mcp("create_account", url, account_data)

    def solve_captcha(self, url: str, mode: Optional[str] = None) -> Dict:
        """Handle CAPTCHA challenges"""
        # Always use SeleniumBase for CAPTCHA
        return self.run_seleniumbase("solve_captcha", url)


def get_recommended_mode(url: str) -> str:
    """Quick helper to get recommended browser mode"""
    browser = HybridBrowser()
    return browser.auto_select_mode(url)


def main():
    """CLI interface for hybrid browser automation"""
    import argparse

    parser = argparse.ArgumentParser(
        description="Hybrid Browser Automation (Playwright + SeleniumBase)"
    )

    parser.add_argument('task', choices=['navigate', 'create-account', 'solve-captcha', 'check-mode'])
    parser.add_argument('--url', required=False, help='Target URL')
    parser.add_argument('--mode', choices=['playwright', 'seleniumbase'], help='Force browser mode')
    parser.add_argument('--email', help='Email for account creation')
    parser.add_argument('--password', help='Password for account creation')
    parser.add_argument('--username', help='Username for account creation')

    args = parser.parse_args()

    browser = HybridBrowser()

    if args.task == 'check-mode':
        mode = browser.auto_select_mode(args.url)
        print(f"Recommended mode for {args.url}: {mode}")
        return 0

    elif args.task == 'navigate':
        result = browser.navigate(args.url, args.mode)
        print(json.dumps(result, indent=2))
        return 0 if result['success'] else 1

    elif args.task == 'create-account':
        account_data = {
            'email': args.email,
            'password': args.password,
            'username': args.username
        }
        result = browser.create_account(args.url, account_data, args.mode)
        print(json.dumps(result, indent=2))
        return 0 if result['success'] else 1

    elif args.task == 'solve-captcha':
        result = browser.solve_captcha(args.url, args.mode)
        print(json.dumps(result, indent=2))
        return 0 if result['success'] else 1

    return 1


if __name__ == '__main__':
    import sys
    sys.exit(main())
