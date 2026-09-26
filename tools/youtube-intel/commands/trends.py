"""
Trend discovery — mine YouTube for trending topics in a niche.

Commands:
    trends <niche> [--depth 3]   Discover trending topics via autocomplete mining
"""

import re
import sys
from argparse import Namespace
from collections import Counter, deque
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Set, Tuple

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


def _mine_autocomplete(
    seed: str,
    depth: int = 3,
    max_per_level: int = 5,
) -> Tuple[List[str], Dict[str, int]]:
    """
    Mine YouTube autocomplete suggestions recursively.

    Starts with a seed query and expands by appending letters a-z and
    using top suggestions as new seeds.

    Returns:
        all_suggestions: flat list of unique suggestions
        frequency: how many times each term appeared across queries
    """
    seen: Set[str] = set()
    frequency: Counter = Counter()
    all_suggestions: List[str] = []

    queue: deque[Tuple[str, int]] = deque([(seed, 0)])
    processed: Set[str] = set()

    while queue:
        query, level = queue.popleft()

        if query.lower() in processed:
            continue
        processed.add(query.lower())

        suggestions = youtube_autocomplete(query)
        for s in suggestions:
            s_lower = s.lower().strip()
            frequency[s_lower] += 1
            if s_lower not in seen:
                seen.add(s_lower)
                all_suggestions.append(s)

        # Expand to next level
        if level < depth - 1:
            # Use top suggestions as new seeds
            for s in suggestions[:max_per_level]:
                if s.lower().strip() not in processed:
                    queue.append((s, level + 1))

            # Also try seed + common suffixes for broader coverage
            suffixes = ["a", "b", "c", "h", "t", "w", "for", "vs", "how"]
            for suffix in suffixes[:3]:  # Limit to avoid too many queries
                expanded = f"{query} {suffix}"
                if expanded.lower() not in processed:
                    queue.append((expanded, level + 1))

    return all_suggestions, dict(frequency)


def _identify_trending_patterns(
    suggestions: List[str],
    frequency: Dict[str, int],
    niche: str,
) -> List[Tuple[str, int, str]]:
    """
    Identify trending patterns from autocomplete data.

    Uses additive scoring: base frequency + fixed bonuses per signal.
    Each signal adds a bounded contribution rather than multiplying,
    so multi-signal terms rank higher without burying single-signal terms.

    Category tracks the PRIMARY signal (highest-priority match), not
    last-match-wins.

    Returns list of (term, score, category) sorted by score.
    Categories: trending, recurring, high-intent, long-tail, general
    """
    results: List[Tuple[str, int, str]] = []
    niche_lower = niche.lower()

    # Category priorities: higher = stronger signal, wins as primary
    CATEGORY_PRIORITY = {
        "general": 0,
        "long-tail": 1,
        "recurring": 2,
        "high-intent": 3,
        "trending": 4,
    }

    # Dynamic year pattern: current year through +4 years
    current_year = datetime.now().year
    year_pattern = "|".join(str(y) for y in range(current_year, current_year + 5))

    for term in suggestions:
        term_lower = term.lower().strip()
        freq = frequency.get(term_lower, 1)
        word_count = len(term_lower.split())

        # Base score = frequency (1-based)
        score = freq
        category = "general"

        # Recurring (appeared in multiple autocomplete queries): +3
        if freq >= 3:
            score += 3
            if CATEGORY_PRIORITY["recurring"] > CATEGORY_PRIORITY[category]:
                category = "recurring"

        # Year mentions suggest trending/timely content: +5
        if re.search(r'\b(' + year_pattern + r')\b', term_lower):
            score += 5
            if CATEGORY_PRIORITY["trending"] > CATEGORY_PRIORITY[category]:
                category = "trending"

        # "How to", "what is", "best" etc. suggest search intent: +4
        intent_words = ["how to", "what is", "best", "top", "vs", "review", "tutorial", "guide"]
        for iw in intent_words:
            if iw in term_lower:
                score += 4
                if CATEGORY_PRIORITY["high-intent"] > CATEGORY_PRIORITY[category]:
                    category = "high-intent"
                break

        # Long-tail (4+ words) with niche term = specific opportunity: +2
        if word_count >= 4 and niche_lower in term_lower:
            score += 2
            if CATEGORY_PRIORITY["long-tail"] > CATEGORY_PRIORITY[category]:
                category = "long-tail"

        results.append((term, int(score), category))

    # Sort by score descending
    results.sort(key=lambda x: x[1], reverse=True)
    return results


def run(client: YouTubeIntelClient, args: Namespace) -> int:
    """Discover trending topics in a niche."""
    niche = args.niche
    depth = args.depth

    print(f"\n{BOLD}{CYAN}Trend Discovery: {niche}{RESET}")
    print(f"  {DIM}Mining YouTube autocomplete (depth={depth})...{RESET}\n")

    # Mine autocomplete
    all_suggestions, frequency = _mine_autocomplete(niche, depth=depth)

    if not all_suggestions:
        print(f"{YELLOW}No autocomplete suggestions found for '{niche}'.{RESET}")
        print(f"{DIM}Try a broader term or check your spelling.{RESET}")
        return 0

    print(f"  {DIM}Found {len(all_suggestions)} unique suggestions{RESET}\n")

    # Identify patterns
    trends = _identify_trending_patterns(all_suggestions, frequency, niche)

    # Display trending searches
    print(f"  {BOLD}Trending Searches:{RESET}")
    trending = [(t, s, c) for t, s, c in trends if c == "trending"][:10]
    if trending:
        rows = [[t, str(s), f"{GREEN}trending{RESET}"] for t, s, c in trending]
        print(format_table(headers=["Search Term", "Score", "Type"], rows=rows))
    else:
        print(f"  {DIM}No explicitly trending terms detected (no year references).{RESET}")

    # High-intent searches
    print(f"\n  {BOLD}High-Intent Searches:{RESET}")
    high_intent = [(t, s, c) for t, s, c in trends if c == "high-intent"][:10]
    if high_intent:
        rows = [[t, str(s), f"{CYAN}high-intent{RESET}"] for t, s, c in high_intent]
        print(format_table(headers=["Search Term", "Score", "Type"], rows=rows))
    else:
        print(f"  {DIM}No high-intent terms detected.{RESET}")

    # Recurring themes
    print(f"\n  {BOLD}Recurring Themes:{RESET}")
    recurring = [(t, s, c) for t, s, c in trends if c == "recurring"][:10]
    if recurring:
        rows = [[t, str(s), f"{YELLOW}recurring{RESET}"] for t, s, c in recurring]
        print(format_table(headers=["Search Term", "Score", "Type"], rows=rows))
    else:
        print(f"  {DIM}No recurring themes detected.{RESET}")

    # Long-tail opportunities
    print(f"\n  {BOLD}Long-Tail Opportunities:{RESET}")
    long_tail = [(t, s, c) for t, s, c in trends if c == "long-tail"][:10]
    if long_tail:
        rows = [[t, str(s), f"{DIM}long-tail{RESET}"] for t, s, c in long_tail]
        print(format_table(headers=["Search Term", "Score", "Type"], rows=rows))
    else:
        print(f"  {DIM}No long-tail opportunities detected.{RESET}")

    # Rising videos in this niche
    print(f"\n  {BOLD}Rising Videos:{RESET}")
    print(f"  {DIM}Searching for recent videos in '{niche}'...{RESET}")
    try:
        recent = client.search_videos(
            query=niche, max_results=5, order="date"
        )
        if recent:
            vid_rows = []
            for v in recent:
                snippet = v.get("snippet", {})
                stats = v.get("statistics", {})
                title = snippet.get("title", "")[:45]
                views = format_count(int(stats.get("viewCount", 0)))
                channel = snippet.get("channelTitle", "")[:20]
                vid_rows.append([title, channel, views])

            print(format_table(
                headers=["Title", "Channel", "Views"],
                rows=vid_rows,
            ))
        else:
            print(f"  {DIM}No recent videos found.{RESET}")
    except Exception as e:
        print(f"  {YELLOW}Could not fetch rising videos: {e}{RESET}")

    # Content gaps summary
    top_5 = trends[:5]
    if top_5:
        print(f"\n  {BOLD}{GREEN}Top Content Opportunities:{RESET}")
        for i, (term, score, category) in enumerate(top_5, 1):
            print(f"    {GREEN}{i}.{RESET} \"{term}\" {DIM}(score: {score}, type: {category}){RESET}")

    return 0
