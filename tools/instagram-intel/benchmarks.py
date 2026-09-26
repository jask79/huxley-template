"""Tiered engagement benchmarks and account classification.

Pure functions — take scalars/dicts in, return enriched results out.
No side effects, no API calls, no pip dependencies.

Implements:
  #3  Tiered Engagement Benchmarks — follower-tier-adjusted thresholds
  #11 Follower/Following Ratio Heuristic — account type classification
"""

from typing import Any, Dict, Tuple


# ---------------------------------------------------------------------------
# #3 — Tiered Engagement Benchmarks
# ---------------------------------------------------------------------------

# Tier definitions: (min_followers, max_followers, tier_name)
_TIERS = [
    (0,         1_000,       "nano"),
    (1_000,     10_000,      "micro"),
    (10_000,    100_000,     "mid"),
    (100_000,   1_000_000,   "macro"),
    (1_000_000, float("inf"), "mega"),
]

# Engagement rate thresholds per tier (percentage)
# Based on industry benchmarks (2024-2025 Instagram averages):
#   nano:  5-8% average
#   micro: 3-5% average
#   mid:   1.5-3% average
#   macro: 1-2% average
#   mega:  0.5-1.5% average
_THRESHOLDS = {
    "nano": {
        "excellent": 8.0,
        "good": 5.0,
        "average": 3.0,
        # below 3.0 = below_average
    },
    "micro": {
        "excellent": 5.0,
        "good": 3.0,
        "average": 1.5,
    },
    "mid": {
        "excellent": 3.0,
        "good": 1.5,
        "average": 0.8,
    },
    "macro": {
        "excellent": 2.0,
        "good": 1.0,
        "average": 0.5,
    },
    "mega": {
        "excellent": 1.5,
        "good": 0.7,
        "average": 0.3,
    },
}


def get_tier(followers: int) -> str:
    """Determine the follower tier for a given follower count.

    Returns: tier name (nano, micro, mid, macro, mega).
    """
    for low, high, name in _TIERS:
        if low <= followers < high:
            return name
    return "mega"


def classify_engagement(rate: float, followers: int) -> Tuple[str, str]:
    """Classify an engagement rate relative to its follower tier.

    Args:
        rate: Engagement rate as a percentage (e.g., 3.5 = 3.5%).
        followers: Account follower count.

    Returns:
        Tuple of (tier_name, rating) where rating is one of:
        "excellent", "good", "average", "below_average".
    """
    tier = get_tier(followers)
    thresholds = _THRESHOLDS.get(tier, _THRESHOLDS["mid"])

    if rate >= thresholds["excellent"]:
        rating = "excellent"
    elif rate >= thresholds["good"]:
        rating = "good"
    elif rate >= thresholds["average"]:
        rating = "average"
    else:
        rating = "below_average"

    return tier, rating


def get_tier_thresholds(followers: int) -> Dict[str, Any]:
    """Get the engagement rate thresholds for a follower count's tier.

    Returns dict with tier name and threshold values.
    """
    tier = get_tier(followers)
    thresholds = _THRESHOLDS.get(tier, _THRESHOLDS["mid"])
    return {
        "tier": tier,
        "excellent_threshold": thresholds["excellent"],
        "good_threshold": thresholds["good"],
        "average_threshold": thresholds["average"],
    }


def enrich_engagement_report(report_dict: Dict[str, Any]) -> Dict[str, Any]:
    """Add tier-aware benchmarks to an engagement report dict.

    Args:
        report_dict: Dict from EngagementReport.to_dict().

    Returns:
        Enriched dict with 'tier', 'rating', and 'tier_thresholds' fields.
    """
    followers = report_dict.get("followers_count", 0)
    rate = report_dict.get("engagement_rate", 0.0)

    tier, rating = classify_engagement(rate, followers)
    thresholds = get_tier_thresholds(followers)

    enriched = dict(report_dict)
    enriched["tier"] = tier
    enriched["rating"] = rating
    enriched["tier_thresholds"] = thresholds
    return enriched


# ---------------------------------------------------------------------------
# #11 — Follower/Following Ratio Heuristic
# ---------------------------------------------------------------------------

# Account type classification by follower/following ratio
# ratio = followers / following
_ACCOUNT_TYPES = [
    # (min_ratio, max_ratio, type_name, description)
    (0.0,   0.1,   "mass_follower",  "Follows many, few follow back"),
    (0.1,   0.5,   "growth_seeker",  "Actively following for growth"),
    (0.5,   1.5,   "balanced",       "Roughly equal followers/following"),
    (1.5,   5.0,   "established",    "More followers than following"),
    (5.0,   20.0,  "influencer",     "Strong audience, selective follows"),
    (20.0,  100.0, "authority",      "Major influence, minimal follows"),
    (100.0, float("inf"), "celebrity", "Public figure / brand account"),
]


def classify_account(followers: int, following: int) -> Dict[str, Any]:
    """Classify an account based on its follower/following ratio.

    Args:
        followers: Number of followers.
        following: Number of accounts being followed.

    Returns:
        Dict with:
          - ratio: float (followers/following)
          - account_type: str (mass_follower, growth_seeker, etc.)
          - description: str (human-readable explanation)
          - tier: str (nano/micro/mid/macro/mega)
    """
    if following <= 0:
        # Edge case: not following anyone
        ratio = float(followers) if followers > 0 else 0.0
        account_type = "celebrity" if followers > 0 else "inactive"
        description = "Not following anyone" if followers > 0 else "No activity"
    else:
        ratio = followers / following
        account_type = "balanced"
        description = ""

        for min_r, max_r, atype, desc in _ACCOUNT_TYPES:
            if min_r <= ratio < max_r:
                account_type = atype
                description = desc
                break

    tier = get_tier(followers)

    return {
        "ratio": round(ratio, 2),
        "account_type": account_type,
        "description": description,
        "tier": tier,
    }


def enrich_profile(profile_dict: Dict[str, Any]) -> Dict[str, Any]:
    """Add account classification to a profile dict.

    Works with both ScrapedUserProfile.to_dict() and CompetitorProfile.to_dict().

    Args:
        profile_dict: Dict with 'followers'/'followers_count' and
                      'following'/'following_count' fields.

    Returns:
        Enriched dict with 'account_classification' sub-dict.
    """
    # Handle different field names across models (use `is None` to avoid
    # falsiness trap where integer 0 would fall through to the fallback key)
    followers = profile_dict.get("followers")
    if followers is None:
        followers = profile_dict.get("followers_count", 0)
    following = profile_dict.get("following")
    if following is None:
        following = profile_dict.get("following_count", 0)

    classification = classify_account(followers, following)

    enriched = dict(profile_dict)
    enriched["account_classification"] = classification
    return enriched
