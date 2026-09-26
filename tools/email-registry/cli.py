#!/usr/bin/env python3
"""
Email Registry CLI — Centralized email account management across all providers.

Usage:
    python3 tools/email-registry/cli.py status
    python3 tools/email-registry/cli.py list
    python3 tools/email-registry/cli.py list --provider gmail
    python3 tools/email-registry/cli.py list --type service
    python3 tools/email-registry/cli.py list --capsule my-capsule
    python3 tools/email-registry/cli.py list --status active
    python3 tools/email-registry/cli.py search "example.com"
    python3 tools/email-registry/cli.py add --email foo@bar.com --provider gmail --type personal --purpose "Description"
    python3 tools/email-registry/cli.py consolidation
    python3 tools/email-registry/cli.py stats
"""

import argparse
import os
import sys
from pathlib import Path

# Resolve paths relative to catalyst root
SCRIPT_DIR = Path(__file__).resolve().parent
CATALYST_ROOT = SCRIPT_DIR.parent.parent
REGISTRY_PATH = CATALYST_ROOT / "global" / "config" / "email-registry.yaml"

# ---------------------------------------------------------------------------
# ANSI color helpers
# ---------------------------------------------------------------------------

RESET  = "\033[0m"
BOLD   = "\033[1m"
DIM    = "\033[2m"
GREEN  = "\033[32m"
YELLOW = "\033[33m"
CYAN   = "\033[36m"
RED    = "\033[31m"
BLUE   = "\033[34m"
MAGENTA = "\033[35m"


def bold(s: str) -> str:
    return f"{BOLD}{s}{RESET}"


def cyan(s: str) -> str:
    return f"{CYAN}{s}{RESET}"


def green(s: str) -> str:
    return f"{GREEN}{s}{RESET}"


def yellow(s: str) -> str:
    return f"{YELLOW}{s}{RESET}"


def red(s: str) -> str:
    return f"{RED}{s}{RESET}"


def dim(s: str) -> str:
    return f"{DIM}{s}{RESET}"


# ---------------------------------------------------------------------------
# YAML loader (stdlib only — no PyYAML dependency required)
# ---------------------------------------------------------------------------

def load_registry() -> dict:
    """Load email registry YAML. Uses PyYAML if available, falls back to basic parser."""
    if not REGISTRY_PATH.exists():
        print(f"ERROR: Registry not found at {REGISTRY_PATH}")
        print("Run ./setup.sh once, or copy global/config/email-registry.example.yaml into place.")
        sys.exit(1)

    text = REGISTRY_PATH.read_text()

    try:
        import yaml
        return yaml.safe_load(text) or {}
    except ImportError:
        return _parse_yaml_basic(text)


def _parse_yaml_basic(text: str) -> dict:
    """Minimal YAML parser for the flat email-registry format.
    Handles top-level email address keys and their single-level string properties.
    NOT a general YAML parser."""
    result = {}
    current_email = None

    for lineno, line in enumerate(text.splitlines(), 1):
        stripped = line.strip()

        # Skip comments and blanks
        if not stripped or stripped.startswith("#"):
            continue

        # Warn on YAML list items (unsupported)
        if stripped.startswith("- "):
            print(f"WARNING: basic YAML parser cannot handle list item at line {lineno}: {stripped[:60]}")
            continue

        # Top-level key (email address — no leading whitespace, ends with colon)
        if not line[0].isspace() and stripped.endswith(":"):
            current_email = stripped.rstrip(":")
            result[current_email] = {}
        # Nested property
        elif current_email and ":" in stripped:
            indent = len(line) - len(line.lstrip())
            if indent > 4:
                print(f"WARNING: basic YAML parser cannot handle deep nesting at line {lineno}: {stripped[:60]}")
                continue
            key, _, value = stripped.partition(":")
            key = key.strip()
            raw_value = value.strip()
            # Handle inline comments — only strip if # is outside quotes
            if '"' not in raw_value and "'" not in raw_value:
                if "  #" in raw_value:
                    raw_value = raw_value[: raw_value.index("  #")].strip()
                elif raw_value.startswith("#"):
                    raw_value = ""
            value = raw_value.strip('"').strip("'")
            # Normalize null / none values
            if value.lower() in ("null", "~", ""):
                value = None
            result[current_email][key] = value

    return result


def save_registry_yaml(data: dict):
    """Write registry back to YAML atomically. Requires PyYAML."""
    try:
        import yaml
        tmp_path = REGISTRY_PATH.with_suffix(".yaml.tmp")
        with open(tmp_path, "w") as f:
            yaml.dump(data, f, default_flow_style=False, sort_keys=False, allow_unicode=True)
        os.replace(tmp_path, REGISTRY_PATH)
    except ImportError:
        print("WARNING: PyYAML not installed — cannot write registry. Install with: pip install pyyaml")
        sys.exit(1)


# ---------------------------------------------------------------------------
# Status icons and helpers
# ---------------------------------------------------------------------------

STATUS_ICONS = {
    "active":      "🟢",
    "inactive":    "🔴",
    "deprecated":  "🟡",
}

TYPE_ICONS = {
    "personal": "👤",
    "business": "💼",
    "service":  "⚙️ ",
    "public":   "🌐",
}

PROVIDER_COLORS = {
    "gmail":            GREEN,
    "google-workspace": GREEN,
    "resend":           CYAN,
    "custom-domain":    MAGENTA,
    "proton":           BLUE,
    "icloud":           BLUE,
    "fastmail":         YELLOW,
}


def status_icon(status: str) -> str:
    return STATUS_ICONS.get(str(status).lower(), "❓")


def type_icon(t: str) -> str:
    return TYPE_ICONS.get(str(t).lower(), "•")


def color_provider(provider: str) -> str:
    color = PROVIDER_COLORS.get(str(provider).lower(), RESET)
    return f"{color}{provider}{RESET}"


def color_provider_padded(provider: str, width: int = 18) -> str:
    """Color a provider string with padding applied BEFORE ANSI codes for correct alignment."""
    color = PROVIDER_COLORS.get(str(provider).lower(), RESET)
    return f"{color}{provider:<{width}}{RESET}"


def fmt_val(v) -> str:
    """Format a possibly-null value for display."""
    if v is None or str(v).lower() in ("null", "none", "~", ""):
        return dim("—")
    return str(v)


# ---------------------------------------------------------------------------
# CLI commands
# ---------------------------------------------------------------------------

def cmd_status(args):
    """Overview grouped by type (personal / business / service / public)."""
    registry = load_registry()
    if not registry:
        print("Registry is empty.")
        return

    by_type = {}
    for email, info in registry.items():
        if not isinstance(info, dict):
            continue
        t = info.get("type", "unknown")
        by_type.setdefault(t, []).append((email, info))

    total = sum(len(v) for v in by_type.values())
    print(f"\n{'='*64}")
    print(f"  {bold('EMAIL REGISTRY')} — {cyan(str(total))} accounts across all providers")
    print(f"{'='*64}\n")

    type_order = ["personal", "business", "service", "public", "unknown"]

    for t in type_order:
        accounts = by_type.pop(t, [])
        if not accounts:
            continue
        icon = type_icon(t)
        print(f"  {icon} {bold(t.upper())} ({len(accounts)})")
        print(f"  {'─'*56}")
        for email, info in sorted(accounts):
            s_icon = status_icon(info.get("status", "unknown"))
            provider = fmt_val(info.get("provider"))
            capsule = info.get("capsule")
            purpose = info.get("purpose", "")
            # Truncate purpose for display
            if purpose and len(purpose) > 40:
                purpose = purpose[:37] + "..."
            line = f"    {s_icon} {email:<35} {provider:<16}"
            if capsule and str(capsule).lower() not in ("null", "none", "~", ""):
                line += f"  [{capsule}]"
            print(line)
            if purpose:
                print(f"         {dim(purpose)}")
        print()

    # Remaining unknown types
    for t, accounts in by_type.items():
        print(f"  • {bold(t.upper())} ({len(accounts)})")
        print(f"  {'─'*56}")
        for email, info in sorted(accounts):
            s_icon = status_icon(info.get("status", "unknown"))
            provider = fmt_val(info.get("provider"))
            print(f"    {s_icon} {email:<35} {provider}")
        print()

    # Provider summary
    by_provider = {}
    for email, info in registry.items():
        if isinstance(info, dict):
            p = info.get("provider", "unknown")
            by_provider[p] = by_provider.get(p, 0) + 1

    print(f"  📊 {bold('By provider:')} {', '.join(f'{p}: {c}' for p, c in sorted(by_provider.items()))}")
    print()


def cmd_list(args):
    """List all accounts with optional filters."""
    registry = load_registry()
    results = []

    for email, info in registry.items():
        if not isinstance(info, dict):
            continue
        if args.provider and info.get("provider") != args.provider:
            continue
        if args.type and info.get("type") != args.type:
            continue
        if args.capsule and info.get("capsule") != args.capsule:
            continue
        if args.status and info.get("status") != args.status:
            continue
        results.append((email, info))

    if not results:
        print("No accounts match your filters.")
        return

    # Header
    print(f"\n{bold('Email'):<45} {bold('Provider'):<20} {bold('Type'):<12} {bold('Status'):<8} {bold('Capsule')}")
    print("─" * 100)

    for email, info in sorted(results):
        s_icon = status_icon(info.get("status", "unknown"))
        t_icon = type_icon(info.get("type", "unknown"))
        provider = fmt_val(info.get("provider"))
        t = info.get("type", "?")
        status = info.get("status", "?")
        capsule = info.get("capsule") or "—"
        if str(capsule).lower() in ("null", "none", "~"):
            capsule = "—"

        print(
            f"{s_icon} {email:<43} {color_provider_padded(provider)} "
            f"{t_icon} {t:<11} {green(status) if status == 'active' else yellow(status):<18} {capsule}"
        )

    print(f"\n{len(results)} account(s)")


def cmd_search(args):
    """Search accounts by email address or purpose text."""
    registry = load_registry()
    query = args.query.lower()
    results = []

    for email, info in registry.items():
        if not isinstance(info, dict):
            continue
        purpose = str(info.get("purpose", "")).lower()
        capsule = str(info.get("capsule", "")).lower()
        if query in email.lower() or query in purpose or query in capsule:
            results.append((email, info))

    if not results:
        print(f"No accounts matching '{args.query}'")
        return

    print(f"\n🔍 {len(results)} result(s) for '{cyan(args.query)}':\n")
    for email, info in sorted(results):
        s_icon = status_icon(info.get("status", "unknown"))
        print(f"  {s_icon} {bold(email)}")
        fields = [
            ("provider",    info.get("provider")),
            ("type",        info.get("type")),
            ("purpose",     info.get("purpose")),
            ("capsule",     info.get("capsule")),
            ("login",       info.get("login_method")),
            ("2fa",         info.get("2fa")),
            ("status",      info.get("status")),
            ("consolidation", info.get("consolidation")),
            ("notes",       info.get("notes")),
        ]
        for k, v in fields:
            if v and str(v).lower() not in ("null", "none", "~"):
                print(f"      {dim(k+':'):<20} {v}")
        print()


def cmd_add(args):
    """Add a new email account to the registry."""
    # Validate email format
    if "@" not in args.email or "." not in args.email.split("@")[-1]:
        print(f"❌ Invalid email address: {args.email}")
        sys.exit(1)

    registry = load_registry()

    if args.email in registry:
        print(f"⚠️  Account already exists: {args.email}")
        existing = registry[args.email]
        for k, v in existing.items():
            print(f"  {k}: {v}")
        sys.exit(1)

    entry = {
        "provider":       args.provider,
        "type":           args.type,
        "purpose":        args.purpose,
        "capsule":        args.capsule,
        "google_admin":   None,
        "login_method":   None,
        "2fa":            None,
        "recovery_email": None,
        "status":         "active",
        "consolidation":  None,
        "notes":          None,
    }

    # Append raw YAML to preserve existing comments and structure
    with open(REGISTRY_PATH, "a") as f:
        f.write(f"\n{args.email}:\n")
        for k, v in entry.items():
            if v is None:
                f.write(f"  {k}: null\n")
            else:
                # Quote string values that contain special chars
                if any(c in str(v) for c in ":#{}[]&*!|>'\"%@`"):
                    f.write(f'  {k}: "{v}"\n')
                else:
                    f.write(f"  {k}: {v}\n")

    print(f"✅ Added: {args.email}")
    for k, v in entry.items():
        print(f"  {k}: {v}")


def cmd_consolidation(args):
    """Show accounts that have been flagged for consolidation decisions."""
    registry = load_registry()
    results = []

    for email, info in registry.items():
        if not isinstance(info, dict):
            continue
        consolidation = info.get("consolidation")
        if consolidation and str(consolidation).lower() not in ("null", "none", "~"):
            results.append((email, info, str(consolidation)))

    if not results:
        print("No accounts flagged for consolidation.")
        return

    # Group by consolidation action
    by_action = {}
    for email, info, action in results:
        by_action.setdefault(action, []).append((email, info))

    action_icons = {
        "keep":   "✅",
        "merge":  "🔄",
        "retire": "🗑️ ",
    }

    print(f"\n{'='*60}")
    print(f"  {bold('CONSOLIDATION PLAN')} — {cyan(str(len(results)))} accounts flagged")
    print(f"{'='*60}\n")

    for action in ["keep", "merge", "retire"]:
        accounts = by_action.pop(action, [])
        if not accounts:
            continue
        icon = action_icons.get(action, "•")
        print(f"  {icon} {bold(action.upper())} ({len(accounts)})")
        print(f"  {'─'*50}")
        for email, info in sorted(accounts):
            purpose = info.get("purpose", "")
            provider = info.get("provider", "?")
            print(f"    {email:<40} {color_provider(provider)}")
            if purpose:
                print(f"         {dim(purpose)}")
        print()

    # Any other custom actions
    for action, accounts in by_action.items():
        print(f"  • {action.upper()} ({len(accounts)})")
        for email, info in sorted(accounts):
            print(f"    {email}")
        print()

    print(f"  💡 Tip: Use `add` or edit the YAML directly to update consolidation flags.")
    print()


def cmd_stats(args):
    """Summary statistics — counts by provider, type, status, and capsule."""
    registry = load_registry()

    if not registry:
        print("Registry is empty.")
        return

    total = 0
    by_provider = {}
    by_type = {}
    by_status = {}
    by_capsule = {}

    for email, info in registry.items():
        if not isinstance(info, dict):
            continue
        total += 1

        p = info.get("provider", "unknown") or "unknown"
        t = info.get("type", "unknown") or "unknown"
        s = info.get("status", "unknown") or "unknown"
        c = info.get("capsule") or None
        if str(c).lower() in ("null", "none", "~"):
            c = None

        by_provider[p] = by_provider.get(p, 0) + 1
        by_type[t] = by_type.get(t, 0) + 1
        by_status[s] = by_status.get(s, 0) + 1
        if c:
            by_capsule[c] = by_capsule.get(c, 0) + 1

    print(f"\n{'='*50}")
    print(f"  {bold('EMAIL REGISTRY STATS')} — {cyan(str(total))} total accounts")
    print(f"{'='*50}\n")

    def _print_section(title: str, data: dict):
        print(f"  {bold(title)}")
        print(f"  {'─'*40}")
        max_count = max(data.values()) if data else 1
        for key, count in sorted(data.items(), key=lambda x: -x[1]):
            bar_len = int((count / max_count) * 30) if max_count > 0 else 0
            bar = "█" * max(bar_len, 1)  # at least 1 block
            print(f"  {key:<22} {cyan(str(count)):>4}  {dim(bar)}")
        print()

    _print_section("By Provider", by_provider)
    _print_section("By Type", by_type)
    _print_section("By Status", by_status)
    if by_capsule:
        _print_section("By Capsule", by_capsule)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Email Registry CLI — centralized email account management",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
examples:
  python3 tools/email-registry/cli.py status
  python3 tools/email-registry/cli.py list --provider gmail
  python3 tools/email-registry/cli.py list --capsule my-capsule
  python3 tools/email-registry/cli.py search "example.com"
  python3 tools/email-registry/cli.py add --email foo@bar.com --provider gmail --type personal --purpose "Test"
  python3 tools/email-registry/cli.py consolidation
  python3 tools/email-registry/cli.py stats
        """,
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # status
    sub.add_parser("status", help="Overview grouped by type (personal/business/service/public)")

    # list
    p_list = sub.add_parser("list", help="List all accounts with optional filters")
    p_list.add_argument("--provider", help="Filter by provider (gmail, resend, etc.)")
    p_list.add_argument("--type", help="Filter by type (personal, business, service, public)")
    p_list.add_argument("--capsule", help="Filter by capsule name")
    p_list.add_argument("--status", help="Filter by status (active, inactive, deprecated)")

    # search
    p_search = sub.add_parser("search", help="Search by email address or purpose text")
    p_search.add_argument("query", help="Search query")

    # add
    p_add = sub.add_parser("add", help="Add a new email account to the registry")
    p_add.add_argument("--email", required=True, help="Email address to add")
    p_add.add_argument("--provider", required=True, help="Provider (gmail, resend, custom-domain, etc.)")
    p_add.add_argument("--type", required=True, help="Type (personal, business, service, public)")
    p_add.add_argument("--purpose", required=True, help="Human-readable purpose description")
    p_add.add_argument("--capsule", default=None, help="Capsule name (optional)")

    # consolidation
    sub.add_parser("consolidation", help="Show accounts flagged for consolidation decisions")

    # stats
    sub.add_parser("stats", help="Summary stats by provider, type, status, capsule")

    args = parser.parse_args()

    commands = {
        "status":       cmd_status,
        "list":         cmd_list,
        "search":       cmd_search,
        "add":          cmd_add,
        "consolidation": cmd_consolidation,
        "stats":        cmd_stats,
    }

    if args.command in commands:
        commands[args.command](args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
