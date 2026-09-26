#!/usr/bin/env python3
"""
TikTok Intel — Automated Trend Poller

Standalone polling script for automated data collection.
Designed to be invoked by macOS LaunchAgent on a schedule:
  - Every 2 hours: Trending hashtags, songs, creators, and videos

Architecture:
    Imports the existing TikTok Intel scrapers (CreativeCenterScraper) so all
    scraping logic stays in one place. Writes snapshots to SQLite at
    monitoring/tiktok-intel.db. Zero code duplication with cli.py.

Auth:
    None required — TikTok Creative Center is public. Uses Playwright + stealth.

Usage:
    python3 poller.py --mode trends             # Trending data snapshot
    python3 poller.py --mode all                # trends + competitor snapshots
    python3 poller.py --mode trends --dry-run   # Dry run (no DB writes)

    # Via cli.py poller subcommand:
    python3 cli.py poller run --mode trends
    python3 cli.py poller run --mode all --dry-run
    python3 cli.py poller status

LaunchAgent:
    com.huxley.tiktok-intel-poller.plist — not shipped; copy
    tools/youtube-intel/com.huxley.youtube-intel-poller.plist and adapt it (every 2 hours)

Log file: {{CATALYST_ROOT}}/logs/tiktok-intel-poller.log
Database:  {{CATALYST_ROOT}}/monitoring/tiktok-intel.db
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
DB_PATH = CATALYST_ROOT / "monitoring" / "tiktok-intel.db"
LOG_PATH = CATALYST_ROOT / "logs" / "tiktok-intel-poller.log"

# Register the tiktok_intel package so sibling imports work when invoked
# directly (python3 poller.py) or via the poller sub-command in cli.py.
import importlib.util as _ilu


def _bootstrap_package():
    """Register tiktok_intel package + all submodules in sys.modules."""
    if "tiktok_intel" in sys.modules:
        return

    # Package root
    pkg_spec = _ilu.spec_from_file_location(
        "tiktok_intel",
        TOOL_DIR / "__init__.py",
        submodule_search_locations=[str(TOOL_DIR)],
    )
    pkg = _ilu.module_from_spec(pkg_spec)
    sys.modules["tiktok_intel"] = pkg
    pkg_spec.loader.exec_module(pkg)

    # Core modules
    for mod_name in [
        "config",
        "exceptions",
        "models",
        "formatters",
        "cache",
        "browser",
        "scoring",
    ]:
        full = f"tiktok_intel.{mod_name}"
        if full not in sys.modules:
            spec = _ilu.spec_from_file_location(full, TOOL_DIR / f"{mod_name}.py")
            mod = _ilu.module_from_spec(spec)
            sys.modules[full] = mod
            spec.loader.exec_module(mod)

    # Scrapers sub-package
    scrapers_dir = TOOL_DIR / "scrapers"
    sp_spec = _ilu.spec_from_file_location(
        "tiktok_intel.scrapers",
        scrapers_dir / "__init__.py",
        submodule_search_locations=[str(scrapers_dir)],
    )
    sp = _ilu.module_from_spec(sp_spec)
    sys.modules["tiktok_intel.scrapers"] = sp

    for scraper_mod in [
        "base",
        "creative_center",
        "top_ads",
        "hashtags",
        "search",
        "competitor",
        "shop",
    ]:
        full = f"tiktok_intel.scrapers.{scraper_mod}"
        if full not in sys.modules:
            spec = _ilu.spec_from_file_location(full, scrapers_dir / f"{scraper_mod}.py")
            mod = _ilu.module_from_spec(spec)
            sys.modules[full] = mod
            spec.loader.exec_module(mod)

    # Execute scrapers __init__ now that submodules are registered
    if not hasattr(sp, "CreativeCenterScraper"):
        sp_spec.loader.exec_module(sp)


_bootstrap_package()

try:
    from tiktok_intel.browser import BrowserManager  # noqa: E402
    from tiktok_intel.scrapers import CreativeCenterScraper  # noqa: E402
except ImportError as _imp_err:
    BrowserManager = None  # type: ignore[assignment,misc]
    CreativeCenterScraper = None  # type: ignore[assignment,misc]
    _BROWSER_IMPORT_ERROR = _imp_err
else:
    _BROWSER_IMPORT_ERROR = None

# ---------------------------------------------------------------------------
# Logging — write to file + stderr simultaneously
# ---------------------------------------------------------------------------


def _setup_logging(log_path: Path) -> logging.Logger:
    """Configure logging to both file and stderr."""
    logger = logging.getLogger("tiktok-intel-poller")
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

    # Stderr handler — INFO and above (for LaunchAgent Console visibility)
    sh = logging.StreamHandler(sys.stderr)
    sh.setLevel(logging.INFO)
    sh.setFormatter(fmt)
    logger.addHandler(sh)

    return logger


log: logging.Logger = logging.getLogger("tiktok-intel-poller")


# ---------------------------------------------------------------------------
# Database — schema init + write helpers
# ---------------------------------------------------------------------------


def _init_db(db_path: Path) -> sqlite3.Connection:
    """
    Open the tiktok-intel SQLite database, creating it + schema if needed.

    Schema:
      trending_snapshots — one row per poll cycle per trend type
        id           — auto-increment PK
        ts           — ISO 8601 UTC timestamp of the snapshot
        trend_type   — 'hashtags' | 'songs' | 'creators' | 'videos'
        country      — country filter used (empty = all)
        item_count   — number of items captured
        data         — JSON array of raw trend items

      competitor_snapshots — one row per competitor per poll cycle
        id           — auto-increment PK
        ts           — ISO 8601 UTC timestamp
        username     — TikTok username (without @)
        item_count   — number of video items captured
        data         — JSON object with profile + videos
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
            trend_type TEXT    NOT NULL,
            country    TEXT    NOT NULL DEFAULT '',
            item_count INTEGER NOT NULL DEFAULT 0,
            data       TEXT    NOT NULL DEFAULT '[]'
        );

        CREATE INDEX IF NOT EXISTS idx_trending_ts
            ON trending_snapshots (ts);
        CREATE INDEX IF NOT EXISTS idx_trending_type
            ON trending_snapshots (trend_type, ts);

        CREATE TABLE IF NOT EXISTS competitor_snapshots (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            ts         TEXT    NOT NULL,
            username   TEXT    NOT NULL,
            item_count INTEGER NOT NULL DEFAULT 0,
            data       TEXT    NOT NULL DEFAULT '{}'
        );

        CREATE INDEX IF NOT EXISTS idx_competitor_ts
            ON competitor_snapshots (ts);
        CREATE INDEX IF NOT EXISTS idx_competitor_username
            ON competitor_snapshots (username, ts);
    """)
    conn.commit()
    return conn


def _insert_trending_snapshot(
    conn: sqlite3.Connection,
    trend_type: str,
    items: list[dict],
    country: str = "",
) -> None:
    """Insert one trending snapshot row."""
    ts = datetime.now(UTC).isoformat()
    conn.execute(
        "INSERT INTO trending_snapshots (ts, trend_type, country, item_count, data) "
        "VALUES (?, ?, ?, ?, ?)",
        (ts, trend_type, country, len(items), json.dumps(items, default=str)),
    )
    conn.commit()


def _insert_competitor_snapshot(
    conn: sqlite3.Connection,
    username: str,
    data: dict,
) -> None:
    """Insert one competitor snapshot row."""
    ts = datetime.now(UTC).isoformat()
    videos = data.get("videos", [])
    conn.execute(
        "INSERT INTO competitor_snapshots (ts, username, item_count, data) VALUES (?, ?, ?, ?)",
        (ts, username, len(videos), json.dumps(data, default=str)),
    )
    conn.commit()


# ---------------------------------------------------------------------------
# Poll modes
# ---------------------------------------------------------------------------

TREND_TYPES = ["hashtags", "songs", "creators", "videos"]


def poll_trends(conn: sqlite3.Connection, dry_run: bool = False) -> None:
    """
    Fetch trending hashtags, songs, creators, and videos from TikTok Creative
    Center and write one snapshot row per trend type.

    Uses the existing CreativeCenterScraper — no duplicate scraping logic here.
    Playwright launches headless by default; the Creative Center is public
    (no auth, no TikTok login required).
    """
    log.info("--- Trends poll started ---")

    if BrowserManager is None:
        log.error("Playwright not installed: %s", _BROWSER_IMPORT_ERROR)
        return None

    total_inserted = 0

    try:
        with BrowserManager(headless=True, stealth_level="standard") as bm:
            scraper = CreativeCenterScraper(browser_manager=bm, verbose=False)

            for trend_type in TREND_TYPES:
                log.info("Scraping trend type: %s", trend_type)
                try:
                    result = scraper.scrape(
                        filters={"type": trend_type, "country": "US"},
                        limit=50,
                    )

                    if result is None or not result.success:
                        log.warning("Scraper returned no result for %s", trend_type)
                        continue

                    # Normalize items to plain dicts for JSON storage
                    items: list[dict] = []
                    for item in result.data or []:
                        if hasattr(item, "to_dict"):
                            items.append(item.to_dict())
                        elif isinstance(item, dict):
                            items.append(item)

                    log.debug("  %s: %d items fetched", trend_type, len(items))

                    if dry_run:
                        log.info(
                            "[DRY-RUN] trending_snapshots: %s -> %d items",
                            trend_type,
                            len(items),
                        )
                    else:
                        _insert_trending_snapshot(conn, trend_type, items, country="US")

                    total_inserted += 1

                except Exception as exc:
                    log.error("Failed to scrape trend type '%s': %s", trend_type, exc)
                    continue
    except Exception as exc:
        log.error("Failed to launch browser for trends poll: %s", exc)

    log.info("Trends poll complete — %d trend type(s) snapshotted", total_inserted)


def poll_competitors(
    conn: sqlite3.Connection,
    usernames: list[str],
    dry_run: bool = False,
) -> None:
    """
    Fetch public profile + recent videos for each tracked competitor.

    Competitors are loaded from a JSON config at:
        tools/tiktok-intel/poller-competitors.json
    Format: ["username1", "username2", ...]

    If the file doesn't exist, this poll is a no-op (logs a notice).
    """
    from tiktok_intel.scrapers import CompetitorScraper  # noqa

    log.info("--- Competitor poll started ---")

    if not usernames:
        log.info(
            "No competitor usernames configured. Create "
            "tools/tiktok-intel/poller-competitors.json to enable."
        )
        return

    log.info("Polling %d competitor(s)", len(usernames))

    if BrowserManager is None:
        log.error("Playwright not installed: %s", _BROWSER_IMPORT_ERROR)
        return

    total_inserted = 0

    try:
        with BrowserManager(headless=True, stealth_level="enhanced") as bm:
            scraper = CompetitorScraper(browser_manager=bm, verbose=False)

            for username in usernames:
                log.info("Scraping competitor: @%s", username)
                try:
                    result = scraper.scrape(
                        filters={"username": username},
                        limit=20,
                    )

                    if result is None or not result.success:
                        log.warning("No result for competitor @%s", username)
                        continue

                    data = result.data
                    if hasattr(data, "to_dict"):
                        data = data.to_dict()
                    elif not isinstance(data, dict):
                        data = {"raw": str(data)}

                    videos = data.get("videos", [])
                    log.debug("  @%s: %d videos scraped", username, len(videos))

                    if dry_run:
                        log.info(
                            "[DRY-RUN] competitor_snapshots: @%s -> %d videos",
                            username,
                            len(videos),
                        )
                    else:
                        _insert_competitor_snapshot(conn, username, data)

                    total_inserted += 1

                except Exception as exc:
                    log.error("Failed to scrape competitor @%s: %s", username, exc)
                    continue
    except Exception as exc:
        log.error("Failed to launch browser for competitor poll: %s", exc)

    log.info("Competitor poll complete — %d competitor(s) snapshotted", total_inserted)


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

        print("\nTikTok Intel Poller — Status")
        print(f"Database: {db_path}\n")

        # trending_snapshots
        rows = conn.execute(
            "SELECT trend_type, COUNT(*) AS cnt, MAX(ts) AS last_ts "
            "FROM trending_snapshots GROUP BY trend_type ORDER BY trend_type"
        ).fetchall()
        if rows:
            print("  Trending snapshots:")
            for r in rows:
                print(f"    {r['trend_type']:12s}  {r['cnt']:5d} snapshots  last: {r['last_ts']}")
        else:
            print("  Trending snapshots: (none)")

        # competitor_snapshots
        rows = conn.execute(
            "SELECT username, COUNT(*) AS cnt, MAX(ts) AS last_ts "
            "FROM competitor_snapshots GROUP BY username ORDER BY username"
        ).fetchall()
        if rows:
            print("\n  Competitor snapshots:")
            for r in rows:
                print(f"    @{r['username']:20s}  {r['cnt']:5d} snapshots  last: {r['last_ts']}")
        else:
            print("\n  Competitor snapshots: (none)")

        # Total rows
        total_trending = conn.execute("SELECT COUNT(*) FROM trending_snapshots").fetchone()[0]
        total_competitors = conn.execute("SELECT COUNT(*) FROM competitor_snapshots").fetchone()[0]
        print(
            f"\n  Total rows: {total_trending + total_competitors:,}  "
            f"(trending: {total_trending:,}, competitors: {total_competitors:,})"
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _load_competitors() -> list[str]:
    """Load competitor usernames from tools/tiktok-intel/poller-competitors.json."""
    config_path = TOOL_DIR / "poller-competitors.json"
    if not config_path.exists():
        return []
    try:
        data = json.loads(config_path.read_text())
        if isinstance(data, list):
            return [str(u).lstrip("@").strip() for u in data if u]
    except (json.JSONDecodeError, OSError) as exc:
        log.warning("Could not read poller-competitors.json: %s", exc)
    return []


# ---------------------------------------------------------------------------
# Entry point — run_poll() is called from cli.py poller command too
# ---------------------------------------------------------------------------


def run_poll(mode: str, dry_run: bool = False, log_path: Path = LOG_PATH) -> int:
    """
    Run one full poll cycle.

    Called from:
      - main()                      — standalone / LaunchAgent
      - cli.py `poller run` command — via cli.py dispatch

    Returns exit code (0 = success, 1 = error).
    """
    global log
    log = _setup_logging(log_path)

    log.info("=== tiktok-intel-poller starting (mode=%s, dry_run=%s) ===", mode, dry_run)

    start_time = time.time()
    exit_code = 0

    try:
        conn = _init_db(DB_PATH)

        if mode in ("trends", "all"):
            poll_trends(conn, dry_run=dry_run)

        if mode in ("all",):
            competitors = _load_competitors()
            poll_competitors(conn, competitors, dry_run=dry_run)

        conn.close()

    except KeyboardInterrupt:
        log.info("Interrupted")
        exit_code = 0
    except Exception as exc:
        log.exception("Unexpected error during poll: %s", exc)
        exit_code = 1
    finally:
        elapsed = time.time() - start_time
        log.info(
            "=== tiktok-intel-poller finished in %.1fs (exit=%d) ===",
            elapsed,
            exit_code,
        )

    return exit_code


def main() -> int:
    """Main entry point for LaunchAgent / direct CLI invocation."""
    parser = argparse.ArgumentParser(
        description="TikTok Intel poller — trending data snapshots",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 poller.py --mode trends              # Trending data (hashtags, songs, creators, videos)
  python3 poller.py --mode all                 # trends + configured competitors
  python3 poller.py --mode trends --dry-run    # Preview without writing to DB

  # Via cli.py (recommended for interactive use):
  python3 cli.py poller run --mode trends
  python3 cli.py poller status

LaunchAgent:
  Installed to: ~/Library/LaunchAgents/com.huxley.tiktok-intel-poller.plist
  Schedule: every 2 hours (StartInterval 7200)
  Manual trigger: launchctl start com.huxley.tiktok-intel-poller
        """,
    )
    parser.add_argument(
        "--mode",
        choices=["trends", "all"],
        default="trends",
        help="Which poll to run (default: trends)",
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
        dry_run=args.dry_run,
        log_path=Path(args.log),
    )


if __name__ == "__main__":
    sys.exit(main())
