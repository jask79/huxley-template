#!/usr/bin/env python3
"""
Navigation Guard for SDK {{ORCHESTRATOR_NAME}} Integration

Ensures Huxley capsule navigation occurs before SDK workflows execute,
preventing stale MCP stamp file issues and ensuring correct MCPs are loaded.

Usage:
    guard = SDKNavigationGuard()
    guard.require_capsule("example-social-capsule")  # Ensures MCPs loaded
    guard.delegate_to_specialist("Python Pro", "example-social-capsule", "Implement auth module")
"""

import subprocess
import sys
from pathlib import Path
from typing import Optional
import json


class SDKNavigationGuard:
    """Guards SDK workflows to ensure correct capsule context is loaded"""

    def __init__(self):
        self.catalyst_root = Path("{{CATALYST_ROOT}}")
        self.navigate_script = self.catalyst_root / "tools" / "navigate_capsule.py"
        self.stamp_file = Path.home() / ".cache/catalyst/last_loaded_capsule"
        self.current_capsule: Optional[str] = None

        # Verify navigation script exists
        if not self.navigate_script.exists():
            raise FileNotFoundError(
                f"Navigation script not found: {self.navigate_script}"
            )

    def get_current_capsule(self) -> Optional[str]:
        """Read current capsule from stamp file"""
        if not self.stamp_file.exists():
            return None

        try:
            stamp_content = self.stamp_file.read_text().strip()
            # Stamp file contains full path, extract capsule name
            if stamp_content.startswith("{{CATALYST_ROOT}}/capsules/"):
                return Path(stamp_content).name
            return stamp_content
        except Exception as e:
            print(f"Warning: Could not read stamp file: {e}", file=sys.stderr)
            return None

    def require_capsule(self, capsule_name: str) -> bool:
        """
        Ensure capsule MCPs are loaded before SDK work.

        Args:
            capsule_name: Name of the capsule to navigate to

        Returns:
            True if navigation successful, raises exception otherwise

        Raises:
            RuntimeError: If navigation fails
        """
        # Check if already in correct capsule
        current = self.get_current_capsule()
        if current == capsule_name and self.current_capsule == capsule_name:
            print(f"✓ Already in capsule: {capsule_name}")
            return True

        print(f"→ Navigating to capsule: {capsule_name}")

        # Execute navigation script
        try:
            result = subprocess.run(
                [sys.executable, str(self.navigate_script), capsule_name],
                capture_output=True,
                text=True,
                check=True,
                timeout=30
            )

            # Verify navigation succeeded
            new_current = self.get_current_capsule()
            if new_current != capsule_name:
                raise RuntimeError(
                    f"Navigation failed: expected {capsule_name}, got {new_current}"
                )

            self.current_capsule = capsule_name
            print(f"✓ Capsule navigation complete: {capsule_name}")
            print(f"  {result.stdout.strip()}")
            return True

        except subprocess.CalledProcessError as e:
            raise RuntimeError(
                f"Navigation script failed: {e.stderr}\n{e.stdout}"
            ) from e
        except subprocess.TimeoutExpired:
            raise RuntimeError(
                f"Navigation timeout after 30s for capsule: {capsule_name}"
            )

    def delegate_to_specialist(
        self,
        agent: str,
        capsule: str,
        task: str,
        context: Optional[dict] = None
    ) -> dict:
        """
        Guard-protected specialist delegation.

        Args:
            agent: Name of specialist agent (e.g., "Python Pro")
            capsule: Capsule name to work in
            task: Task description for specialist
            context: Optional additional context

        Returns:
            Result from specialist (would integrate with SDK Task tool)

        Raises:
            RuntimeError: If navigation fails
        """
        # Ensure capsule MCPs loaded
        self.require_capsule(capsule)

        # Prepare delegation context
        delegation = {
            "agent": agent,
            "capsule": capsule,
            "task": task,
            "context": context or {},
            "guard_verified": True
        }

        print(f"→ Delegating to {agent} in capsule {capsule}")
        print(f"  Task: {task}")

        # NOTE: This is a placeholder for SDK Task tool integration
        # When SDK is installed, this will call:
        # result = sdk.create_task(agent=agent, prompt=task)

        return delegation

    def verify_stamp_file(self, expected_capsule: str) -> bool:
        """
        Verify stamp file matches expected capsule.

        Args:
            expected_capsule: Expected capsule name

        Returns:
            True if stamp file matches, False otherwise
        """
        current = self.get_current_capsule()
        matches = current == expected_capsule

        if matches:
            print(f"✓ Stamp file verified: {expected_capsule}")
        else:
            print(f"⚠ Stamp file mismatch: expected {expected_capsule}, got {current}")

        return matches


def main():
    """CLI for testing navigation guard"""
    import argparse

    parser = argparse.ArgumentParser(description="SDK Navigation Guard")
    parser.add_argument("capsule", help="Capsule name to navigate to")
    parser.add_argument("--verify", action="store_true", help="Verify only, don't navigate")

    args = parser.parse_args()

    guard = SDKNavigationGuard()

    if args.verify:
        if guard.verify_stamp_file(args.capsule):
            print("✓ Verification passed")
            sys.exit(0)
        else:
            print("✗ Verification failed")
            sys.exit(1)
    else:
        try:
            guard.require_capsule(args.capsule)
            print("✓ Navigation successful")
            sys.exit(0)
        except RuntimeError as e:
            print(f"✗ Navigation failed: {e}", file=sys.stderr)
            sys.exit(1)


if __name__ == "__main__":
    main()
