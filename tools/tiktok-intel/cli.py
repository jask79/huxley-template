#!/usr/bin/env python3
"""
TikTok Intelligence CLI — competitive research via Creative Center scraping.

Brand-agnostic Huxley-level tool. Scrapes TikTok Creative Center (public,
no auth) using Playwright + stealth for trending data, top ads, and hashtag
analytics.

Dependencies: playwright, playwright-stealth (both pre-installed).

Exit codes:
    0 — success
    1 — expected error (bad input, scraper failure, rate limit)
    2 — unexpected error (crash, unhandled exception)
"""

import argparse
import json
import logging
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

# ---------------------------------------------------------------------------
# Import resolution — support both `python3 cli.py` and `python3 -m` usage.
# The directory name "tiktok-intel" has a hyphen (not importable directly),
# so we always use relative-style imports via an importlib shim when running
# as a script, and relative imports when running as a package.
# ---------------------------------------------------------------------------
_SCRIPT_DIR = Path(__file__).resolve().parent

def _setup_imports():
    """Make sibling modules importable regardless of invocation method."""
    # If running as part of a package (__package__ is set), relative imports
    # already work via __main__.py. When running cli.py directly as a script,
    # __package__ is None and we need importlib to load from the same directory.
    import importlib.util

    def _load(name: str):
        """Import a sibling module by filename."""
        spec = importlib.util.spec_from_file_location(
            f"tiktok_intel.{name}", _SCRIPT_DIR / f"{name}.py",
            submodule_search_locations=[str(_SCRIPT_DIR)] if name == "__init__" else None,
        )
        mod = importlib.util.module_from_spec(spec)
        sys.modules[f"tiktok_intel.{name}"] = mod
        spec.loader.exec_module(mod)
        return mod

    # Bootstrap: register the package itself so sub-imports resolve
    if "tiktok_intel" not in sys.modules:
        pkg_spec = importlib.util.spec_from_file_location(
            "tiktok_intel",
            _SCRIPT_DIR / "__init__.py",
            submodule_search_locations=[str(_SCRIPT_DIR)],
        )
        pkg = importlib.util.module_from_spec(pkg_spec)
        sys.modules["tiktok_intel"] = pkg
        pkg_spec.loader.exec_module(pkg)

    # Now load each module — they can do relative imports from tiktok_intel
    for mod_name in ["config", "exceptions", "models", "formatters", "cache", "browser", "scoring"]:
        if f"tiktok_intel.{mod_name}" not in sys.modules:
            _load(mod_name)

    # Scrapers sub-package
    scrapers_dir = _SCRIPT_DIR / "scrapers"
    if "tiktok_intel.scrapers" not in sys.modules:
        sp_spec = importlib.util.spec_from_file_location(
            "tiktok_intel.scrapers",
            scrapers_dir / "__init__.py",
            submodule_search_locations=[str(scrapers_dir)],
        )
        sp = importlib.util.module_from_spec(sp_spec)
        sys.modules["tiktok_intel.scrapers"] = sp

    for scraper_mod in ["base", "creative_center", "top_ads", "hashtags", "search", "competitor", "shop"]:
        full = f"tiktok_intel.scrapers.{scraper_mod}"
        if full not in sys.modules:
            s_spec = importlib.util.spec_from_file_location(
                full, scrapers_dir / f"{scraper_mod}.py",
            )
            s = importlib.util.module_from_spec(s_spec)
            sys.modules[full] = s
            s_spec.loader.exec_module(s)

    # Now exec scrapers __init__ — all submodules are already in sys.modules
    # so the `from .X import` statements will resolve correctly.
    sp = sys.modules["tiktok_intel.scrapers"]
    if not hasattr(sp, "CreativeCenterScraper"):
        sp_spec = importlib.util.spec_from_file_location(
            "tiktok_intel.scrapers",
            scrapers_dir / "__init__.py",
            submodule_search_locations=[str(scrapers_dir)],
        )
        sp_spec.loader.exec_module(sp)


# Only run the shim when invoked as a script (not via -m)
if __package__ is None or __package__ == "":
    _setup_imports()

from tiktok_intel import __version__
from tiktok_intel.browser import BrowserManager
from tiktok_intel.cache import FileCache
from tiktok_intel.config import (
    AD_OBJECTIVES,
    AD_SORT_OPTIONS,
    BOLD,
    CYAN,
    DEFAULT_CACHE_TTL,
    DIM,
    EXIT_EXPECTED_ERROR,
    EXIT_SUCCESS,
    EXIT_UNEXPECTED_ERROR,
    GREEN,
    INDUSTRIES,
    MAGENTA,
    RED,
    RESET,
    TREND_TYPES,
    VERSION,
    YELLOW,
)
from tiktok_intel.exceptions import (
    AntiDetectionError,
    BrowserLaunchError,
    CacheError,
    RateLimitError,
    ScraperError,
    SelectorTimeoutError,
    TikTokIntelError,
)
from tiktok_intel.formatters import (
    format_table,
    json_output,
    parse_human_number,
    print_error,
    print_footer,
    print_header,
    _truncate,
    _visible_len,
)
from tiktok_intel.models import ScrapeResult
from tiktok_intel.scrapers import CreativeCenterScraper, HashtagScraper, TopAdsScraper
from tiktok_intel.scrapers import SearchScraper, CompetitorScraper, ShopScraper
from tiktok_intel.config import SEARCH_TYPES
from tiktok_intel.models import (
    SearchVideoResult, SearchUserResult, CompetitorProfile, ShopProduct,
    TrendingHashtag, TrendingSong, TrendingCreator, TrendingVideo,
)
from tiktok_intel.scoring import (
    classify_trend_velocity,
    rank_results,
    safe_parse_float,
    score_competitor_engagement,
    score_shop_product,
    score_video_engagement,
    VELOCITY_ORDER,
)

logger = logging.getLogger("tiktok-intel")


# ---------------------------------------------------------------------------
# Argument parser
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    """Build the CLI argument parser with all subcommands."""
    shared = argparse.ArgumentParser(add_help=False)
    shared.add_argument("-v", "--verbose", action="store_true", help="Enable verbose logging")
    shared.add_argument("--json", action="store_true", help="Output results as JSON")
    shared.add_argument("--dry-run", action="store_true",
                        help="Preview command without launching browser")
    shared.add_argument("--cache-ttl", type=int, default=DEFAULT_CACHE_TTL,
                        help=f"Cache TTL in seconds (default: {DEFAULT_CACHE_TTL})")
    shared.add_argument("--no-cache", action="store_true", help="Bypass cache")
    shared.add_argument("--output-dir", help="Save results as timestamped JSON to this directory")
    shared.add_argument("--no-headless", action="store_true",
                        help="Run browser in headed mode (visible window)")

    parser = argparse.ArgumentParser(
        prog="tiktok-intel",
        parents=[shared],
        description=(
            f"TikTok Intelligence CLI v{VERSION}\n"
            "Competitive research via Creative Center scraping.\n"
            "No auth required — all data is publicly accessible."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Trends examples:\n"
            "  %(prog)s trends --type hashtags --country US --limit 20\n"
            "  %(prog)s trends --type songs --industry beauty --json\n"
            "  %(prog)s trends --type creators --country US\n"
            "  %(prog)s trends --type videos --limit 10\n"
            "\n"
            "Top Ads examples:\n"
            "  %(prog)s top-ads --sort reach --region US --json\n"
            "  %(prog)s top-ads --objective Conversions --limit 10\n"
            "\n"
            "Hashtag examples:\n"
            "  %(prog)s hashtags --hashtag ootd --country US --json\n"
            "\n"
            "Search examples (Phase 2):\n"
            "  %(prog)s search -q 'protein powder' --type video --limit 30\n"
            "  %(prog)s search -q 'fitness influencer' --type user --json\n"
            "\n"
            "Competitor examples (Phase 2):\n"
            "  %(prog)s competitor -u charlidamelio --videos --json\n"
            "  %(prog)s competitor -u therock --videos --limit 20\n"
            "\n"
            "Shop examples (Phase 2):\n"
            "  %(prog)s shop-products -q 'skincare serum' --limit 30\n"
            "  %(prog)s shop-products --shop-id 12345 --json\n"
            "\n"
            "Cache management:\n"
            "  %(prog)s cache-clear\n"
            "  %(prog)s cache-stats\n"
            "\n"
            "Uses Playwright + stealth to scrape TikTok Creative Center & tiktok.com.\n"
        ),
    )

    sub = parser.add_subparsers(dest="command", help="Available commands")

    # --- trends ---
    p = sub.add_parser("trends", parents=[shared],
                       help="Trending hashtags, songs, creators, or videos")
    p.add_argument("--type", dest="trend_type", default="hashtags",
                   choices=TREND_TYPES,
                   help="Type of trending data (default: hashtags)")
    p.add_argument("--country", default="", help="Country code (e.g., US, GB, JP)")
    p.add_argument("--industry", default="", help="Industry filter")
    p.add_argument("--period", default="7", help="Time period in days (default: 7)")
    p.add_argument("--sort", dest="sort_by", default="rank",
                   choices=["rank", "velocity"],
                   help="Sort order (default: rank)")
    p.add_argument("--limit", type=int, default=20, help="Max results (default: 20)")

    # --- top-ads ---
    p = sub.add_parser("top-ads", parents=[shared],
                       help="Top performing ads")
    p.add_argument("--sort", default="for_you", choices=AD_SORT_OPTIONS,
                   help="Sort order (default: for_you)")
    p.add_argument("--region", default="", help="Region/country code (e.g., US)")
    p.add_argument("--objective", default="", help="Ad objective (e.g., Conversions)")
    p.add_argument("--industry", default="", help="Industry filter")
    p.add_argument("--limit", type=int, default=20, help="Max results (default: 20)")

    # --- hashtags ---
    p = sub.add_parser("hashtags", parents=[shared],
                       help="Detailed analytics for a specific hashtag")
    p.add_argument("--hashtag", "--tag", required=True, help="Hashtag to analyze (without #)")
    p.add_argument("--country", default="", help="Country code (e.g., US)")

    # --- cache-clear ---
    sub.add_parser("cache-clear", parents=[shared], help="Clear all cached results")

    # --- cache-stats ---
    sub.add_parser("cache-stats", parents=[shared], help="Show cache statistics")

    # --- search (Phase 2) ---
    p = sub.add_parser("search", parents=[shared],
                       help="Search tiktok.com for videos or users")
    p.add_argument("--query", "-q", required=True, help="Search query")
    p.add_argument("--type", dest="search_type", default="video",
                   choices=SEARCH_TYPES,
                   help="Search type: video or user (default: video)")
    p.add_argument("--sort", dest="sort_by", default="relevance",
                   choices=["relevance", "engagement", "views", "likes"],
                   help="Sort order for video results (default: relevance)")
    p.add_argument("--limit", type=int, default=20, help="Max results (default: 20)")

    # --- competitor (Phase 2) ---
    p = sub.add_parser("competitor", parents=[shared],
                       help="Analyze a TikTok competitor profile")
    p.add_argument("--username", "-u", required=True,
                   help="TikTok username to analyze (without @)")
    p.add_argument("--videos", action="store_true",
                   help="Include recent videos (requires --no-headless; SSR only returns profile)")
    p.add_argument("--limit", type=int, default=10,
                   help="Max recent videos to analyze (default: 10)")

    # --- shop-products (Phase 2) ---
    p = sub.add_parser("shop-products", parents=[shared],
                       help="Search TikTok Shop for products")
    p.add_argument("--query", "-q", default="",
                   help="Product search query")
    p.add_argument("--shop-id", default="",
                   help="Specific shop ID to browse")
    p.add_argument("--sort", dest="sort_by", default="relevance",
                   choices=["relevance", "score", "rating", "price"],
                   help="Sort order for products (default: relevance)")
    p.add_argument("--limit", type=int, default=20, help="Max results (default: 20)")

    return parser


# ---------------------------------------------------------------------------
# Command handlers
# ---------------------------------------------------------------------------

def cmd_trends(args) -> int:
    """Handle the 'trends' command."""
    filters = {
        "type": args.trend_type,
        "country": args.country,
        "industry": args.industry,
        "period": args.period,
    }
    limit = args.limit

    # Dry run — just show what would happen
    if args.dry_run:
        return _dry_run_output("trends", filters, limit, args)

    # Check cache
    cache = _get_cache(args)
    if cache:
        cached = cache.get("trends", filters)
        if cached:
            return _output_cached(cached, args, "trends", filters)

    # Scrape
    result = _run_scraper(CreativeCenterScraper, filters, limit, args)
    if not result:
        return EXIT_EXPECTED_ERROR

    # Apply velocity sorting if requested
    sort_by = getattr(args, "sort_by", "rank")
    if result.success and result.data and sort_by == "velocity":
        # Sort by velocity classification: BREAKOUT > RISING > NEW > STABLE > DECLINING
        result.data = rank_results(
            result.data,
            lambda item: VELOCITY_ORDER.get(classify_trend_velocity(item), 1)
            if not isinstance(item, dict)
            else 1,
        )

    # Pre-compute velocities once for display and JSON (avoids double-call in formatters)
    if result.success and result.data:
        result.velocities = {
            i: classify_trend_velocity(item)
            for i, item in enumerate(result.data)
            if not isinstance(item, dict)
        }

    # Cache result
    if cache and result.success:
        cache.set("trends", filters, result.to_dict())

    # Output
    return _output_result(result, args, _format_trends)


def cmd_top_ads(args) -> int:
    """Handle the 'top-ads' command."""
    filters = {
        "sort": args.sort,
        "region": args.region,
        "objective": args.objective,
        "industry": args.industry,
    }
    limit = args.limit

    if args.dry_run:
        return _dry_run_output("top-ads", filters, limit, args)

    cache = _get_cache(args)
    if cache:
        cached = cache.get("top-ads", filters)
        if cached:
            return _output_cached(cached, args, "top-ads", filters)

    result = _run_scraper(TopAdsScraper, filters, limit, args)
    if not result:
        return EXIT_EXPECTED_ERROR

    if cache and result.success:
        cache.set("top-ads", filters, result.to_dict())

    return _output_result(result, args, _format_top_ads)


def cmd_hashtags(args) -> int:
    """Handle the 'hashtags' command."""
    filters = {
        "hashtag": args.hashtag,
        "country": args.country,
    }

    if args.dry_run:
        return _dry_run_output("hashtags", filters, 1, args)

    cache = _get_cache(args)
    if cache:
        cached = cache.get("hashtags", filters)
        if cached:
            return _output_cached(cached, args, "hashtags", filters)

    result = _run_scraper(HashtagScraper, filters, 1, args)
    if not result:
        return EXIT_EXPECTED_ERROR

    if cache and result.success:
        cache.set("hashtags", filters, result.to_dict())

    return _output_result(result, args, _format_hashtag_analytics)


def cmd_cache_clear(args) -> int:
    """Handle the 'cache-clear' command."""
    cache = FileCache(ttl=args.cache_ttl)
    count = cache.clear()
    if args.json:
        json_output({"cleared": count})
    else:
        print(f"\n{GREEN}Cleared {count} cache entries.{RESET}\n")
    return EXIT_SUCCESS


def cmd_cache_stats(args) -> int:
    """Handle the 'cache-stats' command."""
    cache = FileCache(ttl=args.cache_ttl)
    stats = cache.stats()
    if args.json:
        json_output(stats)
    else:
        print_header("cache-stats")
        rows = [[k, str(v)] for k, v in stats.items()]
        print(format_table(["Key", "Value"], rows))
        print()
    return EXIT_SUCCESS


def cmd_search(args) -> int:
    """Handle the 'search' command."""
    filters = {
        "query": args.query,
        "search_type": args.search_type,
    }
    limit = args.limit

    if args.dry_run:
        return _dry_run_output("search", filters, limit, args)

    cache = _get_cache(args)
    if cache:
        cached = cache.get("search", filters)
        if cached:
            return _output_cached(cached, args, "search", filters)

    result = _run_scraper(SearchScraper, filters, limit, args, stealth_level="enhanced")
    if not result:
        return EXIT_EXPECTED_ERROR

    # Apply scoring and sorting for video results
    sort_by = getattr(args, "sort_by", "relevance")
    if result.success and result.data and args.search_type == "video":
        if sort_by == "engagement":
            result.data = rank_results(result.data, score_video_engagement)
        elif sort_by == "views":
            result.data = rank_results(
                result.data,
                lambda v: v.view_cnt if hasattr(v, "view_cnt") else 0,
            )
        elif sort_by == "likes":
            result.data = rank_results(
                result.data,
                lambda v: v.like_cnt if hasattr(v, "like_cnt") else 0,
            )
        # Pre-compute scores once for display and JSON (avoids double-call in formatters)
        result.scores = {
            i: score_video_engagement(item)
            for i, item in enumerate(result.data)
            if isinstance(item, SearchVideoResult)
        }

    if cache and result.success:
        cache.set("search", filters, result.to_dict())

    return _output_result(result, args, _format_search)


def cmd_competitor(args) -> int:
    """Handle the 'competitor' command."""
    filters = {
        "username": args.username.lstrip("@"),  # strip @ if user includes it
        "include_videos": args.videos,
    }
    limit = args.limit

    if args.dry_run:
        return _dry_run_output("competitor", filters, limit, args)

    cache = _get_cache(args)
    if cache:
        cached = cache.get("competitor", filters)
        if cached:
            return _output_cached(cached, args, "competitor", filters)

    result = _run_scraper(CompetitorScraper, filters, limit, args, stealth_level="enhanced")
    if not result:
        return EXIT_EXPECTED_ERROR

    # Compute engagement metrics from recent videos
    if result.success and result.data:
        from dataclasses import asdict
        profile = result.data[0]
        if isinstance(profile, CompetitorProfile):
            eng = score_competitor_engagement(profile)
            # Rebuild frozen dataclass with engagement fields filled
            d = asdict(profile)
            d["avg_views"] = eng["avg_views"] or d.get("avg_views", "")
            d["avg_likes"] = eng["avg_likes"] or d.get("avg_likes", "")
            d["avg_comments"] = eng["avg_comments"] or d.get("avg_comments", "")
            d["engagement_rate"] = eng["engagement_rate"] or d.get("engagement_rate", "")
            result.data[0] = CompetitorProfile(**d)

    if cache and result.success:
        cache.set("competitor", filters, result.to_dict())

    return _output_result(result, args, _format_competitor)


def cmd_shop_products(args) -> int:
    """Handle the 'shop-products' command."""
    if not args.query and not args.shop_id:
        print(f"{RED}Error: --query or --shop-id is required{RESET}")
        return EXIT_EXPECTED_ERROR

    filters = {
        "query": args.query,
        "shop_id": args.shop_id,
    }
    limit = args.limit

    if args.dry_run:
        return _dry_run_output("shop-products", filters, limit, args)

    cache = _get_cache(args)
    if cache:
        cached = cache.get("shop-products", filters)
        if cached:
            return _output_cached(cached, args, "shop-products", filters)

    result = _run_scraper(ShopScraper, filters, limit, args, stealth_level="enhanced")
    if not result:
        return EXIT_EXPECTED_ERROR

    # Apply scoring and sorting
    sort_by = getattr(args, "sort_by", "relevance")
    if result.success and result.data:
        if sort_by == "score":
            result.data = rank_results(result.data, score_shop_product)
        elif sort_by == "rating":
            result.data = rank_results(
                result.data,
                lambda p: safe_parse_float(p.rating) if hasattr(p, "rating") else 0.0,
            )
        elif sort_by == "price":
            result.data = rank_results(
                result.data,
                lambda p: p.price_raw if hasattr(p, "price_raw") else 0.0,
                reverse=False,  # Ascending — cheapest first
            )
        # Pre-compute scores once for display and JSON (avoids double-call in formatters)
        result.scores = {
            i: score_shop_product(item)
            for i, item in enumerate(result.data)
            if isinstance(item, ShopProduct)
        }

    if cache and result.success:
        cache.set("shop-products", filters, result.to_dict())

    return _output_result(result, args, _format_shop_products)


# ---------------------------------------------------------------------------
# Command dispatch
# ---------------------------------------------------------------------------

COMMANDS = {
    "trends": cmd_trends,
    "top-ads": cmd_top_ads,
    "hashtags": cmd_hashtags,
    "search": cmd_search,
    "competitor": cmd_competitor,
    "shop-products": cmd_shop_products,
    "cache-clear": cmd_cache_clear,
    "cache-stats": cmd_cache_stats,
}


# ---------------------------------------------------------------------------
# Scraper runner
# ---------------------------------------------------------------------------

def _run_scraper(scraper_cls, filters: dict, limit: int, args, stealth_level: str = "standard") -> ScrapeResult | None:
    """Launch browser, instantiate scraper, run, and return result."""
    headless = not getattr(args, "no_headless", False)

    try:
        with BrowserManager(headless=headless, stealth_level=stealth_level) as bm:
            scraper = scraper_cls(browser_manager=bm, verbose=args.verbose)
            return scraper.scrape(filters, limit=limit)
    except BrowserLaunchError as e:
        if args.json:
            json_output(e.to_dict())
        else:
            print_error(str(e), "Ensure Playwright is installed: npx playwright install chromium")
        return None
    except AntiDetectionError as e:
        if args.json:
            json_output(e.to_dict())
        else:
            print_error(str(e), "Try again later or use --no-headless for debugging")
        return None
    except RateLimitError as e:
        if args.json:
            json_output(e.to_dict())
        else:
            print_error(str(e))
            if e.retry_after:
                print(f"{YELLOW}Retry after {e.retry_after}s{RESET}")
        return None
    except SelectorTimeoutError as e:
        if args.json:
            json_output(e.to_dict())
        else:
            print_error(
                str(e),
                "Page structure may have changed. Try --no-headless to inspect.",
            )
        return None
    except ScraperError as e:
        if args.json:
            json_output(e.to_dict())
        else:
            print_error(str(e))
        return None


# ---------------------------------------------------------------------------
# Output helpers
# ---------------------------------------------------------------------------

def _get_cache(args) -> FileCache | None:
    """Return a FileCache instance or None if caching is disabled."""
    if getattr(args, "no_cache", False):
        return None
    return FileCache(ttl=args.cache_ttl)


def _enrich_json_data(result: ScrapeResult) -> list:
    """Add computed scores to result data for JSON output.

    Uses pre-computed scores/velocities from result when available,
    falling back to computing on the fly for cached dict data.
    Returns a list of enriched dicts.
    """
    pre_scores = result.scores
    pre_velocities = result.velocities
    enriched = []
    for i, item in enumerate(result.data):
        if isinstance(item, dict):
            d = dict(item)
        elif hasattr(item, "to_dict"):
            d = item.to_dict()
        else:
            d = {"value": str(item)}

        # Video engagement score (SearchVideoResult)
        if isinstance(item, SearchVideoResult):
            d["engagement_score"] = pre_scores.get(i, score_video_engagement(item))

        # Shop product score
        elif isinstance(item, ShopProduct):
            d["product_score"] = pre_scores.get(i, score_shop_product(item))

        # Trend velocity (all trend types)
        elif isinstance(item, (TrendingHashtag, TrendingSong, TrendingCreator, TrendingVideo)):
            d["velocity"] = pre_velocities.get(i, classify_trend_velocity(item))

        enriched.append(d)
    return enriched


def _output_result(result: ScrapeResult, args, table_formatter) -> int:
    """Output a ScrapeResult in JSON or table format."""
    if not result.success:
        if args.json:
            json_output({"error": result.error, "type": "scraper_error"})
        else:
            print_error(result.error or "Scrape failed")
        return EXIT_EXPECTED_ERROR

    # Save to file if --output-dir
    if args.output_dir:
        _save_to_file(result, args.output_dir)

    if args.json:
        output = result.to_dict()
        # Enrich JSON output with computed scores
        output["data"] = _enrich_json_data(result)
        json_output(output)
    else:
        print_header(result.command, result.filters)
        print(table_formatter(result))
        print_footer(result.count, result.cached)

    return EXIT_SUCCESS


def _output_cached(cached_data: dict, args, command: str, filters: dict) -> int:
    """Output cached data."""
    if args.json:
        cached_data["cached"] = True
        json_output(cached_data)
    else:
        # Reconstruct a minimal ScrapeResult for display
        result = ScrapeResult(
            command=command,
            success=True,
            data=cached_data.get("data", []),
            count=cached_data.get("count", 0),
            filters=filters,
            cached=True,
        )
        formatter = {
            "trends": _format_trends,
            "top-ads": _format_top_ads,
            "hashtags": _format_hashtag_analytics,
            "search": _format_search,
            "competitor": _format_competitor,
            "shop-products": _format_shop_products,
        }.get(command, _format_trends)

        print_header(command, filters)
        print(formatter(result))
        print_footer(result.count, cached=True)

    if args.output_dir:
        _save_to_file_raw(cached_data, command, args.output_dir)

    return EXIT_SUCCESS


def _dry_run_output(command: str, filters: dict, limit: int, args) -> int:
    """Show what would happen without launching the browser."""
    info = {
        "command": command,
        "filters": filters,
        "limit": limit,
        "dry_run": True,
        "would_launch_browser": True,
        "cache_enabled": not getattr(args, "no_cache", False),
        "cache_ttl": args.cache_ttl,
    }
    if args.json:
        json_output(info)
    else:
        print_header(f"{command} (dry-run)", filters)
        rows = [[k, str(v)] for k, v in info.items()]
        print(format_table(["Parameter", "Value"], rows))
        print(f"\n{DIM}No browser launched. Remove --dry-run to scrape.{RESET}\n")
    return EXIT_SUCCESS


def _save_to_file(result: ScrapeResult, output_dir: str) -> None:
    """Save result as timestamped JSON file."""
    _save_to_file_raw(result.to_dict(), result.command, output_dir)


def _save_to_file_raw(data: dict, command: str, output_dir: str) -> None:
    """Save raw dict as timestamped JSON file."""
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = out_path / f"tiktok-intel_{command}_{ts}.json"
    filename.write_text(json.dumps(data, indent=2, default=str))
    logger.info("Saved results to %s", filename)


# ---------------------------------------------------------------------------
# Table formatters
# ---------------------------------------------------------------------------

def _format_trends(result: ScrapeResult) -> str:
    """Format trending data as a terminal table."""
    data = result.data
    if not data:
        return "  (no results)"

    # Determine trend type from filters or first item
    filters = result.filters or {}
    trend_type = filters.get("type", "hashtags")
    pre_velocities = result.velocities  # Pre-computed in cmd_trends

    if trend_type == "hashtags":
        headers = ["#", "Hashtag", "Posts", "Views", "Change", "Velocity"]
        rows = []
        for i, item in enumerate(data):
            if isinstance(item, dict):
                rows.append([
                    str(item.get("rank", "")),
                    item.get("name", ""),
                    item.get("posts", ""),
                    item.get("views", ""),
                    item.get("trend_change", ""),
                    item.get("velocity", ""),
                ])
            else:
                velocity = pre_velocities.get(i, classify_trend_velocity(item))
                rows.append([
                    str(item.rank),
                    _truncate(item.name, 40),
                    item.posts,
                    item.views,
                    _color_change(item.trend_change),
                    _color_velocity(velocity),
                ])
        return format_table(headers, rows)

    elif trend_type == "songs":
        headers = ["#", "Title", "Artist", "Duration", "Posts", "Change", "Velocity"]
        rows = []
        for i, item in enumerate(data):
            if isinstance(item, dict):
                rows.append([
                    str(item.get("rank", "")),
                    item.get("title", ""),
                    item.get("artist", ""),
                    item.get("duration", ""),
                    item.get("posts", ""),
                    item.get("trend_change", ""),
                    item.get("velocity", ""),
                ])
            else:
                velocity = pre_velocities.get(i, classify_trend_velocity(item))
                rows.append([
                    str(item.rank),
                    _truncate(item.title, 35),
                    _truncate(item.artist, 20),
                    item.duration,
                    item.posts,
                    _color_change(item.trend_change),
                    _color_velocity(velocity),
                ])
        return format_table(headers, rows)

    elif trend_type == "creators":
        headers = ["#", "Username", "Followers", "Likes", "Change", "Velocity"]
        rows = []
        for i, item in enumerate(data):
            if isinstance(item, dict):
                rows.append([
                    str(item.get("rank", "")),
                    item.get("username", ""),
                    item.get("followers", ""),
                    item.get("likes", ""),
                    item.get("trend_change", ""),
                    item.get("velocity", ""),
                ])
            else:
                velocity = pre_velocities.get(i, classify_trend_velocity(item))
                rows.append([
                    str(item.rank),
                    _truncate(item.username, 30),
                    item.followers,
                    item.likes,
                    _color_change(item.trend_change),
                    _color_velocity(velocity),
                ])
        return format_table(headers, rows)

    elif trend_type == "videos":
        headers = ["#", "Description", "Creator", "Views", "Likes", "Velocity"]
        rows = []
        for i, item in enumerate(data):
            if isinstance(item, dict):
                rows.append([
                    str(item.get("rank", "")),
                    item.get("description", "")[:50],
                    item.get("creator", ""),
                    item.get("views", ""),
                    item.get("likes", ""),
                    item.get("velocity", ""),
                ])
            else:
                velocity = pre_velocities.get(i, classify_trend_velocity(item))
                rows.append([
                    str(item.rank),
                    _truncate(item.description, 50),
                    _truncate(item.creator, 20),
                    item.views,
                    item.likes,
                    _color_velocity(velocity),
                ])
        return format_table(headers, rows)

    return "  (unsupported trend type)"


def _format_top_ads(result: ScrapeResult) -> str:
    """Format top ads as a terminal table."""
    data = result.data
    if not data:
        return "  (no results)"

    headers = ["#", "Brand", "Description", "Likes", "CTR", "Reach"]
    rows = []
    for item in data:
        if isinstance(item, dict):
            rows.append([
                str(item.get("rank", "")),
                item.get("brand", "")[:20],
                item.get("description", "")[:40],
                item.get("likes", ""),
                item.get("ctr", ""),
                item.get("reach", ""),
            ])
        else:
            rows.append([
                str(item.rank),
                _truncate(item.brand, 20),
                _truncate(item.description, 40),
                item.likes,
                item.ctr,
                item.reach,
            ])
    return format_table(headers, rows)


def _format_hashtag_analytics(result: ScrapeResult) -> str:
    """Format hashtag analytics as a terminal display."""
    data = result.data
    if not data:
        return "  (no results)"

    item = data[0]
    if isinstance(item, dict):
        name = item.get("name", "")
        views = item.get("total_views", "N/A")
        posts = item.get("total_posts", "N/A")
        related = item.get("related_hashtags", [])
        top_videos = item.get("top_videos", [])
    else:
        name = item.name
        views = item.total_views or "N/A"
        posts = item.total_posts or "N/A"
        related = item.related_hashtags
        top_videos = item.top_videos

    lines = [
        f"  {BOLD}#{name}{RESET}",
        f"  {CYAN}Total Views:{RESET} {views}",
        f"  {CYAN}Total Posts:{RESET} {posts}",
    ]

    if related:
        lines.append(f"\n  {BOLD}Related Hashtags:{RESET}")
        for tag in related[:10]:
            lines.append(f"    {DIM}-{RESET} {tag}")

    if top_videos:
        lines.append(f"\n  {BOLD}Top Videos:{RESET}")
        headers = ["Description", "Views", "URL"]
        rows = []
        for vid in top_videos[:5]:
            if isinstance(vid, dict):
                rows.append([
                    _truncate(vid.get("description", ""), 40),
                    vid.get("views", ""),
                    _truncate(vid.get("url", ""), 50),
                ])
        if rows:
            lines.append(format_table(headers, rows))

    return "\n".join(lines)


def _format_search(result: ScrapeResult) -> str:
    """Format search results as a terminal table."""
    data = result.data
    if not data:
        return "  (no results)"

    filters = result.filters or {}
    search_type = filters.get("search_type", "video")
    pre_scores = result.scores  # Pre-computed in cmd_search

    if search_type == "video":
        headers = ["#", "Description", "Creator", "Views", "Likes", "Score", "URL"]
        rows = []
        for i, item in enumerate(data):
            if isinstance(item, dict):
                score_val = item.get("engagement_score", "")
                rows.append([
                    str(i + 1),
                    _truncate(item.get("title", ""), 40),
                    item.get("creator", ""),
                    item.get("views", ""),
                    item.get("likes", ""),
                    str(score_val) if score_val != "" else "",
                    _truncate(item.get("video_url", ""), 45),
                ])
            else:
                score_val = pre_scores.get(i, score_video_engagement(item))
                rows.append([
                    str(i + 1),
                    _truncate(item.title, 40),
                    _truncate(item.creator, 20),
                    item.views,
                    item.likes,
                    str(score_val),
                    _truncate(item.video_url, 45),
                ])
        return format_table(headers, rows)

    elif search_type == "user":
        headers = ["#", "Username", "Nickname", "Followers", "Likes", "Verified"]
        rows = []
        for i, item in enumerate(data):
            if isinstance(item, dict):
                rows.append([
                    str(i + 1),
                    item.get("username", ""),
                    item.get("nickname", ""),
                    item.get("followers", ""),
                    item.get("likes", ""),
                    "Yes" if item.get("verified") else "",
                ])
            else:
                rows.append([
                    str(i + 1),
                    _truncate(item.username, 25),
                    _truncate(item.nickname, 25),
                    item.followers,
                    item.likes,
                    f"{GREEN}Yes{RESET}" if item.verified else "",
                ])
        return format_table(headers, rows)

    return "  (unsupported search type)"


def _format_competitor(result: ScrapeResult) -> str:
    """Format competitor profile as a terminal display."""
    data = result.data
    if not data:
        return "  (no results)"

    item = data[0]
    if isinstance(item, dict):
        username = item.get("username", "")
        nickname = item.get("nickname", "")
        bio = item.get("bio", "")
        followers = item.get("followers", "N/A")
        following = item.get("following", "N/A")
        likes = item.get("likes", "N/A")
        videos_count = item.get("videos_count", 0)
        verified = item.get("verified", False)
        avg_views = item.get("avg_views", "")
        avg_likes = item.get("avg_likes", "")
        engagement_rate = item.get("engagement_rate", "")
        recent_videos = item.get("recent_videos", [])
    else:
        username = item.username
        nickname = item.nickname
        bio = item.bio
        followers = item.followers or "N/A"
        following = item.following or "N/A"
        likes = item.likes or "N/A"
        videos_count = item.videos_count
        verified = item.verified
        avg_views = item.avg_views
        avg_likes = item.avg_likes
        engagement_rate = item.engagement_rate
        recent_videos = item.recent_videos

    verified_badge = f" {GREEN}Verified{RESET}" if verified else ""
    lines = [
        f"  {BOLD}@{username}{RESET}{verified_badge}",
        f"  {DIM}{nickname}{RESET}",
    ]
    if bio:
        lines.append(f"  {DIM}{_truncate(bio, 80)}{RESET}")
    lines.append("")
    lines.append(f"  {CYAN}Followers:{RESET} {followers}   {CYAN}Following:{RESET} {following}   {CYAN}Likes:{RESET} {likes}")
    lines.append(f"  {CYAN}Videos:{RESET} {videos_count}")

    if avg_views or avg_likes or engagement_rate:
        lines.append(f"\n  {BOLD}Engagement Metrics:{RESET}")
        if avg_views:
            lines.append(f"    {CYAN}Avg Views:{RESET} {avg_views}")
        if avg_likes:
            lines.append(f"    {CYAN}Avg Likes:{RESET} {avg_likes}")
        if engagement_rate:
            lines.append(f"    {CYAN}Engagement Rate:{RESET} {engagement_rate}")

    if recent_videos:
        lines.append(f"\n  {BOLD}Recent Videos:{RESET}")
        headers = ["Description", "Views", "Likes", "Comments"]
        rows = []
        for vid in recent_videos[:10]:
            rows.append([
                _truncate(vid.get("description", ""), 40),
                vid.get("views", ""),
                vid.get("likes", ""),
                vid.get("comments", ""),
            ])
        if rows:
            lines.append(format_table(headers, rows))

    return "\n".join(lines)


def _format_shop_products(result: ScrapeResult) -> str:
    """Format shop products as a terminal table."""
    data = result.data
    if not data:
        return "  (no results)"

    pre_scores = result.scores  # Pre-computed in cmd_shop_products
    headers = ["#", "Product", "Price", "Rating", "Sold", "Score", "Seller"]
    rows = []
    for i, item in enumerate(data):
        if isinstance(item, dict):
            score_val = item.get("product_score", "")
            rows.append([
                str(i + 1),
                _truncate(item.get("title", ""), 40),
                item.get("price", ""),
                item.get("rating", ""),
                item.get("sold", ""),
                str(score_val) if score_val != "" else "",
                _truncate(item.get("seller", ""), 20),
            ])
        else:
            score_val = pre_scores.get(i, score_shop_product(item))
            rows.append([
                str(i + 1),
                _truncate(item.title, 40),
                item.price,
                item.rating,
                item.sold,
                str(score_val),
                _truncate(item.seller, 20),
            ])
    return format_table(headers, rows)


def _color_change(change: str) -> str:
    """Colorize trend change indicator."""
    if not change:
        return ""
    change = change.strip()
    if change.startswith("+") or change.lower() == "new":
        return f"{GREEN}{change}{RESET}"
    elif change.startswith("-"):
        return f"{RED}{change}{RESET}"
    return change


def _color_velocity(velocity: str) -> str:
    """Colorize trend velocity classification with ANSI codes.

    BREAKOUT = magenta+bold, RISING = green, NEW = cyan,
    STABLE = dim, DECLINING = red.
    """
    if velocity == "BREAKOUT":
        return f"{MAGENTA}{BOLD}{velocity}{RESET}"
    elif velocity == "RISING":
        return f"{GREEN}{velocity}{RESET}"
    elif velocity == "NEW":
        return f"{CYAN}{velocity}{RESET}"
    elif velocity == "DECLINING":
        return f"{RED}{velocity}{RESET}"
    else:  # STABLE
        return f"{DIM}{velocity}{RESET}"


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def main() -> int:
    """CLI entry point."""
    parser = build_parser()
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return EXIT_EXPECTED_ERROR

    # Configure logging
    log_level = logging.DEBUG if args.verbose else logging.WARNING
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    handler = COMMANDS.get(args.command)
    if not handler:
        parser.print_help()
        return EXIT_EXPECTED_ERROR

    try:
        return handler(args)

    except TikTokIntelError as e:
        if args.json:
            json_output(e.to_dict())
        else:
            print_error(str(e))
        return EXIT_EXPECTED_ERROR

    except KeyboardInterrupt:
        print(f"\n{YELLOW}Interrupted{RESET}")
        return 130

    except Exception as e:
        logger.debug("Unhandled exception", exc_info=True)
        if getattr(args, "json", False):
            json_output({"error": str(e), "type": "unexpected_error"})
        else:
            print(f"\n{RED}Error: {e}{RESET}")
            if getattr(args, "verbose", False):
                import traceback
                traceback.print_exc()
        return EXIT_UNEXPECTED_ERROR


if __name__ == "__main__":
    sys.exit(main())
