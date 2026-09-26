#!/usr/bin/env python3
"""
Instagram Intelligence CLI — competitive research via Graph API + Playwright.

Two-layer architecture:
  Layer 1: Official Meta Graph API (zero risk, System User token, never expires)
  Layer 2: Playwright scraping (Phase 2 — for data the API doesn't expose)

Credentials:
    Per-brand resolution chain:
      1. capsules/ecommerce/brands/{brand}/.env
      2. capsules/ecommerce/.env
      3. Environment variables
      4. macOS Keychain

Dependencies: Python stdlib only (Phase 1). Playwright for Phase 2.

Exit codes:
    0 — success
    1 — expected error (auth, rate limit, user error)
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
# The directory name "instagram-intel" has a hyphen (not importable directly),
# so we use importlib shim when running as a script, and relative imports
# when running as a package.
# ---------------------------------------------------------------------------
_SCRIPT_DIR = Path(__file__).resolve().parent


def _setup_imports():
    """Make sibling modules importable regardless of invocation method."""
    import importlib.util

    def _load(name: str, is_pkg: bool = False):
        """Import a sibling module by filename."""
        if is_pkg:
            init_file = _SCRIPT_DIR / name / "__init__.py"
            spec = importlib.util.spec_from_file_location(
                f"instagram_intel.{name}", init_file,
                submodule_search_locations=[str(_SCRIPT_DIR / name)],
            )
        else:
            spec = importlib.util.spec_from_file_location(
                f"instagram_intel.{name}", _SCRIPT_DIR / f"{name}.py",
            )
        mod = importlib.util.module_from_spec(spec)
        sys.modules[f"instagram_intel.{name}"] = mod
        spec.loader.exec_module(mod)
        return mod

    # Bootstrap: register the package itself
    if "instagram_intel" not in sys.modules:
        pkg_spec = importlib.util.spec_from_file_location(
            "instagram_intel",
            _SCRIPT_DIR / "__init__.py",
            submodule_search_locations=[str(_SCRIPT_DIR)],
        )
        pkg = importlib.util.module_from_spec(pkg_spec)
        sys.modules["instagram_intel"] = pkg
        pkg_spec.loader.exec_module(pkg)

    # Load core modules
    for mod_name in ["config", "exceptions", "models", "formatters", "cache",
                     "scoring", "benchmarks", "analytics", "dedup"]:
        if f"instagram_intel.{mod_name}" not in sys.modules:
            _load(mod_name)

    # clients sub-package
    clients_dir = _SCRIPT_DIR / "clients"
    if "instagram_intel.clients" not in sys.modules:
        cl_spec = importlib.util.spec_from_file_location(
            "instagram_intel.clients",
            clients_dir / "__init__.py",
            submodule_search_locations=[str(clients_dir)],
        )
        cl = importlib.util.module_from_spec(cl_spec)
        sys.modules["instagram_intel.clients"] = cl

    for client_mod in ["graph_api", "scraper"]:
        full = f"instagram_intel.clients.{client_mod}"
        if full not in sys.modules:
            s_spec = importlib.util.spec_from_file_location(
                full, clients_dir / f"{client_mod}.py",
            )
            s = importlib.util.module_from_spec(s_spec)
            sys.modules[full] = s
            s_spec.loader.exec_module(s)

    # Now exec clients __init__
    cl = sys.modules["instagram_intel.clients"]
    if not hasattr(cl, "InstagramGraphClient"):
        cl_spec = importlib.util.spec_from_file_location(
            "instagram_intel.clients",
            clients_dir / "__init__.py",
            submodule_search_locations=[str(clients_dir)],
        )
        cl_spec.loader.exec_module(cl)

    # commands sub-package
    cmds_dir = _SCRIPT_DIR / "commands"
    if "instagram_intel.commands" not in sys.modules:
        cmd_spec = importlib.util.spec_from_file_location(
            "instagram_intel.commands",
            cmds_dir / "__init__.py",
            submodule_search_locations=[str(cmds_dir)],
        )
        cmd = importlib.util.module_from_spec(cmd_spec)
        sys.modules["instagram_intel.commands"] = cmd
        cmd_spec.loader.exec_module(cmd)

    for cmd_mod in ["account", "competitor", "hashtag", "insights",
                     "engagement", "search", "trending", "profile",
                     "cache_cmds", "compare"]:
        full = f"instagram_intel.commands.{cmd_mod}"
        if full not in sys.modules:
            s_spec = importlib.util.spec_from_file_location(
                full, cmds_dir / f"{cmd_mod}.py",
            )
            s = importlib.util.module_from_spec(s_spec)
            sys.modules[full] = s
            s_spec.loader.exec_module(s)


# Only run the shim when invoked as a script (not via -m)
if __package__ is None or __package__ == "":
    _setup_imports()

from instagram_intel import __version__
from instagram_intel.config import (
    BOLD, CYAN, DEFAULT_CACHE_TTL, DIM, EXIT_EXPECTED_ERROR,
    EXIT_SUCCESS, EXIT_UNEXPECTED_ERROR, ENV_IG_USER_ID,
    ENV_META_APP_ID, ENV_META_APP_SECRET, ENV_META_TOKEN, GREEN,
    KEYCHAIN_META_APP_ID, KEYCHAIN_META_APP_SECRET,
    KEYCHAIN_META_TOKEN, MAGENTA, RED, RESET, VERSION, YELLOW,
)
from instagram_intel.exceptions import (
    APIError, AuthError, CacheError, CredentialError,
    InstagramIntelError, RateLimitError, TokenExpiredError,
)
from instagram_intel.formatters import (
    format_table, json_output, print_error, print_footer, print_header,
)
from instagram_intel.clients.graph_api import (
    BrandCredentialLoader, InstagramGraphClient, resolve_brand,
)

# Command handlers
from instagram_intel.commands.account import cmd_account, cmd_auth_status, cmd_mentions
from instagram_intel.commands.competitor import cmd_competitor, cmd_competitor_media
from instagram_intel.commands.hashtag import cmd_hashtag_top, cmd_hashtag_recent
from instagram_intel.commands.insights import cmd_own_insights, cmd_media_insights
from instagram_intel.commands.engagement import cmd_engagement_rate
from instagram_intel.commands.cache_cmds import cmd_cache_clear, cmd_cache_stats
from instagram_intel.commands.search import (
    cmd_search_users, cmd_search_hashtags, cmd_search_content,
)
from instagram_intel.commands.trending import (
    cmd_trending_reels, cmd_trending_audio, cmd_explore,
)
from instagram_intel.commands.profile import (
    cmd_user_profile, cmd_user_reels, cmd_hashtag_deep,
)
from instagram_intel.commands.compare import cmd_competitor_compare

logger = logging.getLogger("instagram-intel")


# ---------------------------------------------------------------------------
# Argument parser
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    """Build the CLI argument parser with all subcommands."""
    shared = argparse.ArgumentParser(add_help=False)
    shared.add_argument("-v", "--verbose", action="store_true",
                        help="Enable verbose logging")
    shared.add_argument("--json", action="store_true",
                        help="Output results as JSON")
    shared.add_argument("--dry-run", action="store_true",
                        help="Show what would happen without executing")
    shared.add_argument("--cache-ttl", type=int, default=DEFAULT_CACHE_TTL,
                        help=f"Cache TTL in seconds (default: {DEFAULT_CACHE_TTL})")
    shared.add_argument("--no-cache", action="store_true",
                        help="Bypass cache")
    shared.add_argument("--output-dir",
                        help="Save results as timestamped JSON to this directory")
    shared.add_argument("--brand",
                        help="Brand context for credentials (default: from META_DEFAULT_BRAND)")
    shared.add_argument("--no-headless", action="store_true",
                        help="Show browser window (scraping commands only)")
    shared.add_argument("--sort", default="smart",
                        choices=["smart", "engagement", "velocity", "none"],
                        help="Sort order for results (default: smart — auto-picks best)")

    parser = argparse.ArgumentParser(
        prog="instagram-intel",
        parents=[shared],
        description=(
            f"Instagram Intelligence CLI v{VERSION}\n"
            "Competitive research via Graph API + Playwright scraping.\n"
            "Layer 1 (Graph API): Zero risk, System User token.\n"
            "Layer 2 (Scraping): For data the API doesn't expose (Phase 2)."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Phase 1 — Graph API commands:\n"
            "  %(prog)s account\n"
            "  %(prog)s auth-status\n"
            "  %(prog)s competitor <username>\n"
            "  %(prog)s competitor-media <username> --limit 10\n"
            "  %(prog)s hashtag-top <hashtag>\n"
            "  %(prog)s hashtag-recent <hashtag>\n"
            "  %(prog)s own-insights --period day\n"
            "  %(prog)s media-insights <media-id>\n"
            "  %(prog)s mentions --limit 10\n"
            "  %(prog)s engagement-rate <username> --limit 25 --json\n"
            "  %(prog)s competitor-compare --usernames nike,adidas,puma\n"
            "  %(prog)s best-times <username> --limit 50\n"
            "\n"
            "Phase 2 — Scraping commands (Playwright):\n"
            "  %(prog)s trending-reels --limit 10\n"
            "  %(prog)s trending-audio --limit 10\n"
            "  %(prog)s explore --topic food --limit 10\n"
            "  %(prog)s search-users nike --limit 5\n"
            "  %(prog)s search-hashtags travel --limit 10\n"
            "  %(prog)s search-content fashion --limit 10\n"
            "  %(prog)s user-profile natgeo\n"
            "  %(prog)s user-reels natgeo --limit 5\n"
            "  %(prog)s hashtag-deep travel --limit 20\n"
            "\n"
            "Cache management:\n"
            "  %(prog)s cache-clear\n"
            "  %(prog)s cache-stats\n"
            "\n"
            "Credential resolution:\n"
            "  1. capsules/ecommerce/brands/{brand}/.env\n"
            "  2. capsules/ecommerce/.env\n"
            "  3. Environment variables\n"
            "  4. macOS Keychain\n"
        ),
    )

    sub = parser.add_subparsers(dest="command", help="Available commands")

    # --- account ---
    sub.add_parser("account", parents=[shared],
                   help="Show connected IG Business Account info")

    # --- auth-status ---
    sub.add_parser("auth-status", parents=[shared],
                   help="Verify token validity, show scopes")

    # --- competitor ---
    p = sub.add_parser("competitor", parents=[shared],
                       help="Full competitor profile via Business Discovery")
    p.add_argument("username", help="Target Instagram username (without @)")

    # --- competitor-media ---
    p = sub.add_parser("competitor-media", parents=[shared],
                       help="Competitor's recent media with engagement")
    p.add_argument("username", help="Target Instagram username (without @)")
    p.add_argument("--limit", type=int, default=25,
                   help="Max media items (default: 25)")
    p.add_argument("--analyze-timing", action="store_true",
                   help="Show best posting times analysis (#6)")

    # --- hashtag-top ---
    p = sub.add_parser("hashtag-top", parents=[shared],
                       help="Top media for a hashtag (Graph API, 30/week limit)")
    p.add_argument("hashtag", help="Hashtag to search (without #)")
    p.add_argument("--limit", type=int, default=25,
                   help="Max results (default: 25, API max: 50)")

    # --- hashtag-recent ---
    p = sub.add_parser("hashtag-recent", parents=[shared],
                       help="Recent media for a hashtag (Graph API, 30/week limit)")
    p.add_argument("hashtag", help="Hashtag to search (without #)")
    p.add_argument("--limit", type=int, default=25,
                   help="Max results (default: 25, API max: 50)")

    # --- own-insights ---
    p = sub.add_parser("own-insights", parents=[shared],
                       help="Account impressions, reach, follower trends")
    p.add_argument("--period", default="day",
                   choices=["day", "week", "days_28", "month", "lifetime"],
                   help="Insight period (default: day)")
    p.add_argument("--since", default="",
                   help="Start date (Unix timestamp or ISO 8601)")
    p.add_argument("--until", default="",
                   help="End date (Unix timestamp or ISO 8601)")

    # --- media-insights ---
    p = sub.add_parser("media-insights", parents=[shared],
                       help="Per-post performance metrics")
    p.add_argument("media_id", help="Media ID to get insights for")

    # --- mentions ---
    p = sub.add_parser("mentions", parents=[shared],
                       help="Media where account is @mentioned")
    p.add_argument("--limit", type=int, default=25,
                   help="Max results (default: 25)")

    # --- engagement-rate ---
    p = sub.add_parser("engagement-rate", parents=[shared],
                       help="Computed engagement rate from Business Discovery data")
    p.add_argument("username", help="Target Instagram username (without @)")
    p.add_argument("--limit", type=int, default=25,
                   help="Recent posts to analyze (default: 25)")

    # --- Phase 2 — Scraping commands (Playwright) ---
    p = sub.add_parser("trending-reels", parents=[shared],
                       help="Currently trending Reels (Playwright)")
    p.add_argument("--limit", type=int, default=20,
                   help="Max results (default: 20)")

    p = sub.add_parser("trending-audio", parents=[shared],
                       help="Trending audio/music on Reels (Playwright)")
    p.add_argument("--limit", type=int, default=20,
                   help="Max results (default: 20)")

    p = sub.add_parser("explore", parents=[shared],
                       help="Explore page content for a topic (Playwright)")
    p.add_argument("--topic", default="",
                   help="Topic to explore")
    p.add_argument("--limit", type=int, default=20,
                   help="Max results (default: 20)")

    p = sub.add_parser("search-users", parents=[shared],
                       help="Search Instagram users (Playwright)")
    p.add_argument("query", help="Search query")
    p.add_argument("--limit", type=int, default=20,
                   help="Max results (default: 20)")
    p.add_argument("--prefer-verified", action="store_true",
                   help="Boost verified accounts in results (#12)")
    p.add_argument("--min-followers", type=int, default=0,
                   help="Filter: minimum follower count")
    p.add_argument("--max-followers", type=int, default=0,
                   help="Filter: maximum follower count (0 = no limit)")

    p = sub.add_parser("search-hashtags", parents=[shared],
                       help="Search hashtags (unlimited, no 30/week cap)")
    p.add_argument("query", help="Search query")
    p.add_argument("--limit", type=int, default=20,
                   help="Max results (default: 20)")

    p = sub.add_parser("search-content", parents=[shared],
                       help="Search posts/reels by keyword (Playwright)")
    p.add_argument("query", help="Search query")
    p.add_argument("--limit", type=int, default=20,
                   help="Max results (default: 20)")

    p = sub.add_parser("user-profile", parents=[shared],
                       help="Public user profile (any account, Playwright)")
    p.add_argument("username", help="Instagram username (without @)")

    p = sub.add_parser("user-reels", parents=[shared],
                       help="User's reels from profile (Playwright)")
    p.add_argument("username", help="Instagram username (without @)")
    p.add_argument("--limit", type=int, default=20,
                   help="Max results (default: 20)")

    p = sub.add_parser("hashtag-deep", parents=[shared],
                       help="Deep hashtag analysis (no 30/week limit, Playwright)")
    p.add_argument("hashtag", help="Hashtag to analyze (without #)")
    p.add_argument("--limit", type=int, default=50,
                   help="Max results (default: 50)")

    # --- competitor-compare ---
    p = sub.add_parser("competitor-compare", parents=[shared],
                       help="Compare engagement across multiple competitors")
    p.add_argument("--usernames", required=True,
                   help="Comma-separated usernames (e.g., nike,adidas,puma)")
    p.add_argument("--limit", type=int, default=25,
                   help="Posts to analyze per account (default: 25)")

    # --- best-times ---
    p = sub.add_parser("best-times", parents=[shared],
                       help="Analyze best posting times from competitor media")
    p.add_argument("username", help="Target Instagram username (without @)")
    p.add_argument("--limit", type=int, default=50,
                   help="Recent posts to analyze (default: 50)")

    # --- search-users with re-ranking flags (#12) ---
    # (already added above, re-ranking flags added inline)

    # --- Cache management ---
    sub.add_parser("cache-clear", parents=[shared],
                   help="Clear all cached results")
    sub.add_parser("cache-stats", parents=[shared],
                   help="Show cache statistics")

    return parser


# ---------------------------------------------------------------------------
# Client initialization
# ---------------------------------------------------------------------------

def _init_client(args) -> InstagramGraphClient | None:
    """Initialize the Graph API client from credentials.

    Credential resolution:
      1. Brand .env files (example-digital-capsule, ecommerce, brand-specific)
      2. Environment variables
      3. macOS Keychain
      4. Auto-discovery for IG user ID (via /me/accounts)

    Returns None if credential resolution fails (error already printed).
    """
    try:
        brand = resolve_brand(getattr(args, "brand", None))
    except CredentialError as e:
        if args.json:
            json_output(e.to_dict())
        else:
            print_error(str(e))
        return None

    loader = BrandCredentialLoader(brand)

    try:
        access_token = loader.require(
            ENV_META_TOKEN, KEYCHAIN_META_TOKEN,
            label="Meta access token",
        )
    except CredentialError as e:
        if args.json:
            json_output(e.to_dict())
        else:
            print_error(str(e))
        return None

    # Optional: app credentials for token debugging
    app_id = loader.get(ENV_META_APP_ID, KEYCHAIN_META_APP_ID) or ""
    app_secret = loader.get(ENV_META_APP_SECRET, KEYCHAIN_META_APP_SECRET) or ""

    # IG user ID: try .env / env vars / Keychain first
    ig_user_id = loader.get(ENV_IG_USER_ID) or ""

    # Auto-discover IG user ID if not set
    if not ig_user_id:
        logger.info("META_IG_USER_ID not set, attempting auto-discovery...")
        try:
            temp_client = InstagramGraphClient(
                access_token=access_token,
                ig_user_id="placeholder",  # will use /me/accounts, not IG-specific
                app_id=app_id,
                app_secret=app_secret,
            )
            ig_user_id = temp_client.discover_ig_user_id()
        except Exception as e:
            logger.debug("Auto-discovery failed: %s", e)

    if not ig_user_id:
        msg = (
            "Could not find Instagram Business Account ID.\n"
            f"  Set META_IG_USER_ID in your brand .env, or ensure your\n"
            f"  Facebook Page has a connected Instagram Business Account.\n"
            f"  Brand: {brand}"
        )
        if args.json:
            json_output({"error": msg, "type": "credential_error"})
        else:
            print_error(msg)
        return None

    return InstagramGraphClient(
        access_token=access_token,
        ig_user_id=ig_user_id,
        app_id=app_id,
        app_secret=app_secret,
        dry_run=getattr(args, "dry_run", False),
    )


# ---------------------------------------------------------------------------
# best-times command handler (thin wrapper — delegates to analytics module)
# ---------------------------------------------------------------------------

def _cmd_best_times(args, client) -> int:
    """Analyze best posting times from competitor media."""
    from instagram_intel.analytics import compute_posting_heatmap, format_best_times
    from instagram_intel.config import BOLD, CYAN, DIM

    username = args.username.lstrip("@")
    limit = getattr(args, "limit", 50)

    try:
        media = client.get_competitor_media(username, limit=limit)
    except Exception as e:
        if args.json:
            json_output({"error": str(e), "type": "api_error"})
        else:
            print_error(str(e))
        return EXIT_EXPECTED_ERROR

    data = [m.to_dict() for m in media]
    analysis = compute_posting_heatmap(data)

    if args.json:
        json_output({
            "success": True,
            "username": username,
            "posts_analyzed": analysis["total_posts"],
            "best_times": analysis["best_times"],
            "coverage": analysis["coverage"],
            "cached": False,
        })
    else:
        print_header("best-times", {"username": username, "posts_analyzed": analysis["total_posts"]})
        print(f"\n  {BOLD}Best Posting Times for @{username}{RESET}")
        print(f"  {DIM}Based on {analysis['total_posts']} posts{RESET}\n")
        print(format_best_times(analysis))
        print_footer(len(analysis["best_times"]))

    return EXIT_SUCCESS


# ---------------------------------------------------------------------------
# Command dispatch
# ---------------------------------------------------------------------------

# Commands that need a Graph API client
_GRAPH_COMMANDS = {
    "account": cmd_account,
    "auth-status": cmd_auth_status,
    "competitor": cmd_competitor,
    "competitor-media": cmd_competitor_media,
    "hashtag-top": cmd_hashtag_top,
    "hashtag-recent": cmd_hashtag_recent,
    "own-insights": cmd_own_insights,
    "media-insights": cmd_media_insights,
    "mentions": cmd_mentions,
    "engagement-rate": cmd_engagement_rate,
    "competitor-compare": cmd_competitor_compare,
    "best-times": _cmd_best_times,  # defined below
}

# Commands that don't need a client
_LOCAL_COMMANDS = {
    "cache-clear": cmd_cache_clear,
    "cache-stats": cmd_cache_stats,
}

# Phase 2 scraping commands (Playwright)
_PHASE2_COMMANDS = {
    "trending-reels": cmd_trending_reels,
    "trending-audio": cmd_trending_audio,
    "explore": cmd_explore,
    "search-users": cmd_search_users,
    "search-hashtags": cmd_search_hashtags,
    "search-content": cmd_search_content,
    "user-profile": cmd_user_profile,
    "user-reels": cmd_user_reels,
    "hashtag-deep": cmd_hashtag_deep,
}


# ---------------------------------------------------------------------------
# Output helpers
# ---------------------------------------------------------------------------

def _dry_run_output(command: str, args) -> int:
    """Show what would happen without executing."""
    info = {
        "command": command,
        "dry_run": True,
        "brand": getattr(args, "brand", None) or "(auto-detect)",
        "cache_enabled": not getattr(args, "no_cache", False),
        "cache_ttl": args.cache_ttl,
    }

    # Add command-specific params
    for attr in ["username", "hashtag", "media_id", "period", "limit", "topic", "query"]:
        val = getattr(args, attr, None)
        if val is not None:
            info[attr] = val

    if args.json:
        json_output(info)
    else:
        print_header(f"{command} (dry-run)")
        rows = [[k, str(v)] for k, v in info.items()]
        print(format_table(["Parameter", "Value"], rows))
        print(f"\n{DIM}No API call made. Remove --dry-run to execute.{RESET}\n")

    return EXIT_SUCCESS


def _save_to_file(data: dict, command: str, output_dir: str) -> None:
    """Save result as timestamped JSON file."""
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = out_path / f"instagram-intel_{command}_{ts}.json"
    filename.write_text(json.dumps(data, indent=2, default=str))
    logger.info("Saved results to %s", filename)


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

    try:
        # Local commands (no client needed)
        if args.command in _LOCAL_COMMANDS:
            return _LOCAL_COMMANDS[args.command](args)

        # Phase 2 stubs
        if args.command in _PHASE2_COMMANDS:
            return _PHASE2_COMMANDS[args.command](args)

        # Dry run — show params without making API calls (before client init)
        if getattr(args, "dry_run", False):
            return _dry_run_output(args.command, args)

        # Graph API commands — need a client (after dry-run check)
        if args.command in _GRAPH_COMMANDS:
            client = _init_client(args)
            if client is None:
                return EXIT_EXPECTED_ERROR
            return _GRAPH_COMMANDS[args.command](args, client)

        # Unknown command
        parser.print_help()
        return EXIT_EXPECTED_ERROR

    except InstagramIntelError as e:
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
