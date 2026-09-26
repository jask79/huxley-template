"""
Content ideation — generate video ideas based on channel data and trends.

Commands:
    ideas [--count 10] [--niche X]       Generate content ideas (heuristic)
    ideas [--count 10] [--niche X] --ai  Generate content ideas (AI-powered)
"""

import json
import logging
import re
import sys
from argparse import Namespace
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

_TOOL_DIR = Path(__file__).resolve().parent.parent
if str(_TOOL_DIR) not in sys.path:
    sys.path.insert(0, str(_TOOL_DIR))

from client import (
    YouTubeIntelClient,
    youtube_autocomplete,
    format_count,
    format_table,
    GREEN, RED, YELLOW, CYAN, BOLD, DIM, RESET,
)

logger = logging.getLogger(__name__)


def _extract_channel_topics(videos: list) -> List[Tuple[str, int]]:
    """
    Extract common topic words from channel video titles.

    Returns (word, frequency) pairs sorted by frequency descending.
    """
    from collections import Counter

    # Common stop words to exclude
    stop_words = {
        "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
        "have", "has", "had", "do", "does", "did", "will", "would", "could",
        "should", "may", "might", "can", "shall", "i", "you", "he", "she",
        "it", "we", "they", "my", "your", "his", "her", "its", "our", "their",
        "this", "that", "these", "those", "in", "on", "at", "to", "for",
        "of", "with", "by", "from", "as", "into", "about", "and", "or",
        "but", "not", "no", "so", "if", "then", "than", "too", "very",
        "just", "how", "what", "when", "where", "why", "which", "who",
        "all", "each", "every", "both", "few", "more", "most", "other",
        "some", "such", "only", "own", "same", "new", "old", "get",
        "|", "-", ":", "&", "!", "?", "#", "//", "ft", "ft.", "vs",
    }

    word_counts: Counter = Counter()
    for v in videos:
        title = v.get("snippet", {}).get("title", "").lower()
        # Strip common punctuation
        for ch in "!?|#()[]{}\"'.,;:":
            title = title.replace(ch, " ")
        words = title.split()
        for w in words:
            w = w.strip("-_")
            if len(w) > 2 and w not in stop_words:
                word_counts[w] += 1

    return word_counts.most_common(20)


def _extract_top_performing_themes(videos: list) -> List[str]:
    """Extract title themes from top-performing videos by views."""
    sorted_vids = sorted(
        videos,
        key=lambda v: int(v.get("statistics", {}).get("viewCount", 0)),
        reverse=True,
    )
    themes = []
    for v in sorted_vids[:10]:
        title = v.get("snippet", {}).get("title", "")
        if title:
            themes.append(title)
    return themes


def _generate_ai_ideas(
    channel_topics: List[Tuple[str, int]],
    top_themes: List[str],
    trending_terms: List[str],
    niche: str,
    count: int,
) -> Optional[List[Dict[str, str]]]:
    """
    Generate content ideas using the Claude AI API.

    Returns a list of idea dicts with keys: title, description, reasoning.
    Returns None if AI is unavailable (missing key, API error, etc.).
    """
    from ai_helper import call_claude

    # Build the topics string from channel data
    if channel_topics:
        topics_str = ", ".join(f"{word} ({freq}x)" for word, freq in channel_topics[:10])
    else:
        topics_str = "(no existing video data)"

    # Build the trending terms string
    if trending_terms:
        trending_str = ", ".join(trending_terms[:15])
    else:
        trending_str = "(no trending data found)"

    # Include top-performing themes for context
    themes_context = ""
    if top_themes:
        themes_context = (
            "\n\nTop-performing video titles on this channel:\n"
            + "\n".join(f"- {t}" for t in top_themes[:5])
        )

    prompt = (
        f"You are a YouTube content strategist. Based on the following data "
        f"about a channel and its niche, generate {count} video ideas.\n\n"
        f"Channel's existing topics: {topics_str}\n"
        f"Trending searches in this niche: {trending_str}\n"
        f"Niche: {niche}"
        f"{themes_context}\n\n"
        f"For each idea, provide:\n"
        f"1. Video title (optimized for YouTube search and CTR)\n"
        f"2. One-sentence description\n"
        f"3. Why this would perform well (based on the data)\n\n"
        f"Format as JSON array: "
        f'[{{"title": "...", "description": "...", "reasoning": "..."}}]'
    )

    response = call_claude(prompt, max_tokens=2048)
    if response is None:
        return None

    # Parse the JSON response — Claude may wrap it in markdown code fences
    text = response.strip()
    # Strip markdown code fences if present
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\n?", "", text)
        text = re.sub(r"\n?```\s*$", "", text)
        text = text.strip()

    try:
        ideas = json.loads(text)
        if not isinstance(ideas, list):
            logger.debug("AI response was not a JSON array: %s", type(ideas))
            return None

        # Validate and normalize each idea
        validated: List[Dict[str, str]] = []
        for item in ideas:
            if isinstance(item, dict) and "title" in item:
                validated.append({
                    "title": str(item.get("title", "")),
                    "description": str(item.get("description", "")),
                    "reasoning": str(item.get("reasoning", "")),
                })
        return validated[:count] if validated else None

    except (json.JSONDecodeError, ValueError) as e:
        logger.debug("Failed to parse AI ideas response: %s", e)
        return None


def _generate_ideas(
    channel_topics: List[Tuple[str, int]],
    top_themes: List[str],
    trending_terms: List[str],
    niche: str,
    count: int,
) -> List[Dict[str, str]]:
    """
    Generate content ideas using heuristic combination of channel data + trends.

    Strategy:
    1. Combine top channel topics with trending search terms
    2. Create title templates using proven formats
    3. Mix channel strengths with search demand
    """
    ideas: List[Dict[str, str]] = []
    seen_lower: Set[str] = set()

    # Title templates (proven YouTube formats)
    templates = [
        "{topic} — Complete Beginner's Guide ({year})",
        "How to {topic} in {year} (Step by Step)",
        "{topic} vs {topic2}: Which Is Better?",
        "Top 10 {topic} Tips You Need to Know",
        "I Tried {trend} for 30 Days — Here's What Happened",
        "Why {topic} Is {trend} Right Now",
        "The Truth About {topic} That Nobody Tells You",
        "{topic} Tutorial for Beginners ({year})",
        "Best {topic} in {year} (Honest Review)",
        "{topic}: Everything You Need to Know",
        "Stop Making These {topic} Mistakes",
        "{trend}: A {topic} Perspective",
        "What I Wish I Knew Before Starting {topic}",
        "{topic} Tips That Actually Work in {year}",
        "Is {trend} Worth It? ({topic} Edition)",
    ]

    year = str(datetime.now().year)
    topic_words = [t[0] for t in channel_topics[:10]]
    topic_pairs = list(zip(topic_words[::2], topic_words[1::2]))

    for template in templates:
        if len(ideas) >= count:
            break

        for topic in topic_words[:5]:
            if len(ideas) >= count:
                break

            # Use a trending term if available
            trend = ""
            if trending_terms:
                for t in trending_terms:
                    if t.lower() != topic.lower():
                        trend = t
                        break

            # Find a second topic for vs-style
            topic2 = ""
            for t in topic_words:
                if t != topic:
                    topic2 = t
                    break

            idea_title = template.format(
                topic=topic.title(),
                topic2=topic2.title() if topic2 else "Alternative",
                trend=trend.title() if trend else niche.title(),
                year=year,
            )

            idea_lower = idea_title.lower()
            if idea_lower not in seen_lower:
                seen_lower.add(idea_lower)

                # Determine source/reasoning
                source = "channel topics"
                if trend and trend.lower() in idea_lower:
                    source = "channel + trending"

                ideas.append({
                    "title": idea_title,
                    "source": source,
                    "topic": topic.title(),
                })

    # Add trending-term-based ideas
    for trend in trending_terms:
        if len(ideas) >= count:
            break
        idea_title = f"How to {trend.title()} — Complete Guide ({year})"
        idea_lower = idea_title.lower()
        if idea_lower not in seen_lower:
            seen_lower.add(idea_lower)
            ideas.append({
                "title": idea_title,
                "source": "trending search",
                "topic": trend.title(),
            })

    return ideas[:count]


def run(client: YouTubeIntelClient, args: Namespace) -> int:
    """Generate content ideas."""
    count = args.count
    niche = args.niche or ""

    print(f"\n{BOLD}{CYAN}Content Idea Generator{RESET}\n")

    # Fetch channel data
    print(f"{DIM}Analyzing your channel...{RESET}")
    try:
        channel_data = client.get_channel()
        channel_name = channel_data.get("snippet", {}).get("title", "Your Channel")
    except Exception:
        channel_name = "Your Channel"

    try:
        videos = client.list_channel_videos(max_results=50)
    except Exception:
        videos = []

    if not videos and not niche:
        print(f"{YELLOW}No videos found on your channel and no --niche specified.{RESET}")
        print(f"{DIM}Either upload some videos or specify: --niche \"your topic\"{RESET}")
        return 1

    # Extract channel topics from existing videos
    channel_topics: List[Tuple[str, int]] = []
    top_themes: List[str] = []

    if videos:
        channel_topics = _extract_channel_topics(videos)
        top_themes = _extract_top_performing_themes(videos)

        if channel_topics:
            print(f"  {DIM}Top channel topics: {', '.join(t[0] for t in channel_topics[:5])}{RESET}")

    # Determine niche for autocomplete mining
    if not niche:
        if channel_topics:
            niche = " ".join(t[0] for t in channel_topics[:2])
        else:
            niche = channel_name

    # Mine trending terms
    print(f"{DIM}Mining trending searches for '{niche}'...{RESET}")
    suggestions = youtube_autocomplete(niche)

    # Get deeper suggestions
    trending_terms: List[str] = []
    for s in suggestions[:3]:
        deeper = youtube_autocomplete(s)
        trending_terms.extend(deeper[:3])
    trending_terms = list(dict.fromkeys(trending_terms))  # dedupe preserving order

    if trending_terms:
        print(f"  {DIM}Found {len(trending_terms)} trending terms{RESET}")

    # Generate ideas
    use_ai = getattr(args, "ai", False)
    ai_ideas = None

    if use_ai:
        print(f"\n{DIM}Generating ideas with AI (Claude)...{RESET}\n")
        ai_ideas = _generate_ai_ideas(
            channel_topics=channel_topics,
            top_themes=top_themes,
            trending_terms=trending_terms,
            niche=niche,
            count=count,
        )
        if ai_ideas is None:
            print(f"  {YELLOW}AI unavailable — falling back to heuristic mode.{RESET}\n")
    else:
        print(f"\n{DIM}Generating ideas...{RESET}\n")

    if ai_ideas:
        # --- AI-powered output ---
        print(f"  {BOLD}AI-Powered Content Ideas for {channel_name}:{RESET}\n")

        for i, idea in enumerate(ai_ideas, 1):
            print(f"  {BOLD}{i:2d}.{RESET} {GREEN}{idea['title']}{RESET}")
            if idea.get("description"):
                print(f"      {idea['description']}")
            if idea.get("reasoning"):
                print(f"      {DIM}Why: {idea['reasoning']}{RESET}")
            print()

        print(f"  {DIM}{'=' * 50}{RESET}")
        print(f"  {BOLD}Summary:{RESET} {len(ai_ideas)} AI-generated ideas")
        print(f"  {DIM}Powered by Claude ({RESET}claude-sonnet-4-20250514{DIM}){RESET}")
    else:
        # --- Heuristic output ---
        ideas = _generate_ideas(
            channel_topics=channel_topics,
            top_themes=top_themes,
            trending_terms=trending_terms,
            niche=niche,
            count=count,
        )

        if not ideas:
            print(f"{YELLOW}Could not generate ideas. Try specifying a --niche.{RESET}")
            return 1

        print(f"  {BOLD}Content Ideas for {channel_name}:{RESET}\n")

        for i, idea in enumerate(ideas, 1):
            source_color = GREEN if "trending" in idea["source"] else DIM
            print(f"  {BOLD}{i:2d}.{RESET} {idea['title']}")
            print(f"      {source_color}Source: {idea['source']}{RESET}  {DIM}Topic: {idea['topic']}{RESET}")
            print()

        # Summary
        trending_count = sum(1 for i in ideas if "trending" in i["source"])
        channel_count = len(ideas) - trending_count

        print(f"  {DIM}{'=' * 50}{RESET}")
        print(f"  {BOLD}Summary:{RESET} {len(ideas)} ideas generated")
        print(f"    {GREEN}Trending-informed:{RESET} {trending_count}")
        print(f"    {CYAN}Channel-informed:{RESET}  {channel_count}")
        print(f"\n  {DIM}Tip: Use --ai for AI-powered ideation with Claude.{RESET}")

    return 0
