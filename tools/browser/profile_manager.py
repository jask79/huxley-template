#!/usr/bin/env python3
"""
Browser Profile Manager for Huxley

Implements browser profile isolation based on example-agent's superior pattern.
Each profile gets a completely isolated browser environment with:
- Dedicated user-data-dir
- Profile decoration (name, color for visual distinction)
- Clean exit handling (avoids crash dialogs)
- Port isolation (18800-18899 range, avoiding reserved ports)

Reference: {{CATALYST_ROOT}}/tools/example-agent-audit/src/browser/chrome.ts
"""

import json
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

# Default CDP port range (avoiding reserved ports like 9222, 18789-18799)
CDP_PORT_RANGE_START = 18800
CDP_PORT_RANGE_END = 18899

# Profile name validation regex (lowercase alphanumeric with hyphens)
PROFILE_NAME_REGEX = re.compile(r"^[a-z0-9][a-z0-9-]*$")


class ProfileColor(Enum):
    """Available profile colors for visual distinction in Chrome UI."""
    ORANGE_RED = "#FF4500"  # Huxley default
    BLUE = "#0066CC"
    GREEN = "#00AA00"
    PURPLE = "#9933FF"
    PINK = "#FF6699"
    CYAN = "#00CCCC"
    ORANGE = "#FF9900"
    INDIGO = "#6666FF"
    MAGENTA = "#CC3366"
    TEAL = "#339966"

    @classmethod
    def from_string(cls, color_str: str) -> "ProfileColor":
        """Parse a color string (hex or name) to ProfileColor."""
        normalized = color_str.strip().upper()
        if normalized.startswith("#"):
            for c in cls:
                if c.value.upper() == normalized:
                    return c
        else:
            # Try name lookup
            name = normalized.replace("-", "_").replace(" ", "_")
            try:
                return cls[name]
            except KeyError:
                pass
        return cls.ORANGE_RED  # Default fallback

    @classmethod
    def allocate_unused(cls, used_colors: Set[str]) -> "ProfileColor":
        """Allocate the first unused color from the palette."""
        used_upper = {c.upper() for c in used_colors}
        for color in cls:
            if color.value.upper() not in used_upper:
                return color
        # All colors used, cycle based on count
        colors = list(cls)
        return colors[len(used_colors) % len(colors)]


@dataclass
class ProfileOptions:
    """Options for creating a browser profile."""
    color: Optional[ProfileColor] = None
    cdp_port: Optional[int] = None
    headless: bool = False
    no_sandbox: bool = False
    # Extra Chrome launch args
    extra_args: List[str] = field(default_factory=list)


@dataclass
class Profile:
    """Represents a browser profile with isolated state."""
    name: str
    path: Path
    cdp_port: int
    color: ProfileColor
    decorated: bool = False
    created_at: Optional[str] = None

    @property
    def user_data_dir(self) -> Path:
        """Path to Chrome's user-data directory for this profile."""
        return self.path / "user-data"

    @property
    def local_state_path(self) -> Path:
        """Path to Chrome's Local State file."""
        return self.user_data_dir / "Local State"

    @property
    def preferences_path(self) -> Path:
        """Path to Default profile's Preferences file."""
        return self.user_data_dir / "Default" / "Preferences"

    @property
    def cdp_url(self) -> str:
        """CDP URL for this profile."""
        return f"http://127.0.0.1:{self.cdp_port}"

    def to_dict(self) -> Dict:
        """Serialize profile to dictionary."""
        return {
            "name": self.name,
            "path": str(self.path),
            "cdp_port": self.cdp_port,
            "color": self.color.value,
            "decorated": self.decorated,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "Profile":
        """Deserialize profile from dictionary."""
        return cls(
            name=data["name"],
            path=Path(data["path"]),
            cdp_port=data["cdp_port"],
            color=ProfileColor.from_string(data["color"]),
            decorated=data.get("decorated", False),
            created_at=data.get("created_at"),
        )


class BrowserProfileManager:
    """
    Manages isolated browser profiles for Huxley automation.

    Each profile gets:
    - Isolated user-data-dir at base_dir/<name>/user-data/
    - Dedicated CDP port from 18800-18899 range
    - Visual decoration (name, color) for easy identification
    - Clean exit handling to avoid crash dialogs
    """

    def __init__(self, base_dir: str = "~/.catalyst/browser"):
        """
        Initialize the profile manager.

        Args:
            base_dir: Base directory for storing browser profiles.
                      Defaults to ~/.catalyst/browser/
        """
        self.base_dir = Path(base_dir).expanduser()
        self.profiles_file = self.base_dir / "profiles.json"
        self._profiles: Dict[str, Profile] = {}
        self._ensure_base_dir()
        self._load_profiles()

    def _ensure_base_dir(self) -> None:
        """Ensure the base directory exists."""
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _load_profiles(self) -> None:
        """Load existing profiles from disk."""
        if self.profiles_file.exists():
            try:
                with open(self.profiles_file, "r") as f:
                    data = json.load(f)
                for profile_data in data.get("profiles", []):
                    profile = Profile.from_dict(profile_data)
                    # Verify profile directory still exists
                    if profile.path.exists():
                        self._profiles[profile.name] = profile
            except (json.JSONDecodeError, KeyError) as e:
                # Corrupted file, start fresh
                print(f"Warning: Could not load profiles.json: {e}")
                self._profiles = {}

    def _save_profiles(self) -> None:
        """Persist profiles to disk."""
        data = {
            "profiles": [p.to_dict() for p in self._profiles.values()]
        }
        with open(self.profiles_file, "w") as f:
            json.dump(data, f, indent=2)

    def _get_used_ports(self) -> Set[int]:
        """Get set of CDP ports currently in use."""
        return {p.cdp_port for p in self._profiles.values()}

    def _get_used_colors(self) -> Set[str]:
        """Get set of colors currently in use."""
        return {p.color.value.upper() for p in self._profiles.values()}

    def _allocate_port(self, preferred: Optional[int] = None) -> int:
        """
        Allocate an available CDP port.

        Args:
            preferred: Preferred port if available.

        Returns:
            Allocated port number.

        Raises:
            RuntimeError: If no ports available.
        """
        used = self._get_used_ports()

        # Try preferred port first
        if preferred is not None:
            if CDP_PORT_RANGE_START <= preferred <= CDP_PORT_RANGE_END:
                if preferred not in used:
                    return preferred

        # Find first available port in range
        for port in range(CDP_PORT_RANGE_START, CDP_PORT_RANGE_END + 1):
            if port not in used:
                return port

        raise RuntimeError(
            f"No available CDP ports in range {CDP_PORT_RANGE_START}-{CDP_PORT_RANGE_END}. "
            f"Delete unused profiles to free ports."
        )

    @staticmethod
    def is_valid_name(name: str) -> bool:
        """Check if a profile name is valid."""
        if not name or len(name) > 64:
            return False
        return bool(PROFILE_NAME_REGEX.match(name))

    def create_profile(
        self,
        name: str,
        options: Optional[ProfileOptions] = None
    ) -> Profile:
        """
        Create a new isolated browser profile.

        Args:
            name: Profile name (lowercase alphanumeric with hyphens).
            options: Optional profile configuration.

        Returns:
            The created Profile object.

        Raises:
            ValueError: If name is invalid or already exists.
            RuntimeError: If no ports available.
        """
        if not self.is_valid_name(name):
            raise ValueError(
                f"Invalid profile name '{name}'. "
                "Use lowercase letters, numbers, and hyphens. "
                "Must start with letter or number."
            )

        if name in self._profiles:
            raise ValueError(f"Profile '{name}' already exists.")

        options = options or ProfileOptions()

        # Allocate port and color
        cdp_port = self._allocate_port(options.cdp_port)
        color = options.color or ProfileColor.allocate_unused(self._get_used_colors())

        # Create profile directory
        profile_path = self.base_dir / name
        profile_path.mkdir(parents=True, exist_ok=True)

        # Create user-data directory
        user_data_dir = profile_path / "user-data"
        user_data_dir.mkdir(parents=True, exist_ok=True)

        # Create profile object
        from datetime import datetime
        profile = Profile(
            name=name,
            path=profile_path,
            cdp_port=cdp_port,
            color=color,
            decorated=False,
            created_at=datetime.now().isoformat(),
        )

        # Save profile
        self._profiles[name] = profile
        self._save_profiles()

        return profile

    def get_profile(self, name: str) -> Optional[Profile]:
        """
        Get an existing profile by name.

        Args:
            name: Profile name.

        Returns:
            Profile object if found, None otherwise.
        """
        return self._profiles.get(name)

    def get_or_create_profile(
        self,
        name: str,
        options: Optional[ProfileOptions] = None
    ) -> Profile:
        """
        Get existing profile or create new one.

        Args:
            name: Profile name.
            options: Options for creating new profile.

        Returns:
            Profile object.
        """
        if name in self._profiles:
            return self._profiles[name]
        return self.create_profile(name, options)

    def list_profiles(self) -> List[Profile]:
        """
        List all existing profiles.

        Returns:
            List of Profile objects.
        """
        return list(self._profiles.values())

    def delete_profile(self, name: str) -> bool:
        """
        Delete a profile and its data.

        Args:
            name: Profile name.

        Returns:
            True if deleted, False if not found.
        """
        if name not in self._profiles:
            return False

        profile = self._profiles[name]

        # Remove directory
        if profile.path.exists():
            shutil.rmtree(profile.path)

        # Remove from registry
        del self._profiles[name]
        self._save_profiles()

        return True

    def decorate_profile(self, profile: Profile) -> None:
        """
        Apply visual decoration to a profile (name, color in Chrome UI).

        This modifies Chrome's Local State and Preferences files to:
        - Set profile name
        - Set profile color
        - Apply theme color

        Args:
            profile: Profile to decorate.
        """
        user_data_dir = profile.user_data_dir
        local_state_path = profile.local_state_path
        preferences_path = profile.preferences_path

        color_hex = profile.color.value.upper()
        color_int = self._parse_hex_to_signed_argb(color_hex)

        # Update Local State
        local_state = self._safe_read_json(local_state_path) or {}
        self._set_deep(local_state, ["profile", "info_cache", "Default", "name"], profile.name)
        self._set_deep(local_state, ["profile", "info_cache", "Default", "shortcut_name"], profile.name)
        self._set_deep(local_state, ["profile", "info_cache", "Default", "user_name"], profile.name)
        self._set_deep(local_state, ["profile", "info_cache", "Default", "profile_color"], color_hex)
        self._set_deep(local_state, ["profile", "info_cache", "Default", "user_color"], color_hex)

        if color_int is not None:
            self._set_deep(local_state, ["profile", "info_cache", "Default", "profile_color_seed"], color_int)
            self._set_deep(local_state, ["profile", "info_cache", "Default", "profile_highlight_color"], color_int)
            self._set_deep(local_state, ["profile", "info_cache", "Default", "default_avatar_fill_color"], color_int)
            self._set_deep(local_state, ["profile", "info_cache", "Default", "default_avatar_stroke_color"], color_int)

        self._safe_write_json(local_state_path, local_state)

        # Update Preferences
        prefs = self._safe_read_json(preferences_path) or {}
        self._set_deep(prefs, ["profile", "name"], profile.name)
        self._set_deep(prefs, ["profile", "profile_color"], color_hex)
        self._set_deep(prefs, ["profile", "user_color"], color_hex)

        if color_int is not None:
            self._set_deep(prefs, ["autogenerated", "theme", "color"], color_int)
            self._set_deep(prefs, ["browser", "theme", "user_color2"], color_int)

        self._safe_write_json(preferences_path, prefs)

        # Mark as decorated
        profile.decorated = True
        self._profiles[profile.name] = profile
        self._save_profiles()

        # Write decoration marker
        marker_path = user_data_dir / ".catalyst-profile-decorated"
        marker_path.write_text(f"{profile.name}\n")

    def ensure_clean_exit(self, profile: Profile) -> None:
        """
        Set exit_type to 'Normal' to avoid crash dialogs on next launch.

        This is critical for automation - Chrome shows a restore dialog
        if it detects an unclean exit. Setting these preferences prevents that.

        Args:
            profile: Profile to fix.
        """
        preferences_path = profile.preferences_path
        prefs = self._safe_read_json(preferences_path) or {}
        self._set_deep(prefs, ["exit_type"], "Normal")
        self._set_deep(prefs, ["exited_cleanly"], True)
        self._safe_write_json(preferences_path, prefs)

    def is_profile_decorated(self, profile: Profile) -> bool:
        """
        Check if a profile has been decorated with its name and color.

        Args:
            profile: Profile to check.

        Returns:
            True if decorated, False otherwise.
        """
        marker_path = profile.user_data_dir / ".catalyst-profile-decorated"
        if not marker_path.exists():
            return False

        # Verify marker content matches current profile
        try:
            content = marker_path.read_text().strip()
            return content == profile.name
        except Exception:
            return False

    def get_launch_args(
        self,
        profile: Profile,
        headless: bool = False,
        no_sandbox: bool = False,
        extra_args: Optional[List[str]] = None
    ) -> List[str]:
        """
        Get Chrome launch arguments for an isolated profile.

        Args:
            profile: Profile to launch.
            headless: Run in headless mode.
            no_sandbox: Disable sandbox (needed in some Linux environments).
            extra_args: Additional Chrome arguments.

        Returns:
            List of Chrome command-line arguments.
        """
        args = [
            f"--remote-debugging-port={profile.cdp_port}",
            f"--user-data-dir={profile.user_data_dir}",
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

        if headless:
            args.extend([
                "--headless=new",
                "--disable-gpu",
            ])

        if no_sandbox:
            args.extend([
                "--no-sandbox",
                "--disable-setuid-sandbox",
            ])

        # Linux-specific
        if sys.platform == "linux":
            args.append("--disable-dev-shm-usage")

        # Add extra args
        if extra_args:
            args.extend(extra_args)

        # Always open a blank tab to ensure a target exists
        args.append("about:blank")

        return args

    # Helper methods for JSON manipulation

    @staticmethod
    def _safe_read_json(path: Path) -> Optional[Dict]:
        """Safely read and parse a JSON file."""
        try:
            if not path.exists():
                return None
            content = path.read_text()
            parsed = json.loads(content)
            if not isinstance(parsed, dict):
                return None
            return parsed
        except Exception:
            return None

    @staticmethod
    def _safe_write_json(path: Path, data: Dict) -> None:
        """Safely write JSON data to a file."""
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2))

    @staticmethod
    def _set_deep(obj: Dict, keys: List[str], value) -> None:
        """Set a deeply nested value in a dictionary."""
        node = obj
        for key in keys[:-1]:
            if key not in node or not isinstance(node[key], dict):
                node[key] = {}
            node = node[key]
        if keys:
            node[keys[-1]] = value

    @staticmethod
    def _parse_hex_to_signed_argb(hex_str: str) -> Optional[int]:
        """
        Parse a hex RGB color to Chrome's signed ARGB int format.

        Chrome stores colors as signed 32-bit integers (SkColor).
        Format: 0xAARRGGBB where AA is alpha (0xFF for opaque).
        """
        cleaned = hex_str.strip().lstrip("#")
        if not re.match(r"^[0-9a-fA-F]{6}$", cleaned):
            return None

        rgb = int(cleaned, 16)
        argb_unsigned = (0xFF << 24) | rgb

        # Convert to signed 32-bit
        if argb_unsigned > 0x7FFFFFFF:
            return argb_unsigned - 0x100000000
        return argb_unsigned


# CLI interface for testing
def main():
    """Command-line interface for profile management."""
    import argparse

    parser = argparse.ArgumentParser(description="Huxley Browser Profile Manager")
    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # List profiles
    subparsers.add_parser("list", help="List all profiles")

    # Create profile
    create_parser = subparsers.add_parser("create", help="Create a new profile")
    create_parser.add_argument("name", help="Profile name")
    create_parser.add_argument("--color", help="Profile color (hex or name)")
    create_parser.add_argument("--port", type=int, help="CDP port")

    # Delete profile
    delete_parser = subparsers.add_parser("delete", help="Delete a profile")
    delete_parser.add_argument("name", help="Profile name")

    # Get launch args
    args_parser = subparsers.add_parser("args", help="Get Chrome launch arguments")
    args_parser.add_argument("name", help="Profile name")
    args_parser.add_argument("--headless", action="store_true", help="Headless mode")

    # Decorate profile
    decorate_parser = subparsers.add_parser("decorate", help="Apply visual decoration")
    decorate_parser.add_argument("name", help="Profile name")

    args = parser.parse_args()

    manager = BrowserProfileManager()

    if args.command == "list":
        profiles = manager.list_profiles()
        if not profiles:
            print("No profiles found.")
        else:
            print(f"{'Name':<20} {'Port':<8} {'Color':<12} {'Decorated'}")
            print("-" * 50)
            for p in profiles:
                print(f"{p.name:<20} {p.cdp_port:<8} {p.color.value:<12} {p.decorated}")

    elif args.command == "create":
        options = ProfileOptions()
        if args.color:
            options.color = ProfileColor.from_string(args.color)
        if args.port:
            options.cdp_port = args.port

        try:
            profile = manager.create_profile(args.name, options)
            print(f"Created profile '{profile.name}'")
            print(f"  Path: {profile.path}")
            print(f"  CDP Port: {profile.cdp_port}")
            print(f"  Color: {profile.color.value}")
        except (ValueError, RuntimeError) as e:
            print(f"Error: {e}")
            sys.exit(1)

    elif args.command == "delete":
        if manager.delete_profile(args.name):
            print(f"Deleted profile '{args.name}'")
        else:
            print(f"Profile '{args.name}' not found")
            sys.exit(1)

    elif args.command == "args":
        profile = manager.get_profile(args.name)
        if not profile:
            print(f"Profile '{args.name}' not found")
            sys.exit(1)

        launch_args = manager.get_launch_args(profile, headless=args.headless)
        print(" ".join(launch_args))

    elif args.command == "decorate":
        profile = manager.get_profile(args.name)
        if not profile:
            print(f"Profile '{args.name}' not found")
            sys.exit(1)

        manager.decorate_profile(profile)
        print(f"Decorated profile '{args.name}'")

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
