#!/usr/bin/env python3
"""
Playwright Context Factory for Huxley Browser Profiles

Provides profile-aware Playwright browser context creation with:
- Automatic profile isolation (cookies, storage, state per profile)
- Stealth mode integration (playwright-stealth)
- Configurable viewport, locale, timezone
- Context reuse support for multi-page workflows
"""

import asyncio
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, AsyncGenerator, Dict, List, Optional, Union

from playwright.async_api import (
    Browser,
    BrowserContext,
    BrowserType,
    Page,
    Playwright,
    async_playwright,
)

# Handle both package and direct imports
try:
    from .profile_manager import BrowserProfileManager, Profile, ProfileOptions
except ImportError:
    from profile_manager import BrowserProfileManager, Profile, ProfileOptions

# Try to import stealth module
try:
    from playwright_stealth import stealth_async
    STEALTH_AVAILABLE = True
except ImportError:
    STEALTH_AVAILABLE = False


@dataclass
class ContextOptions:
    """Options for creating a browser context."""
    # Viewport settings
    viewport_width: int = 1280
    viewport_height: int = 720

    # Locale and timezone
    locale: str = "en-US"
    timezone_id: str = "America/New_York"

    # Geolocation (New York by default)
    geolocation: Optional[Dict[str, float]] = None

    # User agent override
    user_agent: Optional[str] = None

    # Permissions to grant
    permissions: List[str] = field(default_factory=list)

    # Enable stealth mode (if available)
    stealth: bool = True

    # Headless mode
    headless: bool = True

    # Slow motion delay (ms between actions)
    slow_mo: int = 0

    # Record video
    record_video: Optional[Path] = None

    # Record HAR
    record_har: Optional[Path] = None

    # Accept downloads
    accept_downloads: bool = True

    # Extra HTTP headers
    extra_http_headers: Dict[str, str] = field(default_factory=dict)

    # Storage state file to load
    storage_state: Optional[Path] = None

    # Browser args
    no_sandbox: bool = False


async def _apply_stealth(page: Page) -> None:
    """Apply stealth mode to a page if available."""
    if STEALTH_AVAILABLE:
        await stealth_async(page)


@asynccontextmanager
async def create_browser_context(
    profile_name: str,
    options: Optional[ContextOptions] = None,
    manager: Optional[BrowserProfileManager] = None,
) -> AsyncGenerator[BrowserContext, None]:
    """
    Create a Playwright browser context with profile isolation.

    This launches a new Chrome instance for the given profile with
    complete isolation (cookies, localStorage, sessionStorage, etc.).

    Args:
        profile_name: Name of the browser profile to use.
        options: Context configuration options.
        manager: Profile manager instance (created if not provided).

    Yields:
        BrowserContext: Configured Playwright browser context.

    Example:
        async with create_browser_context("my-profile") as context:
            page = await context.new_page()
            await page.goto("https://example.com")
    """
    options = options or ContextOptions()
    manager = manager or BrowserProfileManager()

    # Get or create the profile
    profile = manager.get_or_create_profile(
        profile_name,
        ProfileOptions(headless=options.headless, no_sandbox=options.no_sandbox)
    )

    # Ensure clean exit and decoration
    manager.ensure_clean_exit(profile)
    if not manager.is_profile_decorated(profile):
        manager.decorate_profile(profile)

    # Get launch args
    launch_args = manager.get_launch_args(
        profile,
        headless=options.headless,
        no_sandbox=options.no_sandbox,
    )

    async with async_playwright() as p:
        # Launch browser with profile's user-data-dir
        browser = await p.chromium.launch(
            headless=options.headless,
            args=launch_args[:-1],  # Exclude about:blank, we'll navigate manually
            slow_mo=options.slow_mo,
        )

        # Build context options
        context_opts: Dict[str, Any] = {
            "viewport": {
                "width": options.viewport_width,
                "height": options.viewport_height,
            },
            "locale": options.locale,
            "timezone_id": options.timezone_id,
            "accept_downloads": options.accept_downloads,
        }

        if options.user_agent:
            context_opts["user_agent"] = options.user_agent

        if options.geolocation:
            context_opts["geolocation"] = options.geolocation
            context_opts["permissions"] = options.permissions or ["geolocation"]
        elif options.permissions:
            context_opts["permissions"] = options.permissions

        if options.extra_http_headers:
            context_opts["extra_http_headers"] = options.extra_http_headers

        if options.storage_state and options.storage_state.exists():
            context_opts["storage_state"] = str(options.storage_state)

        if options.record_video:
            options.record_video.mkdir(parents=True, exist_ok=True)
            context_opts["record_video_dir"] = str(options.record_video)

        if options.record_har:
            context_opts["record_har_path"] = str(options.record_har)

        # Create context
        context = await browser.new_context(**context_opts)

        try:
            yield context
        finally:
            # Save storage state if configured
            # (Could add option for auto-save here)

            # Close context and browser
            await context.close()
            await browser.close()


@asynccontextmanager
async def create_persistent_context(
    profile_name: str,
    options: Optional[ContextOptions] = None,
    manager: Optional[BrowserProfileManager] = None,
) -> AsyncGenerator[BrowserContext, None]:
    """
    Create a persistent browser context using Playwright's built-in support.

    Unlike create_browser_context(), this uses Playwright's
    launch_persistent_context() which keeps the browser profile
    state between sessions automatically.

    Args:
        profile_name: Name of the browser profile to use.
        options: Context configuration options.
        manager: Profile manager instance (created if not provided).

    Yields:
        BrowserContext: Persistent Playwright browser context.

    Example:
        async with create_persistent_context("my-profile") as context:
            page = await context.new_page()
            # This session's cookies will persist to next use
    """
    options = options or ContextOptions()
    manager = manager or BrowserProfileManager()

    # Get or create the profile
    profile = manager.get_or_create_profile(
        profile_name,
        ProfileOptions(headless=options.headless, no_sandbox=options.no_sandbox)
    )

    # Ensure clean exit and decoration
    manager.ensure_clean_exit(profile)
    if not manager.is_profile_decorated(profile):
        manager.decorate_profile(profile)

    # Build launch args (without user-data-dir, Playwright handles that)
    extra_args = [
        f"--remote-debugging-port={profile.cdp_port}",
        "--no-first-run",
        "--no-default-browser-check",
        "--disable-sync",
        "--disable-background-networking",
        "--disable-component-update",
        "--disable-features=Translate,MediaRouter",
        "--disable-session-crashed-bubble",
        "--hide-crash-restore-bubble",
        "--password-store=basic",
    ]

    if options.no_sandbox:
        extra_args.extend(["--no-sandbox", "--disable-setuid-sandbox"])

    async with async_playwright() as p:
        # Build context options
        context_opts: Dict[str, Any] = {
            "viewport": {
                "width": options.viewport_width,
                "height": options.viewport_height,
            },
            "locale": options.locale,
            "timezone_id": options.timezone_id,
            "accept_downloads": options.accept_downloads,
            "headless": options.headless,
            "slow_mo": options.slow_mo,
            "args": extra_args,
        }

        if options.user_agent:
            context_opts["user_agent"] = options.user_agent

        if options.geolocation:
            context_opts["geolocation"] = options.geolocation
            context_opts["permissions"] = options.permissions or ["geolocation"]
        elif options.permissions:
            context_opts["permissions"] = options.permissions

        if options.extra_http_headers:
            context_opts["extra_http_headers"] = options.extra_http_headers

        if options.record_video:
            options.record_video.mkdir(parents=True, exist_ok=True)
            context_opts["record_video_dir"] = str(options.record_video)

        if options.record_har:
            context_opts["record_har_path"] = str(options.record_har)

        # Launch persistent context
        context = await p.chromium.launch_persistent_context(
            user_data_dir=str(profile.user_data_dir),
            **context_opts,
        )

        try:
            yield context
        finally:
            await context.close()


async def create_stealth_page(context: BrowserContext) -> Page:
    """
    Create a new page with stealth mode applied.

    Args:
        context: Browser context to create page in.

    Returns:
        Page with stealth mode applied (if available).
    """
    page = await context.new_page()
    await _apply_stealth(page)
    return page


class ProfileAwareBrowser:
    """
    High-level browser interface with profile awareness.

    Provides a simpler API for common browser automation tasks
    with automatic profile management and stealth integration.

    Example:
        browser = ProfileAwareBrowser("my-profile")
        await browser.start()

        page = await browser.new_page()
        await page.goto("https://example.com")

        await browser.stop()
    """

    def __init__(
        self,
        profile_name: str,
        options: Optional[ContextOptions] = None,
        manager: Optional[BrowserProfileManager] = None,
    ):
        self.profile_name = profile_name
        self.options = options or ContextOptions()
        self.manager = manager or BrowserProfileManager()
        self._playwright: Optional[Playwright] = None
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None
        self._profile: Optional[Profile] = None

    @property
    def profile(self) -> Optional[Profile]:
        """Get the current profile."""
        return self._profile

    @property
    def context(self) -> Optional[BrowserContext]:
        """Get the current browser context."""
        return self._context

    async def start(self) -> None:
        """Start the browser with profile isolation."""
        if self._playwright:
            return  # Already started

        # Get or create profile
        self._profile = self.manager.get_or_create_profile(
            self.profile_name,
            ProfileOptions(
                headless=self.options.headless,
                no_sandbox=self.options.no_sandbox,
            )
        )

        # Ensure clean state
        self.manager.ensure_clean_exit(self._profile)
        if not self.manager.is_profile_decorated(self._profile):
            self.manager.decorate_profile(self._profile)

        # Get launch args
        launch_args = self.manager.get_launch_args(
            self._profile,
            headless=self.options.headless,
            no_sandbox=self.options.no_sandbox,
        )

        # Start Playwright
        self._playwright = await async_playwright().start()

        # Launch browser
        self._browser = await self._playwright.chromium.launch(
            headless=self.options.headless,
            args=launch_args[:-1],  # Exclude about:blank
            slow_mo=self.options.slow_mo,
        )

        # Create context
        context_opts: Dict[str, Any] = {
            "viewport": {
                "width": self.options.viewport_width,
                "height": self.options.viewport_height,
            },
            "locale": self.options.locale,
            "timezone_id": self.options.timezone_id,
            "accept_downloads": self.options.accept_downloads,
        }

        if self.options.user_agent:
            context_opts["user_agent"] = self.options.user_agent

        if self.options.geolocation:
            context_opts["geolocation"] = self.options.geolocation
            context_opts["permissions"] = self.options.permissions or ["geolocation"]

        if self.options.extra_http_headers:
            context_opts["extra_http_headers"] = self.options.extra_http_headers

        if self.options.storage_state and self.options.storage_state.exists():
            context_opts["storage_state"] = str(self.options.storage_state)

        self._context = await self._browser.new_context(**context_opts)

    async def stop(self) -> None:
        """Stop the browser and clean up."""
        if self._context:
            await self._context.close()
            self._context = None

        if self._browser:
            await self._browser.close()
            self._browser = None

        if self._playwright:
            await self._playwright.stop()
            self._playwright = None

    async def new_page(self, apply_stealth: bool = True) -> Page:
        """
        Create a new page with optional stealth mode.

        Args:
            apply_stealth: Apply stealth mode to the page.

        Returns:
            New Page instance.
        """
        if not self._context:
            raise RuntimeError("Browser not started. Call start() first.")

        page = await self._context.new_page()
        if apply_stealth:
            await _apply_stealth(page)
        return page

    async def save_storage_state(self, path: Path) -> None:
        """
        Save the current storage state (cookies, localStorage, etc.).

        Args:
            path: Path to save the storage state JSON.
        """
        if not self._context:
            raise RuntimeError("Browser not started.")

        path.parent.mkdir(parents=True, exist_ok=True)
        await self._context.storage_state(path=str(path))

    async def __aenter__(self) -> "ProfileAwareBrowser":
        await self.start()
        return self

    async def __aexit__(self, *args) -> None:
        await self.stop()


# Convenience function for quick one-off automation
async def quick_automation(
    profile_name: str,
    url: str,
    callback,
    options: Optional[ContextOptions] = None,
) -> Any:
    """
    Quick one-off automation with profile isolation.

    Args:
        profile_name: Profile to use.
        url: URL to navigate to.
        callback: Async function that receives the page and performs automation.
        options: Context options.

    Returns:
        Result of the callback function.

    Example:
        async def my_automation(page):
            await page.fill("#email", "test@example.com")
            return await page.title()

        result = await quick_automation("test-profile", "https://example.com", my_automation)
    """
    options = options or ContextOptions()

    async with create_browser_context(profile_name, options) as context:
        page = await create_stealth_page(context)
        await page.goto(url)
        return await callback(page)
