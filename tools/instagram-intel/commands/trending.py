"""Trending commands (Phase 2 -- Playwright scraping).

Commands:
  trending-reels  — Currently trending Reels from instagram.com/reels/
  trending-audio  — Trending audio/music aggregated from Reels
  explore         — Explore page content, optionally filtered by topic
"""

import logging

from ..config import (
    BOLD, CYAN, DIM, EXIT_EXPECTED_ERROR, EXIT_SUCCESS, GREEN, RESET, YELLOW,
)
from ..formatters import format_table, human_number, _truncate
from ..models import ScrapeResult
from ..scoring import velocity_score, score_media_batch
from ..analytics import extract_topics, extract_hashtag_topics, format_topics
from ._scraper_utils import run_scraper, output_result, dry_run

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Command handlers
# ---------------------------------------------------------------------------

def cmd_trending_reels(args, client=None) -> int:
    """Currently trending Reels (Phase 2 -- Playwright scraping)."""
    filters = {}
    limit = getattr(args, "limit", 20) or 20

    if getattr(args, "dry_run", False):
        return dry_run("trending-reels", filters, limit, args)

    result = run_scraper(
        lambda s: s.get_trending_reels(limit=limit),
        args,
        command="trending-reels",
        filters=filters,
        format_map=_FORMAT_MAP,
    )

    if result is None:
        return EXIT_EXPECTED_ERROR

    if isinstance(result, int):
        return result  # Already output by output_cached

    # Enrich with velocity scores (#2)
    sort_mode = getattr(args, "sort", "smart")
    if result.data and sort_mode != "none":
        enriched = _enrich_trending_data(result.data, sort_mode)
        result = ScrapeResult(
            command=result.command,
            success=result.success,
            data=enriched,
            count=len(enriched),
            filters=result.filters,
            cached=result.cached,
        )

    return output_result(result, args, _format_trending_reels)


def cmd_trending_audio(args, client=None) -> int:
    """Trending audio/music on Reels (Phase 2 -- Playwright scraping)."""
    filters = {}
    limit = getattr(args, "limit", 20) or 20

    if getattr(args, "dry_run", False):
        return dry_run("trending-audio", filters, limit, args)

    result = run_scraper(
        lambda s: s.get_trending_audio(limit=limit),
        args,
        command="trending-audio",
        filters=filters,
        format_map=_FORMAT_MAP,
    )

    if result is None:
        return EXIT_EXPECTED_ERROR

    if isinstance(result, int):
        return result

    # Enrich with audio intelligence scores (#5)
    if result.data:
        enriched = _enrich_audio_data(result.data)
        sort_mode = getattr(args, "sort", "smart")
        if sort_mode != "none":
            enriched.sort(key=lambda x: x.get("audio_score", 0), reverse=True)
        result = ScrapeResult(
            command=result.command,
            success=result.success,
            data=enriched,
            count=len(enriched),
            filters=result.filters,
            cached=result.cached,
        )

    return output_result(result, args, _format_trending_audio)


def cmd_explore(args, client=None) -> int:
    """Explore page content for a topic (Phase 2 -- Playwright scraping)."""
    topic = getattr(args, "topic", "") or ""
    filters = {"topic": topic} if topic else {}
    limit = getattr(args, "limit", 20) or 20

    if getattr(args, "dry_run", False):
        return dry_run("explore", filters, limit, args)

    result = run_scraper(
        lambda s: s.get_explore(topic=topic, limit=limit),
        args,
        command="explore",
        filters=filters,
        format_map=_FORMAT_MAP,
    )

    if result is None:
        return EXIT_EXPECTED_ERROR

    if isinstance(result, int):
        return result

    return output_result(result, args, _format_explore)


# ---------------------------------------------------------------------------
# Table formatters
# ---------------------------------------------------------------------------

def _format_trending_reels(result: ScrapeResult) -> str:
    """Format trending reels as a terminal table with velocity scores."""
    data = result.data
    if not data:
        return "  (no results)"

    # Check if velocity scores are present
    has_velocity = any(
        (isinstance(item, dict) and "velocity_score" in item) for item in data
    )

    headers = ["#"]
    if has_velocity:
        headers.append("Vel")
    headers.extend(["Author", "Caption", "Views", "Likes", "Audio"])

    rows = []
    for i, item in enumerate(data):
        if isinstance(item, dict):
            row = [str(item.get("velocity_rank", i + 1)) if has_velocity else str(i + 1)]
            if has_velocity:
                vel = item.get("velocity_score", 0)
                row.append(f"{vel:.1f}" if vel else "-")
            row.extend([
                f"@{item.get('author', '')}" if item.get("author") else "",
                _truncate(item.get("caption", ""), 30),
                item.get("views_fmt", "") or human_number(item.get("views", 0)),
                item.get("likes_fmt", "") or human_number(item.get("likes", 0)),
                _truncate(item.get("audio_name", ""), 22),
            ])
            rows.append(row)
        else:
            row = [str(i + 1)]
            if has_velocity:
                row.append("-")
            row.extend([
                f"@{item.author}" if item.author else "",
                _truncate(item.caption, 30),
                item.views_fmt or human_number(item.views),
                item.likes_fmt or human_number(item.likes),
                _truncate(item.audio_name, 22),
            ])
            rows.append(row)

    table = format_table(headers, rows)

    # Append topic summary (#9) if we have captions
    captions = []
    for item in data:
        cap = item.get("caption", "") if isinstance(item, dict) else getattr(item, "caption", "")
        if cap:
            captions.append(cap)

    if captions:
        topics = extract_topics(captions, top_k=8)
        hashtags = extract_hashtag_topics(captions, top_k=5)
        if topics or hashtags:
            table += f"\n\n  {BOLD}Trending Topics:{RESET}"
            if topics:
                table += "\n" + format_topics(topics, "Keywords")
            if hashtags:
                table += "\n" + format_topics(hashtags, "Hashtags")

    return table


def _format_trending_audio(result: ScrapeResult) -> str:
    """Format trending audio as a terminal table with audio scores (#5)."""
    data = result.data
    if not data:
        return "  (no results)"

    has_score = any(
        (isinstance(item, dict) and "audio_score" in item) for item in data
    )

    headers = ["#", "Audio Name", "Artist", "Used In"]
    if has_score:
        headers.append("Score")

    rows = []
    for i, item in enumerate(data):
        if isinstance(item, dict):
            row = [
                str(i + 1),
                _truncate(item.get("name", ""), 38),
                _truncate(item.get("artist", ""), 22),
                str(item.get("usage_count", 0)),
            ]
            if has_score:
                score = item.get("audio_score", 0)
                row.append(f"{score:.1f}" if score else "-")
            rows.append(row)
        else:
            row = [
                str(i + 1),
                _truncate(item.name, 38),
                _truncate(item.artist, 22),
                str(item.usage_count),
            ]
            if has_score:
                row.append("-")
            rows.append(row)

    return format_table(headers, rows)


def _format_explore(result: ScrapeResult) -> str:
    """Format explore items as a terminal table."""
    data = result.data
    if not data:
        return "  (no results)"

    headers = ["#", "Type", "Author", "Caption", "Likes", "Comments", "Link"]
    rows = []
    for i, item in enumerate(data):
        if isinstance(item, dict):
            rows.append([
                str(i + 1),
                item.get("media_type", ""),
                f"@{item.get('author', '')}" if item.get("author") else "",
                _truncate(item.get("caption", ""), 30),
                item.get("likes_fmt", "") or human_number(item.get("likes", 0)),
                item.get("comments_fmt", "") or human_number(item.get("comments", 0)),
                _truncate(item.get("permalink", ""), 35),
            ])
        else:
            rows.append([
                str(i + 1),
                item.media_type,
                f"@{item.author}" if item.author else "",
                _truncate(item.caption, 30),
                item.likes_fmt or human_number(item.likes),
                item.comments_fmt or human_number(item.comments),
                _truncate(item.permalink, 35),
            ])

    return format_table(headers, rows)


# ---------------------------------------------------------------------------
# Enrichment helpers
# ---------------------------------------------------------------------------

def _enrich_trending_data(data: list, sort_mode: str) -> list:
    """Add velocity scores (#2) and topic extraction (#9) to trending reels."""
    # Convert to dicts if needed
    items = []
    for item in data:
        items.append(item.to_dict() if hasattr(item, "to_dict") else dict(item))

    # Apply velocity scoring (#2)
    if sort_mode in ("smart", "velocity"):
        items = velocity_score(items)
    elif sort_mode == "engagement":
        items = score_media_batch(items, mode="reel", sort=True)

    return items


def _enrich_audio_data(data: list) -> list:
    """Add audio intelligence scores (#5) to trending audio items.

    Score = usage_count * log1p(avg_engagement_of_associated_reels)
    Since we only have usage_count from the aggregated data, we use
    that as the primary signal weighted by count^0.7 for diminishing returns.
    """
    import math

    enriched = []
    for item in data:
        d = item.to_dict() if hasattr(item, "to_dict") else dict(item)
        usage = d.get("usage_count", 0)
        # Audio score: usage count with diminishing returns
        d["audio_score"] = round(math.log1p(usage) * (usage ** 0.3), 2) if usage > 0 else 0
        enriched.append(d)
    return enriched


# Format map for cached output routing
_FORMAT_MAP = {
    "trending-reels": _format_trending_reels,
    "trending-audio": _format_trending_audio,
    "explore": _format_explore,
}
