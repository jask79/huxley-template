"""Multi-competitor comparison command (#4).

Fetches engagement reports for multiple usernames via Business Discovery,
computes composite ranking, and outputs a sorted comparison table.
"""

from ..cache import FileCache
from ..config import (
    BOLD, CYAN, DIM, EXIT_EXPECTED_ERROR, EXIT_SUCCESS, GREEN,
    RED, RESET, YELLOW,
)
from ..formatters import (
    format_table, human_number, json_output, print_error,
    print_footer, print_header,
)
from ..benchmarks import classify_engagement, get_tier
from ..config import COMMAND_TTL, DEFAULT_CACHE_TTL


def cmd_competitor_compare(args, client) -> int:
    """Compare engagement metrics across multiple competitors."""
    raw_usernames = getattr(args, "usernames", "")
    if not raw_usernames:
        print_error("At least one username is required (comma-separated)")
        return EXIT_EXPECTED_ERROR

    usernames = [u.strip().lstrip("@") for u in raw_usernames.split(",") if u.strip()]
    if not usernames:
        print_error("No valid usernames provided")
        return EXIT_EXPECTED_ERROR

    limit = getattr(args, "limit", 25)
    cache = _get_cache(args)
    cache_key_filters = {
        "command": "competitor-compare",
        "usernames": ",".join(sorted(usernames)),
        "limit": limit,
    }

    # Check cache
    if cache:
        cached = cache.get("competitor-compare", cache_key_filters)
        if cached:
            return _output_cached(cached, args)

    # Fetch engagement reports for each username
    reports = []
    errors = []

    for username in usernames:
        try:
            report = client.compute_engagement_rate(username, media_limit=limit)
            report_dict = report.to_dict()

            # Add tier-aware classification
            tier = get_tier(report.followers_count)
            _, rating = classify_engagement(report.engagement_rate, report.followers_count)

            # Composite score: weighted combination of engagement signals
            # Higher weight to engagement_rate (tier-normalized), plus raw volume
            composite = _compute_composite(
                engagement_rate=report.engagement_rate,
                avg_likes=report.avg_likes,
                avg_comments=report.avg_comments,
                followers=report.followers_count,
                tier=tier,
            )

            report_dict["tier"] = tier
            report_dict["rating"] = rating
            report_dict["composite_score"] = round(composite, 2)
            reports.append(report_dict)

        except Exception as e:
            errors.append({"username": username, "error": str(e)})

    if not reports:
        msg = "Failed to fetch data for any username"
        if errors:
            details = "; ".join(f"@{e['username']}: {e['error']}" for e in errors)
            msg += f"\n  {details}"
        if args.json:
            json_output({"error": msg, "errors": errors, "type": "api_error"})
        else:
            print_error(msg)
        return EXIT_EXPECTED_ERROR

    # Sort by composite score descending
    reports.sort(key=lambda r: r.get("composite_score", 0), reverse=True)

    # Add rank
    for i, r in enumerate(reports):
        r["rank"] = i + 1

    # Cache results
    result_data = {
        "data": reports,
        "count": len(reports),
        "errors": errors,
    }
    if cache:
        cache.set("competitor-compare", cache_key_filters, result_data)

    # Output
    if args.json:
        json_output({
            "success": True,
            **result_data,
            "cached": False,
        })
    else:
        print_header("competitor-compare", {"usernames": ", ".join(usernames)})
        _print_comparison_table(reports)
        if errors:
            print(f"\n  {YELLOW}Errors:{RESET}")
            for e in errors:
                print(f"    {RED}@{e['username']}: {e['error']}{RESET}")
        print_footer(len(reports))

    return EXIT_SUCCESS


# ---------------------------------------------------------------------------
# Composite score computation
# ---------------------------------------------------------------------------

def _compute_composite(
    engagement_rate: float,
    avg_likes: float,
    avg_comments: float,
    followers: int,
    tier: str,
) -> float:
    """Compute a composite ranking score for cross-account comparison.

    Components (0-100 scale each, then weighted):
      - Engagement rate score (40%): tier-normalized
      - Volume score (30%): log-scaled avg interactions
      - Reach score (30%): log-scaled follower count

    This produces a single number that balances engagement quality
    (rate) with engagement volume and account size.
    """
    import math

    # Tier-normalized engagement rate score (0-100)
    # Scale relative to tier's "excellent" threshold
    tier_excellent = {
        "nano": 8.0, "micro": 5.0, "mid": 3.0,
        "macro": 2.0, "mega": 1.5,
    }
    threshold = tier_excellent.get(tier, 3.0)
    rate_score = min(100, (engagement_rate / threshold) * 100)

    # Volume score: log-scaled average engagement (0-100)
    avg_total = avg_likes + avg_comments
    volume_score = min(100, (math.log1p(avg_total) / math.log1p(100000)) * 100)

    # Reach score: log-scaled followers (0-100)
    reach_score = min(100, (math.log1p(followers) / math.log1p(10_000_000)) * 100)

    # Weighted composite
    return (rate_score * 0.40) + (volume_score * 0.30) + (reach_score * 0.30)


# ---------------------------------------------------------------------------
# Display helpers
# ---------------------------------------------------------------------------

def _rating_color(rating: str) -> str:
    """Color-code a rating string."""
    colors = {
        "excellent": GREEN,
        "good": YELLOW,
        "average": CYAN,
        "below_average": RED,
    }
    color = colors.get(rating, "")
    return f"{color}{rating}{RESET}" if color else rating


def _print_comparison_table(reports: list) -> None:
    """Render the comparison table to terminal."""
    if not reports:
        print("  (no data)")
        return

    headers = ["Rank", "Username", "Followers", "Eng. Rate", "Tier", "Rating",
               "Avg Likes", "Avg Comments", "Score"]
    rows = []

    for r in reports:
        rows.append([
            str(r.get("rank", "")),
            f"@{r.get('username', '')}",
            human_number(r.get("followers_count", 0)),
            f"{r.get('engagement_rate', 0):.2f}%",
            r.get("tier", ""),
            _rating_color(r.get("rating", "")),
            f"{r.get('avg_likes', 0):.0f}",
            f"{r.get('avg_comments', 0):.0f}",
            f"{r.get('composite_score', 0):.1f}",
        ])

    print(format_table(headers, rows))


# ---------------------------------------------------------------------------
# Cache helpers
# ---------------------------------------------------------------------------

def _get_cache(args, command: str = "competitor-compare") -> FileCache | None:
    if getattr(args, "no_cache", False):
        return None
    user_ttl = getattr(args, "cache_ttl", DEFAULT_CACHE_TTL)
    ttl = COMMAND_TTL.get(command, user_ttl)
    return FileCache(ttl=ttl)


def _output_cached(cached: dict, args) -> int:
    data = cached.get("data", [])
    errors = cached.get("errors", [])
    count = cached.get("count", len(data))

    if args.json:
        json_output({
            "success": True, "data": data, "count": count,
            "errors": errors, "cached": True,
        })
    else:
        usernames = [r.get("username", "") for r in data]
        print_header("competitor-compare", {"usernames": ", ".join(usernames)})
        _print_comparison_table(data)
        if errors:
            print(f"\n  {YELLOW}Errors:{RESET}")
            for e in errors:
                print(f"    {RED}@{e['username']}: {e['error']}{RESET}")
        print_footer(count, cached=True)
    return EXIT_SUCCESS
