"""
Keyword research and competition analysis.

Commands:
    keyword <term>                  Analyze a keyword's competition and opportunity
    keyword compare <term1> <term2> Side-by-side comparison of two keywords
"""

import sys
from argparse import Namespace
from datetime import datetime, timezone
from typing import List, Optional, Tuple

# Ensure tool dir is importable
from pathlib import Path
_TOOL_DIR = Path(__file__).resolve().parent.parent
if str(_TOOL_DIR) not in sys.path:
    sys.path.insert(0, str(_TOOL_DIR))

from client import (
    YouTubeIntelClient,
    youtube_autocomplete,
    format_count,
    format_table,
    GREEN, RED, YELLOW, CYAN, BOLD, DIM, RESET,
)
from db import cache_keyword, get_cached_keyword
from algo_loader import (
    compute_keyword_competition,
    compute_keyword_batch,
    estimate_relative_volume,
    SearchResultVideo,
    AutocompleteData,
    KeywordResult,
)


def _build_search_result_videos(
    client: YouTubeIntelClient,
    videos: list,
) -> List[SearchResultVideo]:
    """Convert raw YouTube API video items into SearchResultVideo objects."""
    results: List[SearchResultVideo] = []
    # Collect channel IDs to batch-fetch subscriber counts
    channel_ids = list({v.get("snippet", {}).get("channelId", "") for v in videos if v.get("snippet", {}).get("channelId")})
    channel_subs: dict = {}

    if channel_ids:
        # Fetch channel stats in batch
        for i in range(0, len(channel_ids), 50):
            batch = channel_ids[i:i + 50]
            try:
                ch_data = client._request(
                    "https://www.googleapis.com/youtube/v3/channels",
                    params={"part": "statistics", "id": ",".join(batch)},
                )
                for item in ch_data.get("items", []):
                    ch_id = item.get("id", "")
                    stats = item.get("statistics", {})
                    channel_subs[ch_id] = int(stats.get("subscriberCount", 0))
            except Exception:
                pass

    for v in videos:
        snippet = v.get("snippet", {})
        stats = v.get("statistics", {})
        content = v.get("contentDetails", {})

        channel_id = snippet.get("channelId", "")
        published = snippet.get("publishedAt", "")

        # Parse published_at
        try:
            pub_dt = datetime.fromisoformat(published.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            pub_dt = datetime.now(timezone.utc)

        # Parse duration to seconds
        duration_str = content.get("duration", "PT0S")
        duration_secs = _parse_duration(duration_str)

        description = snippet.get("description", "")

        results.append(SearchResultVideo(
            video_id=v.get("id", ""),
            title=snippet.get("title", ""),
            channel_id=channel_id,
            channel_title=snippet.get("channelTitle", ""),
            channel_subscriber_count=channel_subs.get(channel_id, 0),
            view_count=int(stats.get("viewCount", 0)),
            like_count=int(stats.get("likeCount", 0)),
            comment_count=int(stats.get("commentCount", 0)),
            published_at=pub_dt,
            duration_seconds=duration_secs,
            has_captions=content.get("caption", "false") == "true",
            description_length=len(description),
        ))

    return results


def _parse_duration(iso_duration: str) -> int:
    """Parse ISO 8601 duration (PT1H2M3S) to total seconds."""
    import re
    if not iso_duration:
        return 0
    match = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", iso_duration)
    if not match:
        return 0
    h, m, s = match.groups()
    return int(h or 0) * 3600 + int(m or 0) * 60 + int(s or 0)


def _analyze_keyword(
    client: YouTubeIntelClient,
    term: str,
    max_results: int = 20,
) -> Tuple[KeywordResult, List[str]]:
    """Run full keyword analysis: autocomplete + search + scoring.

    Returns (result, suggestions) to avoid duplicate autocomplete fetches.
    """
    print(f"{DIM}Fetching autocomplete suggestions...{RESET}")
    suggestions = youtube_autocomplete(term)
    position = estimate_relative_volume(suggestions, term)

    autocomplete = AutocompleteData(
        query=term,
        suggestions=suggestions,
        query_position=position,
        total_suggestions=len(suggestions),
    )

    print(f"{DIM}Searching top {max_results} results for '{term}'...{RESET}")
    raw_videos = client.search_videos(query=term, max_results=max_results)

    print(f"{DIM}Fetching channel data for competition analysis...{RESET}")
    search_results = _build_search_result_videos(client, raw_videos)

    result = compute_keyword_competition(
        keyword=term,
        results=search_results,
        autocomplete=autocomplete,
    )

    # Cache the result
    cache_keyword(
        keyword=term,
        search_volume_proxy=int(result.volume_proxy * 100),
        competition_score=result.competition_score,
        related_terms=suggestions[:10],
    )

    return result, suggestions


def _difficulty_color(label: str) -> str:
    """Return ANSI color for difficulty label."""
    if label in ("very_low", "low"):
        return GREEN
    elif label == "medium":
        return YELLOW
    elif label in ("high", "very_high"):
        return RED
    return RESET


def _score_bar(score: float, width: int = 20) -> str:
    """Render a visual score bar."""
    filled = int(score / 100 * width)
    empty = width - filled
    if score >= 70:
        color = GREEN
    elif score >= 40:
        color = YELLOW
    else:
        color = RED
    return f"{color}{'#' * filled}{DIM}{'.' * empty}{RESET}"


def _print_keyword_result(result: KeywordResult, show_details: bool = True) -> None:
    """Print a formatted keyword analysis result."""
    diff_color = _difficulty_color(result.difficulty_label)

    print(f"\n{BOLD}{CYAN}Keyword Analysis: {result.keyword}{RESET}\n")

    # Main scores
    print(f"  {BOLD}Competition:{RESET}  {result.competition_score:5.1f}/100  {_score_bar(result.competition_score)}")
    print(f"  {BOLD}Opportunity:{RESET}  {result.opportunity_score:5.1f}/100  {_score_bar(result.opportunity_score)}")
    print(f"  {BOLD}Volume Proxy:{RESET} {result.volume_proxy:.2f}      {DIM}(0=none, 1=high){RESET}")
    print(f"  {BOLD}Difficulty:{RESET}   {diff_color}{result.difficulty_label.replace('_', ' ').title()}{RESET}")
    print(f"  {BOLD}Confidence:{RESET}   {result.confidence:.0%}")

    if result.flags:
        flag_str = ", ".join(result.flags)
        print(f"  {DIM}Flags: {flag_str}{RESET}")

    if show_details:
        # Signal breakdown
        print(f"\n  {BOLD}Signal Breakdown:{RESET}")
        signals = [
            ("Authority", result.authority_signal, f"Avg top subs: {format_count(int(result.avg_top_subscribers))}"),
            ("View Momentum", result.view_momentum_signal, f"Avg top views: {format_count(int(result.avg_top_views))}"),
            ("Freshness", result.freshness_signal, f"Median age: {result.median_age_days:.0f} days"),
            ("Engagement", result.engagement_signal, f"Avg rate: {result.avg_engagement_rate:.2%}"),
        ]
        for name, value, detail in signals:
            bar = _score_bar(value * 100, width=15)
            print(f"    {name:<16} {value:.2f}  {bar}  {DIM}{detail}{RESET}")

        if result.freshness_gap:
            print(f"\n  {GREEN}{BOLD}Content Gap Detected{RESET}: Top results are stale ({result.median_age_days:.0f} days old)")
            print(f"  {GREEN}This is a good opportunity to create fresh content!{RESET}")

        # Recommendation
        print(f"\n  {BOLD}Recommendation:{RESET}")
        print(f"  {result.recommendation}")


def _print_related_terms(suggestions: list, term: str) -> None:
    """Print related autocomplete suggestions."""
    related = [s for s in suggestions if s.lower() != term.lower()]
    if related:
        print(f"\n  {BOLD}Related Searches:{RESET}")
        for i, s in enumerate(related[:10], 1):
            print(f"    {DIM}{i:2d}.{RESET} {s}")


def _print_top_videos(
    client: YouTubeIntelClient, term: str, max_show: int = 5
) -> None:
    """Print top-ranking videos for a search term."""
    videos = client.search_videos(query=term, max_results=max_show)
    if not videos:
        return

    print(f"\n  {BOLD}Top Ranking Videos:{RESET}")
    rows = []
    for v in videos[:max_show]:
        snippet = v.get("snippet", {})
        stats = v.get("statistics", {})
        title = snippet.get("title", "")[:50]
        views = format_count(int(stats.get("viewCount", 0)))
        likes = format_count(int(stats.get("likeCount", 0)))
        channel = snippet.get("channelTitle", "")[:20]
        rows.append([title, channel, views, likes])

    print(format_table(
        headers=["Title", "Channel", "Views", "Likes"],
        rows=rows,
    ))


def run_analyze(client: YouTubeIntelClient, args: Namespace) -> int:
    """Run keyword analysis for a single term."""
    term = args.term
    if not term:
        print(f"{RED}Please provide a search term.{RESET}", file=sys.stderr)
        print(f"{DIM}Usage: youtube-intel keyword \"your search term\"{RESET}", file=sys.stderr)
        return 1

    # Check cache first
    cached = get_cached_keyword(term, max_age_hours=6)
    if cached:
        print(f"{DIM}(Using cached result from {cached.get('cached_at', 'recently')}){RESET}")

    result, suggestions = _analyze_keyword(client, term, max_results=args.results)
    _print_keyword_result(result)

    # Print related terms (reuse suggestions from analysis — no duplicate fetch)
    _print_related_terms(suggestions, term)

    return 0


def run_compare(client: YouTubeIntelClient, args: Namespace) -> int:
    """Run side-by-side comparison of two keywords."""
    term1 = args.term1
    term2 = args.term2
    max_results = args.results

    print(f"{BOLD}{CYAN}Comparing keywords...{RESET}\n")

    result1, _ = _analyze_keyword(client, term1, max_results=max_results)
    result2, _ = _analyze_keyword(client, term2, max_results=max_results)

    # Print comparison table
    print(f"\n{BOLD}{'':25s} {'Keyword 1':>20s}  {'Keyword 2':>20s}{RESET}")
    print(f"{'':25s} {CYAN}{term1:>20s}{RESET}  {CYAN}{term2:>20s}{RESET}")
    print(f"  {'':23s} {'=' * 20}  {'=' * 20}")

    rows = [
        ("Competition", f"{result1.competition_score:.1f}", f"{result2.competition_score:.1f}"),
        ("Opportunity", f"{result1.opportunity_score:.1f}", f"{result2.opportunity_score:.1f}"),
        ("Volume Proxy", f"{result1.volume_proxy:.2f}", f"{result2.volume_proxy:.2f}"),
        ("Difficulty", result1.difficulty_label.replace("_", " ").title(),
         result2.difficulty_label.replace("_", " ").title()),
        ("Avg Top Subs", format_count(int(result1.avg_top_subscribers)),
         format_count(int(result2.avg_top_subscribers))),
        ("Avg Top Views", format_count(int(result1.avg_top_views)),
         format_count(int(result2.avg_top_views))),
        ("Median Age (days)", f"{result1.median_age_days:.0f}", f"{result2.median_age_days:.0f}"),
        ("Engagement Rate", f"{result1.avg_engagement_rate:.2%}", f"{result2.avg_engagement_rate:.2%}"),
        ("Content Gap", "Yes" if result1.freshness_gap else "No",
         "Yes" if result2.freshness_gap else "No"),
        ("Confidence", f"{result1.confidence:.0%}", f"{result2.confidence:.0%}"),
    ]

    for label, v1, v2 in rows:
        print(f"  {label:<23s} {v1:>20s}  {v2:>20s}")

    # Winner callout
    print()
    if result1.opportunity_score > result2.opportunity_score:
        print(f"  {GREEN}{BOLD}Better opportunity:{RESET} {GREEN}{term1}{RESET} "
              f"(opportunity {result1.opportunity_score:.1f} vs {result2.opportunity_score:.1f})")
    elif result2.opportunity_score > result1.opportunity_score:
        print(f"  {GREEN}{BOLD}Better opportunity:{RESET} {GREEN}{term2}{RESET} "
              f"(opportunity {result2.opportunity_score:.1f} vs {result1.opportunity_score:.1f})")
    else:
        print(f"  {YELLOW}Both keywords have equal opportunity scores.{RESET}")

    return 0


def run(client: YouTubeIntelClient, args: Namespace) -> int:
    """Route keyword subcommands."""
    action = getattr(args, "keyword_action", None)

    if action == "compare":
        return run_compare(client, args)
    elif action == "analyze":
        return run_analyze(client, args)
    else:
        print(f"{RED}Usage: youtube-intel keyword analyze <term>{RESET}", file=sys.stderr)
        print(f"{RED}       youtube-intel keyword compare <term1> <term2>{RESET}", file=sys.stderr)
        return 1
