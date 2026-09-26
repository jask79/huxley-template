"""Account and media insights commands."""

import logging

from ..cache import FileCache
from ..exceptions import APIError

logger = logging.getLogger("instagram-intel.insights")
from ..config import (
    ACCOUNT_METRICS_LIFETIME, ACCOUNT_METRICS_TIME_SERIES,
    ACCOUNT_METRICS_TOTAL_VALUE, BOLD, CYAN, DIM,
    EXIT_EXPECTED_ERROR, EXIT_SUCCESS, GREEN, MEDIA_METRICS_DEFAULT,
    MEDIA_METRICS_REEL, MEDIA_METRICS_VIDEO, RESET, YELLOW,
)
from ..formatters import (
    format_table, human_number, json_output, print_error,
    print_footer, print_header,
)


def cmd_own_insights(args, client) -> int:
    """Account-level impressions, reach, follower trends."""
    period = getattr(args, "period", "day")
    since = getattr(args, "since", "")
    until = getattr(args, "until", "")
    cache = _get_cache(args)
    filters = {
        "command": "own-insights", "period": period,
        "since": since, "until": until,
    }

    if cache:
        cached = cache.get("own-insights", filters)
        if cached:
            return _output_cached_insights(cached, args)

    # Fetch insights — v24.0 requires splitting by metric_type
    insights = []
    try:
        if period == "lifetime":
            insights = client.get_account_insights(
                metrics=ACCOUNT_METRICS_LIFETIME, period=period,
                since=since, until=until,
            )
        else:
            # Time-series metrics (regular period-based)
            if ACCOUNT_METRICS_TIME_SERIES:
                try:
                    ts_insights = client.get_account_insights(
                        metrics=ACCOUNT_METRICS_TIME_SERIES, period=period,
                        since=since, until=until,
                    )
                    insights.extend(ts_insights)
                except Exception as e:
                    logger.debug("Time-series metrics failed: %s", e)

            # Total value metrics (need metric_type=total_value)
            if ACCOUNT_METRICS_TOTAL_VALUE:
                try:
                    tv_insights = client.get_account_insights(
                        metrics=ACCOUNT_METRICS_TOTAL_VALUE, period=period,
                        since=since, until=until,
                        metric_type="total_value",
                    )
                    insights.extend(tv_insights)
                except Exception as e:
                    logger.debug("Total-value metrics failed: %s", e)

    except Exception as e:
        if args.json:
            json_output({"error": str(e), "type": "api_error"})
        else:
            print_error(
                str(e),
                "Insights require Instagram Business or Creator account. "
                "Period must match metric type (day/week/days_28 for most, "
                "lifetime for follower_count).",
            )
        return EXIT_EXPECTED_ERROR

    if not insights:
        if args.json:
            json_output({
                "success": True, "data": [], "count": 0, "cached": False,
                "warnings": ["No insights available for this account/period."],
            })
        else:
            print_header("own-insights", {"period": period})
            print("  (no insights available)")
            print_footer(0)
        return EXIT_SUCCESS

    data = [i.to_dict() for i in insights]

    if cache:
        cache.set("own-insights", filters, {
            "data": data, "count": len(data),
        })

    if args.json:
        json_output({
            "success": True, "data": data,
            "count": len(data), "cached": False,
        })
    else:
        print_header("own-insights", {"period": period})
        _print_insights(insights)
        print_footer(len(insights))

    return EXIT_SUCCESS


def cmd_media_insights(args, client) -> int:
    """Per-post performance metrics."""
    media_id = args.media_id
    cache = _get_cache(args)
    filters = {"command": "media-insights", "media_id": media_id}

    if cache:
        cached = cache.get("media-insights", filters)
        if cached:
            return _output_cached_insights(cached, args)

    # Try default metrics first, fall back to video/reel metrics on metric mismatch
    try:
        insights = client.get_media_insights(
            media_id, metrics=MEDIA_METRICS_DEFAULT,
        )
    except APIError as e:
        logger.debug("Default metrics failed (code=%s): %s", getattr(e, 'code', '?'), e)
        try:
            insights = client.get_media_insights(
                media_id, metrics=MEDIA_METRICS_REEL,
            )
        except Exception as e:
            if args.json:
                json_output({"error": str(e), "type": "api_error"})
            else:
                print_error(
                    str(e),
                    "Different media types support different metrics. "
                    "Reels use: plays, reach, saved, shares, total_interactions.",
                )
            return EXIT_EXPECTED_ERROR

    data = [i.to_dict() for i in insights]

    if cache:
        cache.set("media-insights", filters, {
            "data": data, "count": len(data),
        })

    if args.json:
        json_output({
            "success": True, "data": data,
            "count": len(data), "cached": False,
        })
    else:
        print_header("media-insights", {"media_id": media_id})
        _print_insights(insights)
        print_footer(len(insights))

    return EXIT_SUCCESS


# ---------------------------------------------------------------------------
# Display helpers
# ---------------------------------------------------------------------------

def _print_insights(insights) -> None:
    """Render insights as formatted terminal output."""
    if not insights:
        print("  (no insights available)")
        return

    for metric in insights:
        print(f"  {BOLD}{metric.name}{RESET} {DIM}({metric.period}){RESET}")
        if metric.title:
            print(f"  {DIM}{metric.title}{RESET}")

        if metric.values:
            for val in metric.values:
                value = val.get("value", "N/A")
                end_time = val.get("end_time", "")
                if isinstance(value, (int, float)):
                    value_str = human_number(int(value))
                elif isinstance(value, dict):
                    # Some metrics return breakdowns as dicts
                    parts = [f"{k}: {v}" for k, v in value.items()]
                    value_str = ", ".join(parts)
                else:
                    value_str = str(value)

                if end_time:
                    from ..formatters import ts_to_str
                    print(f"    {CYAN}{ts_to_str(end_time)}{RESET}: {value_str}")
                else:
                    print(f"    {GREEN}{value_str}{RESET}")
        print()


# ---------------------------------------------------------------------------
# Cache helpers
# ---------------------------------------------------------------------------

def _get_cache(args) -> FileCache | None:
    if getattr(args, "no_cache", False):
        return None
    return FileCache(ttl=args.cache_ttl)


def _output_cached_insights(cached: dict, args) -> int:
    data = cached.get("data", [])
    count = cached.get("count", len(data))
    if args.json:
        json_output({
            "success": True, "data": data,
            "count": count, "cached": True,
        })
    else:
        from ..models import InsightMetric
        insights = [InsightMetric(**d) for d in data]
        print_header("insights (cached)")
        _print_insights(insights)
        print_footer(count, cached=True)
    return EXIT_SUCCESS
