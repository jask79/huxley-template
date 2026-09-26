"""
Keyword Competition Score Algorithm for YouTube Search Terms

Estimates how competitive a YouTube search term is by analyzing the
characteristics of videos currently ranking for that term, plus proxy
signals for search volume.

Algorithm Design:
-----------------
YouTube doesn't expose search volume directly. We construct two INDEPENDENT
scores on separate axes:

**Competition Score (0-100):**
Measures how hard it is to rank for this term. Composed of four signals,
each normalized to 0-1 and combined via weighted sum:

1. **Authority Signal (weight 0.20):** Average subscriber count of top-ranking
   channels. High-authority channels dominating = hard to compete.
   Normalized via log scale (subscribers follow power-law distribution).

2. **View Momentum Signal (weight 0.30):** Average views of top-ranking videos,
   blended with age-weighted view velocity. Fresh high-view videos are a much
   stronger competitive signal than old high-view videos.
   Also log-normalized.

3. **Freshness Signal (weight 0.25):** Median age of top results. If old videos
   still rank, the niche is stale and easier to enter. If results are fresh,
   active competition is high.

4. **Engagement Signal (weight 0.25):** Average engagement rate (likes + comments
   per view). High engagement = loyal audiences, harder to displace.

**Opportunity Score (0-100):**
INDEPENDENT axis based on volume proxy, freshness gap, engagement gap,
and content quality gap. NOT derived from competition. Both scores are
0-100 on independent axes -- the user interprets the 2D space.

Complexity: O(n) where n = number of search results analyzed (typically 20).
Space:      O(n) for storing per-result metrics.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List, Optional, Tuple


# ---------------------------------------------------------------------------
# Data Structures
# ---------------------------------------------------------------------------

@dataclass
class SearchResultVideo:
    """A single video from YouTube search results for a keyword."""
    video_id: str
    title: str
    channel_id: str
    channel_title: str
    channel_subscriber_count: int
    view_count: int
    like_count: int
    comment_count: int
    published_at: datetime
    duration_seconds: int
    has_captions: bool = False
    description_length: int = 0


@dataclass
class AutocompleteData:
    """Data from YouTube's autocomplete/suggest API."""
    query: str
    suggestions: List[str]           # ordered by YouTube's ranking
    query_position: Optional[int]    # position of our query in suggestions (if present)
    total_suggestions: int = 0
    result_count: Optional[int] = None  # total search results if available


@dataclass
class TrendData:
    """Optional Google Trends data for the keyword."""
    interest_over_time: Optional[float] = None   # 0-100 (Google's scale)
    trend_direction: Optional[str] = None        # "rising", "stable", "declining"
    related_queries: List[str] = field(default_factory=list)


@dataclass
class KeywordResult:
    """Complete keyword analysis result."""
    keyword: str
    competition_score: float      # 0-100 (100 = extremely competitive)
    opportunity_score: float      # 0-100 (100 = best opportunity) -- INDEPENDENT axis
    volume_proxy: float           # 0-1 estimated relative search volume
    confidence: float             # 0-1 how trustworthy the scores are
    flags: List[str] = field(default_factory=list)

    # Signal breakdown (each 0-1 before weighting)
    authority_signal: float = 0.0
    view_momentum_signal: float = 0.0
    freshness_signal: float = 0.0
    engagement_signal: float = 0.0

    # Derived insights
    avg_top_subscribers: float = 0.0
    avg_top_views: float = 0.0
    median_age_days: float = 0.0
    avg_engagement_rate: float = 0.0
    freshness_gap: bool = False      # True if old stale content dominates

    # Opportunity sub-signals (new)
    opportunity_volume: float = 0.0        # volume contribution to opportunity
    opportunity_freshness_gap: float = 0.0  # freshness gap contribution
    opportunity_engagement_gap: float = 0.0 # engagement gap contribution
    opportunity_quality_gap: float = 0.0    # content quality gap contribution

    # Actionable output
    difficulty_label: str = ""       # "very_low", "low", "medium", "high", "very_high"
    recommendation: str = ""


@dataclass
class KeywordBatchResult:
    """Results for analyzing multiple keywords (for comparison)."""
    keywords: List[KeywordResult]
    analyzed_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

@dataclass
class KeywordConfig:
    """Tunable weights and thresholds for keyword competition scoring."""
    # Signal weights (must sum to 1.0)
    weight_authority: float = 0.20
    weight_views: float = 0.30
    weight_freshness: float = 0.25
    weight_engagement: float = 0.25

    # View momentum: blend raw views with age-weighted velocity
    view_velocity_blend: float = 0.4  # 40% velocity, 60% raw views

    # Log normalization anchors
    # Subscriber counts: log10(1M) = 6, we normalize to [0, 1] over [0, 7]
    sub_log_cap: float = 7.0       # log10(10M) -- channels above this all map to 1.0
    sub_log_floor: float = 2.0     # log10(100) -- below this is negligible

    # View counts: similar log normalization
    views_log_cap: float = 7.0     # log10(10M views)
    views_log_floor: float = 3.0   # log10(1K views)

    # Freshness: age in days where "fresh" transitions to "stale"
    freshness_fresh_days: float = 90.0    # < 90 days = fresh
    freshness_stale_days: float = 730.0   # > 2 years = stale
    freshness_gap_threshold_days: float = 365.0  # old content gap

    # Engagement rate normalization
    engagement_high: float = 0.08   # 8% engagement = very high
    engagement_low: float = 0.005   # 0.5% = low

    # Volume proxy from autocomplete -- gradient-based (Fix #4)
    # Now uses smooth interpolation instead of hard tiers
    autocomplete_max_position: int = 15  # positions beyond this all get floor score
    autocomplete_floor: float = 0.10     # minimum score for being in autocomplete
    autocomplete_absent_value: float = 0.08  # not in suggestions at all
    # Result count normalization (if available)
    result_count_low: float = 10000.0    # fewer than this = low volume
    result_count_high: float = 5000000.0  # more than this = high volume
    result_count_weight: float = 0.3     # blend weight for result count signal

    # Opportunity weights (independent axis)
    opportunity_weight_volume: float = 0.40
    opportunity_weight_freshness_gap: float = 0.25
    opportunity_weight_engagement_gap: float = 0.20
    opportunity_weight_quality_gap: float = 0.15

    # Minimum results needed for reliable scoring
    min_results: int = 5

    # Number of top results to weight more heavily
    top_n_weight: int = 5


# ---------------------------------------------------------------------------
# Normalization Helpers
# ---------------------------------------------------------------------------

def _log_normalize(value: float, floor: float, cap: float) -> float:
    """
    Map a positive value to [0, 1] using log10 scale with floor and cap.

    Values below 10^floor map to 0, above 10^cap map to 1.
    Linear interpolation in log space between floor and cap.

    This is essential for YouTube metrics which follow power-law distributions:
    subscriber counts range from 0 to 200M+ and view counts similarly.
    Linear normalization would make everything below 1M look identical.

    Complexity: O(1)
    """
    if value <= 0:
        return 0.0
    log_val = math.log10(value)
    if log_val <= floor:
        return 0.0
    if log_val >= cap:
        return 1.0
    return (log_val - floor) / (cap - floor)


def _linear_normalize(value: float, low: float, high: float) -> float:
    """Map value from [low, high] to [0, 1], clamped."""
    if high <= low:
        return 0.5
    return max(0.0, min(1.0, (value - low) / (high - low)))


def _weighted_average(values: List[float], top_n: int) -> float:
    """
    Compute weighted average giving more weight to top-ranked results.

    Top-N results get weight 2.0, remaining get weight 1.0.
    This reflects that position #1-5 in search results matter more
    than position #15-20 for assessing competition.

    Complexity: O(n)
    """
    if not values:
        return 0.0
    total_weight = 0.0
    weighted_sum = 0.0
    for i, v in enumerate(values):
        w = 2.0 if i < top_n else 1.0
        weighted_sum += v * w
        total_weight += w
    return weighted_sum / total_weight


def _median(values: List[float]) -> float:
    """Simple median. O(n log n) for sort, but n is small (<=20)."""
    if not values:
        return 0.0
    s = sorted(values)
    n = len(s)
    if n % 2 == 1:
        return s[n // 2]
    return (s[n // 2 - 1] + s[n // 2]) / 2.0


# ---------------------------------------------------------------------------
# Signal Computation
# ---------------------------------------------------------------------------

def _compute_authority_signal(
    results: List[SearchResultVideo],
    config: KeywordConfig,
) -> Tuple[float, float]:
    """
    Authority signal: how dominant are the channels ranking for this keyword?

    Returns (normalized signal 0-1, raw average subscribers).

    High subscriber channels dominating = high competition. We use log-scale
    normalization because subscriber counts span 6+ orders of magnitude.

    Complexity: O(n)
    """
    if not results:
        return 0.0, 0.0

    sub_counts = [r.channel_subscriber_count for r in results]
    avg_subs = _weighted_average(
        [float(s) for s in sub_counts], config.top_n_weight
    )
    signal = _log_normalize(avg_subs, config.sub_log_floor, config.sub_log_cap)
    return signal, avg_subs


def _compute_view_momentum_signal(
    results: List[SearchResultVideo],
    config: KeywordConfig,
    now: datetime,
) -> Tuple[float, float]:
    """
    View momentum: how many views do the ranking videos have, weighted by
    video age to detect fresh high-performers?

    Returns (normalized signal 0-1, raw average views).

    Blends raw view count with age-weighted view velocity (views/age_days).
    Fresh high-view videos are a MUCH stronger competitive signal than
    old high-view videos that accumulated passively.

    Complexity: O(n)
    """
    if not results:
        return 0.0, 0.0

    raw_views = [float(r.view_count) for r in results]
    avg_raw = _weighted_average(raw_views, config.top_n_weight)
    raw_signal = _log_normalize(avg_raw, config.views_log_floor, config.views_log_cap)

    # Age-weighted velocity: views / age_days for each result
    velocities: List[float] = []
    for r in results:
        age_days = max((now - r.published_at).total_seconds() / 86400.0, 1.0)
        velocities.append(r.view_count / age_days)

    avg_velocity = _weighted_average(velocities, config.top_n_weight)
    # Normalize velocity on a log scale. A velocity of 1000 views/day is high,
    # 10 views/day is low. Use log10 range [1, 5] (10 to 100K views/day).
    velocity_signal = _log_normalize(avg_velocity, 1.0, 5.0)

    # Blend raw views with velocity
    blend = config.view_velocity_blend
    signal = (1.0 - blend) * raw_signal + blend * velocity_signal

    return signal, avg_raw


def _compute_freshness_signal(
    results: List[SearchResultVideo],
    config: KeywordConfig,
    now: datetime,
) -> Tuple[float, float, bool]:
    """
    Freshness signal: how old are the ranking videos?

    Returns (normalized signal 0-1, median age in days, freshness_gap flag).

    INVERTED: fresh results = HIGH competition (active creators competing).
    Old stale results = LOW competition (opportunity to enter).

    The freshness_gap flag is True when median age exceeds the gap threshold,
    indicating a content void that new creators can fill.

    Complexity: O(n log n) for median sort, n is small.
    """
    if not results:
        return 0.5, 0.0, False

    ages_days = []
    for r in results:
        age = (now - r.published_at).total_seconds() / 86400.0
        ages_days.append(max(age, 0.0))

    med_age = _median(ages_days)

    # Invert: fresh = high signal (high competition), stale = low signal
    # Map [stale_days, fresh_days] -> [0, 1]
    # If median age < fresh_days -> signal = 1.0 (very competitive, fresh content)
    # If median age > stale_days -> signal = 0.0 (stale, low competition)
    signal = 1.0 - _linear_normalize(
        med_age,
        config.freshness_fresh_days,
        config.freshness_stale_days,
    )

    freshness_gap = med_age > config.freshness_gap_threshold_days

    return signal, med_age, freshness_gap


def _compute_engagement_signal(
    results: List[SearchResultVideo],
    config: KeywordConfig,
) -> Tuple[float, float]:
    """
    Engagement signal: how engaged are viewers of ranking videos?

    Returns (normalized signal 0-1, raw average engagement rate).

    Engagement rate = (likes + comments) / views.
    High engagement suggests loyal audiences that are harder to pull away.

    Complexity: O(n)
    """
    if not results:
        return 0.0, 0.0

    rates = []
    for r in results:
        if r.view_count > 0:
            rate = (r.like_count + r.comment_count) / r.view_count
            rates.append(rate)
        else:
            rates.append(0.0)

    avg_rate = _weighted_average(rates, config.top_n_weight)
    signal = _linear_normalize(avg_rate, config.engagement_low, config.engagement_high)
    return signal, avg_rate


# ---------------------------------------------------------------------------
# Volume Proxy (improved with gradient + result count)
# ---------------------------------------------------------------------------

def _compute_volume_proxy(
    autocomplete: Optional[AutocompleteData],
    trend: Optional[TrendData],
    config: KeywordConfig,
) -> float:
    """
    Estimate relative search volume from indirect signals.

    YouTube doesn't expose search volume. We proxy it from:
    1. Autocomplete position: terms suggested earlier have higher volume.
       Now uses smooth gradient interpolation instead of hard tiers.
    2. Result count: total number of search results (if available).
       More results = more content = likely higher search demand.
    3. Google Trends interest score (if available): normalized 0-100.

    Combined as: weighted blend of available signals.

    Returns a value in [0, 1].

    Complexity: O(1)
    """
    auto_score = config.autocomplete_absent_value  # default if no data

    if autocomplete is not None:
        pos = autocomplete.query_position
        if pos is not None and pos >= 1:
            # Smooth gradient: position 1 = 1.0, position max_pos = floor
            # Linear interpolation between 1.0 and floor
            max_pos = config.autocomplete_max_position
            if pos >= max_pos:
                auto_score = config.autocomplete_floor
            else:
                # Linear from 1.0 (pos=1) to floor (pos=max_pos)
                auto_score = 1.0 - (1.0 - config.autocomplete_floor) * (pos - 1) / (max_pos - 1)
        elif autocomplete.total_suggestions > 0:
            # Query appeared in related suggestions but not exact match
            auto_score = config.autocomplete_absent_value

        # Blend with result count if available
        if autocomplete.result_count is not None and autocomplete.result_count > 0:
            result_signal = _log_normalize(
                float(autocomplete.result_count),
                math.log10(config.result_count_low),
                math.log10(config.result_count_high),
            )
            rw = config.result_count_weight
            auto_score = (1.0 - rw) * auto_score + rw * result_signal

    trend_score = 0.0
    if trend is not None and trend.interest_over_time is not None:
        trend_score = trend.interest_over_time / 100.0

    return max(auto_score, trend_score * 0.5)


# ---------------------------------------------------------------------------
# Opportunity Score (independent axis)
# ---------------------------------------------------------------------------

def _compute_opportunity_score(
    results: List[SearchResultVideo],
    volume_proxy: float,
    freshness_gap: bool,
    median_age_days: float,
    avg_engagement_rate: float,
    config: KeywordConfig,
    now: datetime,
) -> Tuple[float, float, float, float, float]:
    """
    Compute opportunity score as an INDEPENDENT axis from competition.

    Opportunity measures: "Is there a gap in the market that new content
    can fill, AND is there enough demand to make it worthwhile?"

    Four sub-signals:
    1. Volume (40%): Is there search demand?
    2. Freshness gap (25%): Are top results stale / outdated?
    3. Engagement gap (20%): Are top results poorly engaged (beatable)?
    4. Quality gap (15%): Are top results low-effort (short, no captions, thin)?

    Returns (overall 0-100, volume_sub, freshness_sub, engagement_sub, quality_sub)
    """
    # --- Volume sub-signal ---
    volume_sub = volume_proxy  # already 0-1

    # --- Freshness gap sub-signal ---
    if freshness_gap:
        # Strong signal: top results are old
        # Scale by how old (1 year = moderate, 2+ years = strong)
        freshness_sub = min(1.0, median_age_days / config.freshness_stale_days)
    else:
        # Even without a full "gap", some staleness is opportunity
        freshness_sub = _linear_normalize(
            median_age_days,
            config.freshness_fresh_days * 0.5,  # starts at half the fresh threshold
            config.freshness_gap_threshold_days,
        ) * 0.5  # cap at 0.5 when not a full gap

    # --- Engagement gap sub-signal ---
    # Low engagement in top results = opportunity to beat them with better content
    # Invert: low engagement = high opportunity
    if avg_engagement_rate > 0:
        eng_gap = 1.0 - _linear_normalize(
            avg_engagement_rate,
            config.engagement_low,
            config.engagement_high,
        )
    else:
        eng_gap = 0.8  # no data = moderate opportunity

    # --- Quality gap sub-signal ---
    # Check for low-quality signals in top results: short descriptions,
    # no captions, short videos (potential low-effort content)
    quality_signals: List[float] = []
    if results:
        # Description quality: short descriptions = quality gap
        avg_desc_len = sum(r.description_length for r in results) / len(results)
        desc_gap = 1.0 - _linear_normalize(avg_desc_len, 100.0, 2000.0)
        quality_signals.append(desc_gap)

        # Caption availability: few captions = quality gap
        caption_ratio = sum(1 for r in results if r.has_captions) / len(results)
        caption_gap = 1.0 - caption_ratio
        quality_signals.append(caption_gap)

        # Duration variety: if all videos are very short (<5min), there's a gap
        # for comprehensive long-form content
        avg_duration = sum(r.duration_seconds for r in results) / len(results)
        if avg_duration < 300:  # < 5 min average
            quality_signals.append(0.7)
        elif avg_duration < 600:  # < 10 min
            quality_signals.append(0.3)
        else:
            quality_signals.append(0.0)

    quality_gap = sum(quality_signals) / len(quality_signals) if quality_signals else 0.5

    # --- Combine sub-signals ---
    opportunity = (
        config.opportunity_weight_volume * volume_sub
        + config.opportunity_weight_freshness_gap * freshness_sub
        + config.opportunity_weight_engagement_gap * eng_gap
        + config.opportunity_weight_quality_gap * quality_gap
    )

    # Scale to 0-100
    opportunity_score = round(min(100.0, opportunity * 100), 1)

    return opportunity_score, volume_sub, freshness_sub, eng_gap, quality_gap


# ---------------------------------------------------------------------------
# Difficulty Labels & Recommendations
# ---------------------------------------------------------------------------

_DIFFICULTY_THRESHOLDS = [
    (20, "very_low", "Excellent opportunity. Low barrier to entry, create quality content and rank quickly."),
    (40, "low", "Good opportunity. Some competition but beatable with well-optimized content."),
    (60, "medium", "Moderate competition. Requires strong SEO, good content, and possibly channel authority."),
    (80, "high", "Competitive keyword. Established creators dominate. Consider long-tail variants."),
    (101, "very_high", "Extremely competitive. Major channels dominate. Focus on sub-niches or unique angles."),
]


def _classify_difficulty(competition: float) -> Tuple[str, str]:
    """Map competition score to difficulty label and recommendation."""
    for threshold, label, rec in _DIFFICULTY_THRESHOLDS:
        if competition < threshold:
            return label, rec
    return "very_high", _DIFFICULTY_THRESHOLDS[-1][2]


# ---------------------------------------------------------------------------
# Main Entry Points
# ---------------------------------------------------------------------------

def compute_keyword_competition(
    keyword: str,
    results: List[SearchResultVideo],
    autocomplete: Optional[AutocompleteData] = None,
    trend: Optional[TrendData] = None,
    config: Optional[KeywordConfig] = None,
) -> KeywordResult:
    """
    Compute competition and opportunity scores for a YouTube search keyword.

    Competition and opportunity are now INDEPENDENT axes:
    - Competition (0-100): How hard is it to rank? Based on authority, views,
      freshness, and engagement of current top results.
    - Opportunity (0-100): Is there a gap worth filling? Based on volume,
      content freshness gaps, engagement gaps, and quality gaps.

    A keyword can be both high-competition AND high-opportunity (e.g., a popular
    topic where existing content is outdated). The user interprets the 2D space.

    Parameters
    ----------
    keyword : str
        The search term being analyzed.
    results : list of SearchResultVideo
        Top search results for this keyword (ideally 10-20 videos).
    autocomplete : AutocompleteData or None
        YouTube autocomplete data for volume estimation.
    trend : TrendData or None
        Google Trends data for volume/trajectory.
    config : KeywordConfig or None
        Algorithm tuning parameters.

    Returns
    -------
    KeywordResult with competition score, opportunity score, and breakdown.

    Complexity
    ----------
    Time:  O(n) where n = len(results). All operations are linear scans
           with O(1) normalization. The median in freshness is O(n log n)
           but n <= 20, so effectively O(1).
    Space: O(n) for intermediate lists.

    Edge Cases
    ----------
    - No results: returns competition=0, opportunity depends on volume proxy.
    - All results from same channel: flags "single_channel_dominance".
    - Very few results (<5): low confidence flag.
    - All results very old: freshness_gap flag triggers opportunity boost.
    """
    if config is None:
        config = KeywordConfig()

    now = datetime.now(timezone.utc)
    flags: List[str] = []

    # Handle empty/sparse results
    if not results:
        volume = _compute_volume_proxy(autocomplete, trend, config)
        label, rec = _classify_difficulty(0.0)
        return KeywordResult(
            keyword=keyword,
            competition_score=0.0,
            opportunity_score=round(volume * 100, 1),
            volume_proxy=round(volume, 3),
            confidence=0.2,
            flags=["no_search_results"],
            difficulty_label=label,
            recommendation=rec,
            opportunity_volume=round(volume, 4),
        )

    confidence = 1.0
    if len(results) < config.min_results:
        confidence *= 0.6
        flags.append(f"sparse_results:{len(results)}")

    # Detect single-channel dominance
    channels = set(r.channel_id for r in results)
    if len(channels) == 1:
        flags.append("single_channel_dominance")
    elif len(channels) <= 3 and len(results) >= 10:
        flags.append("oligopoly_top_results")

    # Compute all four signals
    authority_sig, avg_subs = _compute_authority_signal(results, config)
    views_sig, avg_views = _compute_view_momentum_signal(results, config, now)
    freshness_sig, med_age, freshness_gap = _compute_freshness_signal(
        results, config, now
    )
    engagement_sig, avg_engagement = _compute_engagement_signal(results, config)

    if freshness_gap:
        flags.append("content_freshness_gap")

    # Weighted combination for competition score
    competition_raw = (
        config.weight_authority * authority_sig
        + config.weight_views * views_sig
        + config.weight_freshness * freshness_sig
        + config.weight_engagement * engagement_sig
    )
    competition_score = round(competition_raw * 100, 1)

    # Volume proxy
    volume = _compute_volume_proxy(autocomplete, trend, config)

    # Independent opportunity score
    (opportunity_score, opp_vol, opp_fresh, opp_eng, opp_quality) = (
        _compute_opportunity_score(
            results=results,
            volume_proxy=volume,
            freshness_gap=freshness_gap,
            median_age_days=med_age,
            avg_engagement_rate=avg_engagement,
            config=config,
            now=now,
        )
    )

    # Difficulty classification
    label, rec = _classify_difficulty(competition_score)

    return KeywordResult(
        keyword=keyword,
        competition_score=competition_score,
        opportunity_score=opportunity_score,
        volume_proxy=round(volume, 3),
        confidence=round(confidence, 3),
        flags=flags,
        authority_signal=round(authority_sig, 4),
        view_momentum_signal=round(views_sig, 4),
        freshness_signal=round(freshness_sig, 4),
        engagement_signal=round(engagement_sig, 4),
        avg_top_subscribers=round(avg_subs, 0),
        avg_top_views=round(avg_views, 0),
        median_age_days=round(med_age, 1),
        avg_engagement_rate=round(avg_engagement, 5),
        freshness_gap=freshness_gap,
        opportunity_volume=round(opp_vol, 4),
        opportunity_freshness_gap=round(opp_fresh, 4),
        opportunity_engagement_gap=round(opp_eng, 4),
        opportunity_quality_gap=round(opp_quality, 4),
        difficulty_label=label,
        recommendation=rec,
    )


def compute_keyword_batch(
    keywords_data: List[Tuple[
        str,                                    # keyword
        List[SearchResultVideo],                # search results
        Optional[AutocompleteData],             # autocomplete
        Optional[TrendData],                    # trends
    ]],
    config: Optional[KeywordConfig] = None,
) -> KeywordBatchResult:
    """
    Analyze multiple keywords and return ranked results.

    Useful for comparing keyword opportunities side-by-side. Results are
    sorted by opportunity_score descending (best opportunities first).

    Parameters
    ----------
    keywords_data : list of tuples
        Each tuple contains (keyword, results, autocomplete, trend).
    config : KeywordConfig or None
        Shared config for all keywords.

    Returns
    -------
    KeywordBatchResult with keywords sorted by opportunity.

    Complexity: O(k * n) where k = number of keywords, n = results per keyword.
    """
    results = []
    for keyword, search_results, autocomplete, trend in keywords_data:
        result = compute_keyword_competition(
            keyword=keyword,
            results=search_results,
            autocomplete=autocomplete,
            trend=trend,
            config=config,
        )
        results.append(result)

    # Sort by opportunity descending
    results.sort(key=lambda r: r.opportunity_score, reverse=True)

    return KeywordBatchResult(keywords=results)


# ---------------------------------------------------------------------------
# Utility: Estimate Volume from Autocomplete
# ---------------------------------------------------------------------------

def estimate_relative_volume(
    suggestions: List[str],
    target_keyword: str,
) -> Optional[int]:
    """
    Find the position of a keyword in YouTube autocomplete suggestions.

    YouTube orders autocomplete suggestions roughly by search volume.
    Position 1-3 = high volume, 4-7 = medium, 8+ = low.
    Not found = very low or no volume.

    This is a simple utility to extract position from raw autocomplete data.

    Parameters
    ----------
    suggestions : list of str
        Ordered autocomplete suggestions from YouTube.
    target_keyword : str
        The keyword to find.

    Returns
    -------
    Position (1-indexed) or None if not found.

    Complexity: O(k * m) where k = suggestions, m = keyword length.
    """
    target_lower = target_keyword.lower().strip()
    for i, suggestion in enumerate(suggestions):
        if suggestion.lower().strip() == target_lower:
            return i + 1
    # Fuzzy: check if target is a prefix/substring of any suggestion
    for i, suggestion in enumerate(suggestions):
        if target_lower in suggestion.lower():
            return i + 1
    return None
