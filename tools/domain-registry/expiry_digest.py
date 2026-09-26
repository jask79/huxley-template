#!/usr/bin/env python3
"""
Domain Expiry Digest — weekly Telegram report of domains nearing expiration.

Reads the domain registry, buckets every domain by days-to-expiry, and sends
a formatted digest to your Telegram bot.

Requires the `telegram-bot-token` Keychain item (account: huxley) and the
TELEGRAM_CHAT_ID environment variable; without them the digest silently
no-ops.

Usage:
    .venv/bin/python3 tools/domain-registry/expiry_digest.py            # send to Telegram
    .venv/bin/python3 tools/domain-registry/expiry_digest.py --dry-run  # print to stdout, no send

Buckets:
    🔴 Critical: <30 days        🟡 Soon: 30-60 days
    🟢 Upcoming: 60-90 days      ⚪ Unknown expiry
"""

from __future__ import annotations

import argparse
import json
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime
import os
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
CATALYST_ROOT = SCRIPT_DIR.parent.parent
REGISTRY_PATH = CATALYST_ROOT / "global" / "config" / "domain-registry.yaml"

OWNER_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")
KEYCHAIN_SERVICE = "telegram-bot-token"
KEYCHAIN_ACCOUNT = "huxley"

# Skip these statuses — they're not "active domains we need to renew"
SKIP_STATUSES = {"for-sale", "expired", "released"}


def load_registry() -> dict:
    """Load registry YAML using PyYAML from .venv."""
    try:
        import yaml
    except ImportError:
        sys.stderr.write(
            "ERROR: PyYAML not installed. Run with .venv/bin/python3.\n"
        )
        sys.exit(1)
    if not REGISTRY_PATH.exists():
        sys.stderr.write(f"ERROR: registry not found at {REGISTRY_PATH}\n")
        sys.exit(1)
    try:
        return yaml.safe_load(REGISTRY_PATH.read_text()) or {}
    except yaml.YAMLError as e:
        sys.stderr.write(f"ERROR: failed to parse registry YAML: {e}\n")
        sys.exit(1)


def parse_expiry(raw) -> date | None:
    """Coerce expiry to a date. Returns None for unknown/unparseable."""
    if raw is None:
        return None
    if isinstance(raw, date):
        return raw
    s = str(raw).strip().strip("'\"")
    if not s or s.lower() == "unknown":
        return None
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


def bucket_domains(registry: dict, today: date) -> tuple[dict, int, int]:
    """Group domains by urgency bucket.

    Returns (buckets, total_scanned, total_skipped). total_scanned counts every
    domain considered (excluding for-sale/expired); domains >90 days out with
    a known expiry are not added to any bucket.
    """
    buckets = {"expired": [], "critical": [], "soon": [], "upcoming": [], "unknown": []}
    total_scanned = 0
    total_skipped = 0

    for domain, meta in registry.items():
        if not isinstance(meta, dict):
            continue
        if meta.get("status") in SKIP_STATUSES:
            total_skipped += 1
            continue
        total_scanned += 1

        expiry = parse_expiry(meta.get("expires"))
        # Note: for unknown-bucket entries, `expiry` and `days` are both None.
        # Dict shape kept consistent across buckets — consumers must handle None.
        entry = {
            "domain": domain,
            "registrar": meta.get("registrar", "?"),
            "auto_renew": meta.get("auto_renew"),
            "capsule": meta.get("capsule", "n/a"),
            "status": meta.get("status", "?"),
            "expiry": expiry,
            "days": (expiry - today).days if expiry else None,
        }

        if expiry is None:
            buckets["unknown"].append(entry)
        elif entry["days"] < 0:
            buckets["expired"].append(entry)
        elif entry["days"] < 30:
            buckets["critical"].append(entry)
        elif entry["days"] < 60:
            buckets["soon"].append(entry)
        elif entry["days"] < 90:
            buckets["upcoming"].append(entry)
        # else: not in any bucket (>90 days out, no need to alert)

    # Sort each bucket by days ascending (most urgent first)
    for key in ("expired", "critical", "soon", "upcoming"):
        buckets[key].sort(key=lambda x: x["days"])
    buckets["unknown"].sort(key=lambda x: x["domain"])
    return buckets, total_scanned, total_skipped


def format_entry(e: dict) -> str:
    """One-line entry for the digest. Plain text — no Markdown formatting."""
    auto = ""
    if e["auto_renew"] is True:
        auto = " 🔄"  # auto-renew on
    elif e["auto_renew"] is False:
        auto = " ⚠️ no auto-renew"

    if e["expiry"] is not None:
        if e["days"] < 0:
            days_str = f"EXPIRED {abs(e['days'])}d ago ({e['expiry'].isoformat()})"
        else:
            days_str = f"{e['days']}d ({e['expiry'].isoformat()})"
    else:
        days_str = "unknown"

    cap = f" · {e['capsule']}" if e["capsule"] and e["capsule"] != "n/a" else ""
    return f"• {e['domain']} — {days_str} · {e['registrar']}{cap}{auto}"


def format_digest(buckets: dict, today: date, total_scanned: int) -> str:
    lines = [f"🌐 Domain Expiry Digest — {today.isoformat()}", ""]

    sections = [
        ("expired", "⚠️ EXPIRED — past due"),
        ("critical", "🔴 Critical (<30 days)"),
        ("soon", "🟡 Soon (30-60 days)"),
        ("upcoming", "🟢 Upcoming (60-90 days)"),
        ("unknown", "⚪ Unknown expiry — needs classification"),
    ]

    total_alerts = sum(len(buckets[k]) for k, _ in sections)
    if total_alerts == 0:
        lines.append(f"✅ All {total_scanned} domains healthy — no expirations within 90 days.")
        return "\n".join(lines)

    for key, header in sections:
        items = buckets[key]
        if not items:
            continue
        lines.append(f"{header} — {len(items)}")
        for entry in items:
            lines.append(format_entry(entry))
        lines.append("")

    healthy = total_scanned - total_alerts
    lines.append(
        f"{total_alerts} flagged · {healthy} healthy (>90d) · {total_scanned} total in registry"
    )
    return "\n".join(lines)


def _truncate_for_telegram(
    message: str,
    buckets: dict,
    today: date,
    total_scanned: int,
    max_len: int = 4000,
) -> str:
    """If message exceeds Telegram's limit, drop unknown-bucket entries until it fits.

    Critical/soon/upcoming/expired stay intact — those are the actionable items.
    """
    if len(message) <= max_len:
        return message

    unknown = list(buckets.get("unknown", []))
    hidden = 0
    truncated_buckets = {k: list(v) for k, v in buckets.items()}

    while unknown and len(message) > max_len:
        # Drop one unknown entry at a time (from the end — already alpha-sorted)
        unknown.pop()
        hidden += 1
        truncated_buckets["unknown"] = unknown
        rendered = format_digest(truncated_buckets, today, total_scanned)
        suffix = f"\n… and {hidden} more unknown-expiry domains hidden"
        message = rendered + suffix

    # If still too long after dropping all unknowns, hard-truncate as last resort.
    if len(message) > max_len:
        message = message[: max_len - 20] + "\n… [truncated]"
    return message


def get_bot_token() -> str:
    result = subprocess.run(
        [
            "security",
            "find-generic-password",
            "-s", KEYCHAIN_SERVICE,
            "-a", KEYCHAIN_ACCOUNT,
            "-w",
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        sys.stderr.write(
            f"ERROR: Could not retrieve Telegram bot token from Keychain "
            f"(service={KEYCHAIN_SERVICE}, account={KEYCHAIN_ACCOUNT}).\n"
        )
        sys.exit(2)
    token = result.stdout.strip()
    del result  # drop subprocess result object holding the token in memory
    return token


def send_telegram(message: str) -> dict:
    """Send a message via your Telegram bot.

    Plain-text only (no parse_mode) — registry values may contain unbalanced
    Markdown characters (_ * ` [ () that would cause Telegram 400 errors.
    Emoji + bullet structure provides sufficient visual hierarchy.

    Retries once with backoff on transient errors. Honors Telegram 429
    retry_after. Never logs the bot token URL.
    """
    token = get_bot_token()
    # NEVER log this URL — it contains the bot token.
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    data = urllib.parse.urlencode({
        "chat_id": OWNER_CHAT_ID,
        "text": message,
        "disable_web_page_preview": "true",
    }).encode("utf-8")

    def _attempt() -> dict:
        req = urllib.request.Request(url, data=data, method="POST")
        with urllib.request.urlopen(req, timeout=15) as resp:
            body = resp.read().decode("utf-8")
            return json.loads(body)

    attempts = 0
    last_error = "unknown error"
    while attempts < 2:
        attempts += 1
        try:
            return _attempt()
        except urllib.error.HTTPError as e:
            # Do NOT include e.url or repr(e) — bot token leaks via URL.
            status = getattr(e, "code", "?")
            retry_after = None
            try:
                err_body = e.read().decode("utf-8", errors="replace")
                err_json = json.loads(err_body)
                # Telegram rate-limit hint
                retry_after = (err_json.get("parameters") or {}).get("retry_after")
            except (json.JSONDecodeError, OSError, AttributeError):
                err_json = None
            last_error = f"HTTP {status} from Telegram API"
            sys.stderr.write(f"send_telegram: {last_error}\n")
            if attempts < 2:
                delay = retry_after if isinstance(retry_after, (int, float)) else 5
                time.sleep(delay)
                continue
            return {"ok": False, "error": last_error}
        except urllib.error.URLError as e:
            # URLError.reason may include hostname but not the token path.
            last_error = f"network error: {e.reason}"
            sys.stderr.write(f"send_telegram: {last_error}\n")
            if attempts < 2:
                time.sleep(5)
                continue
            return {"ok": False, "error": last_error}
        except (TimeoutError, socket.timeout):
            last_error = "request timed out"
            sys.stderr.write(f"send_telegram: {last_error}\n")
            if attempts < 2:
                time.sleep(5)
                continue
            return {"ok": False, "error": last_error}
        except json.JSONDecodeError:
            last_error = "invalid JSON response from Telegram API"
            sys.stderr.write(f"send_telegram: {last_error}\n")
            if attempts < 2:
                time.sleep(5)
                continue
            return {"ok": False, "error": last_error}

    return {"ok": False, "error": last_error}


def _parse_date(s: str) -> date:
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except ValueError:
        raise argparse.ArgumentTypeError(f"Expected YYYY-MM-DD, got: {s}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print digest to stdout instead of sending to Telegram.",
    )
    parser.add_argument(
        "--today",
        type=_parse_date,
        help="Override today's date (YYYY-MM-DD) for testing.",
    )
    args = parser.parse_args()

    today = args.today or date.today()

    registry = load_registry()
    buckets, total_scanned, _ = bucket_domains(registry, today)
    message = format_digest(buckets, today, total_scanned)
    message = _truncate_for_telegram(message, buckets, today, total_scanned)

    if args.dry_run:
        print(message)
        return 0

    result = send_telegram(message)
    if not result.get("ok"):
        sys.stderr.write(f"Telegram send failed: {result}\n")
        return 3
    message_id = result.get("result", {}).get("message_id", "?")
    print(f"✅ Digest sent (message_id={message_id})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
