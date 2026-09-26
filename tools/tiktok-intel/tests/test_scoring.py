"""Unit tests for the scoring module.

Tests cover all five public functions and the key private helpers,
verifying boundary conditions, known-value computations, and edge cases.

Run: python3 -m pytest tools/tiktok-intel/tests/test_scoring.py -v
"""

import math
import sys
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Import setup: add tool directory to sys.path so the package resolves
# whether tests are run from the repo root or the tool directory.
# ---------------------------------------------------------------------------
_TOOL_DIR = Path(__file__).resolve().parent.parent
_REPO_ROOT = _TOOL_DIR.parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
if str(_TOOL_DIR.parent) not in sys.path:
    sys.path.insert(0, str(_TOOL_DIR.parent))

# Register the package under a valid Python identifier since the directory
# name "tiktok-intel" contains a hyphen.
import importlib.util

if "tiktok_intel" not in sys.modules:
    pkg_spec = importlib.util.spec_from_file_location(
        "tiktok_intel",
        _TOOL_DIR / "__init__.py",
        submodule_search_locations=[str(_TOOL_DIR)],
    )
    pkg = importlib.util.module_from_spec(pkg_spec)
    sys.modules["tiktok_intel"] = pkg
    pkg_spec.loader.exec_module(pkg)

# Now load the submodules we need
for mod_name in ["config", "exceptions", "models", "formatters", "scoring"]:
    full = f"tiktok_intel.{mod_name}"
    if full not in sys.modules:
        spec = importlib.util.spec_from_file_location(
            full, _TOOL_DIR / f"{mod_name}.py",
        )
        mod = importlib.util.module_from_spec(spec)
        sys.modules[full] = mod
        spec.loader.exec_module(mod)

from tiktok_intel.models import (
    CompetitorProfile,
    SearchVideoResult,
    ShopProduct,
    TrendingCreator,
    TrendingHashtag,
    TrendingSong,
    TrendingVideo,
)
from tiktok_intel.scoring import (
    VELOCITY_ORDER,
    _format_count_static,
    _parse_video_stat,
    safe_parse_float,
    classify_trend_velocity,
    rank_results,
    score_competitor_engagement,
    score_shop_product,
    score_video_engagement,
)


# ===========================================================================
# score_video_engagement
# ===========================================================================

class TestScoreVideoEngagement:
    """Tests for score_video_engagement()."""

    def test_zero_views_returns_zero(self):
        """Zero views should always return 0.0."""
        video = SearchVideoResult(
            title="test", creator="test",
            view_cnt=0, like_cnt=100, comment_cnt=50, share_cnt=10,
        )
        assert score_video_engagement(video) == 0.0

    def test_average_engagement_near_fifty(self):
        """~5% weighted engagement (sigmoid midpoint) should score ~50."""
        # Engineer counts so that weighted rate ~ 0.05
        # W_LIKES=0.35, W_COMMENTS=0.40, W_SHARES=0.25
        # Simplest: equal rates r across all three -> weighted = r*(0.35+0.40+0.25) = r
        # So set each rate to 0.05 -> weighted = 0.05
        video = SearchVideoResult(
            title="avg", creator="test",
            view_cnt=10000,
            like_cnt=500,      # 5% like rate
            comment_cnt=500,   # 5% comment rate
            share_cnt=500,     # 5% share rate
        )
        score = score_video_engagement(video)
        assert 45.0 <= score <= 55.0, f"Expected ~50, got {score}"

    def test_high_engagement_above_ninety(self):
        """10%+ engagement should score >90."""
        video = SearchVideoResult(
            title="viral", creator="test",
            view_cnt=100000,
            like_cnt=15000,    # 15%
            comment_cnt=8000,  # 8%
            share_cnt=5000,    # 5%
        )
        score = score_video_engagement(video)
        assert score > 90.0, f"Expected >90, got {score}"

    def test_all_zeros_except_views_near_zero(self):
        """Views with no engagement should give near-zero score."""
        video = SearchVideoResult(
            title="dead", creator="test",
            view_cnt=1000000,
            like_cnt=0, comment_cnt=0, share_cnt=0,
        )
        score = score_video_engagement(video)
        assert score < 5.0, f"Expected near-zero, got {score}"

    def test_likes_greater_than_views_caps_at_hundred(self):
        """Outlier where likes > views should still cap at ~100."""
        video = SearchVideoResult(
            title="outlier", creator="test",
            view_cnt=100,
            like_cnt=500, comment_cnt=200, share_cnt=100,
        )
        score = score_video_engagement(video)
        assert score >= 99.0, f"Expected ~100, got {score}"

    def test_score_is_rounded_to_one_decimal(self):
        """Score should be rounded to one decimal place."""
        video = SearchVideoResult(
            title="precision", creator="test",
            view_cnt=10000,
            like_cnt=300, comment_cnt=200, share_cnt=100,
        )
        score = score_video_engagement(video)
        # Verify it has at most one decimal place
        assert score == round(score, 1)

    def test_score_within_bounds(self):
        """Score must always be in [0.0, 100.0]."""
        for likes in [0, 1, 100, 10000, 1000000]:
            video = SearchVideoResult(
                title="bound", creator="test",
                view_cnt=max(likes, 1),
                like_cnt=likes, comment_cnt=0, share_cnt=0,
            )
            score = score_video_engagement(video)
            assert 0.0 <= score <= 100.0


# ===========================================================================
# score_competitor_engagement
# ===========================================================================

class TestScoreCompetitorEngagement:
    """Tests for score_competitor_engagement()."""

    def test_empty_videos_returns_empty_strings(self):
        """No recent videos should return all empty strings."""
        profile = CompetitorProfile(username="empty", recent_videos=[])
        result = score_competitor_engagement(profile)
        assert result == {
            "avg_views": "",
            "avg_likes": "",
            "avg_comments": "",
            "engagement_rate": "",
        }

    def test_known_values_correct_averages(self):
        """Known video stats should produce correct averages."""
        profile = CompetitorProfile(
            username="test",
            recent_videos=[
                {"views": 1000, "likes": 100, "comments": 50},
                {"views": 3000, "likes": 300, "comments": 150},
            ],
        )
        result = score_competitor_engagement(profile)
        # avg_views = (1000+3000)/2 = 2000 -> "2.0K"
        assert result["avg_views"] == "2.0K"
        # avg_likes = (100+300)/2 = 200
        assert result["avg_likes"] == "200"
        # avg_comments = (50+150)/2 = 100
        assert result["avg_comments"] == "100"
        # engagement_rate = (400+200)/4000 * 100 = 15.0%
        assert result["engagement_rate"] == "15.0%"

    def test_mixed_string_and_int_stats(self):
        """Should handle mix of string and int stat values."""
        profile = CompetitorProfile(
            username="mixed",
            recent_videos=[
                {"view_cnt": 10000, "like_cnt": "1K", "comment_cnt": 200},
                {"views": "5K", "likes": 500, "comments": "100"},
            ],
        )
        result = score_competitor_engagement(profile)
        # Total views = 10000 + 5000 = 15000, avg = 7500 -> "7.5K"
        assert result["avg_views"] == "7.5K"
        # Total likes = 1000 + 500 = 1500, avg = 750
        assert result["avg_likes"] == "750"
        assert result["engagement_rate"] != ""

    def test_zero_views_gives_zero_percent(self):
        """If all videos have zero views, engagement rate should be 0.0%."""
        profile = CompetitorProfile(
            username="ghost",
            recent_videos=[
                {"views": 0, "likes": 0, "comments": 0},
            ],
        )
        result = score_competitor_engagement(profile)
        assert result["engagement_rate"] == "0.0%"


# ===========================================================================
# score_shop_product
# ===========================================================================

class TestScoreShopProduct:
    """Tests for score_shop_product()."""

    def test_worked_example(self):
        """Known values: rating=4.7, reviews=250, sold=5000 should produce ~67.8."""
        product = ShopProduct(
            title="Serum",
            rating="4.7",
            reviews="250",
            sold="5000",
        )
        score = score_shop_product(product)
        # Manually verified:
        # Bayesian rating: (10*4.2 + 250*4.7) / (10+250) = (42+1175)/260 = 4.681
        # rating_score = 4.681 / 5.0 = 0.9362
        # sales: log10(5001) = 3.699 -> 3.699/7.0 = 0.5284
        # density: 250/5000 = 0.05 -> 0.05/0.30 = 0.1667
        # composite: 0.50*0.9362 + 0.35*0.5284 + 0.15*0.1667 = 0.4681 + 0.1849 + 0.025 = 0.678
        # score = 67.8
        assert 65.0 <= score <= 70.0, f"Expected ~67.8, got {score}"

    def test_empty_strings_fall_back_to_prior(self):
        """Empty rating/reviews/sold should use fallback values."""
        product = ShopProduct(
            title="Unknown",
            rating="",
            reviews="",
            sold="",
        )
        score = score_shop_product(product)
        # rating_val=0 -> adjusted=4.2, rating_score=0.84
        # sold=0, reviews=0 -> sales_score = log10(2)/7 ~= 0.043
        # density = 0.0
        # composite = 0.50*0.84 + 0.35*0.043 + 0.15*0 = 0.42 + 0.015 = 0.435
        # score ~ 43.5
        assert 40.0 <= score <= 50.0, f"Expected ~43.5, got {score}"

    def test_high_quality_product_high_score(self):
        """Top-tier product should score high."""
        product = ShopProduct(
            title="Premium",
            rating="4.9",
            reviews="10K",
            sold="100K",
        )
        score = score_shop_product(product)
        assert score > 75.0, f"Expected >75, got {score}"

    def test_score_within_bounds(self):
        """Score must be in [0.0, 100.0]."""
        product = ShopProduct(title="test", rating="5.0", reviews="1M", sold="10M")
        score = score_shop_product(product)
        assert 0.0 <= score <= 100.0

    def test_zero_rating_uses_prior(self):
        """A zero or missing rating should use the global prior mean."""
        product = ShopProduct(title="no-rating", rating="0", reviews="100", sold="1000")
        score = score_shop_product(product)
        # Should still produce a reasonable score from sales and density
        assert score > 0.0


# ===========================================================================
# classify_trend_velocity
# ===========================================================================

class TestClassifyTrendVelocity:
    """Tests for classify_trend_velocity()."""

    def test_new_entry_top_20_is_breakout(self):
        """New entry (rank_diff_type=3) at rank<=20 -> BREAKOUT."""
        item = TrendingHashtag(rank=5, name="viral", rank_diff_type=3, rank_diff=0)
        assert classify_trend_velocity(item) == "BREAKOUT"

    def test_new_entry_rank_30_is_new(self):
        """New entry (rank_diff_type=3) at rank>20 -> NEW."""
        item = TrendingHashtag(rank=30, name="fresh", rank_diff_type=3, rank_diff=0)
        assert classify_trend_velocity(item) == "NEW"

    def test_rank_diff_25_is_breakout(self):
        """Existing entry jumping 25 ranks -> BREAKOUT."""
        item = TrendingSong(rank=3, title="hit", artist="x", rank_diff=25, rank_diff_type=1)
        assert classify_trend_velocity(item) == "BREAKOUT"

    def test_rank_diff_20_is_breakout(self):
        """Boundary: rank_diff=20 -> BREAKOUT (>= threshold)."""
        item = TrendingCreator(rank=10, username="u", rank_diff=20, rank_diff_type=1)
        assert classify_trend_velocity(item) == "BREAKOUT"

    def test_rank_diff_10_is_rising(self):
        """rank_diff=10 -> RISING."""
        item = TrendingHashtag(rank=15, name="up", rank_diff=10, rank_diff_type=1)
        assert classify_trend_velocity(item) == "RISING"

    def test_rank_diff_5_is_rising(self):
        """Boundary: rank_diff=5 -> RISING (>= threshold)."""
        # TrendingVideo does not have rank_diff field, use TrendingHashtag
        item = TrendingHashtag(rank=8, name="rising", rank_diff=5, rank_diff_type=1)
        assert classify_trend_velocity(item) == "RISING"

    def test_rank_diff_4_is_stable(self):
        """Boundary: rank_diff=4 -> STABLE (below RISING threshold)."""
        item = TrendingHashtag(rank=12, name="meh", rank_diff=4, rank_diff_type=1)
        assert classify_trend_velocity(item) == "STABLE"

    def test_rank_diff_negative_10_is_declining(self):
        """rank_diff=-10 -> DECLINING."""
        item = TrendingHashtag(rank=30, name="down", rank_diff=-10, rank_diff_type=2)
        assert classify_trend_velocity(item) == "DECLINING"

    def test_rank_diff_negative_5_is_declining(self):
        """Boundary: rank_diff=-5 -> DECLINING (<= -threshold)."""
        item = TrendingSong(rank=25, title="fade", artist="y", rank_diff=-5, rank_diff_type=2)
        assert classify_trend_velocity(item) == "DECLINING"

    def test_rank_diff_negative_4_is_stable(self):
        """Boundary: rank_diff=-4 -> STABLE (not enough decline)."""
        item = TrendingHashtag(rank=18, name="ok", rank_diff=-4, rank_diff_type=2)
        assert classify_trend_velocity(item) == "STABLE"

    def test_rank_diff_zero_is_stable(self):
        """No movement -> STABLE."""
        item = TrendingHashtag(rank=10, name="steady", rank_diff=0, rank_diff_type=0)
        assert classify_trend_velocity(item) == "STABLE"

    def test_new_entry_at_rank_20_boundary_is_breakout(self):
        """New entry at exactly rank 20 -> BREAKOUT (boundary)."""
        item = TrendingHashtag(rank=20, name="edge", rank_diff_type=3, rank_diff=0)
        assert classify_trend_velocity(item) == "BREAKOUT"

    def test_new_entry_at_rank_21_is_new(self):
        """New entry at rank 21 -> NEW (just above BREAKOUT threshold)."""
        item = TrendingHashtag(rank=21, name="edge2", rank_diff_type=3, rank_diff=0)
        assert classify_trend_velocity(item) == "NEW"

    def test_waterfall_priority_type3_over_rank_diff(self):
        """Waterfall priority: rank_diff_type=3 takes precedence over rank_diff >= 20.

        When a NEW entry (type=3) also has rank_diff >= 20, the type-3 branch
        should fire first. If rank > 20, result is NEW (not BREAKOUT via rank_diff).
        """
        item = TrendingHashtag(rank=25, name="ambiguous", rank_diff_type=3, rank_diff=25)
        assert classify_trend_velocity(item) == "NEW"

    def test_waterfall_priority_type3_breakout_with_high_diff(self):
        """Waterfall priority: NEW entry at top rank with high diff is still BREAKOUT via type-3 branch."""
        item = TrendingHashtag(rank=5, name="double", rank_diff_type=3, rank_diff=30)
        assert classify_trend_velocity(item) == "BREAKOUT"

    def test_works_with_all_trend_types(self):
        """All four trending types should be classifiable.

        Note: TrendingVideo does not have rank_diff/rank_diff_type fields,
        so it defaults to STABLE via getattr fallbacks.
        """
        for cls, kwargs, expected in [
            (TrendingHashtag, {"rank": 5, "name": "h", "rank_diff_type": 3}, "BREAKOUT"),
            (TrendingSong, {"rank": 5, "title": "s", "artist": "a", "rank_diff_type": 3}, "BREAKOUT"),
            (TrendingCreator, {"rank": 5, "username": "c", "rank_diff_type": 3}, "BREAKOUT"),
            (TrendingVideo, {"rank": 5}, "STABLE"),  # No rank_diff fields -> defaults -> STABLE
        ]:
            item = cls(**kwargs)
            result = classify_trend_velocity(item)
            assert result == expected, f"{cls.__name__} expected {expected}, got {result}"


# ===========================================================================
# rank_results
# ===========================================================================

class TestRankResults:
    """Tests for rank_results()."""

    def test_empty_list_returns_empty(self):
        """Empty input -> empty output."""
        assert rank_results([], lambda x: x) == []

    def test_descending_sort_default(self):
        """Default (reverse=True) sorts highest score first."""
        items = [1, 3, 2]
        result = rank_results(items, lambda x: float(x))
        assert result == [3, 2, 1]

    def test_ascending_sort(self):
        """reverse=False sorts lowest score first."""
        items = [3, 1, 2]
        result = rank_results(items, lambda x: float(x), reverse=False)
        assert result == [1, 2, 3]

    def test_tiebreaker_preserves_order(self):
        """Items with identical scores keep their original order."""
        items = ["a", "b", "c"]
        result = rank_results(items, lambda x: 1.0)
        assert result == ["a", "b", "c"]

    def test_tiebreaker_preserves_order_ascending(self):
        """Tie-breaking also works for ascending sort."""
        items = ["x", "y", "z"]
        result = rank_results(items, lambda x: 0.0, reverse=False)
        assert result == ["x", "y", "z"]

    def test_single_item(self):
        """Single-item list returns that item."""
        assert rank_results([42], lambda x: float(x)) == [42]

    def test_with_video_objects(self):
        """Works with SearchVideoResult objects and real scorer."""
        v1 = SearchVideoResult(
            title="low", creator="a",
            view_cnt=10000, like_cnt=100, comment_cnt=10, share_cnt=5,
        )
        v2 = SearchVideoResult(
            title="high", creator="b",
            view_cnt=10000, like_cnt=2000, comment_cnt=500, share_cnt=300,
        )
        result = rank_results([v1, v2], score_video_engagement)
        assert result[0].title == "high"
        assert result[1].title == "low"


# ===========================================================================
# Private helpers
# ===========================================================================

class TestFormatCountStatic:
    """Tests for _format_count_static()."""

    def test_billions(self):
        assert _format_count_static(2_500_000_000) == "2.5B"

    def test_millions(self):
        assert _format_count_static(1_200_000) == "1.2M"

    def test_thousands(self):
        assert _format_count_static(500_000) == "500.0K"

    def test_small_number(self):
        assert _format_count_static(42) == "42"

    def test_zero(self):
        assert _format_count_static(0) == "0"


class TestSafeParseFloat:
    """Tests for safe_parse_float()."""

    def test_none_returns_zero(self):
        assert safe_parse_float(None) == 0.0

    def test_empty_string_returns_zero(self):
        assert safe_parse_float("") == 0.0

    def test_valid_string(self):
        assert safe_parse_float("4.7") == 4.7

    def test_int_value(self):
        assert safe_parse_float(5) == 5.0

    def test_float_value(self):
        assert safe_parse_float(3.14) == 3.14

    def test_invalid_string_returns_zero(self):
        assert safe_parse_float("N/A") == 0.0

    def test_whitespace_string(self):
        assert safe_parse_float("  4.5  ") == 4.5


class TestParseVideoStat:
    """Tests for _parse_video_stat()."""

    def test_first_key_found(self):
        vid = {"views": 1000, "view_cnt": 2000}
        assert _parse_video_stat(vid, "views", "view_cnt") == 1000

    def test_fallback_key(self):
        vid = {"play_count": 5000}
        assert _parse_video_stat(vid, "views", "view_cnt", "play_count") == 5000

    def test_human_readable_string(self):
        vid = {"views": "1.5M"}
        assert _parse_video_stat(vid, "views") == 1_500_000

    def test_no_matching_key(self):
        vid = {"unrelated": 100}
        assert _parse_video_stat(vid, "views", "view_cnt") == 0

    def test_none_value_skipped(self):
        vid = {"views": None, "view_cnt": 3000}
        assert _parse_video_stat(vid, "views", "view_cnt") == 3000


# ===========================================================================
# Velocity ordering constant
# ===========================================================================

class TestVelocityOrder:
    """Verify VELOCITY_ORDER dict is consistent."""

    def test_breakout_is_highest(self):
        assert VELOCITY_ORDER["BREAKOUT"] > VELOCITY_ORDER["RISING"]

    def test_declining_is_lowest(self):
        assert VELOCITY_ORDER["DECLINING"] < VELOCITY_ORDER["STABLE"]

    def test_all_five_categories_present(self):
        assert set(VELOCITY_ORDER.keys()) == {"BREAKOUT", "RISING", "NEW", "STABLE", "DECLINING"}
