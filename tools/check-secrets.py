#!/usr/bin/env python3
"""
Huxley Secrets Validator — Verify all required secrets exist in Keychain.

Reads `keychain.required.toml` files from capsule directories (and root)
to verify every declared secret is accessible via macOS Keychain.

Usage:
    python3 tools/check-secrets.py              # check all capsules
    python3 tools/check-secrets.py --capsule example-capsule  # check one capsule
    python3 tools/check-secrets.py --help

Exit codes:
    0 = all secrets found
    1 = one or more secrets missing (prints fix commands)
"""

from __future__ import annotations

import argparse
import os
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Import secret_provider from global/lib/
# ---------------------------------------------------------------------------

_CATALYST_ROOT = Path(__file__).resolve().parent.parent
_LIB_PATH = _CATALYST_ROOT / "global" / "lib"
sys.path.insert(0, str(_LIB_PATH))

import secret_provider  # noqa: E402

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# Directories to scan for keychain.required.toml
SCAN_DIRS: List[Path] = [
    _CATALYST_ROOT,                                      # root
]

# Also scan all capsule directories
CAPSULES_DIR = _CATALYST_ROOT / "capsules"


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass
class RequiredSecret:
    """A secret declared in keychain.required.toml."""
    env_key: str          # The env var name (e.g., SUPABASE_SERVICE_ROLE_KEY)
    service: str          # Keychain service name
    account: str          # Keychain account (default: huxley)
    source_dir: Path      # Directory containing the toml file
    found: bool = False   # Whether the secret was found in Keychain

    @property
    def source_label(self) -> str:
        """Short label for the source directory."""
        try:
            rel = self.source_dir.relative_to(_CATALYST_ROOT)
            if str(rel) == ".":
                return "root"
            parts = rel.parts
            if parts[0] == "capsules" and len(parts) >= 2:
                return parts[1]
            return str(rel)
        except ValueError:
            return str(self.source_dir)


# ---------------------------------------------------------------------------
# TOML parsing
# ---------------------------------------------------------------------------


def parse_required_toml(toml_path: Path) -> List[RequiredSecret]:
    """Parse a keychain.required.toml file into RequiredSecret entries.

    Expected format:
        [secrets]
        SUPABASE_SERVICE_ROLE_KEY = { service = "ex-supabase-service-role-key", account = "huxley" }
        CLOUDFLARE_API_TOKEN = { service = "ex-cloudflare-api-token", account = "huxley" }
    """
    secrets: List[RequiredSecret] = []

    with open(toml_path, "rb") as f:
        data = tomllib.load(f)

    secrets_section = data.get("secrets", {})
    if not isinstance(secrets_section, dict):
        return secrets

    for env_key, config in secrets_section.items():
        if not isinstance(config, dict):
            continue

        service = config.get("service", "")
        account = config.get("account", "huxley")

        if not service:
            continue

        secrets.append(RequiredSecret(
            env_key=env_key,
            service=service,
            account=account,
            source_dir=toml_path.parent,
        ))

    return secrets


# ---------------------------------------------------------------------------
# Discovery
# ---------------------------------------------------------------------------


def discover_toml_files(capsule_filter: Optional[str] = None) -> List[Path]:
    """Find all keychain.required.toml files in the system.

    If capsule_filter is set, only scan that specific capsule.
    """
    toml_files: List[Path] = []

    if capsule_filter:
        # Only scan the specified capsule
        capsule_dir = CAPSULES_DIR / capsule_filter
        toml_path = capsule_dir / "keychain.required.toml"
        if toml_path.exists():
            toml_files.append(toml_path)
        else:
            print(f"Warning: No keychain.required.toml in {capsule_dir}", file=sys.stderr)
        return toml_files

    # Scan root and tools directories
    for scan_dir in SCAN_DIRS:
        toml_path = scan_dir / "keychain.required.toml"
        if toml_path.exists():
            toml_files.append(toml_path)

    # Scan all capsule directories
    if CAPSULES_DIR.exists():
        for capsule_dir in sorted(CAPSULES_DIR.iterdir()):
            if not capsule_dir.is_dir():
                continue
            toml_path = capsule_dir / "keychain.required.toml"
            if toml_path.exists():
                toml_files.append(toml_path)

            # Also check subdirectories (e.g., capsules/example-capsule/portal/)
            for subdir in sorted(capsule_dir.iterdir()):
                if not subdir.is_dir():
                    continue
                toml_path = subdir / "keychain.required.toml"
                if toml_path.exists():
                    toml_files.append(toml_path)

    return toml_files


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def validate_secrets(secrets: List[RequiredSecret]) -> Tuple[int, int]:
    """Check each secret against Keychain. Returns (found_count, missing_count)."""
    found = 0
    missing = 0

    for secret in secrets:
        secret.found = secret_provider.secret_exists(
            service=secret.service,
            account=secret.account,
        )
        if secret.found:
            found += 1
        else:
            missing += 1

    return found, missing


# ---------------------------------------------------------------------------
# Output formatting
# ---------------------------------------------------------------------------


def _col(text: str, width: int) -> str:
    """Left-align text in a column of given width."""
    return text[:width].ljust(width)


def print_results_table(secrets: List[RequiredSecret]) -> None:
    """Print the validation results as a table."""
    if not secrets:
        print("No keychain.required.toml files found. Nothing to validate.")
        return

    print()
    print(f"  {'Capsule':<20} {'Service':<50} {'Status'}")
    print("  " + "-" * 80)

    current_source = ""
    for secret in secrets:
        source = secret.source_label
        if source != current_source:
            if current_source:
                print()  # Blank line between sources
            current_source = source

        status = "FOUND" if secret.found else "MISSING"
        status_icon = "  " if secret.found else "! "
        print(f"  {status_icon}{_col(source, 18)} {_col(secret.service, 50)} {status}")

    print()


def print_fix_commands(secrets: List[RequiredSecret]) -> None:
    """Print the exact commands to fix missing secrets."""
    missing = [s for s in secrets if not s.found]
    if not missing:
        return

    print("FIX COMMANDS:")
    print("Run these to add the missing secrets to Keychain:\n")
    for secret in missing:
        print(
            f"  security add-generic-password "
            f"-s \"{secret.service}\" "
            f"-a \"{secret.account}\" "
            f"-w \"YOUR_{secret.env_key}_VALUE\""
        )
    print()
    print("Or use the migration script to auto-populate from .env files:")
    print("  python3 tools/migrate-secrets.py --execute\n")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Huxley Secrets Validator — Verify required secrets exist in macOS Keychain",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "TOML format (keychain.required.toml):\n"
            "  [secrets]\n"
            '  SUPABASE_SERVICE_ROLE_KEY = { service = "ex-supabase-service-role-key", account = "huxley" }\n'
            '  CLOUDFLARE_API_TOKEN = { service = "ex-cloudflare-api-token", account = "huxley" }\n'
        ),
    )
    parser.add_argument(
        "--capsule",
        type=str,
        default=None,
        help="Only check a specific capsule (e.g., example-capsule)",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Show additional details during validation",
    )

    args = parser.parse_args()

    # Discover TOML files
    toml_files = discover_toml_files(capsule_filter=args.capsule)

    if not toml_files:
        print("No keychain.required.toml files found.")
        if args.capsule:
            print(f"  Checked: {CAPSULES_DIR / args.capsule}/keychain.required.toml")
        else:
            print(f"  Checked: {_CATALYST_ROOT}, {CAPSULES_DIR}/*/")
        print("\nCreate a keychain.required.toml file to declare required secrets.")
        return 0

    if args.verbose:
        print(f"Found {len(toml_files)} keychain.required.toml file(s):")
        for f in toml_files:
            print(f"  - {f}")
        print()

    # Parse all TOML files
    all_secrets: List[RequiredSecret] = []
    for toml_path in toml_files:
        try:
            secrets = parse_required_toml(toml_path)
            all_secrets.extend(secrets)
            if args.verbose:
                print(f"  Parsed {len(secrets)} entries from {toml_path}")
        except Exception as e:
            print(f"Error parsing {toml_path}: {e}", file=sys.stderr)

    if not all_secrets:
        print("No secret entries found in any keychain.required.toml file.")
        return 0

    # Validate
    found_count, missing_count = validate_secrets(all_secrets)

    # Output
    print_results_table(all_secrets)

    total = found_count + missing_count
    print(f"Results: {found_count}/{total} secrets found in Keychain")

    if missing_count > 0:
        print(f"         {missing_count} secret(s) MISSING\n")
        print_fix_commands(all_secrets)
        return 1

    print("All required secrets are present in Keychain.\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
