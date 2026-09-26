"""
SEO scoring and optimization suggestions.

Commands:
    seo score <video-id>              Full SEO score with breakdown
    seo suggest <video-id>            Score + actionable improvement suggestions
    seo suggest <video-id> --ai       Score + AI-powered improvement suggestions
"""

import json
import logging
import re
import sys
from argparse import Namespace
from pathlib import Path
from typing import Dict, List, Optional

_TOOL_DIR = Path(__file__).resolve().parent.parent
if str(_TOOL_DIR) not in sys.path:
    sys.path.insert(0, str(_TOOL_DIR))

from client import (
    YouTubeIntelClient,
    extract_video_id,
    format_count,
    format_table,
    GREEN, RED, YELLOW, CYAN, BOLD, DIM, RESET,
)
from db import save_seo_score, get_latest_seo_score
from algo_loader import SEOScorer

logger = logging.getLogger(__name__)


def _generate_ai_suggestions(
    video_data: dict,
    result: dict,
    target_keyword: str = "",
) -> Optional[List[Dict[str, str]]]:
    """
    Generate AI-powered SEO improvement suggestions using Claude.

    Parameters
    ----------
    video_data : dict
        Raw YouTube API video resource.
    result : dict-like
        SEO scoring result (SEOResult with dict access).
    target_keyword : str
        The keyword the video is being scored against.

    Returns
    -------
    list of dicts or None
        Each dict has: suggestion, impact (high/medium/low), category.
        Returns None if AI is unavailable.
    """
    from ai_helper import call_claude

    snippet = video_data.get("snippet", {})
    stats = video_data.get("statistics", {})

    title = snippet.get("title", "")
    description = snippet.get("description", "")
    tags = snippet.get("tags", [])

    overall_score = result["overall_score"]
    breakdown = result["breakdown"]

    # Determine keyword
    keyword = target_keyword
    if not keyword:
        # Try to get from SEOResult attribute
        keyword = getattr(result, "target_keyword", "") or ""

    # Build the breakdown string for the prompt
    breakdown_lines = []
    for factor_name, data in breakdown.items():
        score = data.get("score", 0)
        detail = data.get("detail", "")
        weight = data.get("weight_pct", 0)
        breakdown_lines.append(f"  {factor_name}: {score:.0f}/100 (weight: {weight}%) - {detail}")
    breakdown_str = "\n".join(breakdown_lines)

    # Truncate description for the prompt
    desc_preview = description[:500] if description else "(empty)"

    prompt = (
        f"You are a YouTube SEO expert. Analyze this video and provide "
        f"specific optimization suggestions.\n\n"
        f"Video title: {title}\n"
        f"Description (first 500 chars): {desc_preview}\n"
        f"Tags: {', '.join(tags[:20]) if tags else '(none)'}\n"
        f"Target keyword: {keyword or '(auto-detected)'}\n"
        f"Current SEO score: {overall_score:.1f}/100\n\n"
        f"Score breakdown:\n{breakdown_str}\n\n"
        f"Provide 5-7 specific, actionable suggestions to improve this "
        f"video's YouTube SEO. Focus on what would have the most impact. "
        f"Be specific -- don't say \"improve your title,\" say exactly what "
        f"the title should be changed to.\n\n"
        f"Format as JSON array: "
        f'[{{"suggestion": "...", "impact": "high|medium|low", '
        f'"category": "title|description|tags|thumbnail|technical"}}]'
    )

    response = call_claude(prompt, max_tokens=1536)
    if response is None:
        return None

    # Parse the JSON response
    text = response.strip()
    # Strip markdown code fences if present
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\n?", "", text)
        text = re.sub(r"\n?```\s*$", "", text)
        text = text.strip()

    try:
        suggestions = json.loads(text)
        if not isinstance(suggestions, list):
            logger.debug("AI response was not a JSON array: %s", type(suggestions))
            return None

        validated: List[Dict[str, str]] = []
        for item in suggestions:
            if isinstance(item, dict) and "suggestion" in item:
                validated.append({
                    "suggestion": str(item.get("suggestion", "")),
                    "impact": str(item.get("impact", "medium")).lower(),
                    "category": str(item.get("category", "")).lower(),
                })
        return validated if validated else None

    except (json.JSONDecodeError, ValueError) as e:
        logger.debug("Failed to parse AI SEO suggestions: %s", e)
        return None


def _grade_color(grade: str) -> str:
    """Return ANSI color for letter grade."""
    if grade == "A":
        return GREEN
    elif grade == "B":
        return GREEN
    elif grade == "C":
        return YELLOW
    elif grade == "D":
        return RED
    else:
        return RED


def _score_bar(score: float, max_score: float = 100, width: int = 15) -> str:
    """Render a small visual bar for a score."""
    ratio = score / max_score if max_score > 0 else 0
    filled = int(ratio * width)
    empty = width - filled
    if ratio >= 0.7:
        color = GREEN
    elif ratio >= 0.4:
        color = YELLOW
    else:
        color = RED
    return f"{color}{'#' * filled}{DIM}{'.' * empty}{RESET}"


def _print_seo_result(
    video_data: dict,
    result: dict,
    show_suggestions: bool = False,
) -> None:
    """Print formatted SEO score output."""
    snippet = video_data.get("snippet", {})
    title = snippet.get("title", "Unknown")
    channel = snippet.get("channelTitle", "Unknown")

    overall = result.get("overall_score", 0)
    grade = result.get("grade", "?")
    breakdown = result.get("breakdown", {})
    suggestions = result.get("suggestions", [])

    gc = _grade_color(grade)

    print(f"\n{BOLD}{CYAN}SEO Analysis: {title}{RESET}")
    print(f"  {DIM}Channel: {channel}{RESET}\n")

    # Overall score
    print(f"  {BOLD}Overall Score:{RESET} {gc}{BOLD}{overall:.1f}/100{RESET}  Grade: {gc}{BOLD}{grade}{RESET}")
    print(f"  {_score_bar(overall, width=30)}")
    print()

    # Factor breakdown
    print(f"  {BOLD}Factor Breakdown:{RESET}")

    # Friendly names for factors
    factor_names = {
        "title_length": "Title Length",
        "title_keywords": "Title Keywords",
        "description_length": "Description Length",
        "description_links": "Description Links",
        "tags_count": "Tags Count",
        "tags_relevance": "Tags Relevance",
        "thumbnail_custom": "Custom Thumbnail",
        "category_set": "Category Set",
        "engagement_rate": "Engagement Rate",
    }

    # Weights from SEOScorer
    weights = SEOScorer.WEIGHTS

    rows = []
    for factor, data in breakdown.items():
        name = factor_names.get(factor, factor)
        score = data["score"]
        detail = data.get("detail", "")
        weight = weights.get(factor, 0)
        weighted = score * (weight / 100)
        bar = _score_bar(score)

        rows.append([
            name,
            f"{score:.0f}",
            f"x{weight}%",
            f"{weighted:.1f}",
            bar,
            f"{DIM}{detail}{RESET}",
        ])

    print(format_table(
        headers=["Factor", "Score", "Weight", "Weighted", "Bar", "Detail"],
        rows=rows,
    ))

    if show_suggestions and suggestions:
        print(f"\n  {BOLD}{YELLOW}Improvement Suggestions:{RESET}")
        for i, suggestion in enumerate(suggestions, 1):
            print(f"    {YELLOW}{i}.{RESET} {suggestion}")
    elif not suggestions:
        print(f"\n  {GREEN}No major issues found. SEO looks solid!{RESET}")

    print()


def run_score(client: YouTubeIntelClient, args: Namespace) -> int:
    """Full SEO score with breakdown."""
    video_id = extract_video_id(args.video_id)

    print(f"{DIM}Fetching video data...{RESET}")
    video_data = client.get_video(video_id)

    scorer = SEOScorer()
    result = scorer.score(video_data)

    # Save to DB
    save_seo_score(
        video_id=video_id,
        overall_score=result["overall_score"],
        breakdown=result["breakdown"],
    )

    _print_seo_result(video_data, result, show_suggestions=False)
    return 0


def run_suggest(client: YouTubeIntelClient, args: Namespace) -> int:
    """SEO score with actionable suggestions."""
    video_id = extract_video_id(args.video_id)
    use_ai = getattr(args, "ai", False)

    print(f"{DIM}Fetching video data...{RESET}")
    video_data = client.get_video(video_id)

    scorer = SEOScorer()
    result = scorer.score(video_data)

    # Save to DB
    save_seo_score(
        video_id=video_id,
        overall_score=result["overall_score"],
        breakdown=result["breakdown"],
    )

    # Always show the standard score breakdown + heuristic suggestions
    _print_seo_result(video_data, result, show_suggestions=True)

    # If --ai requested, append AI-powered suggestions
    if use_ai:
        print(f"  {DIM}Generating AI-powered suggestions...{RESET}\n")
        ai_suggestions = _generate_ai_suggestions(
            video_data=video_data,
            result=result,
        )

        if ai_suggestions is None:
            print(f"  {YELLOW}AI unavailable — showing heuristic suggestions only.{RESET}\n")
        else:
            # Impact color mapping
            impact_colors = {
                "high": RED,
                "medium": YELLOW,
                "low": DIM,
            }

            print(f"  {BOLD}{CYAN}AI-Powered Suggestions:{RESET}")
            print()
            for i, s in enumerate(ai_suggestions, 1):
                impact = s.get("impact", "medium")
                category = s.get("category", "")
                ic = impact_colors.get(impact, DIM)

                print(f"    {BOLD}{i}.{RESET} {s['suggestion']}")
                print(f"       {ic}Impact: {impact}{RESET}  {DIM}Category: {category}{RESET}")
                print()

            print(f"  {DIM}Powered by Claude (claude-sonnet-4-20250514){RESET}\n")

    return 0


def run(client: YouTubeIntelClient, args: Namespace) -> int:
    """Route SEO subcommands."""
    action = getattr(args, "seo_action", None)

    if action == "score":
        return run_score(client, args)
    elif action == "suggest":
        return run_suggest(client, args)
    else:
        print(f"{YELLOW}Please specify an action: score or suggest{RESET}", file=sys.stderr)
        print(f"{DIM}Usage: youtube-intel seo <score|suggest> <video-id>{RESET}", file=sys.stderr)
        return 1
