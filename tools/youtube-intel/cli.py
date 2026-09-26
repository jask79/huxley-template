#!/usr/bin/env python3
"""
YouTube Intel CLI — Personal YouTube intelligence toolkit.

Replaces VidIQ for personal use. Provides keyword research, SEO scoring,
competitor tracking, VPH monitoring, trend discovery, and channel auditing.

Usage:
    python3 tools/youtube-intel/cli.py keyword "python tutorial"
    python3 tools/youtube-intel/cli.py seo score dQw4w9WgXcQ
    python3 tools/youtube-intel/cli.py vph track dQw4w9WgXcQ
    python3 tools/youtube-intel/cli.py competitor add @mkbhd
    python3 tools/youtube-intel/cli.py audit
    python3 tools/youtube-intel/cli.py trends "tech reviews"
    python3 tools/youtube-intel/cli.py ideas --niche "programming"
    python3 tools/youtube-intel/cli.py besttime
    python3 tools/youtube-intel/cli.py poller run
    python3 tools/youtube-intel/cli.py poller status

Dependencies: None (stdlib only)
Auth: Service Account (Data API) + OAuth (Analytics API) via macOS Keychain.
"""

import argparse
import sys
from pathlib import Path

# Ensure the tool directory is on the path so sibling imports work
TOOL_DIR = Path(__file__).resolve().parent
if str(TOOL_DIR) not in sys.path:
    sys.path.insert(0, str(TOOL_DIR))

from client import (
    YouTubeIntelClient,
    AuthError,
    CredentialError,
    YouTubeIntelError,
)
from db import get_connection

# Terminal colours
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
BOLD = "\033[1m"
DIM = "\033[2m"
RESET = "\033[0m"


def _build_parser() -> argparse.ArgumentParser:
    """Build the top-level argument parser with all subcommands."""
    parser = argparse.ArgumentParser(
        prog="youtube-intel",
        description=f"{BOLD}YouTube Intel{RESET} — Personal YouTube intelligence toolkit",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"""\
{DIM}Auth: Service Account for most commands (automatic).
      OAuth for analytics (audit, besttime): run youtube-api.py auth login{RESET}
""",
    )
    parser.add_argument(
        "--debug", action="store_true",
        help="Enable debug output",
    )

    subparsers = parser.add_subparsers(
        dest="command",
        title="commands",
        metavar="<command>",
    )

    # --- keyword ---
    kw_parser = subparsers.add_parser(
        "keyword",
        help="Keyword research and competition analysis",
        description="Analyze YouTube search keywords for competition and opportunity.",
    )
    kw_sub = kw_parser.add_subparsers(dest="keyword_action", metavar="<action>")

    # keyword analyze <term> (default action)
    kw_analyze = kw_sub.add_parser(
        "analyze",
        help="Analyze a keyword's competition and opportunity",
    )
    kw_analyze.add_argument("term", help="Search term to analyze (e.g. 'python tutorial')")
    kw_analyze.add_argument(
        "--results", type=int, default=20,
        help="Number of search results to analyze (default: 20)",
    )

    # keyword compare <term1> <term2>
    kw_compare = kw_sub.add_parser(
        "compare",
        help="Side-by-side comparison of two keywords",
    )
    kw_compare.add_argument("term1", help="First search term")
    kw_compare.add_argument("term2", help="Second search term")
    kw_compare.add_argument(
        "--results", type=int, default=20,
        help="Number of search results per keyword (default: 20)",
    )

    # --- vph ---
    vph_parser = subparsers.add_parser(
        "vph",
        help="Views Per Hour tracking and analysis",
        description="Track and display VPH (Views Per Hour) for YouTube videos.",
    )
    vph_sub = vph_parser.add_subparsers(dest="vph_action", metavar="<action>")

    # vph show <video-id> (also works as: vph <video-id> via default routing)
    vph_show = vph_sub.add_parser("show", help="Show VPH data for a video")
    vph_show.add_argument("video_id", help="Video ID or URL to show VPH data for")

    # vph track
    vph_track = vph_sub.add_parser("track", help="Start tracking a video's VPH")
    vph_track.add_argument("video_id", help="Video ID or URL to track")

    # vph untrack
    vph_untrack = vph_sub.add_parser("untrack", help="Stop tracking a video")
    vph_untrack.add_argument("video_id", help="Video ID or URL to stop tracking")

    # vph list
    vph_sub.add_parser("list", help="List all tracked videos with latest VPH")

    # --- competitor ---
    comp_parser = subparsers.add_parser(
        "competitor",
        help="Competitor channel intelligence",
        description="Track and analyze competitor YouTube channels.",
    )
    comp_sub = comp_parser.add_subparsers(dest="comp_action", metavar="<action>")

    # competitor add
    comp_add = comp_sub.add_parser("add", help="Start tracking a competitor channel")
    comp_add.add_argument("channel", help="Channel URL, @handle, or ID")

    # competitor remove
    comp_rm = comp_sub.add_parser("remove", help="Stop tracking a competitor")
    comp_rm.add_argument("channel", help="Channel URL, @handle, or ID")

    # competitor list
    comp_sub.add_parser("list", help="List all tracked competitors")

    # competitor report
    comp_sub.add_parser("report", help="Full competitor comparison report")

    # --- seo ---
    seo_parser = subparsers.add_parser(
        "seo",
        help="SEO scoring and optimization suggestions",
        description="Analyze a video's SEO optimization and get improvement suggestions.",
    )
    seo_sub = seo_parser.add_subparsers(dest="seo_action", metavar="<action>")

    # seo score
    seo_score = seo_sub.add_parser("score", help="Full SEO score with breakdown")
    seo_score.add_argument("video_id", help="Video ID or URL to score")

    # seo suggest
    seo_suggest = seo_sub.add_parser("suggest", help="SEO score + actionable suggestions")
    seo_suggest.add_argument("video_id", help="Video ID or URL to analyze")
    seo_suggest.add_argument(
        "--ai", action="store_true", default=False,
        help="Use AI (Claude) for deeper, more specific suggestions",
    )

    # --- audit ---
    audit_parser = subparsers.add_parser(
        "audit",
        help="Channel health audit",
        description="Comprehensive health audit of your YouTube channel.",
    )
    audit_parser.add_argument(
        "--channel", default=None,
        help="Channel ID to audit (default: your own channel)",
    )
    audit_parser.add_argument(
        "--days", type=int, default=28,
        help="Number of days to analyze (default: 28)",
    )

    # --- trends ---
    trends_parser = subparsers.add_parser(
        "trends",
        help="Discover trending topics in a niche",
        description="Mine YouTube search and autocomplete for trending topics.",
    )
    trends_parser.add_argument(
        "niche",
        help="Niche or topic to explore (e.g. 'tech reviews')",
    )
    trends_parser.add_argument(
        "--depth", type=int, default=3,
        help="How many levels deep to mine autocomplete (default: 3)",
    )

    # --- ideas ---
    ideas_parser = subparsers.add_parser(
        "ideas",
        help="Generate content ideas",
        description="Generate video content ideas based on channel data and trends.",
    )
    ideas_parser.add_argument(
        "--count", type=int, default=10,
        help="Number of ideas to generate (default: 10)",
    )
    ideas_parser.add_argument(
        "--niche", default=None,
        help="Niche to focus on (default: derive from channel data)",
    )
    ideas_parser.add_argument(
        "--ai", action="store_true", default=False,
        help="Use AI (Claude) for smarter idea generation",
    )

    # --- besttime ---
    besttime_parser = subparsers.add_parser(
        "besttime",
        help="Find best posting times",
        description="Analyze viewer activity to find optimal posting windows.",
    )
    besttime_parser.add_argument(
        "--days", type=int, default=28,
        help="Number of days to analyze (default: 28)",
    )

    # --- poller ---
    poller_parser = subparsers.add_parser(
        "poller",
        help="Manual control and status for the automated VPH poller",
        description=(
            "Run a poll cycle manually or inspect poller status.\n\n"
            "The LaunchAgent normally runs this hourly — use these commands\n"
            "for on-demand polling or to check when the last snapshot was taken."
        ),
    )
    poller_sub = poller_parser.add_subparsers(dest="poller_action", metavar="<action>")

    # poller run
    poller_run = poller_sub.add_parser(
        "run",
        help="Run one poll cycle now",
    )
    poller_run.add_argument(
        "--mode",
        dest="poller_mode",
        choices=["vph", "competitors", "all"],
        default="vph",
        help="Which poll to run (default: vph)",
    )
    poller_run.add_argument(
        "--dry-run",
        action="store_true",
        help="Log what would be written without touching the database",
    )

    # poller status
    poller_sub.add_parser(
        "status",
        help="Show last poll time and tracked video/competitor counts",
    )

    return parser


def main() -> int:
    """Main entry point."""
    parser = _build_parser()
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 0

    # Import command modules lazily to keep startup fast
    from commands import keyword as cmd_keyword
    from commands import vph as cmd_vph
    from commands import competitor as cmd_competitor
    from commands import seo as cmd_seo
    from commands import audit as cmd_audit
    from commands import trends as cmd_trends
    from commands import ideas as cmd_ideas
    from commands import besttime as cmd_besttime
    from commands import poller as cmd_poller

    # Initialize DB (auto-creates tables on first run)
    try:
        conn = get_connection()
        conn.close()
    except Exception as e:
        print(f"{RED}Failed to initialize database: {e}{RESET}", file=sys.stderr)
        return 1

    # Create API client (service account for Data API, OAuth optional for Analytics)
    try:
        client = YouTubeIntelClient()
        if client.has_oauth:
            auth_mode = f"{GREEN}Service Account + OAuth{RESET}"
        else:
            auth_mode = f"{YELLOW}Service Account only{RESET} {DIM}(audit/besttime need OAuth){RESET}"
        if args.debug:
            print(f"{DIM}Auth: {auth_mode}{RESET}")
    except CredentialError as e:
        print(f"\n{RED}{BOLD}Credential Error{RESET}", file=sys.stderr)
        print(f"{RED}{e}{RESET}", file=sys.stderr)
        return 1
    except AuthError as e:
        print(f"\n{RED}{BOLD}Authentication Error{RESET}", file=sys.stderr)
        print(f"{RED}{e}{RESET}", file=sys.stderr)
        return 1

    # Route to command handler
    try:
        if args.command == "keyword":
            return cmd_keyword.run(client, args)
        elif args.command == "vph":
            return cmd_vph.run(client, args)
        elif args.command == "competitor":
            return cmd_competitor.run(client, args)
        elif args.command == "seo":
            return cmd_seo.run(client, args)
        elif args.command == "audit":
            return cmd_audit.run(client, args)
        elif args.command == "trends":
            return cmd_trends.run(client, args)
        elif args.command == "ideas":
            return cmd_ideas.run(client, args)
        elif args.command == "besttime":
            return cmd_besttime.run(client, args)
        elif args.command == "poller":
            return cmd_poller.run(client, args)
        else:
            parser.print_help()
            return 1

    except AuthError as e:
        print(f"\n{RED}{BOLD}Auth Error{RESET}: {e}", file=sys.stderr)
        print(f"{YELLOW}Run: youtube-api.py auth login{RESET}", file=sys.stderr)
        return 1
    except YouTubeIntelError as e:
        print(f"\n{RED}{BOLD}Error{RESET}: {e}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print(f"\n{DIM}Interrupted.{RESET}")
        return 0
    except Exception as e:
        if args.debug:
            import traceback
            traceback.print_exc()
        else:
            print(f"\n{RED}{BOLD}Unexpected error{RESET}: {e}", file=sys.stderr)
            print(f"{DIM}Run with --debug for full traceback.{RESET}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
