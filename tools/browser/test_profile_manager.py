#!/usr/bin/env python3
"""
Tests for Browser Profile Manager

Run with: python -m pytest tools/browser/test_profile_manager.py -v
"""

import json
import shutil
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from profile_manager import (
    BrowserProfileManager,
    CDP_PORT_RANGE_END,
    CDP_PORT_RANGE_START,
    Profile,
    ProfileColor,
    ProfileOptions,
)


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


class TestProfileColor:
    """Tests for ProfileColor enum."""

    def test_from_string_hex(self):
        """Test parsing hex color strings."""
        assert ProfileColor.from_string("#FF4500") == ProfileColor.ORANGE_RED
        assert ProfileColor.from_string("#0066CC") == ProfileColor.BLUE
        assert ProfileColor.from_string("#00aa00") == ProfileColor.GREEN

    def test_from_string_name(self):
        """Test parsing color names."""
        assert ProfileColor.from_string("ORANGE_RED") == ProfileColor.ORANGE_RED
        assert ProfileColor.from_string("blue") == ProfileColor.BLUE
        assert ProfileColor.from_string("orange-red") == ProfileColor.ORANGE_RED

    def test_from_string_invalid(self):
        """Test fallback for invalid colors."""
        assert ProfileColor.from_string("invalid") == ProfileColor.ORANGE_RED
        assert ProfileColor.from_string("#ZZZZZZ") == ProfileColor.ORANGE_RED

    def test_allocate_unused(self):
        """Test color allocation."""
        # First color should be ORANGE_RED
        assert ProfileColor.allocate_unused(set()) == ProfileColor.ORANGE_RED

        # With ORANGE_RED used, should get BLUE
        used = {ProfileColor.ORANGE_RED.value}
        assert ProfileColor.allocate_unused(used) == ProfileColor.BLUE

    def test_allocate_unused_cycles(self):
        """Test color allocation cycles when all used."""
        # Use all colors
        used = {c.value.upper() for c in ProfileColor}
        # Should cycle back to first
        result = ProfileColor.allocate_unused(used)
        assert result in ProfileColor


class TestBrowserProfileManager:
    """Tests for BrowserProfileManager."""

    def test_init_creates_base_dir(self, temp_dir):
        """Test that init creates the base directory."""
        subdir = Path(temp_dir) / "nested" / "browser"
        manager = BrowserProfileManager(base_dir=str(subdir))
        assert subdir.exists()

    def test_is_valid_name(self):
        """Test profile name validation."""
        assert BrowserProfileManager.is_valid_name("test")
        assert BrowserProfileManager.is_valid_name("my-profile")
        assert BrowserProfileManager.is_valid_name("profile123")
        assert BrowserProfileManager.is_valid_name("a")

        # Invalid names
        assert not BrowserProfileManager.is_valid_name("")
        assert not BrowserProfileManager.is_valid_name("-invalid")
        assert not BrowserProfileManager.is_valid_name("Invalid")  # Uppercase
        assert not BrowserProfileManager.is_valid_name("has space")
        assert not BrowserProfileManager.is_valid_name("has.dot")
        assert not BrowserProfileManager.is_valid_name("a" * 65)  # Too long

    def test_create_profile(self, manager):
        """Test creating a new profile."""
        profile = manager.create_profile("test-profile")

        assert profile.name == "test-profile"
        assert profile.path.exists()
        assert profile.user_data_dir.exists()
        assert CDP_PORT_RANGE_START <= profile.cdp_port <= CDP_PORT_RANGE_END
        assert profile.color in ProfileColor
        assert profile.created_at is not None

    def test_create_profile_with_options(self, manager):
        """Test creating a profile with custom options."""
        options = ProfileOptions(
            color=ProfileColor.BLUE,
            cdp_port=18850,
        )
        profile = manager.create_profile("custom-profile", options)

        assert profile.color == ProfileColor.BLUE
        assert profile.cdp_port == 18850

    def test_create_profile_invalid_name(self, manager):
        """Test creating a profile with invalid name."""
        with pytest.raises(ValueError) as exc_info:
            manager.create_profile("Invalid-Name")
        assert "Invalid profile name" in str(exc_info.value)

    def test_create_profile_duplicate(self, manager):
        """Test creating a duplicate profile."""
        manager.create_profile("test")
        with pytest.raises(ValueError) as exc_info:
            manager.create_profile("test")
        assert "already exists" in str(exc_info.value)

    def test_get_profile(self, manager):
        """Test getting an existing profile."""
        created = manager.create_profile("test")
        retrieved = manager.get_profile("test")

        assert retrieved is not None
        assert retrieved.name == created.name
        assert retrieved.cdp_port == created.cdp_port

    def test_get_profile_not_found(self, manager):
        """Test getting a non-existent profile."""
        assert manager.get_profile("nonexistent") is None

    def test_get_or_create_profile(self, manager):
        """Test get_or_create functionality."""
        # First call creates
        profile1 = manager.get_or_create_profile("test")
        # Second call retrieves
        profile2 = manager.get_or_create_profile("test")

        assert profile1.name == profile2.name
        assert profile1.cdp_port == profile2.cdp_port

    def test_list_profiles(self, manager):
        """Test listing profiles."""
        assert len(manager.list_profiles()) == 0

        manager.create_profile("profile1")
        manager.create_profile("profile2")
        manager.create_profile("profile3")

        profiles = manager.list_profiles()
        assert len(profiles) == 3
        names = {p.name for p in profiles}
        assert names == {"profile1", "profile2", "profile3"}

    def test_delete_profile(self, manager):
        """Test deleting a profile."""
        profile = manager.create_profile("to-delete")
        profile_path = profile.path

        assert profile_path.exists()
        assert manager.delete_profile("to-delete")
        assert not profile_path.exists()
        assert manager.get_profile("to-delete") is None

    def test_delete_profile_not_found(self, manager):
        """Test deleting a non-existent profile."""
        assert not manager.delete_profile("nonexistent")

    def test_port_allocation(self, manager):
        """Test that ports are allocated sequentially."""
        p1 = manager.create_profile("profile1")
        p2 = manager.create_profile("profile2")
        p3 = manager.create_profile("profile3")

        # Ports should be different
        ports = {p1.cdp_port, p2.cdp_port, p3.cdp_port}
        assert len(ports) == 3

        # All should be in range
        for port in ports:
            assert CDP_PORT_RANGE_START <= port <= CDP_PORT_RANGE_END

    def test_port_reuse_after_delete(self, manager):
        """Test that deleted profile's port can be reused."""
        p1 = manager.create_profile("profile1")
        freed_port = p1.cdp_port
        manager.delete_profile("profile1")

        p2 = manager.create_profile("profile2")
        assert p2.cdp_port == freed_port

    def test_persistence(self, temp_dir):
        """Test that profiles persist across manager instances."""
        # Create profile with first manager
        manager1 = BrowserProfileManager(base_dir=temp_dir)
        profile = manager1.create_profile("persistent")
        original_port = profile.cdp_port
        original_color = profile.color

        # Load with new manager
        manager2 = BrowserProfileManager(base_dir=temp_dir)
        loaded = manager2.get_profile("persistent")

        assert loaded is not None
        assert loaded.cdp_port == original_port
        assert loaded.color == original_color

    def test_get_launch_args(self, manager):
        """Test Chrome launch arguments generation."""
        profile = manager.create_profile("test")
        args = manager.get_launch_args(profile)

        assert f"--remote-debugging-port={profile.cdp_port}" in args
        assert f"--user-data-dir={profile.user_data_dir}" in args
        assert "--no-first-run" in args
        assert "--disable-sync" in args
        assert "about:blank" in args  # Should be last

    def test_get_launch_args_headless(self, manager):
        """Test headless mode arguments."""
        profile = manager.create_profile("test")
        args = manager.get_launch_args(profile, headless=True)

        assert "--headless=new" in args
        assert "--disable-gpu" in args

    def test_get_launch_args_no_sandbox(self, manager):
        """Test no-sandbox arguments."""
        profile = manager.create_profile("test")
        args = manager.get_launch_args(profile, no_sandbox=True)

        assert "--no-sandbox" in args
        assert "--disable-setuid-sandbox" in args


class TestProfileDecoration:
    """Tests for profile decoration functionality."""

    def test_decorate_profile(self, manager):
        """Test profile decoration creates correct files."""
        profile = manager.create_profile("decorated")

        # Create initial preference files (as Chrome would)
        profile.user_data_dir.mkdir(parents=True, exist_ok=True)
        (profile.user_data_dir / "Default").mkdir(exist_ok=True)
        profile.preferences_path.write_text("{}")
        profile.local_state_path.write_text("{}")

        manager.decorate_profile(profile)

        # Check Local State
        local_state = json.loads(profile.local_state_path.read_text())
        assert local_state["profile"]["info_cache"]["Default"]["name"] == "decorated"

        # Check Preferences
        prefs = json.loads(profile.preferences_path.read_text())
        assert prefs["profile"]["name"] == "decorated"

        # Check marker file
        marker = profile.user_data_dir / ".catalyst-profile-decorated"
        assert marker.exists()
        assert marker.read_text().strip() == "decorated"

    def test_is_profile_decorated(self, manager):
        """Test decoration detection."""
        profile = manager.create_profile("test")

        # Not decorated initially
        assert not manager.is_profile_decorated(profile)

        # Create marker
        marker = profile.user_data_dir / ".catalyst-profile-decorated"
        marker.write_text("test\n")

        assert manager.is_profile_decorated(profile)

    def test_ensure_clean_exit(self, manager):
        """Test clean exit preference setting."""
        profile = manager.create_profile("test")
        (profile.user_data_dir / "Default").mkdir(parents=True, exist_ok=True)

        # Simulate crash state
        profile.preferences_path.write_text(json.dumps({
            "exit_type": "Crashed",
            "exited_cleanly": False,
        }))

        manager.ensure_clean_exit(profile)

        prefs = json.loads(profile.preferences_path.read_text())
        assert prefs["exit_type"] == "Normal"
        assert prefs["exited_cleanly"] is True


class TestProfile:
    """Tests for Profile dataclass."""

    def test_cdp_url(self, manager):
        """Test CDP URL generation."""
        profile = manager.create_profile("test")
        assert profile.cdp_url == f"http://127.0.0.1:{profile.cdp_port}"

    def test_serialization(self, manager):
        """Test profile serialization round-trip."""
        original = manager.create_profile("test")
        data = original.to_dict()
        restored = Profile.from_dict(data)

        assert restored.name == original.name
        assert restored.cdp_port == original.cdp_port
        assert restored.color == original.color
        assert restored.path == original.path


class TestHelperMethods:
    """Tests for internal helper methods."""

    def test_set_deep(self):
        """Test deep dictionary setting."""
        obj = {}
        BrowserProfileManager._set_deep(obj, ["a", "b", "c"], "value")
        assert obj == {"a": {"b": {"c": "value"}}}

    def test_set_deep_existing(self):
        """Test deep setting with existing structure."""
        obj = {"a": {"existing": True}}
        BrowserProfileManager._set_deep(obj, ["a", "b", "c"], "value")
        assert obj == {"a": {"existing": True, "b": {"c": "value"}}}

    def test_parse_hex_to_signed_argb(self):
        """Test hex color to Chrome's signed ARGB conversion."""
        # Test known values
        result = BrowserProfileManager._parse_hex_to_signed_argb("#FF4500")
        assert result is not None
        assert isinstance(result, int)

        # Invalid input
        assert BrowserProfileManager._parse_hex_to_signed_argb("invalid") is None
        assert BrowserProfileManager._parse_hex_to_signed_argb("#GGG") is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
