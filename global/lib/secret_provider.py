#!/usr/bin/env python3
"""
Huxley Secret Provider — macOS Keychain with env var fallback.

Usage:
    from secret_provider import get_secret, set_secret, list_secrets

    # Retrieve a secret (Keychain first, then env var)
    db_pass = get_secret("ex-supabase-service-role-key")

    # Store a secret in Keychain
    set_secret("ex-supabase-service-role-key", "my-secret-value")

    # List all Huxley secrets in Keychain
    services = list_secrets()

All Keychain operations use the "huxley" account by default.
No external dependencies — stdlib only.
"""

from __future__ import annotations

import os
import platform
import re
import subprocess
import sys
from typing import List, Optional


class SecretNotFoundError(Exception):
    """Raised when a secret cannot be found in Keychain or environment."""

    def __init__(self, service: str, account: str, env_var: str) -> None:
        self.service = service
        self.account = account
        self.env_var = env_var
        super().__init__(self._build_message())

    def _build_message(self) -> str:
        return (
            f"Secret not found: service={self.service!r}, account={self.account!r}\n"
            f"\n"
            f"The secret was not found in macOS Keychain or as environment variable {self.env_var!r}.\n"
            f"\n"
            f"To add it to Keychain, run:\n"
            f"  security add-generic-password -s \"{self.service}\" -a \"{self.account}\" -w \"YOUR_VALUE\"\n"
            f"\n"
            f"Or set the environment variable:\n"
            f"  export {self.env_var}=\"YOUR_VALUE\""
        )


class KeychainError(Exception):
    """Raised when a Keychain operation fails unexpectedly."""
    pass


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

_SUBPROCESS_TIMEOUT = 5  # seconds

_IS_MACOS = platform.system() == "Darwin"


def _service_to_env_var(service: str) -> str:
    """Convert a Keychain service name to an environment variable name.

    Examples:
        "ex-supabase-service-role" -> "EX_SUPABASE_SERVICE_ROLE"
        "ex-postgres-password" -> "EX_POSTGRES_PASSWORD"
    """
    return service.upper().replace("-", "_")


def _run_security_cmd(args: List[str]) -> subprocess.CompletedProcess:
    """Run a macOS `security` command with timeout and error handling.

    Uses stdin=DEVNULL to prevent interactive prompts in non-interactive
    contexts (LaunchAgents, cron jobs). Note: this doesn't fully prevent
    macOS SecurityAgent GUI dialogs — use `security set-keychain-settings`
    to disable auto-lock for that.
    """
    cmd = ["security"] + args
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=_SUBPROCESS_TIMEOUT,
            stdin=subprocess.DEVNULL,
        )
        return result
    except subprocess.TimeoutExpired as exc:
        raise KeychainError(
            f"Keychain command timed out after {_SUBPROCESS_TIMEOUT}s: {' '.join(cmd)}"
        ) from exc
    except FileNotFoundError as exc:
        raise KeychainError(
            "The 'security' command was not found. "
            "Keychain operations require macOS."
        ) from exc


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def get_secret(service: str, account: str = "huxley") -> str:
    """Retrieve a secret, trying macOS Keychain first then environment.

    Args:
        service:  Keychain service name (e.g. "ex-supabase-service-role-key").
        account:  Keychain account name. Defaults to "huxley".

    Returns:
        The secret value as a string.

    Raises:
        SecretNotFoundError: If the secret is not in Keychain or environment.
        KeychainError: If the Keychain command fails unexpectedly.
    """
    env_var = _service_to_env_var(service)

    # --- Try macOS Keychain first ---
    if _IS_MACOS:
        result = _run_security_cmd([
            "find-generic-password",
            "-s", service,
            "-a", account,
            "-w",
        ])
        if result.returncode == 0:
            value = result.stdout.strip()
            if value:
                return value

    # --- Fall back to environment variable ---
    env_value = os.environ.get(env_var)
    if env_value is not None:
        return env_value

    raise SecretNotFoundError(service, account, env_var)


def set_secret(service: str, value: str, account: str = "huxley") -> bool:
    """Store a secret in macOS Keychain.

    If an entry already exists for the given service+account, it is deleted
    first and then re-added (macOS security CLI does not support in-place
    update).

    Args:
        service:  Keychain service name.
        value:    The secret value to store.
        account:  Keychain account name. Defaults to "huxley".

    Returns:
        True if the secret was stored successfully.

    Raises:
        KeychainError: If the Keychain command fails or we are not on macOS.
    """
    if not _IS_MACOS:
        raise KeychainError("set_secret requires macOS Keychain.")

    # Delete existing entry if present (ignore errors if it doesn't exist)
    _run_security_cmd([
        "delete-generic-password",
        "-s", service,
        "-a", account,
    ])

    # Add the new entry.
    # -T /usr/bin/security authorizes the security CLI to read this item
    # without triggering an ACL-based SecurityAgent dialog.
    result = _run_security_cmd([
        "add-generic-password",
        "-s", service,
        "-a", account,
        "-w", value,
        "-U",  # Update if exists (belt-and-suspenders alongside delete above)
        "-T", "/usr/bin/security",
    ])

    if result.returncode != 0:
        stderr = result.stderr.strip()
        raise KeychainError(
            f"Failed to store secret service={service!r}: {stderr}"
        )

    return True


def list_secrets(account: str = "huxley") -> List[str]:
    """List all Keychain service names for the given account.

    Returns:
        A sorted list of service name strings (no secret values exposed).

    Raises:
        KeychainError: If the Keychain command fails or we are not on macOS.
    """
    if not _IS_MACOS:
        raise KeychainError("list_secrets requires macOS Keychain.")

    # `security dump-keychain` outputs all keychain items. We parse for
    # entries matching our account and extract their service names.
    result = _run_security_cmd(["dump-keychain"])

    if result.returncode != 0:
        raise KeychainError(
            f"Failed to dump keychain: {result.stderr.strip()}"
        )

    services: List[str] = []
    current_service: Optional[str] = None
    found_account = False

    # Parse the dump-keychain output.
    # Each item block looks like:
    #   keychain: "/Users/.../login.keychain-db"
    #   version: 256
    #   class: "genp"
    #   attributes:
    #       ...
    #       "svce"<blob>="service-name"
    #       "acct"<blob>="huxley"
    #       ...
    for line in result.stdout.splitlines():
        stripped = line.strip()

        # Detect service name
        svce_match = re.search(r'"svce"<blob>="([^"]*)"', stripped)
        if svce_match:
            current_service = svce_match.group(1)
            found_account = False

        # Detect account name
        acct_match = re.search(r'"acct"<blob>="([^"]*)"', stripped)
        if acct_match:
            if acct_match.group(1) == account and current_service:
                found_account = True

        # When we hit a new "class:" or "keychain:" line, the previous block
        # is complete. Record it if account matched.
        if stripped.startswith("keychain:") or stripped.startswith("class:"):
            if found_account and current_service:
                services.append(current_service)
            current_service = None
            found_account = False

    # Catch the last block
    if found_account and current_service:
        services.append(current_service)

    return sorted(set(services))


def secret_exists(service: str, account: str = "huxley") -> bool:
    """Check whether a secret exists in Keychain (without returning its value).

    Args:
        service:  Keychain service name.
        account:  Keychain account name. Defaults to "huxley".

    Returns:
        True if the secret is retrievable from Keychain.
    """
    if not _IS_MACOS:
        return False

    result = _run_security_cmd([
        "find-generic-password",
        "-s", service,
        "-a", account,
        "-w",
    ])
    return result.returncode == 0 and bool(result.stdout.strip())


# ---------------------------------------------------------------------------
# CLI entry point (for quick testing)
# ---------------------------------------------------------------------------

def _cli() -> None:
    """Minimal CLI for testing secret_provider operations."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Huxley Secret Provider — macOS Keychain with env var fallback",
    )
    sub = parser.add_subparsers(dest="command", help="Available commands")

    # get
    get_p = sub.add_parser("get", help="Retrieve a secret")
    get_p.add_argument("service", help="Keychain service name")
    get_p.add_argument("--account", default="huxley", help="Keychain account (default: huxley)")

    # set
    set_p = sub.add_parser("set", help="Store a secret in Keychain")
    set_p.add_argument("service", help="Keychain service name")
    set_p.add_argument("value", help="Secret value")
    set_p.add_argument("--account", default="huxley", help="Keychain account (default: huxley)")

    # list
    list_p = sub.add_parser("list", help="List all Huxley secrets in Keychain")
    list_p.add_argument("--account", default="huxley", help="Keychain account (default: huxley)")

    # exists
    exists_p = sub.add_parser("exists", help="Check if a secret exists in Keychain")
    exists_p.add_argument("service", help="Keychain service name")
    exists_p.add_argument("--account", default="huxley", help="Keychain account (default: huxley)")

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        sys.exit(0)

    if args.command == "get":
        try:
            value = get_secret(args.service, args.account)
            # Mask the value for safety: show first 5 chars + ****
            masked = value[:5] + "****" if len(value) > 5 else "****"
            print(f"Found (masked): {masked}")
        except SecretNotFoundError as e:
            print(str(e), file=sys.stderr)
            sys.exit(1)

    elif args.command == "set":
        try:
            set_secret(args.service, args.value, args.account)
            print(f"Stored: service={args.service!r}, account={args.account!r}")
        except KeychainError as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)

    elif args.command == "list":
        try:
            services = list_secrets(args.account)
            if services:
                print(f"Secrets for account={args.account!r}:")
                for svc in services:
                    print(f"  - {svc}")
            else:
                print(f"No secrets found for account={args.account!r}")
        except KeychainError as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)

    elif args.command == "exists":
        found = secret_exists(args.service, args.account)
        status = "FOUND" if found else "NOT FOUND"
        print(f"{args.service}: {status}")
        sys.exit(0 if found else 1)


if __name__ == "__main__":
    _cli()
