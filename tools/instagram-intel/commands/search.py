"""Search commands (Phase 2 -- Playwright scraping).

Commands:
  search-users     — Search Instagram users via topsearch API
  search-hashtags  — Search hashtags without the 30/week API cap
  search-content   — Search posts/reels by keyword (tag-based proxy)
"""

import logging

from ..config import (
    BOLD, CYAN, DIM, EXIT_EXPECTED_ERROR, EXIT_SUCCESS, GREEN, RESET, YELLOW,
)
from ..formatters import format_table, human_number, print_error, _truncate
from ..models import ScrapeResult
from ._scraper_utils import run_scraper, output_result, dry_run

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Command handlers
# ---------------------------------------------------------------------------

def cmd_search_users(args, client=None) -> int:
    """Search Instagram users (Phase 2 -- Playwright scraping)."""
    query = getattr(args, "query", "")
    if not query:
        print_error("Search query is required")
        return EXIT_EXPECTED_ERROR

    limit = getattr(args, "limit", 20) or 20
    filters = {"query": query}

    if getattr(args, "dry_run", False):
        return dry_run("search-users", filters, limit, args)

    result = run_scraper(
        lambda s: s.search_users(query=query, limit=limit),
        args,
        command="search-users",
        filters=filters,
        format_map=_FORMAT_MAP,
    )

    if result is None:
        return EXIT_EXPECTED_ERROR

    if isinstance(result, int):
        return result  # Already output by output_cached

    # Apply search re-ranking (#12)
    if result.data:
        reranked = _rerank_users(result.data, args)
        if reranked is not None:
            result = ScrapeResult(
                command=result.command,
                success=result.success,
                data=reranked,
                count=len(reranked),
                filters=result.filters,
                cached=result.cached,
            )

    return output_result(result, args, _format_search_users)


def cmd_search_hashtags(args, client=None) -> int:
    """Search hashtags without the 30/week API cap (Phase 2 -- Playwright scraping)."""
    query = getattr(args, "query", "")
    if not query:
        print_error("Search query is required")
        return EXIT_EXPECTED_ERROR

    limit = getattr(args, "limit", 20) or 20
    filters = {"query": query}

    if getattr(args, "dry_run", False):
        return dry_run("search-hashtags", filters, limit, args)

    result = run_scraper(
        lambda s: s.search_hashtags(query=query, limit=limit),
        args,
        command="search-hashtags",
        filters=filters,
        format_map=_FORMAT_MAP,
    )

    if result is None:
        return EXIT_EXPECTED_ERROR

    if isinstance(result, int):
        return result

    return output_result(result, args, _format_search_hashtags)


def cmd_search_content(args, client=None) -> int:
    """Search posts/reels by keyword (Phase 2 -- Playwright scraping)."""
    query = getattr(args, "query", "")
    if not query:
        print_error("Search query is required")
        return EXIT_EXPECTED_ERROR

    limit = getattr(args, "limit", 20) or 20
    filters = {"query": query}

    if getattr(args, "dry_run", False):
        return dry_run("search-content", filters, limit, args)

    result = run_scraper(
        lambda s: s.search_content(query=query, limit=limit),
        args,
        command="search-content",
        filters=filters,
        format_map=_FORMAT_MAP,
    )

    if result is None:
        return EXIT_EXPECTED_ERROR

    if isinstance(result, int):
        return result

    return output_result(result, args, _format_search_content)


# ---------------------------------------------------------------------------
# Table formatters
# ---------------------------------------------------------------------------

def _format_search_users(result: ScrapeResult) -> str:
    """Format search user results as a terminal table."""
    data = result.data
    if not data:
        return "  (no results)"

    headers = ["#", "Username", "Full Name", "Followers", "Verified", "Private"]
    rows = []
    for i, item in enumerate(data):
        if isinstance(item, dict):
            verified = f"{GREEN}Yes{RESET}" if item.get("is_verified") else ""
            private = f"{YELLOW}Yes{RESET}" if item.get("is_private") else ""
            rows.append([
                str(i + 1),
                f"@{item.get('username', '')}",
                _truncate(item.get("full_name", ""), 25),
                item.get("followers_fmt", "") or human_number(item.get("followers", 0)),
                verified,
                private,
            ])
        else:
            verified = f"{GREEN}Yes{RESET}" if item.is_verified else ""
            private = f"{YELLOW}Yes{RESET}" if item.is_private else ""
            rows.append([
                str(i + 1),
                f"@{item.username}",
                _truncate(item.full_name, 25),
                item.followers_fmt or human_number(item.followers),
                verified,
                private,
            ])

    return format_table(headers, rows)


def _format_search_hashtags(result: ScrapeResult) -> str:
    """Format search hashtag results as a terminal table."""
    data = result.data
    if not data:
        return "  (no results)"

    headers = ["#", "Hashtag", "Media Count"]
    rows = []
    for i, item in enumerate(data):
        if isinstance(item, dict):
            rows.append([
                str(i + 1),
                f"#{item.get('name', '')}",
                item.get("media_count_fmt", "") or human_number(item.get("media_count", 0)),
            ])
        else:
            rows.append([
                str(i + 1),
                f"#{item.name}",
                item.media_count_fmt or human_number(item.media_count),
            ])

    return format_table(headers, rows)


def _format_search_content(result: ScrapeResult) -> str:
    """Format search content results as a terminal table."""
    data = result.data
    if not data:
        return "  (no results)"

    headers = ["#", "Type", "Author", "Caption", "Likes", "Link"]
    rows = []
    for i, item in enumerate(data):
        if isinstance(item, dict):
            rows.append([
                str(i + 1),
                item.get("media_type", ""),
                f"@{item.get('author', '')}" if item.get("author") else "",
                _truncate(item.get("caption", ""), 30),
                item.get("likes_fmt", "") or human_number(item.get("likes", 0)),
                _truncate(item.get("permalink", ""), 40),
            ])
        else:
            rows.append([
                str(i + 1),
                item.media_type,
                f"@{item.author}" if item.author else "",
                _truncate(item.caption, 30),
                item.likes_fmt or human_number(item.likes),
                _truncate(item.permalink, 40),
            ])

    return format_table(headers, rows)


# ---------------------------------------------------------------------------
# Search re-ranking (#12)
# ---------------------------------------------------------------------------

def _rerank_users(data: list, args) -> list | None:
    """Apply preference-based re-ranking to search-users results.

    Filters:
      --prefer-verified: boost verified accounts to top
      --min-followers N: exclude accounts below N followers
      --max-followers N: exclude accounts above N followers (0 = no limit)

    Returns re-ranked list, or None if no re-ranking is needed.
    """
    prefer_verified = getattr(args, "prefer_verified", False)
    min_followers = getattr(args, "min_followers", 0) or 0
    max_followers = getattr(args, "max_followers", 0) or 0

    if not prefer_verified and not min_followers and not max_followers:
        return None  # No re-ranking needed

    result = []
    for item in data:
        d = item.to_dict() if hasattr(item, "to_dict") else (dict(item) if isinstance(item, dict) else item)

        followers = d.get("followers", 0) or 0
        if isinstance(followers, str):
            try:
                followers = int(followers.replace(",", ""))
            except ValueError:
                followers = 0

        # Apply follower filters
        if min_followers and followers < min_followers:
            continue
        if max_followers and followers > max_followers:
            continue

        result.append(d)

    # Boost verified to top if requested
    if prefer_verified:
        verified = [d for d in result if d.get("is_verified", False)]
        not_verified = [d for d in result if not d.get("is_verified", False)]
        result = verified + not_verified

    return result


# Format map for cached output routing
_FORMAT_MAP = {
    "search-users": _format_search_users,
    "search-hashtags": _format_search_hashtags,
    "search-content": _format_search_content,
}
