#!/usr/bin/env python3
"""
YouTube Intel — VPH & Competitor Poller

Standalone polling script for automated data collection.
Designed to be invoked by macOS LaunchAgent on two schedules:
  - Hourly:  VPH (Views Per Hour) snapshots for tracked videos
  - Daily:   Competitor channel stats snapshots

Auth:
    Uses service account auth via get_service_account_token() from client.py.
    Service account credentials in Keychain:
      - google-service-account-client-email
      - google-service-account-private-key
    Only public Data API access is needed — no OAuth / browser login required.

Usage:
    python3 poller.py --mode vph              # Hourly VPH poll
    python3 poller.py --mode competitors      # Daily competitor poll
    python3 poller.py --mode all              # Both (useful for manual runs)
    python3 poller.py --mode vph --dry-run    # Dry run (no DB writes)

Dependencies: None (stdlib only — auth and DB imported from client.py and db.py)

Log file: {{CATALYST_ROOT}}/logs/youtube-intel-poller.log
Database:  {{CATALYST_ROOT}}/monitoring/youtube-intel.db
"""

import argparse
import json
import logging
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Path setup — must happen before importing sibling modules
# ---------------------------------------------------------------------------
TOOL_DIR = Path(__file__).resolve().parent
CATALYST_ROOT = TOOL_DIR.parent.parent
DB_PATH = CATALYST_ROOT / "monitoring" / "youtube-intel.db"
LOG_PATH = CATALYST_ROOT / "logs" / "youtube-intel-poller.log"

if str(TOOL_DIR) not in sys.path:
    sys.path.insert(0, str(TOOL_DIR))

# Import auth from client.py — no duplicated Keychain / token logic here
from client import (
    get_service_account_token,
    CredentialError,
    AuthError,
    YouTubeIntelError,
    YOUTUBE_BASE_URL,
)

# Import DB helpers from db.py — no duplicated SQLite logic here
import db as intel_db

# ---------------------------------------------------------------------------
# YouTube API
# ---------------------------------------------------------------------------
YT_BATCH_SIZE = 50  # videos.list / channels.list: max 50 IDs per call

# ---------------------------------------------------------------------------
# Logging — write to file + stderr simultaneously
# ---------------------------------------------------------------------------

def _setup_logging(log_path: Path) -> logging.Logger:
    """Configure logging to both file and stderr."""
    log_path.parent.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("youtube-intel-poller")
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


log: logging.Logger = logging.getLogger("youtube-intel-poller")

# ---------------------------------------------------------------------------
# YouTube API helpers — use service account token from client.py
# ---------------------------------------------------------------------------

def _yt_get(endpoint: str, params: Dict) -> Dict:
    """
    Make a GET request to the YouTube Data API v3 using the service account token.

    Raises RuntimeError on API errors.
    """
    try:
        access_token = get_service_account_token()
    except (CredentialError, AuthError) as exc:
        raise RuntimeError(f"Service account auth failed: {exc}") from exc

    url = f"{YOUTUBE_BASE_URL}/{endpoint}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url)
    req.add_header("Authorization", f"Bearer {access_token}")
    req.add_header("Accept", "application/json")

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        body = exc.read().decode()
        log.error("YouTube API HTTP %d on %s: %s", exc.code, endpoint, body)

        # 401 = service account token expired mid-session — retry once
        if exc.code == 401:
            log.info("Got 401 — retrying with fresh service account token")
            try:
                from client import _keychain_write, KC_SA_TOKEN_EXPIRY
                _keychain_write(KC_SA_TOKEN_EXPIRY, "huxley", "0")
                access_token = get_service_account_token()
            except (CredentialError, AuthError) as refresh_exc:
                raise RuntimeError(f"Token refresh failed: {refresh_exc}") from refresh_exc

            req2 = urllib.request.Request(url)
            req2.add_header("Authorization", f"Bearer {access_token}")
            req2.add_header("Accept", "application/json")
            with urllib.request.urlopen(req2, timeout=30) as resp2:
                return json.loads(resp2.read().decode())

        raise RuntimeError(f"YouTube API error {exc.code} on {endpoint}: {body}") from exc
    except Exception as exc:
        raise RuntimeError(f"YouTube API network error on {endpoint}: {exc}") from exc


def _fetch_video_stats(video_ids: List[str]) -> Dict[str, int]:
    """
    Fetch current viewCount for up to 50 video IDs in one batched API call.

    Returns: {video_id: view_count}
    Quota cost: 1 unit per call (regardless of batch size).
    """
    data = _yt_get("videos", {
        "part": "statistics",
        "id": ",".join(video_ids),
        "maxResults": 50,
    })

    result: Dict[str, int] = {}
    for item in data.get("items", []):
        vid_id = item.get("id", "")
        stats = item.get("statistics", {})
        try:
            result[vid_id] = int(stats.get("viewCount", 0))
        except (ValueError, TypeError):
            result[vid_id] = 0

    missing = set(video_ids) - set(result.keys())
    if missing:
        log.warning("No stats returned for video IDs: %s (private or deleted?)", missing)

    return result


def _fetch_channel_stats(channel_ids: List[str]) -> Dict[str, Dict]:
    """
    Fetch subscriber/video/view counts for up to 50 channel IDs in one call.

    Returns: {channel_id: {subscriber_count, video_count, view_count}}
    Quota cost: 1 unit per call.
    """
    data = _yt_get("channels", {
        "part": "statistics",
        "id": ",".join(channel_ids),
        "maxResults": 50,
    })

    result: Dict[str, Dict] = {}
    for item in data.get("items", []):
        ch_id = item.get("id", "")
        stats = item.get("statistics", {})
        result[ch_id] = {
            "subscriber_count": int(stats.get("subscriberCount", 0)),
            "video_count": int(stats.get("videoCount", 0)),
            "view_count": int(stats.get("viewCount", 0)),
        }

    missing = set(channel_ids) - set(result.keys())
    if missing:
        log.warning("No stats returned for channel IDs: %s", missing)

    return result

# ---------------------------------------------------------------------------
# Poll modes — use db.py helpers instead of raw SQL
# ---------------------------------------------------------------------------

def poll_vph(dry_run: bool = False) -> None:
    """
    Poll current view counts for all actively-tracked videos.

    Batches up to 50 video IDs per YouTube API call (1 quota unit per batch).
    Inserts one row per video into vph_snapshots via db.add_vph_snapshot().
    """
    log.info("--- VPH poll started ---")

    tracked = intel_db.list_tracked_videos(active_only=True)
    video_ids = [v["video_id"] for v in tracked]

    if not video_ids:
        log.info("No active tracked videos — nothing to poll. "
                 "Add videos with: youtube-intel vph track <video_id>")
        return

    log.info("Polling view counts for %d tracked video(s)", len(video_ids))

    total_inserted = 0
    api_calls = 0

    for i in range(0, len(video_ids), YT_BATCH_SIZE):
        batch = video_ids[i : i + YT_BATCH_SIZE]
        log.debug("Fetching batch %d/%d (%d video IDs)",
                  i // YT_BATCH_SIZE + 1,
                  (len(video_ids) - 1) // YT_BATCH_SIZE + 1,
                  len(batch))
        try:
            stats = _fetch_video_stats(batch)
            api_calls += 1
            for vid_id in batch:
                view_count = stats.get(vid_id, 0)
                log.debug("  %s: %d views", vid_id, view_count)
                if dry_run:
                    log.info("[DRY-RUN] vph_snapshots: %s → %d views", vid_id, view_count)
                else:
                    intel_db.add_vph_snapshot(vid_id, view_count)
                total_inserted += 1
        except RuntimeError as exc:
            log.error("Failed to fetch video batch %s…: %s", batch[0], exc)
            continue

    log.info(
        "VPH poll complete — %d snapshot(s) recorded, %d API call(s) used (%.2f quota units)",
        total_inserted, api_calls, float(api_calls),
    )


def poll_competitors(dry_run: bool = False) -> None:
    """
    Poll channel statistics for all tracked competitors.

    Batches up to 50 channel IDs per YouTube API call (1 quota unit per batch).
    Inserts one row per channel into competitor_snapshots via db.add_competitor_snapshot().
    """
    log.info("--- Competitor poll started ---")

    competitors = intel_db.list_competitors()
    channel_ids = [c["channel_id"] for c in competitors]

    if not channel_ids:
        log.info("No competitor channels tracked — nothing to poll. "
                 "Add channels with: youtube-intel competitor add <channel_id>")
        return

    log.info("Polling stats for %d competitor channel(s)", len(channel_ids))

    total_inserted = 0
    api_calls = 0

    for i in range(0, len(channel_ids), YT_BATCH_SIZE):
        batch = channel_ids[i : i + YT_BATCH_SIZE]
        log.debug("Fetching channel batch %d/%d (%d channel IDs)",
                  i // YT_BATCH_SIZE + 1,
                  (len(channel_ids) - 1) // YT_BATCH_SIZE + 1,
                  len(batch))
        try:
            stats = _fetch_channel_stats(batch)
            api_calls += 1
            for ch_id in batch:
                ch_stats = stats.get(ch_id, {
                    "subscriber_count": 0,
                    "video_count": 0,
                    "view_count": 0,
                })
                log.debug("  %s: subs=%d videos=%d views=%d",
                          ch_id,
                          ch_stats["subscriber_count"],
                          ch_stats["video_count"],
                          ch_stats["view_count"])
                if dry_run:
                    log.info(
                        "[DRY-RUN] competitor_snapshots: %s → subs=%d videos=%d views=%d",
                        ch_id,
                        ch_stats["subscriber_count"],
                        ch_stats["video_count"],
                        ch_stats["view_count"],
                    )
                else:
                    intel_db.add_competitor_snapshot(
                        ch_id,
                        ch_stats["subscriber_count"],
                        ch_stats["video_count"],
                        ch_stats["view_count"],
                    )
                total_inserted += 1
        except RuntimeError as exc:
            log.error("Failed to fetch channel batch %s…: %s", batch[0], exc)
            continue

    log.info(
        "Competitor poll complete — %d snapshot(s) recorded, %d API call(s) used",
        total_inserted, api_calls,
    )

# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def run_poll(mode: str, dry_run: bool = False, log_path: Path = LOG_PATH) -> int:
    """
    Run a poll cycle. Can be called from CLI (commands/poller.py) or main().

    Returns exit code (0 = success, 1 = error).
    """
    global log
    log = _setup_logging(log_path)

    log.info("=== youtube-intel-poller starting (mode=%s, dry_run=%s) ===",
             mode, dry_run)

    start_time = time.time()
    exit_code = 0

    try:
        if mode in ("vph", "all"):
            poll_vph(dry_run=dry_run)

        if mode in ("competitors", "all"):
            poll_competitors(dry_run=dry_run)

    except RuntimeError as exc:
        log.error("Poll failed: %s", exc)
        exit_code = 1
    except KeyboardInterrupt:
        log.info("Interrupted")
        exit_code = 0
    except Exception as exc:
        log.exception("Unexpected error: %s", exc)
        exit_code = 1
    finally:
        elapsed = time.time() - start_time
        log.info("=== youtube-intel-poller finished in %.1fs (exit=%d) ===", elapsed, exit_code)

    return exit_code


def main() -> int:
    """Main entry point for LaunchAgent / direct CLI invocation. Returns exit code."""
    parser = argparse.ArgumentParser(
        description="YouTube Intel poller — VPH and competitor stats",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 poller.py --mode vph              # Hourly VPH snapshot
  python3 poller.py --mode competitors      # Daily competitor snapshot
  python3 poller.py --mode all              # Both polls (manual runs)
  python3 poller.py --mode vph --dry-run    # Preview without writing

LaunchAgent schedule:
  VPH poll        → hourly    (com.huxley.youtube-intel-poller.plist)
  Competitor poll → daily 6AM (com.huxley.youtube-intel-poller.plist)
        """,
    )
    parser.add_argument(
        "--mode",
        choices=["vph", "competitors", "all"],
        required=True,
        help="Which poll to run",
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
