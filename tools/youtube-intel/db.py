"""
SQLite storage layer for YouTube Intel.

Database location: monitoring/youtube-intel.db (relative to Huxley root).
"""

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

CATALYST_ROOT = Path(__file__).resolve().parent.parent.parent
DB_PATH = CATALYST_ROOT / "monitoring" / "youtube-intel.db"
SCHEMA_PATH = Path(__file__).resolve().parent / "schema.sql"


def _now_utc() -> str:
    """ISO 8601 UTC timestamp."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def get_connection() -> sqlite3.Connection:
    """Get a connection to the YouTube Intel database, initializing if needed."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")

    # Initialize schema if tables don't exist
    cursor = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='tracked_videos'"
    )
    if cursor.fetchone() is None:
        schema_sql = SCHEMA_PATH.read_text()
        conn.executescript(schema_sql)

    return conn


# ---------------------------------------------------------------------------
# Tracked Videos
# ---------------------------------------------------------------------------

def add_tracked_video(
    video_id: str, channel_id: str, title: str, published_at: str = ""
) -> bool:
    """Add a video to tracking. Returns True if newly added, False if reactivated/already existed."""
    conn = get_connection()
    try:
        cursor = conn.execute(
            "SELECT tracking_active FROM tracked_videos WHERE video_id = ?",
            (video_id,),
        )
        existing = cursor.fetchone()
        if existing:
            # Reactivate if inactive
            if not existing["tracking_active"]:
                conn.execute(
                    "UPDATE tracked_videos SET tracking_active = 1 WHERE video_id = ?",
                    (video_id,),
                )
                conn.commit()
            return False  # Already existed
        conn.execute(
            """INSERT INTO tracked_videos (video_id, channel_id, title, published_at)
               VALUES (?, ?, ?, ?)""",
            (video_id, channel_id, title, published_at),
        )
        conn.commit()
        return True  # Newly added
    except sqlite3.Error:
        return False
    finally:
        conn.close()


def remove_tracked_video(video_id: str) -> bool:
    """Stop tracking a video (soft-disable)."""
    conn = get_connection()
    try:
        cursor = conn.execute(
            "UPDATE tracked_videos SET tracking_active = 0 WHERE video_id = ?",
            (video_id,),
        )
        conn.commit()
        return cursor.rowcount > 0
    finally:
        conn.close()


def list_tracked_videos(active_only: bool = True) -> List[Dict[str, Any]]:
    """List all tracked videos."""
    conn = get_connection()
    try:
        where = "WHERE tracking_active = 1" if active_only else ""
        rows = conn.execute(
            f"SELECT * FROM tracked_videos {where} ORDER BY added_at DESC"
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_tracked_video(video_id: str) -> Optional[Dict[str, Any]]:
    """Get a single tracked video."""
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM tracked_videos WHERE video_id = ?", (video_id,)
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# VPH Snapshots
# ---------------------------------------------------------------------------

def add_vph_snapshot(video_id: str, view_count: int) -> None:
    """Record a view count snapshot for a tracked video."""
    conn = get_connection()
    try:
        conn.execute(
            "INSERT INTO vph_snapshots (video_id, view_count) VALUES (?, ?)",
            (video_id, view_count),
        )
        conn.commit()
    finally:
        conn.close()


def get_vph_snapshots(
    video_id: str, limit: int = 168
) -> List[Dict[str, Any]]:
    """Get recent VPH snapshots for a video (default: last 7 days hourly = 168)."""
    conn = get_connection()
    try:
        rows = conn.execute(
            """SELECT view_count, snapshot_time
               FROM vph_snapshots
               WHERE video_id = ?
               ORDER BY snapshot_time DESC
               LIMIT ?""",
            (video_id, limit),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_latest_vph_snapshot(video_id: str) -> Optional[Dict[str, Any]]:
    """Get the most recent snapshot for a video."""
    conn = get_connection()
    try:
        row = conn.execute(
            """SELECT view_count, snapshot_time
               FROM vph_snapshots
               WHERE video_id = ?
               ORDER BY snapshot_time DESC
               LIMIT 1""",
            (video_id,),
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def calculate_vph(video_id: str, hours: int = 1) -> Optional[float]:
    """
    Calculate VPH over the given window.

    Uses the most recent snapshot and the snapshot closest to `hours` ago
    to compute views-per-hour over that span. Returns None if insufficient data.
    """
    conn = get_connection()
    try:
        # Get newest snapshot
        newest_row = conn.execute(
            """SELECT view_count, snapshot_time
               FROM vph_snapshots
               WHERE video_id = ?
               ORDER BY snapshot_time DESC
               LIMIT 1""",
            (video_id,),
        ).fetchone()

        if newest_row is None:
            return None

        # Get snapshot closest to `hours` ago
        target_time = f"-{hours} hours"
        oldest_row = conn.execute(
            """SELECT view_count, snapshot_time
               FROM vph_snapshots
               WHERE video_id = ?
                 AND snapshot_time <= strftime('%Y-%m-%dT%H:%M:%SZ',
                     datetime('now', ?))
               ORDER BY snapshot_time DESC
               LIMIT 1""",
            (video_id, target_time),
        ).fetchone()

        # Fallback: if no snapshot old enough, use the oldest available
        if oldest_row is None:
            oldest_row = conn.execute(
                """SELECT view_count, snapshot_time
                   FROM vph_snapshots
                   WHERE video_id = ?
                   ORDER BY snapshot_time ASC
                   LIMIT 1""",
                (video_id,),
            ).fetchone()

        if oldest_row is None or oldest_row["snapshot_time"] == newest_row["snapshot_time"]:
            return None

        views_diff = newest_row["view_count"] - oldest_row["view_count"]
        t_newest = datetime.fromisoformat(newest_row["snapshot_time"].replace("Z", "+00:00"))
        t_oldest = datetime.fromisoformat(oldest_row["snapshot_time"].replace("Z", "+00:00"))
        hours_elapsed = (t_newest - t_oldest).total_seconds() / 3600.0

        if hours_elapsed <= 0:
            return None

        return views_diff / hours_elapsed
    finally:
        conn.close()


def calculate_avg_vph(video_id: str, hours: int = 24) -> Optional[float]:
    """Calculate average VPH over a window (e.g., 24h, 168h for 7d)."""
    conn = get_connection()
    try:
        rows = conn.execute(
            """SELECT view_count, snapshot_time
               FROM vph_snapshots
               WHERE video_id = ?
               ORDER BY snapshot_time DESC""",
            (video_id,),
        ).fetchall()

        if len(rows) < 2:
            return None

        newest = rows[0]
        # Find the snapshot closest to `hours` ago
        t_newest = datetime.fromisoformat(newest["snapshot_time"].replace("Z", "+00:00"))
        target_secs = hours * 3600.0
        best = None
        best_diff = float("inf")

        for row in rows[1:]:
            t_row = datetime.fromisoformat(row["snapshot_time"].replace("Z", "+00:00"))
            diff = abs((t_newest - t_row).total_seconds() - target_secs)
            if diff < best_diff:
                best_diff = diff
                best = row

        if best is None:
            # Fall back to oldest available
            best = rows[-1]

        views_diff = newest["view_count"] - best["view_count"]
        t_best = datetime.fromisoformat(best["snapshot_time"].replace("Z", "+00:00"))
        hours_elapsed = (t_newest - t_best).total_seconds() / 3600.0

        if hours_elapsed <= 0:
            return None

        return views_diff / hours_elapsed
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Competitors
# ---------------------------------------------------------------------------

def add_competitor(
    channel_id: str, channel_name: str, channel_handle: str = ""
) -> bool:
    """Add a competitor channel. Returns True if newly added."""
    conn = get_connection()
    try:
        conn.execute(
            """INSERT INTO competitors (channel_id, channel_name, channel_handle)
               VALUES (?, ?, ?)
               ON CONFLICT(channel_id) DO UPDATE SET
                   channel_name = excluded.channel_name,
                   channel_handle = excluded.channel_handle""",
            (channel_id, channel_name, channel_handle),
        )
        conn.commit()
        return True
    except sqlite3.Error:
        return False
    finally:
        conn.close()


def remove_competitor(channel_id: str) -> bool:
    """Remove a competitor. Returns True if found and removed."""
    conn = get_connection()
    try:
        cursor = conn.execute(
            "DELETE FROM competitors WHERE channel_id = ?", (channel_id,)
        )
        conn.commit()
        return cursor.rowcount > 0
    finally:
        conn.close()


def list_competitors() -> List[Dict[str, Any]]:
    """List all tracked competitors."""
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM competitors ORDER BY added_at DESC"
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_competitor(channel_id: str) -> Optional[Dict[str, Any]]:
    """Get a single competitor by channel ID."""
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM competitors WHERE channel_id = ?", (channel_id,)
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def add_competitor_snapshot(
    channel_id: str,
    subscriber_count: int,
    video_count: int,
    view_count: int,
) -> None:
    """Record a snapshot of competitor channel stats."""
    conn = get_connection()
    try:
        conn.execute(
            """INSERT INTO competitor_snapshots
               (channel_id, subscriber_count, video_count, view_count)
               VALUES (?, ?, ?, ?)""",
            (channel_id, subscriber_count, video_count, view_count),
        )
        conn.commit()
    finally:
        conn.close()


def get_competitor_snapshots(
    channel_id: str, limit: int = 60
) -> List[Dict[str, Any]]:
    """Get recent competitor snapshots (default: last 60 days daily)."""
    conn = get_connection()
    try:
        rows = conn.execute(
            """SELECT subscriber_count, video_count, view_count, snapshot_time
               FROM competitor_snapshots
               WHERE channel_id = ?
               ORDER BY snapshot_time DESC
               LIMIT ?""",
            (channel_id, limit),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Keyword Cache
# ---------------------------------------------------------------------------

def cache_keyword(
    keyword: str,
    search_volume_proxy: int,
    competition_score: float,
    related_terms: List[str],
) -> None:
    """Cache keyword research results."""
    conn = get_connection()
    try:
        conn.execute(
            """INSERT INTO keyword_cache
               (keyword, search_volume_proxy, competition_score, related_terms)
               VALUES (?, ?, ?, ?)
               ON CONFLICT(keyword) DO UPDATE SET
                   search_volume_proxy = excluded.search_volume_proxy,
                   competition_score = excluded.competition_score,
                   related_terms = excluded.related_terms,
                   cached_at = strftime('%Y-%m-%dT%H:%M:%SZ', 'now')""",
            (keyword, search_volume_proxy, competition_score, json.dumps(related_terms)),
        )
        conn.commit()
    finally:
        conn.close()


def get_cached_keyword(
    keyword: str, max_age_hours: int = 24
) -> Optional[Dict[str, Any]]:
    """Get cached keyword data if still fresh."""
    conn = get_connection()
    try:
        row = conn.execute(
            """SELECT * FROM keyword_cache
               WHERE keyword = ?
               AND cached_at > strftime('%Y-%m-%dT%H:%M:%SZ',
                   datetime('now', ? || ' hours'))""",
            (keyword, str(-max_age_hours)),
        ).fetchone()
        if row:
            result = dict(row)
            result["related_terms"] = json.loads(result["related_terms"])
            return result
        return None
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# SEO Scores
# ---------------------------------------------------------------------------

def save_seo_score(
    video_id: str, overall_score: float, breakdown: Dict[str, Any]
) -> None:
    """Save an SEO score for a video."""
    conn = get_connection()
    try:
        conn.execute(
            """INSERT INTO video_seo_scores (video_id, overall_score, breakdown)
               VALUES (?, ?, ?)""",
            (video_id, overall_score, json.dumps(breakdown)),
        )
        conn.commit()
    finally:
        conn.close()


def get_latest_seo_score(video_id: str) -> Optional[Dict[str, Any]]:
    """Get the most recent SEO score for a video."""
    conn = get_connection()
    try:
        row = conn.execute(
            """SELECT * FROM video_seo_scores
               WHERE video_id = ?
               ORDER BY scored_at DESC
               LIMIT 1""",
            (video_id,),
        ).fetchone()
        if row:
            result = dict(row)
            result["breakdown"] = json.loads(result["breakdown"])
            return result
        return None
    finally:
        conn.close()
