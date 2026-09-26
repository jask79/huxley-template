"""
Views Per Hour (VPH) tracking and analysis.

Commands:
    vph <video-id>          Show current VPH and history
    vph track <video-id>    Start tracking a video
    vph untrack <video-id>  Stop tracking a video
    vph list                List all tracked videos with latest VPH
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
    extract_video_id,
    format_count,
    format_duration,
    format_table,
    GREEN, RED, YELLOW, CYAN, BOLD, DIM, RESET,
)
from db import (
    add_tracked_video,
    remove_tracked_video,
    list_tracked_videos,
    get_tracked_video,
    get_vph_snapshots,
    get_latest_vph_snapshot,
    calculate_vph,
    calculate_avg_vph,
    add_vph_snapshot,
)


def _format_vph(vph: float) -> str:
    """Format VPH with color based on magnitude."""
    if vph >= 1000:
        return f"{GREEN}{BOLD}{vph:,.0f}{RESET}"
    elif vph >= 100:
        return f"{GREEN}{vph:,.0f}{RESET}"
    elif vph >= 10:
        return f"{YELLOW}{vph:,.0f}{RESET}"
    elif vph > 0:
        return f"{DIM}{vph:,.1f}{RESET}"
    else:
        return f"{DIM}--{RESET}"


def _format_time_ago(iso_time: str) -> str:
    """Convert ISO timestamp to 'X ago' format."""
    try:
        dt = datetime.fromisoformat(iso_time.replace("Z", "+00:00"))
        delta = datetime.now(timezone.utc) - dt
        total_secs = int(delta.total_seconds())
        if total_secs < 60:
            return "just now"
        elif total_secs < 3600:
            mins = total_secs // 60
            return f"{mins}m ago"
        elif total_secs < 86400:
            hours = total_secs // 3600
            return f"{hours}h ago"
        else:
            days = total_secs // 86400
            return f"{days}d ago"
    except (ValueError, AttributeError):
        return "unknown"


def run_show(client: YouTubeIntelClient, args: Namespace) -> int:
    """Show VPH data for a specific video."""
    video_id_raw = args.video_id
    if not video_id_raw:
        print(f"{RED}Please provide a video ID or URL.{RESET}", file=sys.stderr)
        print(f"{DIM}Usage: youtube-intel vph <video-id>{RESET}", file=sys.stderr)
        return 1

    video_id = extract_video_id(video_id_raw)

    # Check if we're tracking this video
    tracked = get_tracked_video(video_id)
    if not tracked:
        print(f"{YELLOW}Video '{video_id}' is not being tracked.{RESET}")
        print(f"{DIM}To start tracking: youtube-intel vph track {video_id}{RESET}")

        # Still show current stats from API
        print(f"\n{DIM}Fetching current stats from API...{RESET}")
        video_data = client.get_video(video_id)
        snippet = video_data.get("snippet", {})
        stats = video_data.get("statistics", {})
        title = snippet.get("title", "Unknown")
        views = int(stats.get("viewCount", 0))

        print(f"\n{BOLD}{title}{RESET}")
        print(f"  Views: {format_count(views)}")
        print(f"\n{DIM}Start tracking to see VPH over time.{RESET}")
        return 0

    title = tracked.get("title", "Unknown")
    print(f"\n{BOLD}{CYAN}VPH Report: {title}{RESET}")
    print(f"  {DIM}Video ID: {video_id}{RESET}\n")

    # Current VPH
    current_vph = calculate_vph(video_id)
    avg_vph_24h = calculate_avg_vph(video_id, hours=24)
    avg_vph_7d = calculate_avg_vph(video_id, hours=168)

    if current_vph is not None:
        print(f"  {BOLD}Current VPH:{RESET}  {_format_vph(current_vph)}")
    else:
        print(f"  {BOLD}Current VPH:{RESET}  {DIM}Insufficient data (need 2+ snapshots){RESET}")

    if avg_vph_24h is not None:
        print(f"  {BOLD}24h Avg VPH:{RESET}  {_format_vph(avg_vph_24h)}")
    if avg_vph_7d is not None:
        print(f"  {BOLD}7d Avg VPH:{RESET}   {_format_vph(avg_vph_7d)}")

    # Snapshot history
    snapshots = get_vph_snapshots(video_id, limit=24)
    if not snapshots:
        print(f"\n  {YELLOW}No VPH snapshots yet.{RESET}")
        print(f"  {DIM}The poller records snapshots hourly. Wait for data to accumulate.{RESET}")
        return 0

    print(f"\n  {BOLD}Recent Snapshots:{RESET} (latest {len(snapshots)})")
    rows = []
    prev_views = None
    for snap in reversed(snapshots):  # oldest first for display
        views = snap["view_count"]
        time_str = _format_time_ago(snap["snapshot_time"])
        delta = ""
        if prev_views is not None:
            diff = views - prev_views
            if diff > 0:
                delta = f"{GREEN}+{format_count(diff)}{RESET}"
            elif diff == 0:
                delta = f"{DIM}+0{RESET}"
            else:
                delta = f"{RED}{format_count(diff)}{RESET}"
        prev_views = views
        rows.append([time_str, format_count(views), delta])

    print(format_table(
        headers=["Time", "Views", "Delta"],
        rows=rows,
    ))

    return 0


def run_track(client: YouTubeIntelClient, args: Namespace) -> int:
    """Start tracking a video."""
    video_id = extract_video_id(args.video_id)

    # Fetch video info from API
    print(f"{DIM}Fetching video info...{RESET}")
    video_data = client.get_video(video_id)
    snippet = video_data.get("snippet", {})
    stats = video_data.get("statistics", {})

    title = snippet.get("title", "Unknown")
    channel_id = snippet.get("channelId", "")
    published_at = snippet.get("publishedAt", "")
    views = int(stats.get("viewCount", 0))

    # Add to tracking
    added = add_tracked_video(
        video_id=video_id,
        channel_id=channel_id,
        title=title,
        published_at=published_at,
    )

    # Record initial snapshot
    add_vph_snapshot(video_id, views)

    if added:
        print(f"\n{GREEN}{BOLD}Now tracking:{RESET} {title}")
        print(f"  {DIM}Video ID:{RESET}  {video_id}")
        print(f"  {DIM}Views:{RESET}     {format_count(views)}")
        print(f"  {DIM}Channel:{RESET}   {snippet.get('channelTitle', 'Unknown')}")
        print(f"\n{DIM}VPH data will appear after the poller records a second snapshot.{RESET}")
    else:
        print(f"{YELLOW}Video already tracked (re-activated):{RESET} {title}")

    return 0


def run_untrack(client: YouTubeIntelClient, args: Namespace) -> int:
    """Stop tracking a video."""
    video_id = extract_video_id(args.video_id)
    removed = remove_tracked_video(video_id)

    if removed:
        print(f"{GREEN}Stopped tracking video:{RESET} {video_id}")
        print(f"{DIM}Historical data is preserved.{RESET}")
    else:
        print(f"{YELLOW}Video '{video_id}' was not being tracked.{RESET}")

    return 0


def run_list(client: YouTubeIntelClient, args: Namespace) -> int:
    """List all tracked videos with latest VPH."""
    videos = list_tracked_videos(active_only=True)

    if not videos:
        print(f"{YELLOW}No videos being tracked.{RESET}")
        print(f"{DIM}Start tracking: youtube-intel vph track <video-id>{RESET}")
        return 0

    print(f"\n{BOLD}{CYAN}Tracked Videos ({len(videos)}){RESET}\n")

    rows = []
    for v in videos:
        vid = v["video_id"]
        title = v["title"][:40]
        vph = calculate_vph(vid)
        avg_24 = calculate_avg_vph(vid, hours=24)
        latest = get_latest_vph_snapshot(vid)

        vph_str = _format_vph(vph) if vph is not None else f"{DIM}--{RESET}"
        avg_str = _format_vph(avg_24) if avg_24 is not None else f"{DIM}--{RESET}"
        views_str = format_count(latest["view_count"]) if latest else f"{DIM}--{RESET}"
        last_snap = _format_time_ago(latest["snapshot_time"]) if latest else f"{DIM}never{RESET}"

        rows.append([title, vid[:11], views_str, vph_str, avg_str, last_snap])

    print(format_table(
        headers=["Title", "Video ID", "Views", "VPH", "24h Avg", "Last Snap"],
        rows=rows,
    ))

    return 0


def run(client: YouTubeIntelClient, args: Namespace) -> int:
    """Route VPH subcommands."""
    action = getattr(args, "vph_action", None)

    if action == "track":
        return run_track(client, args)
    elif action == "untrack":
        return run_untrack(client, args)
    elif action == "list":
        return run_list(client, args)
    elif action == "show":
        return run_show(client, args)
    else:
        print(f"{RED}Please specify a VPH action.{RESET}", file=sys.stderr)
        print(f"{DIM}Usage:{RESET}")
        print(f"  youtube-intel vph show <video-id>    Show VPH data")
        print(f"  youtube-intel vph track <video-id>   Start tracking")
        print(f"  youtube-intel vph untrack <video-id> Stop tracking")
        print(f"  youtube-intel vph list               List tracked videos")
        return 1
