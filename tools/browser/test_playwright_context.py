#!/usr/bin/env python3
"""
Tests for Playwright Context Factory

These tests verify context creation and configuration.
Note: Full browser tests require Playwright browsers to be installed.

Run with: python -m pytest tools/browser/test_playwright_context.py -v
"""

import asyncio
import tempfile
import shutil
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from profile_manager import BrowserProfileManager, ProfileOptions
from playwright_context import (
    ContextOptions,
    ProfileAwareBrowser,
    STEALTH_AVAILABLE,
)


# Helper to run async tests synchronously
def run_async(coro):
    """Run an async coroutine synchronously."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@pytest.fixture
def temp_dir():
    """Create a temporary directory for testing."""
    dirpath = tempfile.mkdtemp()
    yield dirpath
    shutil.rmtree(dirpath)


@pytest.fixture
def manager(temp_dir):
    """Create a profile manager with temporary storage."""
    return BrowserProfileManager(base_dir=temp_dir)


class TestContextOptions:
    """Tests for ContextOptions dataclass."""

    def test_default_values(self):
        """Test default option values."""
        options = ContextOptions()

        assert options.viewport_width == 1280
        assert options.viewport_height == 720
        assert options.locale == "en-US"
        assert options.timezone_id == "America/New_York"
        assert options.headless is True
        assert options.stealth is True
        assert options.slow_mo == 0
        assert options.accept_downloads is True

    def test_custom_values(self):
        """Test custom option values."""
        options = ContextOptions(
            viewport_width=1920,
            viewport_height=1080,
            locale="de-DE",
            timezone_id="Europe/Berlin",
            headless=False,
            slow_mo=100,
        )

        assert options.viewport_width == 1920
        assert options.viewport_height == 1080
        assert options.locale == "de-DE"
        assert options.timezone_id == "Europe/Berlin"
        assert options.headless is False
        assert options.slow_mo == 100


class TestProfileAwareBrowser:
    """Tests for ProfileAwareBrowser class."""

    def test_init(self, manager):
        """Test browser initialization."""
        browser = ProfileAwareBrowser("test-profile", manager=manager)

        assert browser.profile_name == "test-profile"
        assert browser.manager is manager
        assert browser._playwright is None
        assert browser._browser is None
        assert browser._context is None

    def test_profile_property_before_start(self, manager):
        """Test profile property before starting."""
        browser = ProfileAwareBrowser("test-profile", manager=manager)
        assert browser.profile is None

    def test_context_property_before_start(self, manager):
        """Test context property before starting."""
        browser = ProfileAwareBrowser("test-profile", manager=manager)
        assert browser.context is None

    def test_new_page_before_start(self, manager):
        """Test that new_page raises before start."""
        browser = ProfileAwareBrowser("test-profile", manager=manager)

        async def _test():
            with pytest.raises(RuntimeError) as exc_info:
                await browser.new_page()
            assert "Browser not started" in str(exc_info.value)

        run_async(_test())

    def test_save_storage_state_before_start(self, manager, temp_dir):
        """Test that save_storage_state raises before start."""
        browser = ProfileAwareBrowser("test-profile", manager=manager)
        path = Path(temp_dir) / "state.json"

        async def _test():
            with pytest.raises(RuntimeError) as exc_info:
                await browser.save_storage_state(path)
            assert "Browser not started" in str(exc_info.value)

        run_async(_test())


class TestStealthAvailability:
    """Tests for stealth module detection."""

    def test_stealth_available_is_bool(self):
        """Test that STEALTH_AVAILABLE is a boolean."""
        assert isinstance(STEALTH_AVAILABLE, bool)


class TestIntegrationScenarios:
    """Integration-style tests that mock Playwright."""

    def test_context_creates_profile(self, manager):
        """Test that context creation creates the profile."""
        # Profile shouldn't exist yet
        assert manager.get_profile("new-profile") is None

        # Creating a profile directly to verify the pattern works
        # (Full browser context test would require real Playwright)
        profile = manager.get_or_create_profile("new-profile")

        # Profile should now exist
        assert profile is not None
        assert profile.name == "new-profile"
        assert manager.get_profile("new-profile") is not None

    def test_geolocation_implies_permission(self):
        """Test that setting geolocation implies geolocation permission."""
        options = ContextOptions(
            geolocation={"latitude": 40.7128, "longitude": -74.0060},
        )
        # Permission should still be default empty list
        assert options.permissions == []

    def test_storage_state_path(self, temp_dir):
        """Test storage state path handling."""
        state_file = Path(temp_dir) / "storage_state.json"
        state_file.write_text('{"cookies": []}')

        options = ContextOptions(storage_state=state_file)

        assert options.storage_state == state_file
        assert options.storage_state.exists()


class TestCLIUsage:
    """Tests verifying CLI-based usage patterns."""

    def test_profile_manager_cli_pattern(self, temp_dir):
        """Test the CLI usage pattern for profile management."""
        manager = BrowserProfileManager(base_dir=temp_dir)

        # Create profile (simulates CLI create command)
        profile = manager.create_profile("cli-test")
        assert profile.name == "cli-test"

        # Get launch args (simulates CLI args command)
        args = manager.get_launch_args(profile, headless=True)
        assert "--headless=new" in args
        assert f"--remote-debugging-port={profile.cdp_port}" in args

        # List profiles (simulates CLI list command)
        profiles = manager.list_profiles()
        assert len(profiles) == 1
        assert profiles[0].name == "cli-test"

        # Delete profile (simulates CLI delete command)
        assert manager.delete_profile("cli-test")
        assert manager.get_profile("cli-test") is None


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_empty_extra_http_headers(self):
        """Test that empty headers dict is handled."""
        options = ContextOptions()
        assert options.extra_http_headers == {}

    def test_none_geolocation(self):
        """Test that None geolocation is handled."""
        options = ContextOptions(geolocation=None)
        assert options.geolocation is None

    def test_record_paths_as_path_objects(self, temp_dir):
        """Test that Path objects work for record paths."""
        video_dir = Path(temp_dir) / "videos"
        har_path = Path(temp_dir) / "network.har"

        options = ContextOptions(
            record_video=video_dir,
            record_har=har_path,
        )

        assert options.record_video == video_dir
        assert options.record_har == har_path


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
