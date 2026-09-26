"""
YouTube Intel CLI — poller subcommand

Provides manual control and status inspection for the automated poller.

Commands:
  youtube-intel poller run     — Run one full poll cycle immediately
  youtube-intel poller status  — Show last poll time and tracked counts
"""

import sys
from pathlib import Path

# Resolve paths relative to the tool directory so imports always work
TOOL_DIR = Path(__file__).resolve().parent.parent
CATALYST_ROOT = TOOL_DIR.parent.parent
DB_PATH = CATALYST_ROOT / "monitoring" / "youtube-intel.db"
LOG_PATH = CATALYST_ROOT / "logs" / "youtube-intel-poller.log"

# Terminal colours (re-declared to avoid circular imports from cli.py)
GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
CYAN   = "\033[96m"
BOLD   = "\033[1m"
DIM    = "\033[2m"
RESET  = "\033[0m"


def _cmd_run(args) -> int:
    """Run one poll cycle immediately (vph, competitors, or all)."""
    from poller import run_poll

    mode    = getattr(args, "poller_mode", "vph")
    dry_run = getattr(args, "dry_run", False)

    print(f"{CYAN}{BOLD}YouTube Intel Poller{RESET} — running mode={BOLD}{mode}{RESET}"
          + (f"  {YELLOW}[dry-run]{RESET}" if dry_run else ""))
    print(f"{DIM}Log: {LOG_PATH}{RESET}\n")

    exit_code = run_poll(mode=mode, dry_run=dry_run, log_path=LOG_PATH)

    if exit_code == 0:
        print(f"\n{GREEN}Poll complete.{RESET}")
    else:
        print(f"\n{RED}Poll finished with errors — check {LOG_PATH}{RESET}",
              file=sys.stderr)

    return exit_code


def _cmd_status(args) -> int:  # noqa: ARG001
    """Show last poll time and counts of tracked videos / competitors."""
    import sqlite3
    from db import get_connection

    if not DB_PATH.exists():
        print(f"{RED}Database not found:{RESET} {DB_PATH}", file=sys.stderr)
        print(f"{YELLOW}Initialize with:{RESET} "
              f"sqlite3 {DB_PATH} < tools/youtube-intel/schema.sql", file=sys.stderr)
        return 1

    try:
        conn = get_connection()
        conn.row_factory = sqlite3.Row

        # Tracked videos
        videos_row = conn.execute(
            "SELECT COUNT(*) AS total, "
            "SUM(CASE WHEN tracking_active=1 THEN 1 ELSE 0 END) AS active "
            "FROM tracked_videos"
        ).fetchone()

        # Competitors
        comp_count = conn.execute(
            "SELECT COUNT(*) AS total FROM competitors"
        ).fetchone()["total"]

        # Last VPH snapshot
        last_vph = conn.execute(
            "SELECT snapshot_time FROM vph_snapshots ORDER BY snapshot_time DESC LIMIT 1"
        ).fetchone()

        # Last competitor snapshot
        last_comp = conn.execute(
            "SELECT snapshot_time FROM competitor_snapshots ORDER BY snapshot_time DESC LIMIT 1"
        ).fetchone()

        conn.close()
    except sqlite3.Error as exc:
        print(f"{RED}Database error:{RESET} {exc}", file=sys.stderr)
        return 1

    # LaunchAgent status
    import subprocess
    la_status = "unknown"
    try:
        result = subprocess.run(
            ["launchctl", "list", "com.huxley.youtube-intel-poller"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0:
            la_status = f"{GREEN}loaded{RESET}"
        else:
            la_status = (
                f"{YELLOW}not loaded{RESET}  "
                f"{DIM}(cp tools/youtube-intel/com.huxley.youtube-intel-poller.plist "
                f"~/Library/LaunchAgents/ && "
                f"launchctl load ~/Library/LaunchAgents/com.huxley.youtube-intel-poller.plist){RESET}"
            )
    except Exception:
        la_status = f"{DIM}(launchctl unavailable){RESET}"

    total_videos  = videos_row["total"]  if videos_row  else 0
    active_videos = videos_row["active"] if videos_row  else 0

    print(f"\n{BOLD}YouTube Intel Poller — Status{RESET}")
    print(f"{'LaunchAgent':<22} {la_status}")
    print(f"{'Tracked videos':<22} {GREEN}{active_videos} active{RESET} / {total_videos} total")
    print(f"{'Competitor channels':<22} {comp_count}")
    print(f"{'Last VPH snapshot':<22} "
          + (f"{CYAN}{last_vph['snapshot_time']}{RESET}" if last_vph else f"{DIM}(none yet){RESET}"))
    print(f"{'Last competitor snap':<22} "
          + (f"{CYAN}{last_comp['snapshot_time']}{RESET}" if last_comp else f"{DIM}(none yet){RESET}"))
    print(f"\n{DIM}Log: {LOG_PATH}"
          f"\nManual run: youtube-intel poller run{RESET}\n")

    return 0


def run(client, args) -> int:  # noqa: ARG001 — client unused (no API calls for status)
    """Route poller subcommand to the correct handler."""
    action = getattr(args, "poller_action", None)

    if action == "run":
        return _cmd_run(args)
    elif action == "status":
        return _cmd_status(args)
    else:
        print(f"{YELLOW}Usage:{RESET}  youtube-intel poller <run|status>", file=sys.stderr)
        print(f"  {DIM}run     — poll now (one cycle){RESET}")
        print(f"  {DIM}status  — show last poll time and tracked counts{RESET}")
        return 1
