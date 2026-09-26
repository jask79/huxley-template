"""Shared scraper lifecycle utilities for Phase 2 commands.

Extracted from trending.py/search.py/profile.py to avoid triplication.
All Phase 2 command modules import from here.
"""

import logging
from typing import Any, Callable, Dict, Optional

from ..cache import FileCache
from ..config import (
    COMMAND_TTL, DEFAULT_CACHE_TTL, DIM, EXIT_EXPECTED_ERROR, EXIT_SUCCESS, RESET,
)
from ..exceptions import AntiDetectionError, ScraperError
from ..formatters import (
    format_table, json_output, print_error, print_footer, print_header,
)
from ..models import ScrapeResult

logger = logging.getLogger(__name__)


def run_scraper(
    func: Callable,
    args,
    command: str,
    filters: dict,
    cache_key: str = "",
    format_map: Optional[Dict[str, Callable]] = None,
) -> "ScrapeResult | int | None":
    """Launch the Instagram scraper, run a function, and handle errors.

    Pattern mirrors tiktok-intel/cli.py _run_scraper.
    Returns ScrapeResult on success, int (exit code) if cached, None on error.
    """
    from ..clients.scraper import InstagramScraper

    headless = not getattr(args, "no_headless", False)
    cache = get_cache(args, command=command)

    # Check cache first
    if cache:
        cached = cache.get(cache_key or command, filters)
        if cached:
            return output_cached(cached, args, command, filters, format_map)

    try:
        with InstagramScraper(headless=headless, cache=cache, verbose=args.verbose) as scraper:
            data = func(scraper)

            if data is None or (isinstance(data, list) and len(data) == 0):
                result = ScrapeResult(
                    command=command,
                    success=False,
                    error=(
                        f"No data returned for '{command}'. Instagram may be "
                        "blocking scraping, the page structure changed, or the "
                        "query returned no results. Try --no-headless for debugging."
                    ),
                    filters=filters,
                )
                return output_error(result, args)

            if isinstance(data, list):
                result = ScrapeResult(
                    command=command,
                    success=True,
                    data=data,
                    count=len(data),
                    filters=filters,
                )
            elif isinstance(data, dict):
                result = ScrapeResult(
                    command=command,
                    success=True,
                    data=[data],
                    count=1,
                    filters=filters,
                )
            else:
                result = ScrapeResult(
                    command=command,
                    success=False,
                    error="Unexpected data format from scraper",
                    filters=filters,
                )
                return output_error(result, args)

            # Cache successful result
            if cache and result.success:
                cache.set(cache_key or command, filters, result.to_dict())

            return result

    except AntiDetectionError as e:
        if args.json:
            json_output(e.to_dict())
        else:
            print_error(str(e), "Try again later or use --no-headless for debugging")
        return None

    except ScraperError as e:
        if args.json:
            json_output(e.to_dict())
        else:
            print_error(str(e))
        return None

    except Exception as e:
        if args.json:
            json_output({"error": str(e), "type": "scraper_error"})
        else:
            print_error(f"Scraper error: {e}")
            if args.verbose:
                import traceback
                traceback.print_exc()
        return None


def get_cache(args, command: str = "") -> Optional[FileCache]:
    """Return a FileCache or None if caching is disabled.

    Uses command-specific TTL from COMMAND_TTL if available, falling
    back to the --cache-ttl CLI arg or DEFAULT_CACHE_TTL.
    """
    if getattr(args, "no_cache", False):
        return None
    # Command-specific TTL takes priority unless user explicitly set --cache-ttl
    user_ttl = getattr(args, "cache_ttl", DEFAULT_CACHE_TTL)
    ttl = COMMAND_TTL.get(command, user_ttl) if command else user_ttl
    return FileCache(ttl=ttl)


def output_cached(
    cached_data: dict,
    args,
    command: str,
    filters: dict,
    format_map: Optional[Dict[str, Callable]] = None,
) -> int:
    """Output cached results."""
    if args.json:
        cached_data["cached"] = True
        json_output(cached_data)
    else:
        result = ScrapeResult(
            command=command,
            success=True,
            data=cached_data.get("data", []),
            count=cached_data.get("count", 0),
            filters=filters,
            cached=True,
        )
        print_header(command, filters)
        formatter = _format_generic
        if format_map:
            formatter = format_map.get(command, _format_generic)
        print(formatter(result))
        print_footer(result.count, cached=True)

    return EXIT_SUCCESS


def output_error(result: ScrapeResult, args) -> int:
    """Output error result."""
    if args.json:
        json_output({"error": result.error, "type": "scraper_error"})
    else:
        print_error(result.error or "Scrape failed")
    return EXIT_EXPECTED_ERROR


def output_result(result: ScrapeResult, args, formatter: Callable) -> int:
    """Output a ScrapeResult in JSON or table format."""
    if not result.success:
        return output_error(result, args)

    if args.json:
        json_output(result.to_dict())
    else:
        print_header(result.command, result.filters)
        print(formatter(result))
        print_footer(result.count, result.cached)

    return EXIT_SUCCESS


def dry_run(command: str, filters: dict, limit: int, args) -> int:
    """Show what would happen without launching browser."""
    info = {
        "command": command,
        "filters": filters,
        "limit": limit,
        "dry_run": True,
        "would_launch_browser": True,
        "cache_enabled": not getattr(args, "no_cache", False),
    }
    if args.json:
        json_output(info)
    else:
        print_header(f"{command} (dry-run)", filters)
        rows = [[k, str(v)] for k, v in info.items()]
        print(format_table(["Parameter", "Value"], rows))
        print(f"\n{DIM}No browser launched. Remove --dry-run to scrape.{RESET}\n")
    return EXIT_SUCCESS


def _format_generic(result: ScrapeResult) -> str:
    """Generic fallback formatter for list data."""
    data = result.data
    if not data:
        return "  (no results)"

    first = data[0]
    if isinstance(first, dict):
        headers = list(first.keys())[:6]
        rows = []
        for item in data:
            rows.append([str(item.get(h, ""))[:40] for h in headers])
        return format_table(headers, rows)

    return f"  {len(data)} item(s)"
