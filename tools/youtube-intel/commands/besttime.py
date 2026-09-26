"""
Best posting time analysis.

Commands:
    besttime [--days 28]   Analyze viewer activity and recommend posting windows
"""

import sys
from argparse import Namespace
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple

_TOOL_DIR = Path(__file__).resolve().parent.parent
if str(_TOOL_DIR) not in sys.path:
    sys.path.insert(0, str(_TOOL_DIR))

from client import (
    YouTubeIntelClient,
    format_count,
    format_table,
    GREEN, RED, YELLOW, CYAN, BOLD, DIM, RESET,
)


# Day names for display
DAY_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

# Heatmap characters (from lowest to highest activity)
HEAT_CHARS = [" ", ".", ":", "o", "O", "#", "@"]


def _build_heatmap(
    daily_data: List[Tuple[str, int, int]],
) -> Dict[int, Dict[int, float]]:
    """
    Build a day-of-week x aggregated-activity map from daily analytics.

    Since YouTube Analytics daily data doesn't break down by hour,
    we aggregate by day-of-week to identify the best days. For hourly
    patterns we use the video-level publish-time vs performance data.

    Args:
        daily_data: List of (date_str, views, watch_minutes) tuples.

    Returns:
        {day_of_week (0=Mon): {0: total_views}} — simplified to day-level.
    """
    day_views: Dict[int, List[int]] = {d: [] for d in range(7)}

    for date_str, views, watch_mins in daily_data:
        try:
            dt = datetime.strptime(date_str, "%Y-%m-%d")
            dow = dt.weekday()  # 0=Mon, 6=Sun
            day_views[dow].append(views)
        except (ValueError, TypeError):
            continue

    # Average views per day-of-week
    result: Dict[int, Dict[int, float]] = {}
    for dow, view_list in day_views.items():
        avg = sum(view_list) / len(view_list) if view_list else 0
        result[dow] = {0: avg}

    return result


def _analyze_publish_times(
    videos: list,
) -> Dict[int, Dict[int, float]]:
    """
    Analyze when videos were published and how they performed.

    Build a day-of-week x hour-of-day performance map based on
    actual video publish times and their age-normalized view counts.
    Uses views-per-day instead of raw views to remove the confound
    where older videos dominate simply due to accumulated watch time.

    Returns:
        {day_of_week: {hour: avg_views_per_day_per_video}}
    """
    now = datetime.now(timezone.utc)

    # Collect (dow, hour, views_per_day) tuples
    data_points: List[Tuple[int, int, float]] = []

    for v in videos:
        snippet = v.get("snippet", {})
        stats = v.get("statistics", {})
        pub = snippet.get("publishedAt", "")
        views = int(stats.get("viewCount", 0))

        try:
            dt = datetime.fromisoformat(pub.replace("Z", "+00:00"))
            age_days = max((now - dt).total_seconds() / 86400, 1.0)
            views_per_day = views / age_days
            dow = dt.weekday()
            hour = dt.hour
            data_points.append((dow, hour, views_per_day))
        except (ValueError, AttributeError):
            continue

    if not data_points:
        return {}

    # Aggregate: for each (dow, hour), compute average views-per-day
    bucket: Dict[Tuple[int, int], List[float]] = defaultdict(list)
    for dow, hour, vpd in data_points:
        bucket[(dow, hour)].append(vpd)

    result: Dict[int, Dict[int, float]] = {}
    for (dow, hour), vpd_list in bucket.items():
        if dow not in result:
            result[dow] = {}
        result[dow][hour] = sum(vpd_list) / len(vpd_list)

    return result


def _render_heatmap(
    day_data: Dict[int, Dict[int, float]],
    hours: List[int],
    title: str = "Activity Heatmap",
) -> None:
    """Render a terminal heatmap for day-of-week x hour-of-day."""
    # Find min/max for normalization
    all_values = []
    for dow_data in day_data.values():
        all_values.extend(dow_data.values())

    if not all_values:
        print(f"  {DIM}No data for heatmap.{RESET}")
        return

    min_val = min(all_values)
    max_val = max(all_values)
    val_range = max_val - min_val if max_val > min_val else 1

    print(f"  {BOLD}{title}{RESET}\n")

    # Header row with hour labels
    hour_labels = "".join(f"{h:3d}" for h in hours)
    print(f"       {DIM}{hour_labels}{RESET}")

    # Each day row
    for dow in range(7):
        day_name = DAY_NAMES[dow]
        row_chars = []
        for h in hours:
            val = day_data.get(dow, {}).get(h, 0)
            # Normalize to 0-6 index for HEAT_CHARS
            if val > 0:
                normalized = (val - min_val) / val_range
                idx = min(len(HEAT_CHARS) - 1, int(normalized * (len(HEAT_CHARS) - 1)))
            else:
                idx = 0
            char = HEAT_CHARS[idx]

            # Colorize
            if idx >= 5:
                row_chars.append(f"{GREEN}{BOLD}{char}{RESET}")
            elif idx >= 3:
                row_chars.append(f"{YELLOW}{char}{RESET}")
            elif idx >= 1:
                row_chars.append(f"{DIM}{char}{RESET}")
            else:
                row_chars.append(f" ")

        row_str = "  ".join(row_chars)
        print(f"  {BOLD}{day_name}{RESET}  {row_str}")

    # Legend
    print(f"\n  {DIM}Legend: ' '=no data  .=low  :=below avg  o=avg  O=above avg  #=high  @=peak{RESET}")


def _find_top_windows(
    day_data: Dict[int, Dict[int, float]],
    top_n: int = 5,
) -> List[Tuple[int, int, float]]:
    """
    Find the top N posting windows (day, hour) by performance.

    Returns list of (day_of_week, hour, score) sorted by score descending.
    """
    windows: List[Tuple[int, int, float]] = []
    for dow, hour_data in day_data.items():
        for hour, score in hour_data.items():
            windows.append((dow, hour, score))

    windows.sort(key=lambda x: x[2], reverse=True)
    return windows[:top_n]


def _find_best_days(
    day_data: Dict[int, Dict[int, float]],
) -> List[Tuple[int, float]]:
    """Find best days by total aggregated activity."""
    day_totals: List[Tuple[int, float]] = []
    for dow in range(7):
        total = sum(day_data.get(dow, {}).values())
        day_totals.append((dow, total))

    day_totals.sort(key=lambda x: x[1], reverse=True)
    return day_totals


def run(client: YouTubeIntelClient, args: Namespace) -> int:
    """Find best posting times from viewer activity and publish-time analysis."""
    days = args.days

    now = datetime.now(timezone.utc)
    start_date = (now - timedelta(days=days)).strftime("%Y-%m-%d")
    end_date = now.strftime("%Y-%m-%d")

    print(f"\n{BOLD}{CYAN}Best Posting Time Analysis{RESET}")
    print(f"  {DIM}Analyzing last {days} days of data...{RESET}\n")

    # Approach 1: Daily analytics (viewer activity by day of week)
    daily_heatmap: Dict[int, Dict[int, float]] = {}

    try:
        print(f"{DIM}Fetching daily analytics...{RESET}")
        daily = client.get_daily_analytics(start_date=start_date, end_date=end_date)
        daily_rows = daily.get("rows", [])

        if daily_rows:
            daily_data = [(r[0], int(r[1]), int(r[2])) for r in daily_rows]
            daily_heatmap = _build_heatmap(daily_data)

            # Best days by average views
            best_days = _find_best_days(daily_heatmap)

            print(f"\n  {BOLD}Best Days to Publish (by avg daily views):{RESET}\n")
            rows = []
            for dow, total in best_days:
                bar_len = int(total / max(best_days[0][1], 1) * 20) if best_days[0][1] > 0 else 0
                bar = f"{GREEN}{'#' * bar_len}{DIM}{'.' * (20 - bar_len)}{RESET}"
                rows.append([DAY_NAMES[dow], f"{total:,.0f}", bar])

            print(format_table(
                headers=["Day", "Avg Views", "Activity"],
                rows=rows,
            ))

    except Exception as e:
        print(f"  {YELLOW}Daily analytics unavailable: {e}{RESET}")
        print(f"  {DIM}(Requires YouTube Analytics API access){RESET}")

    # Approach 2: Publish-time performance analysis
    print(f"\n{DIM}Analyzing publish-time performance...{RESET}")
    try:
        videos = client.list_channel_videos(max_results=50)

        if videos:
            publish_heatmap = _analyze_publish_times(videos)

            if publish_heatmap:
                # Determine hour range from data
                all_hours = set()
                for dow_data in publish_heatmap.values():
                    all_hours.update(dow_data.keys())

                if all_hours:
                    hours = sorted(all_hours)

                    print()
                    _render_heatmap(
                        publish_heatmap,
                        hours=hours,
                        title="Publish Time vs Performance (views/day)",
                    )

                    # Top windows
                    top_windows = _find_top_windows(publish_heatmap, top_n=5)

                    if top_windows:
                        print(f"\n  {BOLD}{GREEN}Top 5 Posting Windows:{RESET}\n")
                        rows = []
                        for rank, (dow, hour, score) in enumerate(top_windows, 1):
                            time_str = f"{DAY_NAMES[dow]} {hour:02d}:00"
                            rows.append([
                                f"#{rank}",
                                time_str,
                                f"{score:,.1f} avg views/day",
                            ])

                        print(format_table(
                            headers=["Rank", "Window", "Performance"],
                            rows=rows,
                        ))
            else:
                print(f"  {DIM}Not enough publish-time data for hourly analysis.{RESET}")

        else:
            print(f"  {YELLOW}No videos found on your channel.{RESET}")

    except Exception as e:
        print(f"  {YELLOW}Publish-time analysis failed: {e}{RESET}")

    # Summary recommendations
    print(f"\n{'=' * 50}")
    print(f"  {BOLD}Recommendations:{RESET}\n")

    if daily_heatmap:
        best_days = _find_best_days(daily_heatmap)
        top_day = DAY_NAMES[best_days[0][0]] if best_days else "N/A"
        worst_day = DAY_NAMES[best_days[-1][0]] if best_days else "N/A"
        print(f"  {GREEN}Best day:{RESET}  {top_day}")
        print(f"  {RED}Worst day:{RESET} {worst_day}")

    print(f"\n  {DIM}For more accurate hourly data, ensure you have 50+ videos")
    print(f"  published across different times. The more data points,")
    print(f"  the more reliable the recommendations.{RESET}")
    print()

    return 0
