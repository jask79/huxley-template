"""Pure-function scoring and ranking layer for TikTok Intelligence data.

All functions are stateless with NO I/O, NO browser, NO side effects.
They operate on frozen dataclasses from models.py and return computed scores.

Scoring philosophy:
  - Video engagement uses a sigmoid curve centered at TikTok's mean engagement rate
  - Shop products use Bayesian-adjusted ratings to handle sparse reviews
  - Trend velocity classifies items by rank movement magnitude and type
  - All scores are normalized to 0-100 range
"""

import math
from typing import Any, Callable, Dict, List, TypeVar, Union

from .formatters import parse_human_number
from .models import (
    CompetitorProfile,
    SearchVideoResult,
    ShopProduct,
    TrendingCreator,
    TrendingHashtag,
    TrendingSong,
    TrendingVideo,
)

# ---------------------------------------------------------------------------
# Type aliases
# ---------------------------------------------------------------------------

T = TypeVar("T")
TrendItem = Union[TrendingHashtag, TrendingSong, TrendingCreator, TrendingVideo]

# ---------------------------------------------------------------------------
# Video Engagement Constants
# ---------------------------------------------------------------------------

W_LIKES = 0.35
"""Likes are highest volume but lowest intent signal."""

W_COMMENTS = 0.40
"""Comments require text input — strongest available intent signal."""

W_SHARES = 0.25
"""Shares have highest friction, but fewer total makes weight feel inflated above 0.25."""

SIGMOID_MIDPOINT = 0.05
"""TikTok mean engagement ~4-6%; center sigmoid at 5%."""

SIGMOID_STEEPNESS = 60.0
"""Gives good discrimination in the 1-10% range.

rate=1% -> ~8, rate=3% -> ~23, rate=5% -> 50, rate=8% -> ~86, rate=10% -> ~95.
"""

# ---------------------------------------------------------------------------
# Shop Product Constants
# ---------------------------------------------------------------------------

RATING_PRIOR_MEAN = 4.2
"""TikTok Shop global average rating (Bayesian prior mean)."""

RATING_PRIOR_WEIGHT = 10
"""Bayesian C parameter — how much to weight the prior vs observed."""

SALES_LOG_CAP = 7.0
"""log10(10M) — normalization ceiling for log-scaled sales."""

REVIEW_DENSITY_CAP = 0.30
"""30% review rate = maximum density score."""

PRODUCT_W_RATING = 0.50
"""Weight of Bayesian-adjusted rating in composite product score."""

PRODUCT_W_SALES = 0.35
"""Weight of log-scaled sales volume in composite product score."""

PRODUCT_W_REVIEW_DENSITY = 0.15
"""Weight of review density in composite product score."""

# ---------------------------------------------------------------------------
# Trend Velocity Constants
# ---------------------------------------------------------------------------

BREAKOUT_RANK_THRESHOLD = 20
"""New entries at rank <= 20 are classified as BREAKOUT."""

BREAKOUT_JUMP_THRESHOLD = 20
"""Existing entries that jump 20+ ranks are classified as BREAKOUT."""

RISING_MIN_JUMP = 5
"""Minimum rank improvement to classify as RISING."""

DECLINING_MIN_DROP = 5
"""Minimum rank decline (negative diff) to classify as DECLINING."""

# ---------------------------------------------------------------------------
# Velocity classification ordering (for sort comparisons)
# ---------------------------------------------------------------------------

VELOCITY_ORDER = {
    "BREAKOUT": 4,
    "RISING": 3,
    "NEW": 2,
    "STABLE": 1,
    "DECLINING": 0,
}


# ---------------------------------------------------------------------------
# Public functions
# ---------------------------------------------------------------------------

def score_video_engagement(video: SearchVideoResult) -> float:
    """Score a video's engagement quality on a 0-100 sigmoid scale.

    Uses a weighted combination of like/comment/share rates relative to
    view count, passed through a sigmoid centered at TikTok's mean
    engagement rate. This rewards above-average engagement nonlinearly
    while compressing outliers at both extremes.

    Args:
        video: A SearchVideoResult with view_cnt, like_cnt, comment_cnt,
               share_cnt fields populated.

    Returns:
        Float score in [0.0, 100.0], rounded to one decimal place.
        Returns 0.0 if view_cnt is zero.
    """
    if video.view_cnt == 0:
        return 0.0

    like_rate = video.like_cnt / video.view_cnt
    comment_rate = video.comment_cnt / video.view_cnt
    share_rate = video.share_cnt / video.view_cnt

    raw_rate = (
        W_LIKES * like_rate
        + W_COMMENTS * comment_rate
        + W_SHARES * share_rate
    )

    score = 100.0 / (1.0 + math.exp(-SIGMOID_STEEPNESS * (raw_rate - SIGMOID_MIDPOINT)))
    return max(0.0, min(100.0, round(score, 1)))


def score_competitor_engagement(profile: CompetitorProfile) -> Dict[str, str]:
    """Compute aggregate engagement metrics from a competitor's recent videos.

    Iterates over ``profile.recent_videos`` (list of dicts with varying key
    names) and computes average views, likes, comments, and an overall
    engagement rate.

    Args:
        profile: A CompetitorProfile with recent_videos populated.

    Returns:
        Dict with keys ``avg_views``, ``avg_likes``, ``avg_comments``,
        ``engagement_rate`` — all human-readable strings. Returns dict with
        all empty strings if no videos are available.
    """
    empty = {
        "avg_views": "",
        "avg_likes": "",
        "avg_comments": "",
        "engagement_rate": "",
    }

    if not profile.recent_videos:
        return empty

    total_views = 0
    total_likes = 0
    total_comments = 0
    count = len(profile.recent_videos)

    for vid in profile.recent_videos:
        total_views += _parse_video_stat(vid, "views", "view_cnt", "play_count", "playCount")
        total_likes += _parse_video_stat(vid, "likes", "like_cnt", "digg_count", "diggCount")
        total_comments += _parse_video_stat(vid, "comments", "comment_cnt", "comment_count", "commentCount")

    # Floor division is intentional — sub-unit precision (e.g., "1233.7 views")
    # is meaningless for human-readable display of engagement averages.
    avg_views = total_views // count if count else 0
    avg_likes = total_likes // count if count else 0
    avg_comments = total_comments // count if count else 0

    if total_views > 0:
        eng_rate = (total_likes + total_comments) / total_views * 100
        eng_str = f"{eng_rate:.1f}%"
    else:
        eng_str = "0.0%"

    return {
        "avg_views": _format_count_static(avg_views),
        "avg_likes": _format_count_static(avg_likes),
        "avg_comments": _format_count_static(avg_comments),
        "engagement_rate": eng_str,
    }


def score_shop_product(
    product: ShopProduct,
    global_avg_rating: float = RATING_PRIOR_MEAN,
) -> float:
    """Score a TikTok Shop product on a 0-100 composite scale.

    Combines three signals:
      1. Bayesian-adjusted rating (shrinks toward global mean for sparse reviews)
      2. Log-scaled sales volume (log10, capped at 10M)
      3. Review density (reviews/sales, capped at 30%)

    Args:
        product: A ShopProduct with rating, reviews, sold fields.
        global_avg_rating: Platform average rating to use as Bayesian prior.

    Returns:
        Float score in [0.0, 100.0], rounded to one decimal place.
    """
    rating_val = safe_parse_float(product.rating)
    reviews_count = parse_human_number(product.reviews)
    sold_count = parse_human_number(product.sold)

    # Bayesian-adjusted rating
    if rating_val <= 0:
        adjusted_rating = global_avg_rating
    else:
        adjusted_rating = (
            (RATING_PRIOR_WEIGHT * global_avg_rating + reviews_count * rating_val)
            / (RATING_PRIOR_WEIGHT + reviews_count)
        )
    rating_score = adjusted_rating / 5.0

    # Log-scaled sales
    raw_log_sales = math.log10(max(sold_count, 1) + 1)
    sales_score = min(raw_log_sales / SALES_LOG_CAP, 1.0)

    # Review density
    density = reviews_count / max(sold_count, 1) if sold_count > 0 else 0.0
    density_score = min(density / REVIEW_DENSITY_CAP, 1.0)

    # Composite
    raw_score = (
        PRODUCT_W_RATING * rating_score
        + PRODUCT_W_SALES * sales_score
        + PRODUCT_W_REVIEW_DENSITY * density_score
    )
    return max(0.0, min(100.0, round(raw_score * 100.0, 1)))


def classify_trend_velocity(item: TrendItem) -> str:
    """Classify a trending item's velocity based on rank movement.

    Waterfall classification (first match wins):
      - rank_diff_type == 3 AND rank <= 20 -> "BREAKOUT"
      - rank_diff_type == 3               -> "NEW"
      - rank_diff >= 20                   -> "BREAKOUT"
      - rank_diff >= 5                    -> "RISING"
      - rank_diff <= -5                   -> "DECLINING"
      - else                              -> "STABLE"

    Args:
        item: Any trending dataclass (TrendingHashtag, TrendingSong,
              TrendingCreator, TrendingVideo).

    Returns:
        One of: "BREAKOUT", "NEW", "RISING", "DECLINING", "STABLE".
    """
    rank_diff_type = getattr(item, "rank_diff_type", 0)
    rank_diff = getattr(item, "rank_diff", 0)
    rank = getattr(item, "rank", 999)

    if rank_diff_type == 3 and rank <= BREAKOUT_RANK_THRESHOLD:
        return "BREAKOUT"
    if rank_diff_type == 3:
        return "NEW"
    if rank_diff >= BREAKOUT_JUMP_THRESHOLD:
        return "BREAKOUT"
    if rank_diff >= RISING_MIN_JUMP:
        return "RISING"
    if rank_diff <= -DECLINING_MIN_DROP:
        return "DECLINING"
    return "STABLE"


def rank_results(
    items: List[T],
    scorer: Callable[[T], float],
    reverse: bool = True,
) -> List[T]:
    """Sort items by a scoring function, preserving original order on ties.

    Uses a stable sort with (score, original_index) tuples so that items
    with identical scores retain their input ordering.

    Args:
        items: List of items to rank.
        scorer: Function that takes an item and returns a numeric score.
        reverse: If True (default), sort descending (highest score first).

    Returns:
        New list of items sorted by score.
    """
    scored = [(scorer(item), i, item) for i, item in enumerate(items)]
    if reverse:
        scored.sort(key=lambda x: (-x[0], x[1]))
    else:
        scored.sort(key=lambda x: (x[0], x[1]))
    return [item for _, _, item in scored]


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _format_count_static(value: int) -> str:
    """Format a raw numeric value into a human-readable count string.

    Standalone version of BaseScraper._format_count for use in pure-function
    context without a scraper instance.

    Args:
        value: Integer count to format.

    Returns:
        Human-readable string like "1.2M", "500K", or "42".
    """
    if not isinstance(value, (int, float)):
        return str(value) if value else ""

    num = float(value)
    if num >= 1_000_000_000:
        return f"{num / 1_000_000_000:.1f}B"
    if num >= 1_000_000:
        return f"{num / 1_000_000:.1f}M"
    if num >= 1_000:
        return f"{num / 1_000:.1f}K"
    return str(int(num))


def safe_parse_float(s: Any) -> float:
    """Robustly parse a string (or any value) to float.

    Handles None, empty strings, non-numeric strings, and already-numeric
    values gracefully.

    Args:
        s: Value to parse.

    Returns:
        Parsed float, or 0.0 on any failure.
    """
    if s is None:
        return 0.0
    if isinstance(s, (int, float)):
        return float(s)
    if isinstance(s, str):
        s = s.strip()
        if not s:
            return 0.0
        try:
            return float(s)
        except ValueError:
            return 0.0
    return 0.0


def _parse_video_stat(vid: Dict[str, Any], *keys: str) -> int:
    """Extract a numeric stat from a video dict, trying multiple key names.

    TikTok APIs and scraper outputs use inconsistent key names for the same
    metric (e.g., "views" vs "view_cnt" vs "play_count"). This helper tries
    each key in order and handles both integer and human-readable string values.

    Args:
        vid: Video dict from recent_videos list.
        *keys: Key names to try, in priority order.

    Returns:
        Integer value of the first matching key, or 0 if none found.
    """
    for key in keys:
        val = vid.get(key)
        if val is None:
            continue
        if isinstance(val, (int, float)):
            return int(val)
        if isinstance(val, str) and val.strip():
            parsed = parse_human_number(val)
            if parsed > 0:
                return parsed
            # Try direct float parse for decimal strings like "1234.0"
            try:
                return int(float(val))
            except ValueError:
                continue
    return 0
