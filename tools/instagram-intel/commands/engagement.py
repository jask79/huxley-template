"""Engagement rate computation command."""

from ..cache import FileCache
from ..config import (
    BOLD, CYAN, DIM, EXIT_EXPECTED_ERROR, EXIT_SUCCESS, GREEN,
    RED, RESET, YELLOW,
)
from ..formatters import (
    human_number, json_output, print_error, print_footer, print_header,
)
from ..benchmarks import classify_engagement, get_tier, get_tier_thresholds
from ..config import COMMAND_TTL, DEFAULT_CACHE_TTL


def cmd_engagement_rate(args, client) -> int:
    """Compute engagement rate from Business Discovery data."""
    username = args.username.lstrip("@")
    limit = getattr(args, "limit", 25)
    cache = _get_cache(args)
    filters = {
        "command": "engagement-rate", "username": username, "limit": limit,
    }

    if cache:
        cached = cache.get("engagement-rate", filters)
        if cached:
            return _output_cached(cached, args, username)

    try:
        report = client.compute_engagement_rate(username, media_limit=limit)
    except Exception as e:
        if args.json:
            json_output({"error": str(e), "type": "api_error"})
        else:
            print_error(
                str(e),
                "Engagement rate requires Business Discovery access. "
                "Target must be a Business or Creator account.",
            )
        return EXIT_EXPECTED_ERROR

    data = report.to_dict()

    # Enrich with tiered benchmarks (#3)
    tier, rating = classify_engagement(report.engagement_rate, report.followers_count)
    thresholds = get_tier_thresholds(report.followers_count)
    data["tier"] = tier
    data["rating"] = rating
    data["tier_thresholds"] = thresholds

    if cache:
        cache.set("engagement-rate", filters, {"data": data})

    if args.json:
        json_output({"success": True, "data": data, "cached": False})
    else:
        print_header("engagement-rate", {"username": username})
        _print_engagement(report, tier=tier, rating=rating, thresholds=thresholds)
        print_footer(1)

    return EXIT_SUCCESS


# ---------------------------------------------------------------------------
# Display helpers
# ---------------------------------------------------------------------------

def _rate_color(rate: float) -> str:
    """Color the engagement rate based on typical Instagram benchmarks."""
    if rate >= 6.0:
        return f"{GREEN}{rate:.2f}%{RESET}"
    elif rate >= 3.0:
        return f"{YELLOW}{rate:.2f}%{RESET}"
    elif rate >= 1.0:
        return f"{CYAN}{rate:.2f}%{RESET}"
    else:
        return f"{RED}{rate:.2f}%{RESET}"


def _rating_label(rating: str) -> str:
    """Color-code a tier-aware rating label."""
    colors = {
        "excellent": GREEN,
        "good": YELLOW,
        "average": CYAN,
        "below_average": RED,
    }
    color = colors.get(rating, "")
    display = rating.replace("_", " ").title()
    return f"{color}{display}{RESET}" if color else display


def _print_engagement(
    report,
    tier: str = "",
    rating: str = "",
    thresholds: dict = None,
) -> None:
    """Render engagement report to terminal with tier-aware benchmarks (#3)."""
    lines = [
        f"  {BOLD}@{report.username}{RESET}",
        "",
        f"  {CYAN}Followers:{RESET}       {human_number(report.followers_count)}",
        f"  {CYAN}Total Posts:{RESET}     {human_number(report.media_count)}",
        f"  {CYAN}Media Analyzed:{RESET}  {report.media_analyzed}",
        "",
        f"  {CYAN}Avg Likes:{RESET}       {report.avg_likes:.1f}",
        f"  {CYAN}Avg Comments:{RESET}    {report.avg_comments:.1f}",
        f"  {BOLD}{CYAN}Engagement Rate:{RESET} {_rate_color(report.engagement_rate)}",
    ]

    # Tier-aware rating (#3)
    if tier and rating:
        lines.append(f"  {CYAN}Account Tier:{RESET}    {tier}")
        lines.append(f"  {CYAN}Rating:{RESET}          {_rating_label(rating)}")

    lines.append("")
    lines.append(f"  {DIM}Formula: (avg_likes + avg_comments) / followers * 100{RESET}")
    lines.append(f"  {DIM}Based on {report.media_analyzed} most recent posts{RESET}")

    # Tier-specific benchmark context (#3)
    if thresholds:
        tier_name = thresholds.get("tier", tier)
        lines.append(f"\n  {BOLD}Benchmarks for {tier_name} tier:{RESET}")
        lines.append(f"    {GREEN}{thresholds.get('excellent_threshold', 6)}%+{RESET}  Excellent")
        lines.append(f"    {YELLOW}{thresholds.get('good_threshold', 3)}%+{RESET}  Good")
        lines.append(f"    {CYAN}{thresholds.get('average_threshold', 1)}%+{RESET}  Average")
        lines.append(f"    {RED}<{thresholds.get('average_threshold', 1)}%{RESET}  Below Average")
    else:
        # Fallback flat benchmarks
        lines.append(f"\n  {BOLD}Benchmarks:{RESET}")
        lines.append(f"    {GREEN}6%+{RESET}   Excellent (viral potential)")
        lines.append(f"    {YELLOW}3-6%{RESET}  Good (above average)")
        lines.append(f"    {CYAN}1-3%{RESET}  Average")
        lines.append(f"    {RED}<1%{RESET}   Below average")

    print("\n".join(lines))


# ---------------------------------------------------------------------------
# Cache helpers
# ---------------------------------------------------------------------------

def _get_cache(args, command: str = "engagement-rate") -> FileCache | None:
    if getattr(args, "no_cache", False):
        return None
    user_ttl = getattr(args, "cache_ttl", DEFAULT_CACHE_TTL)
    ttl = COMMAND_TTL.get(command, user_ttl)
    return FileCache(ttl=ttl)


def _output_cached(cached: dict, args, username: str) -> int:
    data = cached.get("data", {})
    if args.json:
        json_output({"success": True, "data": data, "cached": True})
    else:
        from ..models import EngagementReport
        import dataclasses
        # Strip enrichment keys not in the dataclass to avoid TypeError
        valid_fields = {f.name for f in dataclasses.fields(EngagementReport)}
        clean = {k: v for k, v in data.items() if k in valid_fields}
        report = EngagementReport(**clean)
        # Re-derive tier-aware enrichments from cached data
        tier, rating = classify_engagement(report.engagement_rate, report.followers_count)
        thresholds = get_tier_thresholds(report.followers_count)
        print_header("engagement-rate", {"username": username})
        _print_engagement(report, tier=tier, rating=rating, thresholds=thresholds)
        print_footer(1, cached=True)
    return EXIT_SUCCESS
