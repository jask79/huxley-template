#!/usr/bin/env python3
"""
MCP Context Locator - Discovers parent capsule .mcp.json from any working directory

Usage:
    from mcp_locator import find_capsule_mcp_config

    mcp_path = find_capsule_mcp_config()  # Auto-detect from cwd
    mcp_path = find_capsule_mcp_config("/path/to/subdir")  # Explicit start
"""

import os
import sys
from pathlib import Path
from typing import Optional


class MCPConfigNotFoundError(Exception):
    """Raised when no .mcp.json can be found in parent directories"""
    pass


def find_capsule_mcp_config(start_dir: Optional[str] = None) -> Path:
    """
    Walk up directory tree to find nearest .mcp.json

    Args:
        start_dir: Directory to start search from (defaults to cwd)

    Returns:
        Path to .mcp.json file

    Raises:
        MCPConfigNotFoundError: If no .mcp.json found before reaching capsules/ or filesystem root
    """
    # Normalize and resolve symlinks/relative paths
    current = Path(start_dir or os.getcwd()).resolve()
    capsules_dir = Path("{{CATALYST_ROOT}}/capsules").resolve()

    # Filesystem root fallback (prevents infinite loop)
    filesystem_root = Path("/").resolve()

    # Traverse upward
    while True:
        # Check for .mcp.json at current level
        mcp_file = current / ".mcp.json"
        if mcp_file.exists():
            return mcp_file

        # Stop at capsules directory (capsule boundary)
        if current == capsules_dir:
            raise MCPConfigNotFoundError(
                f"No .mcp.json found between {start_dir or os.getcwd()} and {capsules_dir}\n"
                f"Are you inside a capsule? Run: navigate to <capsule-name>"
            )

        # Stop at filesystem root (safety fallback)
        if current == filesystem_root:
            raise MCPConfigNotFoundError(
                f"No .mcp.json found (reached filesystem root)\n"
                f"You may be outside the Huxley capsules directory.\n"
                f"Expected path: {{CATALYST_ROOT}}/capsules/<capsule-name>/"
            )

        # Move up one directory
        current = current.parent


def get_capsule_info(mcp_config_path: Path) -> dict:
    """
    Extract capsule information from .mcp.json path

    Returns:
        {
            "capsule_name": "example-capsule",
            "capsule_root": Path("{{CATALYST_ROOT}}/capsules/example-capsule"),
            "mcp_config": Path("{{CATALYST_ROOT}}/capsules/example-capsule/.mcp.json")
        }
    """
    capsule_root = mcp_config_path.parent
    capsule_name = capsule_root.name

    return {
        "capsule_name": capsule_name,
        "capsule_root": capsule_root,
        "mcp_config": mcp_config_path
    }


def get_relative_path_from_capsule(working_dir: Optional[Path] = None) -> Optional[Path]:
    """
    Get current working directory's path relative to capsule root

    Returns:
        Relative path from capsule root (e.g., "portal-v2/src") or None if at capsule root
    """
    try:
        base_dir = (working_dir or Path.cwd()).resolve()
        mcp_config = find_capsule_mcp_config(str(base_dir))
        capsule_root = mcp_config.parent
        current_dir = base_dir

        if current_dir == capsule_root:
            return None

        return current_dir.relative_to(capsule_root)
    except (MCPConfigNotFoundError, ValueError):
        return None


if __name__ == "__main__":
    """CLI interface for testing and shell integration"""
    import argparse

    parser = argparse.ArgumentParser(description="Locate capsule .mcp.json from any subdirectory")
    parser.add_argument("--find", action="store_true", help="Print path to .mcp.json")
    parser.add_argument("--info", action="store_true", help="Print capsule info as JSON")
    parser.add_argument("--relative", action="store_true", help="Print relative path from capsule root")
    parser.add_argument("--start-dir", help="Starting directory (defaults to cwd)")

    args = parser.parse_args()

    try:
        if args.find:
            mcp_path = find_capsule_mcp_config(args.start_dir)
            print(mcp_path)

        elif args.info:
            import json
            mcp_path = find_capsule_mcp_config(args.start_dir)
            info = get_capsule_info(mcp_path)
            # Convert Path objects to strings for JSON serialization
            info_serializable = {
                "capsule_name": info["capsule_name"],
                "capsule_root": str(info["capsule_root"]),
                "mcp_config": str(info["mcp_config"])
            }
            print(json.dumps(info_serializable, indent=2))

        elif args.relative:
            start_dir = Path(args.start_dir).resolve() if args.start_dir else None
            rel_path = get_relative_path_from_capsule(start_dir)
            if rel_path:
                print(rel_path)
            else:
                print("(at capsule root)")

        else:
            # Default: just verify we can find it
            start_dir = Path(args.start_dir).resolve() if args.start_dir else None
            mcp_path = find_capsule_mcp_config(str(start_dir) if start_dir else None)
            info = get_capsule_info(mcp_path)
            rel_path = get_relative_path_from_capsule(start_dir)

            print(f"✅ Found capsule: {info['capsule_name']}")
            print(f"   Config: {mcp_path}")
            if rel_path:
                print(f"   Working in: {rel_path}")

    except MCPConfigNotFoundError as e:
        print(f"❌ {e}", file=sys.stderr)
        sys.exit(1)
