"""Engagement scoring and velocity ranking for Instagram Intelligence.

Pure functions — take lists/dicts in, return enriched lists/dicts out.
No side effects, no API calls, no pip dependencies.

Implements:
  #1 Composite Engagement Score — weighted score per media item
  #2 Virality / Trend Velocity  — time-decay scoring (Hacker News formula variant)
"""

import math
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# #1 — Composite Engagement Score
# ---------------------------------------------------------------------------

# Weights for engagement signals (sum = 1.0)
_WEIGHTS_STANDARD = {
    "likes": 0.30,
    "comments": 0.35,
    "views": 0.00,      # not available for non-video
    "saves": 0.20,
    "shares": 0.15,
}

_WEIGHTS_REEL = {
    "likes": 0.20,
    "comments": 0.25,
    "views": 0.25,
    "saves": 0.15,
    "shares": 0.15,
}


def _get_numeric(item: Dict[str, Any], key: str, fallback_key: str = "") -> int:
    """Extract a numeric value from a dict, trying primary then fallback key."""
    val = item.get(key)
    if val is None and fallback_key:
        val = item.get(fallback_key)
    if val is None:
        return 0
    if isinstance(val, str):
        try:
            val = int(val.replace(",", ""))
        except (ValueError, AttributeError):
            return 0
    try:
        return int(val)
    except (ValueError, TypeError):
        return 0


def score_media_item(
    item: Dict[str, Any],
    mode: str = "standard",
    followers: int = 0,
) -> Dict[str, Any]:
    """Compute a composite engagement score for a single media item.

    The score is a weighted sum of normalized engagement signals.
    If followers > 0, signals are normalized per-1000 followers for
    cross-account comparability.

    Args:
        item: Media item dict (from to_dict()).
        mode: "standard" (posts/carousels) or "reel" (reels/video).
        followers: Account follower count for normalization. 0 = raw counts.

    Returns:
        New dict with 'engagement_score' added (float, 0-100 scale).
    """
    weights = _WEIGHTS_REEL if mode == "reel" else _WEIGHTS_STANDARD

    likes = _get_numeric(item, "like_count", "likes")
    comments = _get_numeric(item, "comments_count", "comments")
    views = _get_numeric(item, "views", "video_views")
    saves = _get_numeric(item, "saves", "saved")
    shares = _get_numeric(item, "shares")

    signals = {
        "likes": likes,
        "comments": comments,
        "views": views,
        "saves": saves,
        "shares": shares,
    }

    # Normalize by followers if available (per-1000 followers)
    divisor = max(followers / 1000, 1) if followers > 0 else 1

    # Weighted sum with log-dampening to prevent outlier domination
    # log1p(x) maps 0->0, 10->2.4, 100->4.6, 1000->6.9, 10000->9.2
    raw_score = 0.0
    for signal_name, weight in weights.items():
        val = signals.get(signal_name, 0) / divisor
        raw_score += weight * math.log1p(val)

    # Scale to 0-100 range
    # Note: when followers > 0, signals are divided by followers/1000 which
    # compresses scores for large accounts. Scores are NOT comparable across
    # different follower tiers — use within-account ranking only.
    # log1p(10000) ~= 9.21 is the practical max per signal at the nano tier.
    max_theoretical = 9.21
    score = min(100.0, (raw_score / max_theoretical) * 100)

    enriched = dict(item)
    enriched["engagement_score"] = round(score, 2)
    return enriched


def score_media_batch(
    items: List[Dict[str, Any]],
    mode: str = "standard",
    followers: int = 0,
    sort: bool = True,
) -> List[Dict[str, Any]]:
    """Score and optionally sort a batch of media items.

    Args:
        items: List of media item dicts.
        mode: "standard" or "reel".
        followers: Follower count for normalization.
        sort: If True, sort descending by engagement_score.

    Returns:
        List of enriched dicts with 'engagement_score' field.
    """
    if not items:
        return []

    scored = [score_media_item(item, mode=mode, followers=followers) for item in items]
    if sort:
        scored.sort(key=lambda x: x.get("engagement_score", 0), reverse=True)
    return scored


# ---------------------------------------------------------------------------
# #2 — Virality / Trend Velocity Score
# ---------------------------------------------------------------------------

# Hacker News-style gravity constant — higher = faster decay
_GRAVITY = 1.8


def _parse_timestamp(ts: str) -> float:
    """Parse an ISO 8601 timestamp to Unix epoch seconds."""
    if not ts:
        return 0.0
    try:
        # Handle various ISO formats
        clean = ts.replace("+0000", "+00:00").replace("Z", "+00:00")
        dt = datetime.fromisoformat(clean)
        return dt.timestamp()
    except (ValueError, OSError):
        return 0.0


def velocity_score(
    items: List[Dict[str, Any]],
    now: Optional[float] = None,
    gravity: float = _GRAVITY,
) -> List[Dict[str, Any]]:
    """Compute trend velocity scores using a Hacker News-style formula.

    Formula: velocity = (engagement_points - 1)^0.8 / (age_hours + 2)^gravity

    Items with recent high engagement rank higher than older viral posts.

    Args:
        items: List of media item dicts. Should have likes/comments/views
               and timestamp fields.
        now: Current Unix epoch time (for testing). Defaults to time.time().
        gravity: Decay factor. Higher = faster decay of older content.

    Returns:
        List of enriched dicts with 'velocity_score' and 'velocity_rank' fields,
        sorted by velocity_score descending.
    """
    if not items:
        return []

    if now is None:
        now = time.time()

    scored = []
    for item in items:
        likes = _get_numeric(item, "like_count", "likes")
        comments = _get_numeric(item, "comments_count", "comments")
        views = _get_numeric(item, "views")

        # Engagement points: likes + 2*comments + views/100
        points = likes + (2 * comments) + (views / 100)

        # Age in hours
        ts = item.get("timestamp", "")
        epoch = _parse_timestamp(ts)
        if epoch > 0:
            age_hours = max((now - epoch) / 3600, 0.1)
        else:
            # No timestamp — assume moderately old (24h)
            age_hours = 24.0

        # Velocity formula
        numerator = max(points - 1, 0) ** 0.8
        denominator = (age_hours + 2) ** gravity
        vel = numerator / denominator if denominator > 0 else 0

        enriched = dict(item)
        enriched["velocity_score"] = round(vel, 4)
        scored.append(enriched)

    # Sort by velocity descending
    scored.sort(key=lambda x: x.get("velocity_score", 0), reverse=True)

    # Add rank
    for i, item in enumerate(scored):
        item["velocity_rank"] = i + 1

    return scored
