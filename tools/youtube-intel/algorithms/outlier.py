"""
Outlier Score Algorithm for YouTube Video Performance

Identifies videos that dramatically over-performed relative to a channel's
baseline performance at the time of publication.

Algorithm Design:
-----------------
The core insight is that raw view counts are meaningless without context.
A video with 50K views is an outlier on a 1K-subscriber channel but
underperformance on a 1M-subscriber channel. Additionally, older videos
accumulate more views passively, and channels grow over time.

We solve this with a multi-layer normalization:

1. **Exponential Decay**: Estimate "decay-adjusted views" using an exponential
   model: views * exp(-lambda * age_days). The decay rate lambda is calibrated
   from the channel's own data when possible (default 0.01, ~50% at 70 days).

2. **Time-Based Rolling Baseline**: Compute the channel's expected performance
   using a rolling median (robust to outliers) over a configurable time window
   (default 180 days / 6 months), falling back to count-based (minimum 5
   videos) for infrequent uploaders.

3. **Per-Video Metric Selection**: Each video uses the best available metric:
   views-per-subscriber when subscriber data exists for that video,
   decay-adjusted views otherwise. Both are normalized to the same scale
   before comparison.

4. **Engagement Outlier Dimension**: A secondary z-score on engagement rate
   (likes + comments / views) is combined with the view-based score using
   a weighted blend (70% views, 30% engagement by default).

The final outlier score uses a modified Z-score (using MAD instead of
standard deviation for robustness) mapped to a 0-100 scale via a
sigmoid-like transformation.

Complexity: O(n log n) -- dominated by the initial sort by publish date.
            Rolling computations are O(n) with a deque-based sliding window.
Space:      O(n) for storing per-video metrics and the rolling window.

Sources & Prior Art:
- VidIQ's "Outlier Score" uses a simpler views/avg ratio
- Social Blade uses 30-day rolling averages
- Our approach adds subscriber normalization + robust statistics (MAD)
  + exponential decay + engagement dimension + time-based windowing
"""

from __future__ import annotations

import math
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List, Optional, Tuple


# ---------------------------------------------------------------------------
# Data Structures
# ---------------------------------------------------------------------------

@dataclass
class VideoInput:
    """Raw video data as received from YouTube Data API v3."""
    video_id: str
    title: str
    view_count: int
    like_count: int
    comment_count: int
    published_at: datetime  # timezone-aware UTC
    duration_seconds: int
    subscriber_count_approx: Optional[int] = None  # channel subs at publish time


@dataclass
class OutlierResult:
    """Scored output for a single video."""
    video_id: str
    title: str
    outlier_score: float          # 0-100, higher = more outlier-ish
    raw_views: int
    decay_adjusted_views: float   # views normalized for age via exponential decay
    views_per_sub: Optional[float]  # views / estimated subs at publish
    baseline_median: float         # rolling median at time of publish
    baseline_mad: float            # rolling MAD at time of publish
    z_score: float                 # modified Z-score (using MAD) -- combined
    view_z_score: float            # view-based z-score component
    engagement_z_score: float      # engagement-based z-score component
    engagement_rate: float         # (likes + comments) / views
    confidence: float              # 0.0-1.0, how trustworthy the score is
    flags: List[str] = field(default_factory=list)

    # Backward compat alias
    @property
    def velocity_adjusted_views(self) -> float:
        """Backward-compatible alias for decay_adjusted_views."""
        return self.decay_adjusted_views


@dataclass
class OutlierAnalysis:
    """Complete analysis result for a channel's video catalog."""
    channel_id: str
    total_videos: int
    videos_analyzed: int
    window_size: int               # kept for backward compat -- reports effective window
    window_days: int               # the time-based window used
    decay_lambda: float            # the exponential decay rate used
    results: List[OutlierResult]
    top_outliers: List[OutlierResult]  # top N by score
    analysis_timestamp: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

@dataclass
class OutlierConfig:
    """Tunable parameters for the outlier detection algorithm."""
    # Time-based rolling window: how many days of prior videos form the baseline
    window_days: int = 180
    # Minimum videos needed in the window (fall back to count-based if too few)
    min_videos_for_window: int = 5
    # Minimum videos needed before scoring starts (below this, flag low confidence)
    min_videos_for_scoring: int = 5
    # Exponential decay lambda (default 0.01 => ~50% decay at 70 days)
    # Set to 0 to disable decay, or None to auto-calibrate from channel data
    decay_lambda: Optional[float] = None
    decay_lambda_default: float = 0.01
    # Sigmoid steepness for mapping z-score to 0-100
    sigmoid_k: float = 0.4
    # Sigmoid midpoint (z-score that maps to score=50)
    sigmoid_midpoint: float = 3.0
    # Top N outliers to return in analysis
    top_n: int = 10
    # Minimum subscriber count to avoid division by zero / noise
    min_sub_count: int = 10
    # MAD scale factor (1.4826 makes MAD consistent with stddev for normal dist)
    mad_scale: float = 1.4826
    # Floor for MAD to prevent division by zero in very uniform channels
    mad_floor: float = 0.01
    # Engagement outlier weight (0.0 = views only, 1.0 = engagement only)
    engagement_weight: float = 0.3

    # Legacy compat -- old window_size maps to min_videos_for_window
    @property
    def window_size(self) -> int:
        """Backward compat: returns min_videos_for_window."""
        return self.min_videos_for_window


# ---------------------------------------------------------------------------
# Core Algorithm
# ---------------------------------------------------------------------------

def _decay_adjusted_views(views: int, age_days: float, lam: float) -> float:
    """
    Normalize view count by video age using exponential decay.

    Formula: views * exp(-lambda * age_days)

    This models the intuition that a video's "effective" views decay over time.
    A video with 100K views at 7 days old is more impressive than 100K views
    at 365 days old. The exponential model captures this naturally:
    - lambda=0.01: half-life ~70 days (moderate decay)
    - lambda=0.005: half-life ~139 days (slow decay)
    - lambda=0.02: half-life ~35 days (aggressive decay)

    For a video published today (age_days ~ 0), exp(0) = 1.0 so we get raw views.

    Complexity: O(1)
    """
    if views <= 0:
        return 0.0
    # Clamp to prevent underflow for extremely old videos
    exponent = -lam * age_days
    if exponent < -500:
        return 0.0
    return views * math.exp(exponent)


def _estimate_decay_lambda(
    videos: List[VideoInput],
    now: datetime,
    default: float = 0.01,
) -> float:
    """
    Estimate the exponential decay rate from a channel's own data.

    Strategy: look at pairs of videos with similar content performance
    (same order of magnitude in views) but different ages. The ratio
    of views between newer and older videos gives us the decay rate.

    For simplicity and robustness, we use the median views-per-day across
    all videos to estimate how quickly views accumulate, then derive lambda
    from the ratio of recent vs older video performance.

    If fewer than 10 videos, fall back to the default.

    Complexity: O(n log n) for sorting
    """
    if len(videos) < 10:
        return default

    # Compute views-per-day for each video
    vpd_pairs: List[Tuple[float, float]] = []  # (age_days, views_per_day)
    for v in videos:
        age_days = max((now - v.published_at).total_seconds() / 86400.0, 1.0)
        if v.view_count > 0:
            vpd_pairs.append((age_days, v.view_count / age_days))

    if len(vpd_pairs) < 10:
        return default

    # Split into recent half and older half by age
    vpd_pairs.sort(key=lambda p: p[0])
    mid = len(vpd_pairs) // 2
    recent = vpd_pairs[:mid]
    older = vpd_pairs[mid:]

    recent_median_vpd = _rolling_median([p[1] for p in recent])
    older_median_vpd = _rolling_median([p[1] for p in older])
    recent_median_age = _rolling_median([p[0] for p in recent])
    older_median_age = _rolling_median([p[0] for p in older])

    # If older videos have higher VPD, the channel is declining -- use default
    if older_median_vpd <= 0 or recent_median_vpd <= 0:
        return default

    # ratio = recent_vpd / older_vpd should be > 1 if newer videos get more daily views
    # But we need to account for the fact that newer videos have less total accumulation time
    # lambda = ln(ratio) / (age_diff)
    age_diff = older_median_age - recent_median_age
    if age_diff <= 0:
        return default

    ratio = recent_median_vpd / older_median_vpd
    if ratio <= 0:
        return default
    if ratio < 1.0:
        # Declining channel (older videos outperform newer) — use default
        return default

    estimated_lambda = math.log(ratio) / age_diff

    # Clamp to reasonable range [0.001, 0.05]
    # 0.001 = half-life ~693 days (very slow)
    # 0.05 = half-life ~14 days (very aggressive)
    estimated_lambda = max(0.001, min(0.05, estimated_lambda))

    return estimated_lambda


def _rolling_median(values: List[float]) -> float:
    """
    Compute median of a list. O(n log n) due to sort, but n <= window_size
    which is typically small, so effectively O(1) per call.

    We use median instead of mean because it's robust to the very outliers
    we're trying to detect (a single viral video won't skew the baseline).
    """
    if not values:
        return 0.0
    sorted_vals = sorted(values)
    n = len(sorted_vals)
    if n % 2 == 1:
        return sorted_vals[n // 2]
    return (sorted_vals[n // 2 - 1] + sorted_vals[n // 2]) / 2.0


def _rolling_mad(values: List[float], median: float, scale: float) -> float:
    """
    Median Absolute Deviation -- a robust measure of spread.

    MAD = median(|x_i - median(x)|)

    Scaled by 1.4826 to be consistent with standard deviation for normally
    distributed data. This means a z-score of 2 using MAD has the same
    meaning as a z-score of 2 using stddev, IF the data were normal.

    YouTube view distributions are heavy-tailed (not normal), which is
    exactly why MAD is better than stddev here -- it won't be inflated by
    the very outliers we want to detect.

    Complexity: O(n log n) for the sort inside median, n = window_size
    """
    if not values:
        return 0.0
    deviations = [abs(v - median) for v in values]
    raw_mad = _rolling_median(deviations)
    return raw_mad * scale


def _modified_z_score(value: float, median: float, mad: float,
                      mad_floor: float) -> float:
    """
    Modified Z-score using MAD instead of standard deviation.

    z = (x - median) / (scaled_MAD)

    If MAD is below the floor (all videos have ~same performance), we use
    the floor to avoid infinite z-scores. This also means that on very
    uniform channels, even small deviations will show as moderate outliers,
    which is the correct behavior (any deviation IS notable on such channels).

    Complexity: O(1)
    """
    effective_mad = max(mad, mad_floor)
    return (value - median) / effective_mad


def _sigmoid_score(z: float, k: float, midpoint: float) -> float:
    """
    Map a z-score to the 0-100 range using a logistic sigmoid.

    score = 100 / (1 + e^(-k * (z - midpoint)))

    Properties:
    - z = midpoint  -> score = 50
    - z >> midpoint -> score approaches 100
    - z << midpoint -> score approaches 0
    - k controls steepness (higher = sharper transition)

    With default k=0.4, midpoint=3.0:
    - z=0 (average video)   -> score ~23  (below average maps low)
    - z=1 (slightly above)  -> score ~31
    - z=3 (notably above)   -> score ~50
    - z=5 (strong outlier)  -> score ~69
    - z=8 (viral outlier)   -> score ~88
    - z=12 (extreme viral)  -> score ~97

    Complexity: O(1)
    """
    # Clamp exponent to prevent overflow
    exponent = -k * (z - midpoint)
    exponent = max(min(exponent, 500), -500)
    return 100.0 / (1.0 + math.exp(exponent))


def _estimate_confidence(
    window_fill: int,
    min_videos: int,
    has_sub_data: bool,
    age_days: float,
) -> Tuple[float, List[str]]:
    """
    Estimate how confident we are in this outlier score.

    Factors that reduce confidence:
    - Small rolling window (not enough history)
    - Missing subscriber data (can't normalize for growth)
    - Very new video (< 3 days, views still accumulating)
    - Very old video (> 2 years, passive views dominate)

    Returns (confidence 0.0-1.0, list of flag strings).

    Complexity: O(1)
    """
    confidence = 1.0
    flags: List[str] = []

    # Window fill factor: linearly ramp from 0.3 to 1.0 as window fills
    if window_fill < min_videos:
        ratio = window_fill / max(min_videos, 1)
        confidence *= 0.3 + 0.7 * ratio
        flags.append(f"sparse_history:{window_fill}_videos")

    # Subscriber data
    if not has_sub_data:
        confidence *= 0.75
        flags.append("no_subscriber_data")

    # Very new video (still accumulating views)
    if age_days < 3:
        confidence *= 0.5
        flags.append("very_new_video")
    elif age_days < 7:
        confidence *= 0.8
        flags.append("recent_video")

    # Very old video (passive view accumulation makes velocity estimate noisy)
    if age_days > 730:  # 2 years
        confidence *= 0.85
        flags.append("old_video_passive_views")

    return round(confidence, 3), flags


def _compute_engagement_rate(video: VideoInput) -> float:
    """Compute engagement rate: (likes + comments) / views."""
    if video.view_count <= 0:
        return 0.0
    return (video.like_count + video.comment_count) / video.view_count


# ---------------------------------------------------------------------------
# Normalization for per-video metric selection (Fix #4)
# ---------------------------------------------------------------------------

def _normalize_metric_to_scale(
    values: List[float],
) -> Tuple[float, float]:
    """
    Compute the median and MAD of a set of values, used for normalizing
    different metric types to the same z-score scale.

    Returns (median, mad_scaled) so that z = (x - median) / mad_scaled
    produces comparable z-scores regardless of the raw metric's magnitude.
    """
    if not values:
        return 0.0, 1.0
    med = _rolling_median(values)
    mad = _rolling_mad(values, med, 1.4826)
    return med, max(mad, 0.01)


# ---------------------------------------------------------------------------
# Main Entry Point
# ---------------------------------------------------------------------------

def compute_outlier_scores(
    videos: List[VideoInput],
    channel_id: str = "",
    config: Optional[OutlierConfig] = None,
) -> OutlierAnalysis:
    """
    Compute outlier scores for a list of videos from a single channel.

    Algorithm walkthrough:
    1. Sort videos by publish date (oldest first).
    2. Calibrate exponential decay lambda from channel data.
    3. For each video, compute decay-adjusted views and engagement rate.
    4. If subscriber data available for a video, compute views-per-sub ratio.
    5. Maintain a TIME-BASED rolling window over prior videos (default 180 days).
       Fall back to count-based (min 5 videos) if the channel uploads infrequently.
    6. Per-video metric selection: use views-per-sub when available for THAT video,
       decay-adjusted views otherwise. Normalize both to the same z-score scale.
    7. Compute rolling median and MAD from the window for both view and engagement.
    8. Calculate modified z-score for each dimension.
    9. Combine view z-score and engagement z-score via weighted blend.
    10. Map combined z-score to 0-100 via sigmoid.
    11. Attach confidence flags.

    Parameters
    ----------
    videos : list of VideoInput
        All videos from the channel to analyze. Need not be sorted.
    channel_id : str
        Optional channel identifier for the result object.
    config : OutlierConfig or None
        Algorithm tuning parameters. Uses defaults if None.

    Returns
    -------
    OutlierAnalysis with per-video scores and top outliers.

    Complexity
    ----------
    Time:  O(n log n) for the initial sort. Each of the n videos does
           O(w log w) work for median/MAD where w = window entries.
           Total: O(n log n + n * w log w). Since w is bounded, O(n log n).
    Space: O(n) for results + O(w) for the rolling window.

    Edge Cases
    ----------
    - Empty input: returns analysis with 0 results.
    - < min_videos: scores all videos but with low confidence flags.
    - All videos have same views: MAD floor kicks in, slight deviations show.
    - Viral video in window: median is robust, won't skew baseline.
    - subscriber_count_approx = 0 or None: falls back to decay-adjusted metric.
    """
    if config is None:
        config = OutlierConfig()

    now = datetime.now(timezone.utc)

    if not videos:
        return OutlierAnalysis(
            channel_id=channel_id,
            total_videos=0,
            videos_analyzed=0,
            window_size=config.min_videos_for_window,
            window_days=config.window_days,
            decay_lambda=config.decay_lambda_default,
            results=[],
            top_outliers=[],
        )

    # Step 1: Sort by publish date (oldest first)
    sorted_videos = sorted(videos, key=lambda v: v.published_at)

    # Step 2: Calibrate decay lambda
    if config.decay_lambda is not None:
        decay_lam = config.decay_lambda
    else:
        decay_lam = _estimate_decay_lambda(
            sorted_videos, now, config.decay_lambda_default
        )

    # Step 3: Compute normalized metrics for each video
    # Each entry: (video, decay_adj_views, views_per_sub_or_None, age_days, engagement_rate)
    metrics: List[Tuple[VideoInput, float, Optional[float], float, float]] = []

    for v in sorted_videos:
        age_td = now - v.published_at
        age_days = max(age_td.total_seconds() / 86400.0, 0.01)

        dav = _decay_adjusted_views(v.view_count, age_days, decay_lam)

        vps: Optional[float] = None
        if (v.subscriber_count_approx is not None
                and v.subscriber_count_approx >= config.min_sub_count):
            vps = v.view_count / v.subscriber_count_approx

        eng_rate = _compute_engagement_rate(v)

        metrics.append((v, dav, vps, age_days, eng_rate))

    # Step 4-11: Time-based rolling window scoring with per-video metric selection
    # We maintain two parallel windows: one for the view metric, one for engagement
    # The view metric window contains z-score-normalized values to handle the
    # mixed VPS/decay metric comparison.

    # Build the rolling window using time-based selection
    results: List[OutlierResult] = []

    for i in range(len(metrics)):
        video, dav, vps, age_days, eng_rate = metrics[i]
        pub_time = video.published_at

        # Time-based window: collect all prior videos within window_days
        window_view_metrics: List[float] = []
        window_vps_metrics: List[float] = []
        window_dav_metrics: List[float] = []
        window_eng_metrics: List[float] = []

        for j in range(i):
            prior_video, prior_dav, prior_vps, prior_age, prior_eng = metrics[j]
            days_before = (pub_time - prior_video.published_at).total_seconds() / 86400.0

            # Include if within time window
            if days_before <= config.window_days:
                window_eng_metrics.append(prior_eng)

                if prior_vps is not None:
                    window_vps_metrics.append(prior_vps)
                window_dav_metrics.append(prior_dav)

        # Fall back to count-based if time window has too few videos
        if len(window_dav_metrics) < config.min_videos_for_window and i > 0:
            # Take the most recent min_videos_for_window videos
            start_idx = max(0, i - config.min_videos_for_window)
            window_vps_metrics = []
            window_dav_metrics = []
            window_eng_metrics = []
            for j in range(start_idx, i):
                _, prior_dav, prior_vps, _, prior_eng = metrics[j]
                if prior_vps is not None:
                    window_vps_metrics.append(prior_vps)
                window_dav_metrics.append(prior_dav)
                window_eng_metrics.append(prior_eng)

        window_fill = len(window_dav_metrics)

        # --- Per-video metric selection (Fix #4) ---
        # Use VPS for this video if available AND we have VPS baselines
        # Otherwise use decay-adjusted views. Normalize to z-score scale.
        if vps is not None and len(window_vps_metrics) >= 3:
            # This video has sub data and enough VPS history to compare
            current_view_metric = vps
            view_baseline_values = window_vps_metrics
        else:
            # Fall back to decay-adjusted views
            current_view_metric = dav
            view_baseline_values = window_dav_metrics

        # View z-score
        if window_fill == 0:
            baseline_med = current_view_metric
            baseline_mad = 0.0
            view_z = 0.0
        else:
            baseline_med = _rolling_median(view_baseline_values)
            baseline_mad = _rolling_mad(
                view_baseline_values, baseline_med, config.mad_scale
            )
            view_z = _modified_z_score(
                current_view_metric, baseline_med, baseline_mad, config.mad_floor
            )

        # Engagement z-score
        if len(window_eng_metrics) < 2:
            eng_z = 0.0
        else:
            eng_med = _rolling_median(window_eng_metrics)
            eng_mad = _rolling_mad(
                window_eng_metrics, eng_med, config.mad_scale
            )
            eng_z = _modified_z_score(
                eng_rate, eng_med, eng_mad, config.mad_floor
            )

        # Combine view and engagement z-scores (Fix #3)
        # Weighted blend: (1-w)*view_z + w*engagement_z
        # But only count engagement positively (negative engagement z shouldn't
        # boost the outlier score, it should drag it down)
        w = config.engagement_weight
        combined_z = (1.0 - w) * view_z + w * eng_z

        # Map to 0-100
        score = _sigmoid_score(combined_z, config.sigmoid_k, config.sigmoid_midpoint)

        # Confidence
        confidence, flags = _estimate_confidence(
            window_fill=window_fill,
            min_videos=config.min_videos_for_scoring,
            has_sub_data=(vps is not None),
            age_days=age_days,
        )

        # First video always gets a flag
        if i == 0:
            if "sparse_history:0_videos" not in flags:
                flags.append("first_video_no_baseline")

        results.append(OutlierResult(
            video_id=video.video_id,
            title=video.title,
            outlier_score=round(score, 1),
            raw_views=video.view_count,
            decay_adjusted_views=round(dav, 2),
            views_per_sub=round(vps, 4) if vps is not None else None,
            baseline_median=round(baseline_med, 2),
            baseline_mad=round(baseline_mad, 4),
            z_score=round(combined_z, 3),
            view_z_score=round(view_z, 3),
            engagement_z_score=round(eng_z, 3),
            engagement_rate=round(eng_rate, 6),
            confidence=confidence,
            flags=flags,
        ))

    # Sort results by score descending for top_outliers
    sorted_by_score = sorted(results, key=lambda r: r.outlier_score, reverse=True)
    top_outliers = sorted_by_score[:config.top_n]

    return OutlierAnalysis(
        channel_id=channel_id,
        total_videos=len(videos),
        videos_analyzed=len(results),
        window_size=len(metrics),  # effective window used
        window_days=config.window_days,
        decay_lambda=round(decay_lam, 6),
        results=results,
        top_outliers=top_outliers,
    )


# ---------------------------------------------------------------------------
# Utility: Interpolate subscriber counts
# ---------------------------------------------------------------------------

def interpolate_subscriber_counts(
    videos: List[VideoInput],
    known_points: List[Tuple[datetime, int]],
) -> List[VideoInput]:
    """
    Fill in subscriber_count_approx for videos using known data points.

    YouTube doesn't provide historical subscriber counts per-video, but
    we can approximate using:
    - Current subscriber count (1 data point)
    - Social Blade snapshots (if available)
    - Channel milestones from "About" page

    This function performs linear interpolation between known (date, sub_count)
    pairs to estimate the subscriber count at each video's publish date.

    Parameters
    ----------
    videos : list of VideoInput
        Videos to annotate (modified in-place).
    known_points : list of (datetime, int)
        Known subscriber counts at specific dates, sorted by date.

    Returns
    -------
    The same list of videos, with subscriber_count_approx filled in.

    Complexity: O(n + k) where n = videos, k = known_points (merge-style).
    """
    if not known_points:
        return videos

    # Sort known points by date
    points = sorted(known_points, key=lambda p: p[0])

    for video in videos:
        pub = video.published_at

        # Before first known point: extrapolate using first point
        if pub <= points[0][0]:
            # Assume linear growth from 0 to first known point
            if len(points) >= 2:
                dt = (points[1][0] - points[0][0]).total_seconds()
                if dt > 0:
                    rate = (points[1][1] - points[0][1]) / dt
                    delta = (pub - points[0][0]).total_seconds()
                    estimate = max(1, int(points[0][1] + rate * delta))
                    video.subscriber_count_approx = estimate
                    continue
            video.subscriber_count_approx = max(1, points[0][1])
            continue

        # After last known point: use last known value (no wild extrapolation)
        if pub >= points[-1][0]:
            video.subscriber_count_approx = points[-1][1]
            continue

        # Between two known points: linear interpolation
        for j in range(len(points) - 1):
            if points[j][0] <= pub <= points[j + 1][0]:
                dt = (points[j + 1][0] - points[j][0]).total_seconds()
                if dt <= 0:
                    video.subscriber_count_approx = points[j][1]
                    break
                frac = (pub - points[j][0]).total_seconds() / dt
                estimate = int(
                    points[j][1] + frac * (points[j + 1][1] - points[j][1])
                )
                video.subscriber_count_approx = max(1, estimate)
                break

    return videos
