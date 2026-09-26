#!/usr/bin/env python3
"""
Huxley Capsule Navigation with Dynamic MCP Loading

Navigates to a capsule and prepares for MCP reload. Since Claude Code loads
MCPs at session start, this script:
1. Updates stamp file to track current capsule
2. Verifies capsule has .mcp.json configuration
3. Returns capsule path for shell integration

For dynamic MCP loading to work, Claude Code must be restarted in the target
capsule directory where it will load that capsule's .mcp.json automatically.
"""

import os
import sys
import json
from pathlib import Path
from typing import Optional, Dict, Any

# Add tools directory to path for imports
TOOLS_DIR = Path(__file__).parent
sys.path.insert(0, str(TOOLS_DIR))

from nav import CapsuleNavigator
from mcp_locator import find_capsule_mcp_config, get_capsule_info, MCPConfigNotFoundError


class CapsuleNavigationError(Exception):
    """Raised when capsule navigation fails"""
    pass


class MCPNavigator:
    """Handles capsule navigation with MCP context management"""

    def __init__(self):
        self.catalyst_root = Path("{{CATALYST_ROOT}}")
        self.stamp_file = Path.home() / ".cache/catalyst/last_loaded_capsule"
        self.navigator = CapsuleNavigator()

    def get_current_capsule(self) -> Optional[str]:
        """Read current capsule from stamp file"""
        if not self.stamp_file.exists():
            return None

        try:
            stamp_content = self.stamp_file.read_text().strip()
            # Stamp file contains capsule name
            return stamp_content
        except Exception:
            return None

    def update_stamp_file(self, capsule_name: str, capsule_path: Path) -> None:
        """Update stamp file with current capsule (stores capsule name only)"""
        self.stamp_file.parent.mkdir(parents=True, exist_ok=True)
        self.stamp_file.write_text(f"{capsule_name}\n")

    def verify_mcp_config(self, capsule_path: Path) -> Path:
        """Verify capsule has .mcp.json configuration"""
        mcp_config = capsule_path / ".mcp.json"

        if not mcp_config.exists():
            # Check if parent Huxley has one (fallback)
            catalyst_mcp = self.catalyst_root / ".mcp.json"
            if catalyst_mcp.exists():
                return catalyst_mcp
            else:
                raise CapsuleNavigationError(
                    f"No .mcp.json found in capsule or Huxley root"
                )

        # Validate JSON format
        try:
            with open(mcp_config) as f:
                config = json.load(f)

            if "mcpServers" not in config:
                raise CapsuleNavigationError(
                    f"Invalid .mcp.json: missing 'mcpServers' key"
                )

            return mcp_config

        except json.JSONDecodeError as e:
            raise CapsuleNavigationError(
                f"Invalid JSON in .mcp.json: {e}"
            )

    def get_mcp_info(self, mcp_config: Path) -> Dict[str, Any]:
        """Extract MCP server information from config"""
        with open(mcp_config) as f:
            config = json.load(f)

        servers = config.get("mcpServers", {})

        return {
            "config_path": str(mcp_config),
            "server_count": len(servers),
            "servers": list(servers.keys())
        }

    def navigate_to_capsule(self, query: str, from_shell: bool = False) -> Dict[str, Any]:
        """
        Navigate to a capsule and prepare for MCP loading

        Args:
            query: Capsule name or keyword query
            from_shell: If True, called from shell integration (quieter output)

        Returns:
            Dictionary with navigation results

        Raises:
            CapsuleNavigationError: If navigation fails
        """
        # Find capsule using navigator
        capsule = self.navigator.find_capsule(query)

        if not capsule:
            raise CapsuleNavigationError(
                f"Capsule not found: '{query}'\n"
                f"Available capsules: {', '.join(c.name for c in self.navigator.capsules)}"
            )

        capsule_path = Path(capsule.path)

        # Verify MCP configuration exists
        try:
            mcp_config = self.verify_mcp_config(capsule_path)
            mcp_info = self.get_mcp_info(mcp_config)
        except CapsuleNavigationError as e:
            if not from_shell:
                print(f"⚠️  Warning: {e}", file=sys.stderr)
            # Continue without MCPs
            mcp_info = {
                "config_path": None,
                "server_count": 0,
                "servers": []
            }

        # Update stamp file
        self.update_stamp_file(capsule.name, capsule_path)

        # Check if already in this capsule
        current_dir = Path.cwd().resolve()
        already_here = current_dir == capsule_path.resolve()

        result = {
            "capsule_name": capsule.name,
            "capsule_path": str(capsule_path),
            "already_here": already_here,
            "mcp_config": mcp_info["config_path"],
            "mcp_servers": mcp_info["servers"],
            "mcp_count": mcp_info["server_count"],
            "requires_restart": not already_here  # Need restart if changing location
        }

        return result

    def navigate_with_mcp_path(self, mcp_config_path: str) -> Dict[str, Any]:
        """
        Navigate using direct .mcp.json path (for session start hook)

        Args:
            mcp_config_path: Path to .mcp.json file

        Returns:
            Dictionary with navigation results
        """
        mcp_config = Path(mcp_config_path)

        if not mcp_config.exists():
            raise CapsuleNavigationError(f"MCP config not found: {mcp_config_path}")

        capsule_path = mcp_config.parent
        capsule_name = capsule_path.name

        # Get MCP info
        mcp_info = self.get_mcp_info(mcp_config)

        # Update stamp file
        self.update_stamp_file(capsule_name, capsule_path)

        return {
            "capsule_name": capsule_name,
            "capsule_path": str(capsule_path),
            "already_here": True,  # Called from session start, we're already here
            "mcp_config": mcp_info["config_path"],
            "mcp_servers": mcp_info["servers"],
            "mcp_count": mcp_info["server_count"],
            "requires_restart": False
        }


def main():
    """CLI entry point"""
    import argparse

    parser = argparse.ArgumentParser(
        description="Navigate to a capsule and load its MCPs"
    )
    parser.add_argument(
        "capsule",
        nargs="?",
        help="Capsule name or keyword query"
    )
    parser.add_argument(
        "--from-shell",
        action="store_true",
        help="Called from shell integration (use with direct .mcp.json path)"
    )
    parser.add_argument(
        "--status",
        action="store_true",
        help="Show current capsule status"
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output results as JSON"
    )

    args = parser.parse_args()

    try:
        nav = MCPNavigator()

        if args.status:
            # Show current status
            current = nav.get_current_capsule()
            if current:
                print(f"Current capsule: {current}")
            else:
                print("No capsule loaded (working in Huxley root)")
            sys.exit(0)

        if not args.capsule:
            parser.error("capsule name is required (use --status to check current capsule)")

        # Handle --from-shell mode (direct .mcp.json path)
        if args.from_shell:
            result = nav.navigate_with_mcp_path(args.capsule)
        else:
            result = nav.navigate_to_capsule(args.capsule, from_shell=False)

        # Output results
        if args.json:
            print(json.dumps(result, indent=2))
        else:
            if result["already_here"]:
                print(f"✅ Already in capsule: {result['capsule_name']}")
            else:
                print(f"📍 Navigate to: {result['capsule_path']}")
                print(f"✅ Capsule: {result['capsule_name']}")

            if result["mcp_config"]:
                print(f"🔌 MCPs: {result['mcp_count']} servers available")
                if result["mcp_servers"]:
                    print(f"   Servers: {', '.join(result['mcp_servers'][:5])}")
                    if len(result["mcp_servers"]) > 5:
                        print(f"   ... and {len(result['mcp_servers']) - 5} more")
            else:
                print(f"⚠️  No MCPs configured for this capsule")

            if result["requires_restart"] and not args.from_shell:
                print()
                print("💡 To load capsule MCPs, restart Claude Code in the capsule directory:")
                print(f"   cd {result['capsule_path']}")
                print(f"   claude")

        sys.exit(0)

    except CapsuleNavigationError as e:
        print(f"❌ Navigation failed: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"❌ Unexpected error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
