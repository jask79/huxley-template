"""Profile & hashtag deep commands (Phase 2 -- Playwright scraping).

Commands:
  user-profile  — Any public user's profile (not limited to Business accounts)
  user-reels    — A user's reels from their profile /reels/ tab
  hashtag-deep  — Deep hashtag data (no 30/week API limit)
"""

import logging

from ..config import (
    BOLD, CYAN, DIM, EXIT_EXPECTED_ERROR, EXIT_SUCCESS, GREEN, RESET, YELLOW,
)
from ..formatters import format_table, human_number, print_error, _truncate
from ..models import ScrapeResult
from ..benchmarks import classify_account
from ._scraper_utils import run_scraper, output_result, dry_run

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Command handlers
# ---------------------------------------------------------------------------

def cmd_user_profile(args, client=None) -> int:
    """Any public user's profile (Phase 2 -- works for all public accounts)."""
    username = getattr(args, "username", "")
    if not username:
        print_error("Username is required")
        return EXIT_EXPECTED_ERROR

    username = username.strip().lstrip("@")
    filters = {"username": username}

    if getattr(args, "dry_run", False):
        return dry_run("user-profile", filters, 1, args)

    result = run_scraper(
        lambda s: s.get_user_profile(username=username),
        args,
        command="user-profile",
        filters=filters,
        format_map=_FORMAT_MAP,
    )

    if result is None:
        return EXIT_EXPECTED_ERROR

    if isinstance(result, int):
        return result

    return output_result(result, args, _format_user_profile)


def cmd_user_reels(args, client=None) -> int:
    """A user's reels from their profile /reels/ tab."""
    username = getattr(args, "username", "")
    if not username:
        print_error("Username is required")
        return EXIT_EXPECTED_ERROR

    username = username.strip().lstrip("@")
    limit = getattr(args, "limit", 20) or 20
    filters = {"username": username}

    if getattr(args, "dry_run", False):
        return dry_run("user-reels", filters, limit, args)

    result = run_scraper(
        lambda s: s.get_user_reels(username=username, limit=limit),
        args,
        command="user-reels",
        filters=filters,
        format_map=_FORMAT_MAP,
    )

    if result is None:
        return EXIT_EXPECTED_ERROR

    if isinstance(result, int):
        return result

    return output_result(result, args, _format_user_reels)


def cmd_hashtag_deep(args, client=None) -> int:
    """Deep hashtag data with no 30/week API limit."""
    hashtag = getattr(args, "hashtag", "")
    if not hashtag:
        print_error("Hashtag is required")
        return EXIT_EXPECTED_ERROR

    hashtag = hashtag.strip().lstrip("#")
    limit = getattr(args, "limit", 50) or 50
    filters = {"hashtag": hashtag}

    if getattr(args, "dry_run", False):
        return dry_run("hashtag-deep", filters, limit, args)

    result = run_scraper(
        lambda s: s.get_hashtag_deep(hashtag=hashtag, limit=limit),
        args,
        command="hashtag-deep",
        filters=filters,
        format_map=_FORMAT_MAP,
    )

    if result is None:
        return EXIT_EXPECTED_ERROR

    if isinstance(result, int):
        return result

    return output_result(result, args, _format_hashtag_deep)


# ---------------------------------------------------------------------------
# Table formatters
# ---------------------------------------------------------------------------

def _format_user_profile(result: ScrapeResult) -> str:
    """Format a user profile as a detailed display."""
    data = result.data
    if not data:
        return "  (no results)"

    item = data[0]
    if isinstance(item, dict):
        username = item.get("username", "")
        full_name = item.get("full_name", "")
        bio = item.get("biography", "")
        followers = item.get("followers", 0)
        following = item.get("following", 0)
        media_count = item.get("media_count", 0)
        is_verified = item.get("is_verified", False)
        is_private = item.get("is_private", False)
        is_business = item.get("is_business", False)
        category = item.get("category", "")
        external_url = item.get("external_url", "")
        followers_fmt = item.get("followers_fmt", "") or human_number(followers)
        following_fmt = item.get("following_fmt", "") or human_number(following)
    else:
        username = item.username
        full_name = item.full_name
        bio = item.biography
        followers = item.followers
        following = item.following
        media_count = item.media_count
        is_verified = item.is_verified
        is_private = item.is_private
        is_business = item.is_business
        category = item.category
        external_url = item.external_url
        followers_fmt = item.followers_fmt or human_number(followers)
        following_fmt = item.following_fmt or human_number(following)

    verified_badge = f" {GREEN}Verified{RESET}" if is_verified else ""
    private_badge = f" {YELLOW}Private{RESET}" if is_private else ""
    business_badge = f" {CYAN}Business{RESET}" if is_business else ""

    lines = [
        f"  {BOLD}@{username}{RESET}{verified_badge}{private_badge}{business_badge}",
    ]
    if full_name:
        lines.append(f"  {full_name}")
    if category:
        lines.append(f"  {DIM}{category}{RESET}")
    if bio:
        lines.append(f"  {DIM}{_truncate(bio, 80)}{RESET}")
    lines.append("")

    lines.append(
        f"  {CYAN}Followers:{RESET} {followers_fmt}   "
        f"{CYAN}Following:{RESET} {following_fmt}   "
        f"{CYAN}Posts:{RESET} {human_number(media_count)}"
    )

    if external_url:
        lines.append(f"  {CYAN}Website:{RESET} {external_url}")

    # Account classification (#11)
    classification = classify_account(followers, following)
    ratio = classification.get("ratio", 0)
    acct_type = classification.get("account_type", "")
    description = classification.get("description", "")
    tier = classification.get("tier", "")

    lines.append("")
    lines.append(f"  {CYAN}F/F Ratio:{RESET} {ratio:.1f}x   "
                 f"{CYAN}Type:{RESET} {acct_type}   "
                 f"{CYAN}Tier:{RESET} {tier}")
    if description:
        lines.append(f"  {DIM}{description}{RESET}")

    return "\n".join(lines)


def _format_user_reels(result: ScrapeResult) -> str:
    """Format user reels as a terminal table."""
    data = result.data
    if not data:
        return "  (no results)"

    headers = ["#", "Caption", "Views", "Likes", "Comments", "Audio", "Link"]
    rows = []
    for i, item in enumerate(data):
        if isinstance(item, dict):
            rows.append([
                str(i + 1),
                _truncate(item.get("caption", ""), 35),
                item.get("views_fmt", "") or human_number(item.get("views", 0)),
                item.get("likes_fmt", "") or human_number(item.get("likes", 0)),
                human_number(item.get("comments", 0)),
                _truncate(item.get("audio_name", ""), 20),
                _truncate(item.get("permalink", ""), 35),
            ])
        else:
            rows.append([
                str(i + 1),
                _truncate(item.caption, 35),
                item.views_fmt or human_number(item.views),
                item.likes_fmt or human_number(item.likes),
                human_number(item.comments),
                _truncate(item.audio_name, 20),
                _truncate(item.permalink, 35),
            ])

    return format_table(headers, rows)


def _format_hashtag_deep(result: ScrapeResult) -> str:
    """Format deep hashtag data as a detailed display with relevance scoring (#10)."""
    data = result.data
    if not data:
        return "  (no results)"

    item = data[0]
    if isinstance(item, dict):
        name = item.get("name", "")
        media_count = item.get("media_count", 0)
        media_count_fmt = item.get("media_count_fmt", "") or human_number(media_count)
        top_posts = item.get("top_posts", [])
        recent_posts = item.get("recent_posts", [])
    else:
        name = item.name
        media_count = item.media_count
        media_count_fmt = item.media_count_fmt or human_number(media_count)
        top_posts = item.top_posts
        recent_posts = item.recent_posts

    lines = [
        f"  {BOLD}#{name}{RESET}",
        f"  {CYAN}Total Media:{RESET} {media_count_fmt}",
    ]

    if top_posts:
        # Re-rank top posts by engagement (#10)
        scored_top = _score_hashtag_posts(top_posts)
        lines.append(f"\n  {BOLD}Top Posts (ranked by engagement):{RESET}")
        headers = ["#", "Score", "Type", "Author", "Likes", "Link"]
        rows = []
        for i, post in enumerate(scored_top[:10]):
            if isinstance(post, dict):
                score = post.get("_relevance_score", 0)
                rows.append([
                    str(i + 1),
                    f"{score:.1f}" if score else "-",
                    post.get("media_type", ""),
                    f"@{post.get('author', '')}" if post.get("author") else "",
                    post.get("likes_fmt", "") or human_number(post.get("likes", 0)),
                    _truncate(post.get("permalink", ""), 38),
                ])
        if rows:
            lines.append(format_table(headers, rows))

    if recent_posts:
        lines.append(f"\n  {BOLD}Recent Posts:{RESET}")
        headers = ["#", "Type", "Author", "Likes", "Link"]
        rows = []
        for i, post in enumerate(recent_posts[:10]):
            if isinstance(post, dict):
                rows.append([
                    str(i + 1),
                    post.get("media_type", ""),
                    f"@{post.get('author', '')}" if post.get("author") else "",
                    post.get("likes_fmt", "") or human_number(post.get("likes", 0)),
                    _truncate(post.get("permalink", ""), 40),
                ])
        if rows:
            lines.append(format_table(headers, rows))

    return "\n".join(lines)


def _score_hashtag_posts(posts: list) -> list:
    """Score and re-rank hashtag posts by engagement relevance (#10).

    Uses a simple engagement score: likes + 2*comments.
    Returns sorted copy with _relevance_score added.
    """
    import math

    scored = []
    for post in posts:
        if not isinstance(post, dict):
            scored.append(post)
            continue
        likes = post.get("likes", 0) or 0
        comments = post.get("comments", 0) or 0
        if isinstance(likes, str):
            try:
                likes = int(likes.replace(",", ""))
            except ValueError:
                likes = 0
        if isinstance(comments, str):
            try:
                comments = int(comments.replace(",", ""))
            except ValueError:
                comments = 0
        score = math.log1p(likes + 2 * comments)
        p = dict(post)
        p["_relevance_score"] = round(score, 2)
        scored.append(p)

    scored.sort(key=lambda x: x.get("_relevance_score", 0) if isinstance(x, dict) else 0, reverse=True)
    return scored


# Format map for cached output routing
_FORMAT_MAP = {
    "user-profile": _format_user_profile,
    "user-reels": _format_user_reels,
    "hashtag-deep": _format_hashtag_deep,
}
