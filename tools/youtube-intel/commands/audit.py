"""
Channel health audit.

Commands:
    audit [--channel ID] [--days 28]   Comprehensive channel health report
"""

import re
import sys
from argparse import Namespace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List

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
from algo_loader import (
    compute_outlier_scores,
    VideoInput,
)


def _trend_arrow(values: List[float]) -> str:
    """Determine trend direction from a series of values."""
    if len(values) < 2:
        return f"{DIM}--{RESET}"
    first_half = sum(values[:len(values) // 2]) / max(len(values) // 2, 1)
    second_half = sum(values[len(values) // 2:]) / max(len(values) - len(values) // 2, 1)

    if first_half == 0:
        return f"{DIM}--{RESET}"

    pct_change = (second_half - first_half) / first_half * 100

    if pct_change > 10:
        return f"{GREEN}+{pct_change:.0f}%{RESET}"
    elif pct_change > 0:
        return f"{GREEN}+{pct_change:.1f}%{RESET}"
    elif pct_change > -10:
        return f"{YELLOW}{pct_change:.1f}%{RESET}"
    else:
        return f"{RED}{pct_change:.0f}%{RESET}"


def _health_grade(metrics: Dict[str, Any]) -> str:
    """Compute an overall health grade from channel metrics."""
    score = 0
    factors = 0

    # Upload consistency (target: 1+ per week)
    if metrics.get("uploads_per_week", 0) >= 2:
        score += 100
    elif metrics.get("uploads_per_week", 0) >= 1:
        score += 70
    elif metrics.get("uploads_per_week", 0) >= 0.5:
        score += 40
    else:
        score += 10
    factors += 1

    # Engagement rate
    eng = metrics.get("avg_engagement_rate", 0)
    if eng >= 5:
        score += 100
    elif eng >= 3:
        score += 80
    elif eng >= 1:
        score += 50
    else:
        score += 20
    factors += 1

    # View trend
    trend = metrics.get("view_trend_pct", 0)
    if trend > 10:
        score += 100
    elif trend > 0:
        score += 70
    elif trend > -10:
        score += 40
    else:
        score += 10
    factors += 1

    avg = score / max(factors, 1)
    if avg >= 80:
        return f"{GREEN}{BOLD}A{RESET}"
    elif avg >= 65:
        return f"{GREEN}B{RESET}"
    elif avg >= 50:
        return f"{YELLOW}C{RESET}"
    elif avg >= 35:
        return f"{RED}D{RESET}"
    else:
        return f"{RED}{BOLD}F{RESET}"


def run(client: YouTubeIntelClient, args: Namespace) -> int:
    """Run channel health audit."""
    days = args.days
    channel_id = args.channel

    now = datetime.now(timezone.utc)
    start_date = (now - timedelta(days=days)).strftime("%Y-%m-%d")
    end_date = now.strftime("%Y-%m-%d")

    # Get channel info
    print(f"{DIM}Fetching channel data...{RESET}")
    if channel_id:
        channel_data = client.get_channel(channel_id=channel_id)
    else:
        channel_data = client.get_channel()
        channel_id = channel_data["id"]

    snippet = channel_data.get("snippet", {})
    stats = channel_data.get("statistics", {})
    channel_name = snippet.get("title", "Unknown")
    subs = int(stats.get("subscriberCount", 0))
    total_videos = int(stats.get("videoCount", 0))
    total_views = int(stats.get("viewCount", 0))

    print(f"\n{BOLD}{CYAN}Channel Health Audit: {channel_name}{RESET}")
    print(f"  {DIM}Period: Last {days} days ({start_date} to {end_date}){RESET}")
    print(f"  {DIM}Channel ID: {channel_id}{RESET}\n")

    # Channel overview
    print(f"  {BOLD}Channel Overview:{RESET}")
    print(f"    Subscribers:  {format_count(subs)}")
    print(f"    Total Videos: {format_count(total_videos)}")
    print(f"    Total Views:  {format_count(total_views)}")

    # Analytics data
    metrics: Dict[str, Any] = {}

    print(f"\n{DIM}Fetching analytics data...{RESET}")
    try:
        analytics = client.get_channel_analytics(start_date=start_date, end_date=end_date)
        col_headers = analytics.get("columnHeaders", [])
        rows_data = analytics.get("rows", [])

        if rows_data and col_headers:
            row = rows_data[0]
            col_names = [h.get("name", "") for h in col_headers]

            # Map column names to values
            analytics_map = dict(zip(col_names, row))

            period_views = int(analytics_map.get("views", 0))
            watch_mins = int(analytics_map.get("estimatedMinutesWatched", 0))
            subs_gained = int(analytics_map.get("subscribersGained", 0))
            subs_lost = int(analytics_map.get("subscribersLost", 0))
            likes = int(analytics_map.get("likes", 0))
            comments = int(analytics_map.get("comments", 0))
            shares = int(analytics_map.get("shares", 0))
            avg_view_duration = float(analytics_map.get("averageViewDuration", 0))
            impressions = int(analytics_map.get("impressions", 0))
            ctr = float(analytics_map.get("impressionClickThroughRate", 0))

            print(f"\n  {BOLD}Period Performance ({days} days):{RESET}")
            print(f"    Views:              {format_count(period_views)}")
            print(f"    Watch Time:         {format_count(watch_mins)} minutes ({watch_mins // 60:,} hours)")
            print(f"    Subscribers:        {GREEN}+{format_count(subs_gained)}{RESET} / {RED}-{format_count(subs_lost)}{RESET} = {GREEN}net +{format_count(subs_gained - subs_lost)}{RESET}")
            print(f"    Likes:              {format_count(likes)}")
            print(f"    Comments:           {format_count(comments)}")
            print(f"    Shares:             {format_count(shares)}")
            print(f"    Avg View Duration:  {avg_view_duration:.0f}s ({avg_view_duration / 60:.1f}m)")
            print(f"    Impressions:        {format_count(impressions)}")
            print(f"    CTR:                {ctr:.2%}")

            if period_views > 0:
                eng_rate = (likes + comments) / period_views * 100
                metrics["avg_engagement_rate"] = eng_rate
                print(f"    Engagement Rate:    {eng_rate:.2f}%")

    except Exception as e:
        print(f"  {YELLOW}Could not fetch analytics: {e}{RESET}")
        print(f"  {DIM}(Analytics API requires YouTube Partner Program or content owner access){RESET}")

    # Daily trends
    try:
        print(f"\n{DIM}Fetching daily data...{RESET}")
        daily = client.get_daily_analytics(start_date=start_date, end_date=end_date)
        daily_rows = daily.get("rows", [])

        if daily_rows:
            daily_views = [int(r[1]) for r in daily_rows]  # index 1 = views
            metrics["daily_views"] = daily_views

            # View trend
            if len(daily_views) >= 2:
                first_half = sum(daily_views[:len(daily_views) // 2])
                second_half = sum(daily_views[len(daily_views) // 2:])
                if first_half > 0:
                    metrics["view_trend_pct"] = (second_half - first_half) / first_half * 100

            avg_daily = sum(daily_views) / len(daily_views) if daily_views else 0
            peak_day_views = max(daily_views) if daily_views else 0
            low_day_views = min(daily_views) if daily_views else 0

            print(f"\n  {BOLD}View Trends:{RESET}")
            print(f"    Average Daily Views:  {avg_daily:,.0f}")
            print(f"    Peak Day:             {format_count(peak_day_views)}")
            print(f"    Low Day:              {format_count(low_day_views)}")
            print(f"    Trend:                {_trend_arrow(daily_views)}")

    except Exception as e:
        print(f"  {DIM}Daily analytics unavailable: {e}{RESET}")

    # Top and worst performing videos
    try:
        print(f"\n{DIM}Fetching top videos...{RESET}")
        top_vids = client.get_top_videos_analytics(
            start_date=start_date, end_date=end_date, max_results=10
        )
        top_rows = top_vids.get("rows", [])

        if top_rows:
            # Get video details for the IDs
            video_ids = [r[0] for r in top_rows]
            video_details = client.get_videos_batch(video_ids)
            vid_map = {v["id"]: v for v in video_details}

            print(f"\n  {BOLD}Top Performing Videos:{RESET}")
            table_rows = []
            for r in top_rows[:5]:
                vid_id = r[0]
                views = int(r[1])
                detail = vid_map.get(vid_id, {})
                title = detail.get("snippet", {}).get("title", vid_id)[:40]
                table_rows.append([title, format_count(views)])

            print(format_table(
                headers=["Video", "Views"],
                rows=table_rows,
            ))

            if len(top_rows) >= 5:
                # Worst performers (last few)
                print(f"\n  {BOLD}Lowest Performing Videos:{RESET}")
                bottom_rows = []
                for r in reversed(top_rows[-3:]):
                    vid_id = r[0]
                    views = int(r[1])
                    detail = vid_map.get(vid_id, {})
                    title = detail.get("snippet", {}).get("title", vid_id)[:40]
                    bottom_rows.append([title, format_count(views)])

                print(format_table(
                    headers=["Video", "Views"],
                    rows=bottom_rows,
                ))

    except Exception as e:
        print(f"  {DIM}Top videos analytics unavailable: {e}{RESET}")

    # Upload consistency
    print(f"\n{DIM}Analyzing upload consistency...{RESET}")
    try:
        recent_videos = client.list_channel_videos(channel_id=channel_id, max_results=50)

        if recent_videos:
            # Count videos in the audit period
            period_start = now - timedelta(days=days)
            period_videos = []
            for v in recent_videos:
                pub = v.get("snippet", {}).get("publishedAt", "")
                try:
                    pub_dt = datetime.fromisoformat(pub.replace("Z", "+00:00"))
                    if pub_dt >= period_start:
                        period_videos.append(v)
                except (ValueError, AttributeError):
                    pass

            uploads_per_week = len(period_videos) / (days / 7) if days > 0 else 0
            metrics["uploads_per_week"] = uploads_per_week

            print(f"\n  {BOLD}Upload Consistency:{RESET}")
            print(f"    Videos in period:     {len(period_videos)}")
            print(f"    Uploads per week:     {uploads_per_week:.1f}")

            if uploads_per_week >= 2:
                print(f"    Assessment:           {GREEN}Excellent consistency{RESET}")
            elif uploads_per_week >= 1:
                print(f"    Assessment:           {GREEN}Good consistency{RESET}")
            elif uploads_per_week >= 0.5:
                print(f"    Assessment:           {YELLOW}Could upload more frequently{RESET}")
            else:
                print(f"    Assessment:           {RED}Inconsistent — aim for weekly uploads{RESET}")

            # Outlier analysis on period videos
            if len(period_videos) >= 3:
                video_inputs = []
                for v in period_videos:
                    s = v.get("snippet", {})
                    st = v.get("statistics", {})
                    cd = v.get("contentDetails", {})
                    try:
                        pub_dt = datetime.fromisoformat(
                            s.get("publishedAt", "").replace("Z", "+00:00")
                        )
                    except (ValueError, AttributeError):
                        pub_dt = now

                    dur = cd.get("duration", "PT0S")
                    dur_match = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", dur)
                    dur_secs = 0
                    if dur_match:
                        h, m, s_val = dur_match.groups()
                        dur_secs = int(h or 0) * 3600 + int(m or 0) * 60 + int(s_val or 0)

                    video_inputs.append(VideoInput(
                        video_id=v.get("id", ""),
                        title=s.get("title", ""),
                        view_count=int(st.get("viewCount", 0)),
                        like_count=int(st.get("likeCount", 0)),
                        comment_count=int(st.get("commentCount", 0)),
                        published_at=pub_dt,
                        duration_seconds=dur_secs,
                        subscriber_count_approx=subs,
                    ))

                analysis = compute_outlier_scores(
                    videos=video_inputs,
                    channel_id=channel_id,
                )

                if analysis.top_outliers:
                    print(f"\n  {BOLD}Outlier Videos (over-performed):{RESET}")
                    outlier_rows = []
                    for o in analysis.top_outliers[:3]:
                        if o.outlier_score >= 50:
                            outlier_rows.append([
                                o.title[:40],
                                format_count(o.raw_views),
                                f"{o.outlier_score:.0f}",
                            ])
                    if outlier_rows:
                        print(format_table(
                            headers=["Video", "Views", "Outlier Score"],
                            rows=outlier_rows,
                        ))
                    else:
                        print(f"    {DIM}No significant outliers detected.{RESET}")

    except Exception as e:
        print(f"  {DIM}Upload analysis unavailable: {e}{RESET}")

    # Overall health grade
    grade = _health_grade(metrics)
    print(f"\n{'=' * 50}")
    print(f"  {BOLD}Overall Channel Health: {grade}")
    print(f"{'=' * 50}")

    return 0
