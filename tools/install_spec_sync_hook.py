#!/usr/bin/env python3
"""
Pre-commit Hook Installer for Automatic Spec Sync

Installs git pre-commit hook that automatically syncs spec files before each commit.

Usage:
    ./tools/install_spec_sync_hook.py --all              # Install in all capsules
    ./tools/install_spec_sync_hook.py --capsule <path>   # Install in specific capsule
    ./tools/install_spec_sync_hook.py --uninstall        # Remove hooks
"""

import sys
import os
from pathlib import Path
from typing import List, Optional
import stat


# Pre-commit hook template
HOOK_TEMPLATE = """#!/bin/bash
# Auto-generated pre-commit hook for automatic spec sync
# DO NOT EDIT - managed by tools/install_spec_sync_hook.py

# Colors for output
RED='\\033[0;31m'
GREEN='\\033[0;32m'
YELLOW='\\033[1;33m'
NC='\\033[0m' # No Color

echo "${YELLOW}[pre-commit]${NC} Syncing specifications..."

# Get Huxley root
CATALYST_ROOT="$CATALYST_ROOT"
if [ -z "$CATALYST_ROOT" ]; then
    # Try to find it relative to git root
    GIT_ROOT=$(git rev-parse --show-toplevel 2>/dev/null)
    if [ -f "$GIT_ROOT/tools/sync_specs.py" ]; then
        CATALYST_ROOT="$GIT_ROOT"
    else
        # Capsule is in Huxley/capsules/<name> - go up two levels
        CATALYST_ROOT=$(cd "$GIT_ROOT/../.." && pwd)
        # Verify we found Huxley root
        if [ ! -f "$CATALYST_ROOT/tools/sync_specs.py" ]; then
            echo "${RED}✗${NC} Cannot find Huxley root"
            exit 0
        fi
    fi
fi

# Run spec sync
if [ -f "$CATALYST_ROOT/tools/sync_specs.py" ]; then
    python3 "$CATALYST_ROOT/tools/sync_specs.py" --auto
    SYNC_RESULT=$?

    if [ $SYNC_RESULT -eq 0 ]; then
        # Stage updated spec files
        git add standards.yaml product.yaml specs/*.yaml context/spec_updates.log 2>/dev/null
        echo "${GREEN}✓${NC} Specs synchronized"
    else
        echo "${RED}✗${NC} Spec sync failed"
        echo "Review changes manually or use: git commit --no-verify"
        exit 1
    fi
else
    echo "${YELLOW}⚠${NC} sync_specs.py not found, skipping"
fi

# Continue with commit
exit 0
"""


class HookInstaller:
    """Manages pre-commit hook installation"""

    def __init__(self):
        self.catalyst_root = self._find_catalyst_root()
        if not self.catalyst_root:
            raise RuntimeError("Could not find Huxley root directory")

    def _find_catalyst_root(self) -> Optional[Path]:
        """Find Huxley root directory"""
        # Try environment variable
        if 'CATALYST_ROOT' in os.environ:
            return Path(os.environ['CATALYST_ROOT'])

        # Try current directory and parents
        current = Path.cwd()
        for path in [current] + list(current.parents):
            if (path / 'tools' / 'sync_specs.py').exists():
                return path

        return None

    def find_capsules(self) -> List[Path]:
        """Find all capsules with git repositories"""
        capsules = []

        capsules_dir = self.catalyst_root / 'capsules'
        if not capsules_dir.exists():
            return capsules

        for item in capsules_dir.iterdir():
            if item.is_dir() and (item / '.git').exists():
                capsules.append(item)

        return capsules

    def install_hook(self, capsule_path: Path) -> bool:
        """Install pre-commit hook in a capsule"""
        git_dir = capsule_path / '.git'
        if not git_dir.exists():
            print(f"✗ Not a git repository: {capsule_path.name}", file=sys.stderr)
            return False

        hooks_dir = git_dir / 'hooks'
        hooks_dir.mkdir(exist_ok=True)

        hook_path = hooks_dir / 'pre-commit'

        # Check for existing hook
        if hook_path.exists():
            with open(hook_path, 'r') as f:
                existing_content = f.read()

            # Check if it's already our hook
            if 'tools/sync_specs.py' in existing_content:
                print(f"✓ Hook already installed: {capsule_path.name}")
                return True

            # Backup existing hook
            backup_path = hooks_dir / 'pre-commit.backup'
            print(f"⚠ Backing up existing hook: {capsule_path.name}")
            with open(backup_path, 'w') as f:
                f.write(existing_content)

        # Write hook
        try:
            with open(hook_path, 'w') as f:
                f.write(HOOK_TEMPLATE)

            # Make executable
            hook_path.chmod(hook_path.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)

            print(f"✓ Installed hook: {capsule_path.name}")
            return True

        except Exception as e:
            print(f"✗ Failed to install hook in {capsule_path.name}: {e}", file=sys.stderr)
            return False

    def uninstall_hook(self, capsule_path: Path) -> bool:
        """Uninstall pre-commit hook from a capsule"""
        hook_path = capsule_path / '.git' / 'hooks' / 'pre-commit'

        if not hook_path.exists():
            print(f"- No hook installed: {capsule_path.name}")
            return True

        # Check if it's our hook
        with open(hook_path, 'r') as f:
            content = f.read()

        if 'tools/sync_specs.py' not in content:
            print(f"⚠ Skipping non-managed hook: {capsule_path.name}")
            return False

        # Remove hook
        try:
            hook_path.unlink()
            print(f"✓ Uninstalled hook: {capsule_path.name}")

            # Restore backup if it exists
            backup_path = capsule_path / '.git' / 'hooks' / 'pre-commit.backup'
            if backup_path.exists():
                backup_path.rename(hook_path)
                print(f"  Restored backup hook")

            return True

        except Exception as e:
            print(f"✗ Failed to uninstall hook in {capsule_path.name}: {e}", file=sys.stderr)
            return False

    def install_all(self) -> int:
        """Install hooks in all capsules"""
        capsules = self.find_capsules()

        if not capsules:
            print("No capsules with git repositories found")
            return 0

        print(f"Installing pre-commit hooks in {len(capsules)} capsules...\n")

        success_count = 0
        for capsule in capsules:
            if self.install_hook(capsule):
                success_count += 1

        print(f"\n{success_count}/{len(capsules)} hooks installed successfully")
        return success_count

    def uninstall_all(self) -> int:
        """Uninstall hooks from all capsules"""
        capsules = self.find_capsules()

        if not capsules:
            print("No capsules with git repositories found")
            return 0

        print(f"Uninstalling pre-commit hooks from {len(capsules)} capsules...\n")

        success_count = 0
        for capsule in capsules:
            if self.uninstall_hook(capsule):
                success_count += 1

        print(f"\n{success_count} hooks uninstalled")
        return success_count


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description='Install automatic spec sync pre-commit hooks'
    )
    parser.add_argument(
        '--all',
        action='store_true',
        help='Install hooks in all capsules'
    )
    parser.add_argument(
        '--capsule',
        type=Path,
        help='Install hook in specific capsule'
    )
    parser.add_argument(
        '--uninstall',
        action='store_true',
        help='Uninstall hooks instead of installing'
    )

    args = parser.parse_args()

    if not args.all and not args.capsule:
        parser.print_help()
        print("\nError: Must specify --all or --capsule", file=sys.stderr)
        sys.exit(1)

    try:
        installer = HookInstaller()

        if args.uninstall:
            # Uninstall mode
            if args.all:
                installer.uninstall_all()
            elif args.capsule:
                installer.uninstall_hook(args.capsule)
        else:
            # Install mode
            if args.all:
                installer.install_all()
            elif args.capsule:
                if installer.install_hook(args.capsule):
                    print("\n✓ Hook installation complete")
                else:
                    print("\n✗ Hook installation failed", file=sys.stderr)
                    sys.exit(1)

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
