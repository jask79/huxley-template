"""Hashtag search and media commands."""

from ..cache import FileCache
from ..config import (
    BOLD, CYAN, DIM, EXIT_EXPECTED_ERROR, EXIT_SUCCESS,
    HASHTAG_WEEKLY_LIMIT, RESET, YELLOW,
)
from ..formatters import (
    _truncate, format_table, human_number, json_output, print_error,
    print_footer, print_header, ts_to_str,
)


def cmd_hashtag_top(args, client) -> int:
    """Top media for a hashtag via Graph API."""
    hashtag = args.hashtag.lstrip("#")
    limit = getattr(args, "limit", 25)
    cache = _get_cache(args)
    filters = {"command": "hashtag-top", "hashtag": hashtag, "limit": limit}

    if cache:
        cached = cache.get("hashtag-top", filters)
        if cached:
            return _output_cached_media(cached, args, "hashtag-top", hashtag)

    # Step 1: Search for hashtag ID
    try:
        hashtag_id = client.hashtag_search(hashtag)
        if not hashtag_id:
            msg = f"Hashtag '#{hashtag}' not found"
            if args.json:
                json_output({"error": msg, "type": "not_found"})
            else:
                print_error(msg)
            return EXIT_EXPECTED_ERROR
    except Exception as e:
        if args.json:
            json_output({"error": str(e), "type": "api_error"})
        else:
            print_error(str(e))
        return EXIT_EXPECTED_ERROR

    # Step 2: Get top media
    try:
        media = client.hashtag_top_media(hashtag_id, limit=limit)
    except Exception as e:
        if args.json:
            json_output({"error": str(e), "type": "api_error"})
        else:
            print_error(str(e))
        return EXIT_EXPECTED_ERROR

    data = [m.to_dict() for m in media]
    warnings = [
        f"Graph API allows {HASHTAG_WEEKLY_LIMIT} unique hashtag searches "
        f"per 7-day rolling window."
    ]

    if cache:
        cache.set("hashtag-top", filters, {
            "data": data, "count": len(data), "hashtag_id": hashtag_id,
        })

    if args.json:
        json_output({
            "success": True, "data": data, "count": len(data),
            "hashtag_id": hashtag_id, "cached": False,
            "warnings": warnings,
        })
    else:
        print_header("hashtag-top", {"hashtag": f"#{hashtag}"})
        _print_media_table(media)
        print_footer(len(media), warnings=warnings)

    return EXIT_SUCCESS


def cmd_hashtag_recent(args, client) -> int:
    """Recent media for a hashtag via Graph API."""
    hashtag = args.hashtag.lstrip("#")
    limit = getattr(args, "limit", 25)
    cache = _get_cache(args)
    filters = {"command": "hashtag-recent", "hashtag": hashtag, "limit": limit}

    if cache:
        cached = cache.get("hashtag-recent", filters)
        if cached:
            return _output_cached_media(cached, args, "hashtag-recent", hashtag)

    try:
        hashtag_id = client.hashtag_search(hashtag)
        if not hashtag_id:
            msg = f"Hashtag '#{hashtag}' not found"
            if args.json:
                json_output({"error": msg, "type": "not_found"})
            else:
                print_error(msg)
            return EXIT_EXPECTED_ERROR
    except Exception as e:
        if args.json:
            json_output({"error": str(e), "type": "api_error"})
        else:
            print_error(str(e))
        return EXIT_EXPECTED_ERROR

    try:
        media = client.hashtag_recent_media(hashtag_id, limit=limit)
    except Exception as e:
        if args.json:
            json_output({"error": str(e), "type": "api_error"})
        else:
            print_error(str(e))
        return EXIT_EXPECTED_ERROR

    data = [m.to_dict() for m in media]
    warnings = [
        f"Graph API allows {HASHTAG_WEEKLY_LIMIT} unique hashtag searches "
        f"per 7-day rolling window."
    ]

    if cache:
        cache.set("hashtag-recent", filters, {
            "data": data, "count": len(data), "hashtag_id": hashtag_id,
        })

    if args.json:
        json_output({
            "success": True, "data": data, "count": len(data),
            "hashtag_id": hashtag_id, "cached": False,
            "warnings": warnings,
        })
    else:
        print_header("hashtag-recent", {"hashtag": f"#{hashtag}"})
        _print_media_table(media)
        print_footer(len(media), warnings=warnings)

    return EXIT_SUCCESS


# ---------------------------------------------------------------------------
# Display helpers
# ---------------------------------------------------------------------------

def _print_media_table(media) -> None:
    """Render hashtag media list as a table."""
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


# ---------------------------------------------------------------------------
# Cache helpers
# ---------------------------------------------------------------------------

def _get_cache(args) -> FileCache | None:
    if getattr(args, "no_cache", False):
        return None
    return FileCache(ttl=args.cache_ttl)


def _output_cached_media(cached: dict, args, command: str, hashtag: str) -> int:
    data = cached.get("data", [])
    count = cached.get("count", len(data))
    if args.json:
        json_output({
            "success": True, "data": data, "count": count,
            "hashtag_id": cached.get("hashtag_id", ""),
            "cached": True,
        })
    else:
        from ..models import MediaItem
        media = [MediaItem(**m) for m in data]
        print_header(command, {"hashtag": f"#{hashtag}"})
        _print_media_table(media)
        print_footer(count, cached=True)
    return EXIT_SUCCESS
