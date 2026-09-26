"""Competitor intelligence commands (Business Discovery)."""

from ..cache import FileCache
from ..config import (
    BOLD, CYAN, DIM, EXIT_EXPECTED_ERROR, EXIT_SUCCESS, GREEN,
    RESET, YELLOW,
)
from ..formatters import (
    _truncate, format_table, human_number, json_output, print_error,
    print_footer, print_header, ts_to_str,
)
from ..scoring import score_media_batch
from ..analytics import compute_posting_heatmap, format_best_times


def cmd_competitor(args, client) -> int:
    """Full competitor profile via Business Discovery."""
    username = args.username.lstrip("@")
    cache = _get_cache(args)
    filters = {"command": "competitor", "username": username}

    if cache:
        cached = cache.get("competitor", filters)
        if cached:
            return _output_cached_competitor(cached, args, username)

    try:
        profile = client.get_competitor_profile(username)
    except Exception as e:
        if args.json:
            json_output({"error": str(e), "type": "api_error"})
        else:
            print_error(
                str(e),
                "Business Discovery requires the target account to be a "
                "Business or Creator account.",
            )
        return EXIT_EXPECTED_ERROR

    data = profile.to_dict()

    if cache:
        cache.set("competitor", filters, {"data": data})

    if args.json:
        json_output({"success": True, "data": data, "cached": False})
    else:
        print_header("competitor", {"username": username})
        _print_competitor_profile(profile)
        print_footer(1)

    return EXIT_SUCCESS


def cmd_competitor_media(args, client) -> int:
    """Competitor's recent media with engagement metrics."""
    username = args.username.lstrip("@")
    limit = getattr(args, "limit", 25)
    cache = _get_cache(args)
    filters = {"command": "competitor-media", "username": username, "limit": limit}

    if cache:
        cached = cache.get("competitor-media", filters)
        if cached:
            return _output_cached_competitor_media(cached, args, username)

    try:
        media = client.get_competitor_media(username, limit=limit)
    except Exception as e:
        if args.json:
            json_output({"error": str(e), "type": "api_error"})
        else:
            print_error(str(e))
        return EXIT_EXPECTED_ERROR

    data = [m.to_dict() for m in media]

    # Enrich with engagement scores (#1)
    sort_mode = getattr(args, "sort", "smart")
    should_sort = sort_mode != "none"
    data = score_media_batch(data, mode="standard", sort=should_sort)

    if cache:
        cache.set("competitor-media", filters, {
            "data": data, "count": len(data),
        })

    if args.json:
        json_output({
            "success": True, "data": data,
            "count": len(data), "cached": False,
        })
    else:
        print_header("competitor-media", {"username": username, "limit": limit})
        _print_media_table_scored(data)

        # Timing analysis (#6) — triggered by --analyze-timing flag
        if getattr(args, "analyze_timing", False):
            timing = compute_posting_heatmap(data)
            print(f"\n  {BOLD}Best Posting Times:{RESET}")
            print(format_best_times(timing))

        print_footer(len(media))

    return EXIT_SUCCESS


# ---------------------------------------------------------------------------
# Display helpers
# ---------------------------------------------------------------------------

def _print_competitor_profile(profile) -> None:
    """Render competitor profile to terminal."""
    lines = [
        f"  {BOLD}@{profile.username}{RESET}",
        f"  {DIM}{profile.name}{RESET}",
    ]
    if profile.biography:
        lines.append(f"  {DIM}{_truncate(profile.biography, 80)}{RESET}")
    lines.append("")
    lines.append(
        f"  {CYAN}Followers:{RESET} {human_number(profile.followers_count)}   "
        f"{CYAN}Posts:{RESET} {human_number(profile.media_count)}"
    )
    if profile.website:
        lines.append(f"  {CYAN}Website:{RESET} {profile.website}")
    if profile.ig_id:
        lines.append(f"  {CYAN}IG ID:{RESET} {profile.ig_id}")
    print("\n".join(lines))


def _print_media_table(media) -> None:
    """Render media list as a table (legacy, for cached non-scored data)."""
    if not media:
        print("  (no media found)")
        return

    headers = ["#", "Type", "Likes", "Comments", "Date", "Caption", "Link"]
    rows = []
    for i, m in enumerate(media):
        rows.append([
            str(i + 1),
            m.media_type,
            human_number(m.like_count),
            human_number(m.comments_count),
            ts_to_str(m.timestamp),
            _truncate(m.caption, 35),
            _truncate(m.permalink, 45),
        ])
    print(format_table(headers, rows))


def _print_media_table_scored(data: list) -> None:
    """Render scored media list (list of dicts with engagement_score)."""
    if not data:
        print("  (no media found)")
        return

    headers = ["#", "Score", "Type", "Likes", "Comments", "Date", "Caption"]
    rows = []
    for i, m in enumerate(data):
        score = m.get("engagement_score", 0)
        score_str = f"{score:.1f}" if score else "-"
        rows.append([
            str(i + 1),
            score_str,
            m.get("media_type", ""),
            human_number(m.get("like_count", 0)),
            human_number(m.get("comments_count", 0)),
            ts_to_str(m.get("timestamp", "")),
            _truncate(m.get("caption", ""), 40),
        ])
    print(format_table(headers, rows))


# ---------------------------------------------------------------------------
# Cache output helpers
# ---------------------------------------------------------------------------

def _get_cache(args) -> FileCache | None:
    if getattr(args, "no_cache", False):
        return None
    return FileCache(ttl=args.cache_ttl)


def _output_cached_competitor(cached: dict, args, username: str) -> int:
    data = cached.get("data", {})
    if args.json:
        json_output({"success": True, "data": data, "cached": True})
    else:
        from ..models import CompetitorProfile
        profile = CompetitorProfile(**data)
        print_header("competitor", {"username": username})
        _print_competitor_profile(profile)
        print_footer(1, cached=True)
    return EXIT_SUCCESS


def _output_cached_competitor_media(cached: dict, args, username: str) -> int:
    data = cached.get("data", [])
    count = cached.get("count", len(data))
    if args.json:
        json_output({"success": True, "data": data, "count": count, "cached": True})
    else:
        from ..models import MediaItem
        media = [MediaItem(**m) for m in data]
        print_header("competitor-media", {"username": username})
        _print_media_table(media)
        print_footer(count, cached=True)
    return EXIT_SUCCESS
