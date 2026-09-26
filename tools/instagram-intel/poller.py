#!/usr/bin/env python3
"""
Instagram Intel — Automated Trend + Insights Poller

Standalone polling script for automated data collection.
Designed to be invoked by macOS LaunchAgent hourly:
  - `trending` mode: Trending Reels + trending audio via Playwright scraping
  - `insights` mode: Own account insights via Meta Graph API (requires token)
  - `all` mode: both trending and insights

Architecture:
    Imports existing instagram-intel scrapers and Graph API client — no code
    duplication with cli.py. Writes snapshots to SQLite at
    monitoring/instagram-intel.db.

Auth:
    trending: No auth required — Playwright scraping (Phase 2)
    insights: Meta Graph API token (resolved from .env / Keychain per cli.py)

Usage:
    python3 poller.py --mode trending          # Trending reels + audio
    python3 poller.py --mode insights          # Own account insights
    python3 poller.py --mode all               # Both
    python3 poller.py --mode all --dry-run     # Dry run (no DB writes)

    # Via cli.py poller subcommand:
    python3 cli.py poller run --mode all
    python3 cli.py poller run --mode trending --dry-run
    python3 cli.py poller status

LaunchAgent:
    com.huxley.instagram-intel-poller.plist — not shipped; copy
    tools/youtube-intel/com.huxley.youtube-intel-poller.plist and adapt it (every hour)

Log file: {{CATALYST_ROOT}}/logs/instagram-intel-poller.log
Database:  {{CATALYST_ROOT}}/monitoring/instagram-intel.db
"""

import argparse
import json
import logging
import sqlite3
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

# ---------------------------------------------------------------------------
# Path setup — must happen before importing sibling modules
# ---------------------------------------------------------------------------
TOOL_DIR = Path(__file__).resolve().parent
CATALYST_ROOT = TOOL_DIR.parent.parent
DB_PATH = CATALYST_ROOT / "monitoring" / "instagram-intel.db"
LOG_PATH = CATALYST_ROOT / "logs" / "instagram-intel-poller.log"

# Register the instagram_intel package for direct script invocation.
# cli.py already bootstraps the package; poller.py must do the same when
# invoked standalone by the LaunchAgent.
_TOOL_PARENT = str(TOOL_DIR.parent)
if _TOOL_PARENT not in sys.path:
    sys.path.insert(0, _TOOL_PARENT)

import importlib.util as _ilu


def _bootstrap_package():
    """Register instagram_intel package in sys.modules (idempotent)."""
    if "instagram_intel" in sys.modules:
        return

    pkg_spec = _ilu.spec_from_file_location(
        "instagram_intel",
        TOOL_DIR / "__init__.py",
        submodule_search_locations=[str(TOOL_DIR)],
    )
    pkg = _ilu.module_from_spec(pkg_spec)
    sys.modules["instagram_intel"] = pkg
    pkg_spec.loader.exec_module(pkg)

    # Core modules
    for mod_name in [
        "config",
        "exceptions",
        "models",
        "formatters",
        "cache",
        "scoring",
        "analytics",
        "dedup",
        "benchmarks",
    ]:
        full = f"instagram_intel.{mod_name}"
        mod_path = TOOL_DIR / f"{mod_name}.py"
        if full not in sys.modules and mod_path.exists():
            spec = _ilu.spec_from_file_location(full, mod_path)
            mod = _ilu.module_from_spec(spec)
            sys.modules[full] = mod
            spec.loader.exec_module(mod)

    # Clients sub-package
    clients_dir = TOOL_DIR / "clients"
    if clients_dir.exists() and "instagram_intel.clients" not in sys.modules:
        cp_spec = _ilu.spec_from_file_location(
            "instagram_intel.clients",
            clients_dir / "__init__.py",
            submodule_search_locations=[str(clients_dir)],
        )
        cp = _ilu.module_from_spec(cp_spec)
        sys.modules["instagram_intel.clients"] = cp
        cp_spec.loader.exec_module(cp)

        for client_mod in ["graph_api"]:
            full = f"instagram_intel.clients.{client_mod}"
            mod_path = clients_dir / f"{client_mod}.py"
            if full not in sys.modules and mod_path.exists():
                spec = _ilu.spec_from_file_location(full, mod_path)
                mod = _ilu.module_from_spec(spec)
                sys.modules[full] = mod
                spec.loader.exec_module(mod)

    # Commands sub-package
    cmds_dir = TOOL_DIR / "commands"
    if cmds_dir.exists() and "instagram_intel.commands" not in sys.modules:
        cmd_spec = _ilu.spec_from_file_location(
            "instagram_intel.commands",
            cmds_dir / "__init__.py",
            submodule_search_locations=[str(cmds_dir)],
        )
        cmd_pkg = _ilu.module_from_spec(cmd_spec)
        sys.modules["instagram_intel.commands"] = cmd_pkg
        cmd_spec.loader.exec_module(cmd_pkg)

        for cmd_mod in [
            "_scraper_utils",
            "account",
            "cache_cmds",
            "compare",
            "competitor",
            "engagement",
            "hashtag",
            "insights",
            "profile",
            "search",
            "trending",
        ]:
            full = f"instagram_intel.commands.{cmd_mod}"
            mod_path = cmds_dir / f"{cmd_mod}.py"
            if full not in sys.modules and mod_path.exists():
                spec = _ilu.spec_from_file_location(full, mod_path)
                mod = _ilu.module_from_spec(spec)
                sys.modules[full] = mod
                spec.loader.exec_module(mod)


_bootstrap_package()


# ---------------------------------------------------------------------------
# Logging — write to file + stderr simultaneously
# ---------------------------------------------------------------------------


def _setup_logging(log_path: Path) -> logging.Logger:
    """Configure logging to both file and stderr."""
    logger = logging.getLogger("instagram-intel-poller")
    if logger.hasHandlers():
        return logger
    log_path.parent.mkdir(parents=True, exist_ok=True)
    logger.setLevel(logging.DEBUG)

    fmt = logging.Formatter(
        "%(asctime)s  %(levelname)-8s  %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )

    # File handler — DEBUG and above
    fh = logging.FileHandler(log_path, encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(fmt)
    logger.addHandler(fh)

    # Stderr handler — INFO and above (visible in LaunchAgent Console output)
    sh = logging.StreamHandler(sys.stderr)
    sh.setLevel(logging.INFO)
    sh.setFormatter(fmt)
    logger.addHandler(sh)

    return logger


log: logging.Logger = logging.getLogger("instagram-intel-poller")


# ---------------------------------------------------------------------------
# Database — schema init + write helpers
# ---------------------------------------------------------------------------


def _init_db(db_path: Path) -> sqlite3.Connection:
    """
    Open the instagram-intel SQLite database, creating it + schema if needed.

    Schema:
      trending_snapshots — one row per poll cycle per trend type
        id         — auto-increment PK
        ts         — ISO 8601 UTC timestamp of the snapshot
        type       — 'reels' | 'audio'
        item_count — number of items captured
        data       — JSON array of raw trend items

      insight_snapshots — one row per poll cycle per period
        id         — auto-increment PK
        ts         — ISO 8601 UTC timestamp
        period     — period string ('day', 'week', 'days_28', 'lifetime')
        item_count — number of insight metrics captured
        data       — JSON array of insight metric dicts
    """
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row

    conn.executescript("""
        PRAGMA journal_mode = WAL;
        PRAGMA foreign_keys = ON;

        CREATE TABLE IF NOT EXISTS trending_snapshots (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            ts         TEXT    NOT NULL,
            type       TEXT    NOT NULL,
            item_count INTEGER NOT NULL DEFAULT 0,
            data       TEXT    NOT NULL DEFAULT '[]'
        );

        CREATE INDEX IF NOT EXISTS idx_ig_trending_ts
            ON trending_snapshots (ts);
        CREATE INDEX IF NOT EXISTS idx_ig_trending_type
            ON trending_snapshots (type, ts);

        CREATE TABLE IF NOT EXISTS insight_snapshots (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            ts         TEXT    NOT NULL,
            period     TEXT    NOT NULL DEFAULT 'day',
            item_count INTEGER NOT NULL DEFAULT 0,
            data       TEXT    NOT NULL DEFAULT '[]'
        );

        CREATE INDEX IF NOT EXISTS idx_ig_insight_ts
            ON insight_snapshots (ts);
        CREATE INDEX IF NOT EXISTS idx_ig_insight_period
            ON insight_snapshots (period, ts);
    """)
    conn.commit()
    return conn


def _insert_trending_snapshot(
    conn: sqlite3.Connection,
    trend_type: str,
    items: list[dict],
) -> None:
    """Insert one trending snapshot row."""
    ts = datetime.now(UTC).isoformat()
    conn.execute(
        "INSERT INTO trending_snapshots (ts, type, item_count, data) VALUES (?, ?, ?, ?)",
        (ts, trend_type, len(items), json.dumps(items, default=str)),
    )
    conn.commit()


def _insert_insight_snapshot(
    conn: sqlite3.Connection,
    period: str,
    items: list[dict],
) -> None:
    """Insert one insight snapshot row."""
    ts = datetime.now(UTC).isoformat()
    conn.execute(
        "INSERT INTO insight_snapshots (ts, period, item_count, data) VALUES (?, ?, ?, ?)",
        (ts, period, len(items), json.dumps(items, default=str)),
    )
    conn.commit()


# ---------------------------------------------------------------------------
# Poll modes
# ---------------------------------------------------------------------------


class _MockArgs:
    """Minimal args namespace to satisfy scraper + client constructors."""

    def __init__(
        self,
        headless: bool = True,
        no_cache: bool = True,
        cache_ttl: int = 0,
        brand: str | None = None,
    ):
        self.no_headless = not headless
        self.no_cache = no_cache
        self.cache_ttl = cache_ttl
        self.brand = brand
        self.verbose = False
        self.json = False
        self.dry_run = False
        self.output_dir = None
        self.sort = "none"
        # insights-specific defaults
        self.period = "day"
        self.since = ""
        self.until = ""


def poll_trending(conn: sqlite3.Connection, dry_run: bool = False) -> None:
    """
    Fetch trending Reels and trending audio via Playwright scraping.

    Uses instagram_intel.commands.trending module — same scraper as the CLI.
    Stores two snapshot rows: one for 'reels', one for 'audio'.
    """
    log.info("--- Trending poll started ---")

    # Import the scraper runner from the commands layer
    from instagram_intel.commands._scraper_utils import run_scraper  # noqa

    args_mock = _MockArgs(headless=True)

    for trend_type in ("reels", "audio"):
        log.info("Scraping trending %s", trend_type)
        try:
            if trend_type == "reels":
                result = run_scraper(
                    lambda s: s.get_trending_reels(limit=30),
                    args_mock,
                    command="trending-reels",
                    filters={},
                    format_map={},
                )
            else:
                result = run_scraper(
                    lambda s: s.get_trending_audio(limit=30),
                    args_mock,
                    command="trending-audio",
                    filters={},
                    format_map={},
                )

            if result is None:
                log.warning("Scraper returned None for trending %s", trend_type)
                continue

            # run_scraper returns either a ScrapeResult or an int (exit code)
            if isinstance(result, int):
                log.warning("Scraper returned exit code %d for trending %s", result, trend_type)
                continue

            # Normalize to plain dicts
            items: list[dict] = []
            for item in result.data or []:
                if hasattr(item, "to_dict"):
                    items.append(item.to_dict())
                elif isinstance(item, dict):
                    items.append(item)

            log.debug("  trending %s: %d items", trend_type, len(items))

            if dry_run:
                log.info(
                    "[DRY-RUN] trending_snapshots: %s → %d items",
                    trend_type,
                    len(items),
                )
            else:
                _insert_trending_snapshot(conn, trend_type, items)

        except Exception as exc:
            log.error("Failed to scrape trending %s: %s", trend_type, exc)
            continue

    log.info("Trending poll complete")


def poll_insights(
    conn: sqlite3.Connection,
    period: str = "day",
    dry_run: bool = False,
) -> None:
    """
    Fetch own account insights via Meta Graph API and store a snapshot.

    Requires a valid Meta access token (resolved via cli.py credential chain).
    If credentials are missing, logs a warning and returns (non-fatal — the
    trending poll will still succeed).
    """
    log.info("--- Insights poll started (period=%s) ---", period)

    try:
        from instagram_intel.clients.graph_api import (
            BrandCredentialLoader,
            InstagramGraphClient,
            resolve_brand,
        )
        from instagram_intel.config import (
            ENV_IG_USER_ID,
            ENV_META_APP_ID,
            ENV_META_APP_SECRET,
            ENV_META_TOKEN,
            KEYCHAIN_META_APP_ID,
            KEYCHAIN_META_APP_SECRET,
            KEYCHAIN_META_TOKEN,
        )
        from instagram_intel.exceptions import CredentialError
    except ImportError as exc:
        log.error("Failed to import Graph API client: %s", exc)
        return

    # Resolve credentials — mirror the exact chain used by cli.py _init_client()
    try:
        brand = resolve_brand(None)
        loader = BrandCredentialLoader(brand)
        access_token = loader.require(
            ENV_META_TOKEN,
            KEYCHAIN_META_TOKEN,
            label="Meta access token",
        )
    except CredentialError as exc:
        log.warning("Insights poll skipped — no Meta credentials: %s", exc)
        return
    except Exception as exc:
        log.warning("Insights poll skipped — credential resolution failed: %s", exc)
        return

    app_id = loader.get(ENV_META_APP_ID, KEYCHAIN_META_APP_ID) or ""
    app_secret = loader.get(ENV_META_APP_SECRET, KEYCHAIN_META_APP_SECRET) or ""

    # IG user ID — env/cache first, then auto-discover
    _ig_cache = Path.home() / ".instagram-intel" / "config.json"
    ig_user_id = loader.get(ENV_IG_USER_ID) or ""
    if not ig_user_id and _ig_cache.exists():
        try:
            ig_user_id = json.loads(_ig_cache.read_text()).get("ig_user_id", "")
        except (json.JSONDecodeError, OSError):
            pass

    if not ig_user_id:
        log.warning(
            "Insights poll skipped — META_IG_USER_ID not set and auto-discovery "
            "not attempted from poller. Run `instagram-intel account` once to cache it."
        )
        return

    try:
        client = InstagramGraphClient(
            access_token=access_token,
            ig_user_id=ig_user_id,
            app_id=app_id,
            app_secret=app_secret,
        )

        # Fetch metrics — same split used by cmd_own_insights
        from instagram_intel.config import (
            ACCOUNT_METRICS_TIME_SERIES,
            ACCOUNT_METRICS_TOTAL_VALUE,
        )

        insights = []
        if period == "lifetime":
            from instagram_intel.config import ACCOUNT_METRICS_LIFETIME

            insights = client.get_account_insights(
                metrics=ACCOUNT_METRICS_LIFETIME,
                period=period,
            )
        else:
            if ACCOUNT_METRICS_TIME_SERIES:
                try:
                    ts_insights = client.get_account_insights(
                        metrics=ACCOUNT_METRICS_TIME_SERIES,
                        period=period,
                    )
                    insights.extend(ts_insights)
                except Exception as exc:
                    log.debug("Time-series metrics failed: %s", exc)

            if ACCOUNT_METRICS_TOTAL_VALUE:
                try:
                    tv_insights = client.get_account_insights(
                        metrics=ACCOUNT_METRICS_TOTAL_VALUE,
                        period=period,
                        metric_type="total_value",
                    )
                    insights.extend(tv_insights)
                except Exception as exc:
                    log.debug("Total-value metrics failed: %s", exc)

        data = [i.to_dict() if hasattr(i, "to_dict") else dict(i) for i in insights]
        log.debug("  insights: %d metrics fetched (period=%s)", len(data), period)

        if dry_run:
            log.info("[DRY-RUN] insight_snapshots: period=%s → %d metrics", period, len(data))
        else:
            _insert_insight_snapshot(conn, period, data)

        log.info("Insights poll complete — %d metrics stored (period=%s)", len(data), period)

    except Exception as exc:
        log.error("Insights poll failed: %s", exc)


# ---------------------------------------------------------------------------
# Status query
# ---------------------------------------------------------------------------


def status(db_path: Path) -> None:
    """Print poll status: last run times and row counts per table."""
    if not db_path.exists():
        print(f"Database not found: {db_path}")
        print("Run 'poller run' at least once to initialize.")
        return

    with sqlite3.connect(str(db_path)) as conn:
        conn.row_factory = sqlite3.Row

        print("\nInstagram Intel Poller — Status")
        print(f"Database: {db_path}\n")

        # trending_snapshots
        rows = conn.execute(
            "SELECT type, COUNT(*) AS cnt, MAX(ts) AS last_ts "
            "FROM trending_snapshots GROUP BY type ORDER BY type"
        ).fetchall()
        if rows:
            print("  Trending snapshots:")
            for r in rows:
                print(f"    {r['type']:8s}  {r['cnt']:5d} snapshots  last: {r['last_ts']}")
        else:
            print("  Trending snapshots: (none)")

        # insight_snapshots
        rows = conn.execute(
            "SELECT period, COUNT(*) AS cnt, MAX(ts) AS last_ts "
            "FROM insight_snapshots GROUP BY period ORDER BY period"
        ).fetchall()
        if rows:
            print("\n  Insight snapshots:")
            for r in rows:
                print(f"    {r['period']:10s}  {r['cnt']:5d} snapshots  last: {r['last_ts']}")
        else:
            print("\n  Insight snapshots: (none)")

        total_trending = conn.execute("SELECT COUNT(*) FROM trending_snapshots").fetchone()[0]
        total_insights = conn.execute("SELECT COUNT(*) FROM insight_snapshots").fetchone()[0]
        print(
            f"\n  Total rows: {total_trending + total_insights:,}  "
            f"(trending: {total_trending:,}, insights: {total_insights:,})"
        )


# ---------------------------------------------------------------------------
# Entry point — run_poll() is called from cli.py poller command too
# ---------------------------------------------------------------------------


def run_poll(
    mode: str,
    period: str = "day",
    dry_run: bool = False,
    log_path: Path = LOG_PATH,
) -> int:
    """
    Run one full poll cycle.

    Called from:
      - main()                      — standalone / LaunchAgent
      - cli.py `poller run` command — via cli.py dispatch

    Returns exit code (0 = success, 1 = error).
    """
    global log
    log = _setup_logging(log_path)

    log.info(
        "=== instagram-intel-poller starting (mode=%s, period=%s, dry_run=%s) ===",
        mode,
        period,
        dry_run,
    )

    start_time = time.time()
    exit_code = 0

    try:
        with _init_db(DB_PATH) as conn:
            if mode in ("trending", "all"):
                poll_trending(conn, dry_run=dry_run)

            if mode in ("insights", "all"):
                poll_insights(conn, period=period, dry_run=dry_run)

    except KeyboardInterrupt:
        log.info("Interrupted")
        exit_code = 0
    except Exception as exc:
        log.exception("Unexpected error during poll: %s", exc)
        exit_code = 1
    finally:
        elapsed = time.time() - start_time
        log.info(
            "=== instagram-intel-poller finished in %.1fs (exit=%d) ===",
            elapsed,
            exit_code,
        )

    return exit_code


def main() -> int:
    """Main entry point for LaunchAgent / direct CLI invocation."""
    parser = argparse.ArgumentParser(
        description="Instagram Intel poller — trending data + account insights",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 poller.py --mode trending             # Trending reels + audio (no auth)
  python3 poller.py --mode insights             # Own account insights (requires Meta token)
  python3 poller.py --mode all                  # Both
  python3 poller.py --mode all --dry-run        # Preview without writing to DB

  # Via cli.py (recommended for interactive use):
  python3 cli.py poller run --mode all
  python3 cli.py poller status

LaunchAgent:
  Installed to: ~/Library/LaunchAgents/com.huxley.instagram-intel-poller.plist
  Schedule: every hour (StartInterval 3600)
  Manual trigger: launchctl start com.huxley.instagram-intel-poller
        """,
    )
    parser.add_argument(
        "--mode",
        choices=["trending", "insights", "all"],
        default="all",
        help="Which poll to run (default: all)",
    )
    parser.add_argument(
        "--period",
        default="day",
        choices=["day", "week", "days_28", "lifetime"],
        help="Insights period (default: day)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Log what would be written without touching the database",
    )
    parser.add_argument(
        "--log",
        default=str(LOG_PATH),
        help=f"Path to log file (default: {LOG_PATH})",
    )
    args = parser.parse_args()

    return run_poll(
        mode=args.mode,
        period=args.period,
        dry_run=args.dry_run,
        log_path=Path(args.log),
    )


if __name__ == "__main__":
    sys.exit(main())
