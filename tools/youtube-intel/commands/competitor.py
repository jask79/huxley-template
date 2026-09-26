"""
Competitor channel intelligence.

Commands:
    competitor add <channel>     Track a competitor channel
    competitor remove <channel>  Stop tracking a competitor
    competitor list              List all tracked competitors
    competitor report            Full comparison report
"""

import sys
from argparse import Namespace
from datetime import datetime, timezone
from pathlib import Path

_TOOL_DIR = Path(__file__).resolve().parent.parent
if str(_TOOL_DIR) not in sys.path:
    sys.path.insert(0, str(_TOOL_DIR))

from client import (
    YouTubeIntelClient,
    format_count,
    format_duration,
    format_table,
    GREEN, RED, YELLOW, CYAN, BOLD, DIM, RESET,
)
from db import (
    add_competitor,
    remove_competitor,
    list_competitors,
    get_competitor,
    add_competitor_snapshot,
    get_competitor_snapshots,
)


def _resolve_channel(client: YouTubeIntelClient, identifier: str) -> dict:
    """Resolve a channel identifier and return full channel data."""
    channel_id, channel_name = client.resolve_channel_id(identifier)
    channel_data = client.get_channel(channel_id=channel_id)
    return channel_data


def run_add(client: YouTubeIntelClient, args: Namespace) -> int:
    """Start tracking a competitor channel."""
    identifier = args.channel

    print(f"{DIM}Resolving channel...{RESET}")
    channel_data = _resolve_channel(client, identifier)

    channel_id = channel_data["id"]
    snippet = channel_data.get("snippet", {})
    stats = channel_data.get("statistics", {})

    channel_name = snippet.get("title", "Unknown")
    channel_handle = snippet.get("customUrl", "")
    subs = int(stats.get("subscriberCount", 0))
    videos = int(stats.get("videoCount", 0))
    views = int(stats.get("viewCount", 0))

    # Add to DB
    added = add_competitor(
        channel_id=channel_id,
        channel_name=channel_name,
        channel_handle=channel_handle,
    )

    # Record initial snapshot
    add_competitor_snapshot(
        channel_id=channel_id,
        subscriber_count=subs,
        video_count=videos,
        view_count=views,
    )

    print(f"\n{GREEN}{BOLD}Now tracking competitor:{RESET} {channel_name}")
    print(f"  {DIM}Channel ID:{RESET}   {channel_id}")
    if channel_handle:
        print(f"  {DIM}Handle:{RESET}      {channel_handle}")
    print(f"  {DIM}Subscribers:{RESET} {format_count(subs)}")
    print(f"  {DIM}Videos:{RESET}      {format_count(videos)}")
    print(f"  {DIM}Total Views:{RESET} {format_count(views)}")

    return 0


def run_remove(client: YouTubeIntelClient, args: Namespace) -> int:
    """Stop tracking a competitor channel."""
    identifier = args.channel

    # Try to resolve to channel ID
    try:
        channel_id, channel_name = client.resolve_channel_id(identifier)
    except Exception:
        # If resolution fails, try using the identifier directly
        channel_id = identifier
        channel_name = identifier

    removed = remove_competitor(channel_id)

    if removed:
        print(f"{GREEN}Stopped tracking:{RESET} {channel_name} ({channel_id})")
        print(f"{DIM}Historical snapshots are preserved.{RESET}")
    else:
        print(f"{YELLOW}Channel '{identifier}' was not being tracked.{RESET}")

    return 0


def run_list(client: YouTubeIntelClient, args: Namespace) -> int:
    """List all tracked competitors with latest stats."""
    competitors = list_competitors()

    if not competitors:
        print(f"{YELLOW}No competitors being tracked.{RESET}")
        print(f"{DIM}Add one: youtube-intel competitor add @channelhandle{RESET}")
        return 0

    print(f"\n{BOLD}{CYAN}Tracked Competitors ({len(competitors)}){RESET}\n")

    rows = []
    for comp in competitors:
        ch_id = comp["channel_id"]
        name = comp["channel_name"][:30]
        handle = comp.get("channel_handle", "") or ""

        # Get latest snapshot
        snapshots = get_competitor_snapshots(ch_id, limit=1)
        if snapshots:
            snap = snapshots[0]
            subs = format_count(snap["subscriber_count"])
            vids = str(snap["video_count"])
            views = format_count(snap["view_count"])
        else:
            subs = f"{DIM}--{RESET}"
            vids = f"{DIM}--{RESET}"
            views = f"{DIM}--{RESET}"

        rows.append([name, handle, subs, vids, views])

    print(format_table(
        headers=["Channel", "Handle", "Subs", "Videos", "Views"],
        rows=rows,
    ))

    return 0


def _calculate_growth(snapshots: list, field: str) -> str:
    """Calculate growth from oldest to newest snapshot."""
    if len(snapshots) < 2:
        return f"{DIM}--{RESET}"

    newest = snapshots[0][field]
    oldest = snapshots[-1][field]
    diff = newest - oldest

    if diff > 0:
        return f"{GREEN}+{format_count(diff)}{RESET}"
    elif diff < 0:
        return f"{RED}{format_count(diff)}{RESET}"
    else:
        return f"{DIM}+0{RESET}"


def run_report(client: YouTubeIntelClient, args: Namespace) -> int:
    """Full competitor comparison report."""
    competitors = list_competitors()

    if not competitors:
        print(f"{YELLOW}No competitors being tracked.{RESET}")
        print(f"{DIM}Add some: youtube-intel competitor add @channelhandle{RESET}")
        return 0

    print(f"\n{BOLD}{CYAN}Competitor Intelligence Report{RESET}")
    print(f"{DIM}Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}{RESET}\n")

    # Get your own channel for comparison
    try:
        print(f"{DIM}Fetching your channel data...{RESET}")
        my_channel = client.get_channel()
        my_stats = my_channel.get("statistics", {})
        my_name = my_channel.get("snippet", {}).get("title", "Your Channel")
        my_subs = int(my_stats.get("subscriberCount", 0))
        my_videos_count = int(my_stats.get("videoCount", 0))
        my_views = int(my_stats.get("viewCount", 0))
        has_own = True
    except Exception:
        has_own = False

    # Build comparison table
    print(f"{BOLD}Channel Comparison:{RESET}\n")
    rows = []

    if has_own:
        rows.append([
            f"{GREEN}{my_name}{RESET}",
            format_count(my_subs),
            str(my_videos_count),
            format_count(my_views),
            f"{DIM}(you){RESET}",
        ])

    for comp in competitors:
        ch_id = comp["channel_id"]
        name = comp["channel_name"][:30]
        snapshots = get_competitor_snapshots(ch_id, limit=30)

        if snapshots:
            latest = snapshots[0]
            subs = format_count(latest["subscriber_count"])
            vids = str(latest["video_count"])
            views = format_count(latest["view_count"])
            growth = _calculate_growth(snapshots, "subscriber_count")
        else:
            subs = f"{DIM}--{RESET}"
            vids = f"{DIM}--{RESET}"
            views = f"{DIM}--{RESET}"
            growth = f"{DIM}--{RESET}"

        rows.append([name, subs, vids, views, growth])

    print(format_table(
        headers=["Channel", "Subs", "Videos", "Total Views", "Sub Growth"],
        rows=rows,
    ))

    # Per-competitor deep dive
    for comp in competitors:
        ch_id = comp["channel_id"]
        name = comp["channel_name"]

        print(f"\n{'=' * 60}")
        print(f"{BOLD}{CYAN}{name}{RESET}")
        if comp.get("channel_handle"):
            print(f"  {DIM}{comp['channel_handle']}{RESET}")
        print()

        # Fetch recent videos
        try:
            print(f"  {DIM}Fetching recent uploads...{RESET}")
            recent_videos = client.list_channel_videos(channel_id=ch_id, max_results=10)

            if recent_videos:
                # Upload frequency
                dates = []
                for v in recent_videos:
                    pub = v.get("snippet", {}).get("publishedAt", "")
                    if pub:
                        try:
                            dt = datetime.fromisoformat(pub.replace("Z", "+00:00"))
                            dates.append(dt)
                        except ValueError:
                            pass

                if len(dates) >= 2:
                    dates.sort(reverse=True)
                    total_days = (dates[0] - dates[-1]).total_seconds() / 86400
                    if total_days > 0:
                        freq = len(dates) / total_days * 7  # videos per week
                        print(f"  {BOLD}Upload Frequency:{RESET} ~{freq:.1f} videos/week")

                # Top recent videos
                print(f"\n  {BOLD}Recent Videos:{RESET}")
                vid_rows = []
                for v in recent_videos[:5]:
                    snippet = v.get("snippet", {})
                    stats = v.get("statistics", {})
                    title = snippet.get("title", "")[:45]
                    views = format_count(int(stats.get("viewCount", 0)))
                    likes = format_count(int(stats.get("likeCount", 0)))
                    vid_rows.append([title, views, likes])

                print(format_table(
                    headers=["Title", "Views", "Likes"],
                    rows=vid_rows,
                ))

                # Engagement stats
                total_views = sum(int(v.get("statistics", {}).get("viewCount", 0)) for v in recent_videos)
                total_likes = sum(int(v.get("statistics", {}).get("likeCount", 0)) for v in recent_videos)
                total_comments = sum(int(v.get("statistics", {}).get("commentCount", 0)) for v in recent_videos)

                if total_views > 0:
                    eng_rate = (total_likes + total_comments) / total_views * 100
                    print(f"\n  {BOLD}Avg Engagement Rate:{RESET} {eng_rate:.2f}%")
                    print(f"  {DIM}(across last {len(recent_videos)} videos){RESET}")

        except Exception as e:
            print(f"  {YELLOW}Could not fetch recent videos: {e}{RESET}")

    return 0


def run(client: YouTubeIntelClient, args: Namespace) -> int:
    """Route competitor subcommands."""
    action = getattr(args, "comp_action", None)

    if action == "add":
        return run_add(client, args)
    elif action == "remove":
        return run_remove(client, args)
    elif action == "list":
        return run_list(client, args)
    elif action == "report":
        return run_report(client, args)
    else:
        print(f"{YELLOW}Please specify an action: add, remove, list, or report{RESET}", file=sys.stderr)
        print(f"{DIM}Usage: youtube-intel competitor <add|remove|list|report>{RESET}", file=sys.stderr)
        return 1
