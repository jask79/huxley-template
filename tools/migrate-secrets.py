#!/usr/bin/env python3
"""
Huxley Secret Migration — Move secrets from .env files to macOS Keychain.

Scans known .env files, classifies each variable as SECRET or PUBLIC,
and migrates secrets to macOS Keychain using the secret_provider library.

Modes:
    --dry-run   (default) Show classification table; what would be migrated
    --execute   Actually write secrets to Keychain
    --verify    Check that all expected secrets are readable from Keychain

Usage:
    python3 tools/migrate-secrets.py                  # dry-run
    python3 tools/migrate-secrets.py --execute        # migrate
    python3 tools/migrate-secrets.py --verify         # verify post-migration
    python3 tools/migrate-secrets.py --help           # help

NEVER prints actual secret values. Masked output only.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from dataclasses import dataclass, field
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

# All known .env files to scan. Add one entry per capsule that keeps its own .env.
ENV_FILES: List[Path] = [
    _CATALYST_ROOT / ".env",
    _CATALYST_ROOT / "capsules" / "example-capsule" / ".env",
]

# Patterns that indicate a variable is SECRET (checked against key name)
SECRET_PATTERNS: List[str] = [
    "PASSWORD",
    "SECRET",
    "TOKEN",
    "API_KEY",
    "PRIVATE",
    "SERVICE_ROLE",
    "ACCESS_TOKEN",
    "SMTP_LOGIN",
]

# Patterns that indicate a variable is PUBLIC (checked against key name).
# These take precedence over SECRET_PATTERNS when there's a conflict.
PUBLIC_PATTERNS: List[str] = [
    "URL",
    "_URL",
    "VITE_",
    "NODE_ENV",
    "_REF",
    "_ENABLED",
    "_REQUESTS",
    "_WINDOW",
    "_CONTEXT",
    "_KEYWORDS",
    "_DIR",
    "_NAME",
    "_HOST",
    "_PORT",
    "_DOMAIN",
    "_EMAIL",
    "_FROM_",
    "PUBLISHABLE",
    "ANON_KEY",
    "USE_SANDBOX",
    "_ALLOWED_",
]

# Exceptions: keys with _ID are public UNLESS they contain SECRET_ID
PUBLIC_ID_PATTERN = "_ID"
SECRET_ID_EXCEPTION = "SECRET_ID"

# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass
class EnvVar:
    """Represents a single environment variable from a .env file."""
    key: str
    value: str
    source_file: Path
    classification: str = ""        # "SECRET" or "PUBLIC"
    keychain_service: str = ""      # Keychain service name (for secrets only)
    keychain_account: str = "huxley"

    @property
    def masked_value(self) -> str:
        """Return a masked version of the value. Never expose full secrets."""
        if len(self.value) <= 5:
            return "****"
        return self.value[:5] + "****"

    @property
    def capsule_name(self) -> str:
        """Derive the capsule name from the source file path."""
        rel = self.source_file.relative_to(_CATALYST_ROOT)
        parts = rel.parts
        if parts[0] == "capsules" and len(parts) >= 2:
            return parts[1]
        if parts[0] == "tools" and len(parts) >= 2:
            return parts[1]
        return "root"


@dataclass
class MigrationPlan:
    """Holds the full migration plan across all .env files."""
    secrets: List[EnvVar] = field(default_factory=list)
    public_vars: List[EnvVar] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Classification logic
# ---------------------------------------------------------------------------


def _matches_patterns(key: str, patterns: List[str]) -> bool:
    """Check if a key name matches any of the given patterns."""
    upper_key = key.upper()
    for pattern in patterns:
        if pattern in upper_key:
            return True
    return False


def classify_variable(key: str) -> str:
    """Classify a variable name as SECRET or PUBLIC.

    PUBLIC patterns take precedence to avoid false positives
    (e.g., SUPABASE_URL contains no secret even though it has "SUPABASE").
    The _ID suffix is public unless it's SECRET_ID.
    """
    upper_key = key.upper()

    # Check public patterns first (they take precedence)
    if _matches_patterns(upper_key, PUBLIC_PATTERNS):
        return "PUBLIC"

    # _ID is public unless it's SECRET_ID
    if PUBLIC_ID_PATTERN in upper_key and SECRET_ID_EXCEPTION not in upper_key:
        return "PUBLIC"

    # Check secret patterns
    if _matches_patterns(upper_key, SECRET_PATTERNS):
        return "SECRET"

    # Default: PUBLIC (conservative — don't migrate what we're unsure about)
    return "PUBLIC"


# ---------------------------------------------------------------------------
# Keychain service name generation
# ---------------------------------------------------------------------------

# Capsule short-name prefixes for Keychain service names. One entry per capsule;
# the prefix becomes part of the service name (e.g. ex-supabase-service-role-key).
CAPSULE_PREFIXES: Dict[str, str] = {
    "example-capsule": "ex",
}


def _key_to_hyphenated(key: str) -> str:
    """Convert an env var key name to lowercase-hyphenated form.

    e.g., SUPABASE_SERVICE_ROLE_KEY -> supabase-service-role-key
    """
    return key.lower().replace("_", "-")


def compute_keychain_service(env_var: EnvVar) -> str:
    """Compute the Keychain service name for a secret.

    Root .env:    "{key_lowered_hyphenated}"
    Capsule .env: "{prefix}-{key_lowered_hyphenated}"
    Tools .env:   "{tool-name}-{key_lowered_hyphenated}"
    """
    hyphenated = _key_to_hyphenated(env_var.key)
    capsule = env_var.capsule_name

    if capsule == "root":
        return f"{hyphenated}"

    # Use short prefix if available, otherwise the capsule name itself
    prefix = CAPSULE_PREFIXES.get(capsule, capsule)
    return f"{prefix}-{hyphenated}"


# ---------------------------------------------------------------------------
# .env file parsing
# ---------------------------------------------------------------------------


def parse_env_file(filepath: Path) -> List[Tuple[str, str]]:
    """Parse a .env file, returning (key, value) pairs.

    Handles:
    - Comments (lines starting with #)
    - Blank lines
    - Quoted values (single or double quotes)
    - Inline comments after values
    """
    entries: List[Tuple[str, str]] = []

    if not filepath.exists():
        return entries

    with open(filepath, "r") as f:
        for line in f:
            line = line.strip()

            # Skip comments and blank lines
            if not line or line.startswith("#"):
                continue

            # Must contain = sign
            if "=" not in line:
                continue

            key, _, raw_value = line.partition("=")
            key = key.strip()
            raw_value = raw_value.strip()

            # Remove surrounding quotes if present
            if len(raw_value) >= 2:
                if (raw_value[0] == '"' and raw_value[-1] == '"') or \
                   (raw_value[0] == "'" and raw_value[-1] == "'"):
                    raw_value = raw_value[1:-1]

            # Skip empty keys
            if not key:
                continue

            entries.append((key, raw_value))

    return entries


# ---------------------------------------------------------------------------
# Plan generation
# ---------------------------------------------------------------------------


def build_migration_plan() -> MigrationPlan:
    """Scan all known .env files and build the migration plan."""
    plan = MigrationPlan()

    for env_path in ENV_FILES:
        if not env_path.exists():
            plan.errors.append(f"File not found: {env_path}")
            continue

        entries = parse_env_file(env_path)
        for key, value in entries:
            var = EnvVar(key=key, value=value, source_file=env_path)
            var.classification = classify_variable(key)

            if var.classification == "SECRET":
                var.keychain_service = compute_keychain_service(var)
                plan.secrets.append(var)
            else:
                plan.public_vars.append(var)

    return plan


# ---------------------------------------------------------------------------
# Output formatting
# ---------------------------------------------------------------------------

def _col(text: str, width: int) -> str:
    """Left-align text in a column of given width."""
    return text[:width].ljust(width)


def _source_label(path: Path) -> str:
    """Return a short human-readable label for the source .env file."""
    try:
        rel = path.relative_to(_CATALYST_ROOT)
        return str(rel)
    except ValueError:
        return str(path)


def print_classification_table(plan: MigrationPlan) -> None:
    """Print a table showing how each variable was classified."""
    all_vars = plan.secrets + plan.public_vars
    all_vars.sort(key=lambda v: (str(v.source_file), v.key))

    print("\n" + "=" * 100)
    print("CLASSIFICATION TABLE")
    print("=" * 100)
    print(f"{'Source':<50} {'Key':<35} {'Class':<8} {'Keychain Service'}")
    print("-" * 100)

    current_source = ""
    for var in all_vars:
        source = _source_label(var.source_file)
        if source != current_source:
            if current_source:
                print()  # Blank line between files
            current_source = source
            print(f"  [{source}]")

        kc_svc = var.keychain_service if var.classification == "SECRET" else "-"
        marker = "***" if var.classification == "SECRET" else "   "
        print(f"  {marker} {_col(var.key, 33)} {_col(var.classification, 8)} {kc_svc}")

    print()


def print_migration_summary(plan: MigrationPlan) -> None:
    """Print a summary of what will be migrated."""
    print("\n" + "=" * 70)
    print("MIGRATION SUMMARY")
    print("=" * 70)
    print(f"  Total variables scanned:  {len(plan.secrets) + len(plan.public_vars)}")
    print(f"  Classified as SECRET:     {len(plan.secrets)}")
    print(f"  Classified as PUBLIC:     {len(plan.public_vars)}")
    print(f"  Errors:                   {len(plan.errors)}")

    if plan.errors:
        print("\n  Errors:")
        for err in plan.errors:
            print(f"    - {err}")

    print()

    if plan.secrets:
        print("SECRETS TO MIGRATE:")
        print(f"  {'Keychain Service':<50} {'Key':<35} {'Masked Value'}")
        print("  " + "-" * 95)
        for var in sorted(plan.secrets, key=lambda v: v.keychain_service):
            print(f"  {_col(var.keychain_service, 50)} {_col(var.key, 35)} {var.masked_value}")
    else:
        print("  No secrets found to migrate.")

    print()


# ---------------------------------------------------------------------------
# Execution modes
# ---------------------------------------------------------------------------


def mode_dry_run(plan: MigrationPlan) -> int:
    """Show what would be migrated without making changes."""
    print("\n[DRY RUN] No changes will be made.\n")
    print_classification_table(plan)
    print_migration_summary(plan)

    print("To execute the migration, run:")
    print("  python3 tools/migrate-secrets.py --execute\n")
    return 0


def mode_execute(plan: MigrationPlan) -> int:
    """Execute the migration: write secrets to Keychain."""
    if not plan.secrets:
        print("No secrets to migrate.")
        return 0

    print(f"\n[EXECUTE] Migrating {len(plan.secrets)} secrets to macOS Keychain...\n")

    success = 0
    failed = 0

    for var in sorted(plan.secrets, key=lambda v: v.keychain_service):
        try:
            secret_provider.set_secret(
                service=var.keychain_service,
                value=var.value,
                account=var.keychain_account,
            )
            print(f"  OK  {var.keychain_service} <- {var.key} ({var.masked_value})")
            success += 1
        except secret_provider.KeychainError as e:
            print(f"  FAIL {var.keychain_service} <- {var.key}: {e}")
            failed += 1

    print(f"\nResults: {success} stored, {failed} failed")

    if failed > 0:
        print("\nSome secrets failed to migrate. Check errors above.")
        return 1

    print("\nAll secrets migrated successfully.")
    print("Run verification with: python3 tools/migrate-secrets.py --verify")
    return 0


def mode_verify(plan: MigrationPlan) -> int:
    """Verify that all expected secrets are readable from Keychain."""
    if not plan.secrets:
        print("No secrets to verify.")
        return 0

    print(f"\n[VERIFY] Checking {len(plan.secrets)} secrets in macOS Keychain...\n")

    found = 0
    missing = 0

    print(f"  {'Keychain Service':<50} {'Status':<10} {'Source Key'}")
    print("  " + "-" * 80)

    for var in sorted(plan.secrets, key=lambda v: v.keychain_service):
        exists = secret_provider.secret_exists(
            service=var.keychain_service,
            account=var.keychain_account,
        )
        if exists:
            status = "FOUND"
            found += 1
        else:
            status = "MISSING"
            missing += 1

        print(f"  {_col(var.keychain_service, 50)} {_col(status, 10)} {var.key}")

    print(f"\nResults: {found} found, {missing} missing")

    if missing > 0:
        print("\nMissing secrets. Run migration with: python3 tools/migrate-secrets.py --execute")
        return 1

    print("\nAll secrets verified in Keychain.")
    return 0


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Huxley Secret Migration — Move secrets from .env files to macOS Keychain",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python3 tools/migrate-secrets.py              # dry-run (default)\n"
            "  python3 tools/migrate-secrets.py --execute     # migrate secrets\n"
            "  python3 tools/migrate-secrets.py --verify      # verify migration\n"
        ),
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--dry-run",
        action="store_true",
        default=True,
        help="Show classification table and migration plan (default)",
    )
    mode.add_argument(
        "--execute",
        action="store_true",
        help="Execute the migration: write secrets to Keychain",
    )
    mode.add_argument(
        "--verify",
        action="store_true",
        help="Verify all expected secrets are in Keychain",
    )

    args = parser.parse_args()

    # Build the migration plan (always needed)
    plan = build_migration_plan()

    if args.execute:
        return mode_execute(plan)
    elif args.verify:
        return mode_verify(plan)
    else:
        return mode_dry_run(plan)


if __name__ == "__main__":
    sys.exit(main())
