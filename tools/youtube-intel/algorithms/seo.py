"""
SEO Scoring Algorithm for YouTube Videos

Keyword-aware, YouTube-2024-era SEO analysis that scores a video's
optimization across multiple factors and produces actionable suggestions.

Algorithm Design:
-----------------
YouTube SEO has evolved significantly. Tags are nearly irrelevant, while
title optimization, description depth, captions, and post-publish engagement
signals dominate. This scorer reflects that reality.

The score is split into two components:
- **Pre-publish score**: Factors the creator controls before uploading
  (title, description, metadata, tags). This is the actionable SEO score.
- **Post-publish score**: Performance feedback after the video is live
  (engagement rate, view-to-sub ratio). Useful but not directly controllable.

The overall score is a weighted combination of both.

Each factor produces:
- A 0-100 score
- Human-readable details
- Specific, actionable suggestions when score < 70

The scorer is keyword-aware: if a target keyword is provided, title and
description checks are evaluated relative to that keyword. If no keyword
is provided, the primary keyword is inferred from the title.

Complexity: O(n) where n = length of description text (for pattern scanning).
Space:      O(1) beyond the input data.

Weight Structure (2024-era YouTube SEO):
- Title optimization: 25%
- Description quality: 20%
- Captions/transcript: 10%
- Video metadata: 10%
- Technical signals: 10%
- Tags: 5%  (drastically reduced from legacy)
- Engagement (post-publish): 20%
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# Data Structures
# ---------------------------------------------------------------------------

@dataclass
class FactorScore:
    """Score for a single SEO factor."""
    name: str
    score: float          # 0-100
    weight: float         # 0-1
    details: str          # human-readable explanation
    suggestions: List[str] = field(default_factory=list)  # specific fixes

    @property
    def weighted_score(self) -> float:
        """Score contribution to overall (score * weight)."""
        return self.score * self.weight


@dataclass
class SEOResult:
    """Complete SEO analysis result."""
    overall_score: float          # 0-100
    pre_publish_score: float      # 0-100 (what creator controls)
    post_publish_score: float     # 0-100 (performance feedback)
    factor_breakdown: Dict[str, FactorScore]  # per-factor details
    suggestions: List[str]        # all actionable improvement tips
    target_keyword: str           # the keyword scored against
    keyword_detected: bool        # True if keyword was explicitly provided
    grade: str                    # letter grade A-F

    # Legacy compat: dict-like access
    def __getitem__(self, key: str) -> Any:
        """Allow dict-style access for backward compatibility."""
        if key == "overall_score":
            return self.overall_score
        elif key == "grade":
            return self.grade
        elif key == "breakdown":
            return self._legacy_breakdown()
        elif key == "suggestions":
            return self.suggestions
        raise KeyError(key)

    def get(self, key: str, default: Any = None) -> Any:
        """Dict-style .get() for backward compatibility."""
        try:
            return self[key]
        except KeyError:
            return default

    def _legacy_breakdown(self) -> Dict[str, Dict[str, Any]]:
        """Convert factor_breakdown to legacy dict format."""
        result: Dict[str, Dict[str, Any]] = {}
        for key, factor in self.factor_breakdown.items():
            result[key] = {
                "score": factor.score,
                "max": 100,
                "detail": factor.details,
                "weight_pct": round(factor.weight * 100),
            }
        return result


# ---------------------------------------------------------------------------
# Power Words & Keyword Inference
# ---------------------------------------------------------------------------

# Context-aware power word categories (not just a flat checklist)
_POWER_WORD_CATEGORIES = {
    "how_to": ["how to", "how i", "step by step", "walkthrough"],
    "list": ["top", "best", "worst", "reasons why"],
    "comparison": ["vs", "versus", "compared to", "or"],
    "comprehensive": ["ultimate", "complete", "definitive", "everything you need"],
    "tutorial": ["tutorial", "guide", "course", "lesson", "learn"],
    "review": ["review", "honest review", "worth it", "should you"],
    "urgency": ["before you", "stop", "don't", "mistake", "warning"],
    "results": ["results", "transformation", "before and after", "i tried"],
}

# Common stop words to filter during keyword inference
_STOP_WORDS = frozenset({
    "a", "an", "the", "is", "it", "in", "on", "at", "to", "for", "of",
    "and", "or", "but", "not", "with", "this", "that", "my", "your",
    "i", "we", "you", "he", "she", "they", "me", "us", "him", "her",
    "its", "our", "their", "do", "does", "did", "was", "were", "be",
    "been", "being", "have", "has", "had", "will", "would", "could",
    "should", "may", "might", "can", "just", "even", "also", "so",
    "very", "really", "actually", "about", "from", "by", "up", "out",
    "no", "all", "more", "most", "some", "any", "each", "every",
    "what", "which", "who", "whom", "when", "where", "why", "how",
    "if", "then", "than", "too", "only", "own", "same", "into",
    "over", "after", "before", "between", "under", "again", "here",
    "there", "once", "why", "get", "got", "make", "made", "new",
    "like", "need", "know", "thing", "things", "way", "still",
})

# Timestamp/chapter pattern
_TIMESTAMP_PATTERN = re.compile(r'\b\d{1,2}:\d{2}\b')

# YouTube category IDs to names (common ones)
_CATEGORY_NAMES = {
    "1": "Film & Animation", "2": "Autos & Vehicles", "10": "Music",
    "15": "Pets & Animals", "17": "Sports", "19": "Travel & Events",
    "20": "Gaming", "22": "People & Blogs", "23": "Comedy",
    "24": "Entertainment", "25": "News & Politics", "26": "Howto & Style",
    "27": "Education", "28": "Science & Technology", "29": "Nonprofits & Activism",
}


# ---------------------------------------------------------------------------
# Keyword Inference
# ---------------------------------------------------------------------------

def _infer_keyword(title: str, description: str) -> str:
    """
    Infer the primary keyword from a video's title.

    Strategy:
    1. Remove common power words and filler to get the core topic.
    2. Extract the longest meaningful noun phrase.
    3. Cross-check against description for reinforcement.

    This is a best-effort heuristic. The suggestion system will always
    recommend re-running with an explicit keyword for best results.

    Complexity: O(n) where n = len(title)
    """
    title_clean = title.lower().strip()

    # Remove common patterns that aren't the keyword
    # Remove text in brackets/parens (often format markers like [4K], (Official))
    title_clean = re.sub(r'\[.*?\]', '', title_clean)
    title_clean = re.sub(r'\(.*?\)', '', title_clean)

    # Remove leading numbers/emojis/special chars
    title_clean = re.sub(r'^[\d\s.#\-:!?]+', '', title_clean)

    # Remove power words/phrases
    for category_words in _POWER_WORD_CATEGORIES.values():
        for phrase in category_words:
            title_clean = title_clean.replace(phrase.lower(), ' ')

    # Remove trailing year patterns (2024, 2025, etc.)
    title_clean = re.sub(r'\b20\d{2}\b', '', title_clean)

    # Remove pipe/dash separators and everything after (usually channel name)
    title_clean = re.sub(r'\s*[|]\s*.*$', '', title_clean)
    title_clean = re.sub(r'\s+-\s+.*$', '', title_clean)

    # Tokenize and remove stop words
    words = title_clean.split()
    meaningful = [w.strip('.,!?:;"\'-') for w in words
                  if w.strip('.,!?:;"\'-').lower() not in _STOP_WORDS
                  and len(w.strip('.,!?:;"\'-')) > 1]

    if not meaningful:
        # Fallback: use first 3 non-stop words from original title
        words = title.lower().split()
        meaningful = [w.strip('.,!?:;"\'-') for w in words
                      if w.strip('.,!?:;"\'-').lower() not in _STOP_WORDS][:3]

    if not meaningful:
        return title[:50].strip()

    # Build candidate: up to 4 consecutive meaningful words
    candidate = " ".join(meaningful[:4]).strip()

    # Cross-check: if candidate appears in description, it's likely correct
    desc_lower = description.lower()
    if candidate in desc_lower:
        return candidate

    # Try shorter versions
    for length in range(min(3, len(meaningful)), 0, -1):
        shorter = " ".join(meaningful[:length]).strip()
        if shorter and shorter in desc_lower:
            return shorter

    # No description match -- return best guess
    return candidate if candidate else title[:50].strip()


# ---------------------------------------------------------------------------
# Factor Scoring Functions
# ---------------------------------------------------------------------------

def _score_title(
    title: str,
    target_keyword: str,
) -> FactorScore:
    """
    Score title optimization (25% weight).

    Checks:
    - Keyword in first 60 chars (front-loaded)
    - Length 40-70 chars optimal
    - No ALL CAPS spam
    - Power word usage (context-aware)
    """
    score = 0.0
    details_parts: List[str] = []
    suggestions: List[str] = []
    title_lower = title.lower()
    keyword_lower = target_keyword.lower()

    # --- Keyword placement (40 points) ---
    if keyword_lower and keyword_lower in title_lower:
        kw_pos = title_lower.index(keyword_lower)
        if kw_pos < 60:
            score += 40
            details_parts.append(f"keyword at position {kw_pos}")
        else:
            score += 20
            details_parts.append(f"keyword at position {kw_pos} (late)")
            suggestions.append(
                f"Move your target keyword '{target_keyword}' to the first "
                f"60 characters of the title (currently at position {kw_pos})."
            )
    elif keyword_lower:
        details_parts.append("keyword missing from title")
        suggestions.append(
            f"Include your target keyword '{target_keyword}' in the title, "
            f"ideally within the first 60 characters."
        )

    # --- Length (25 points) ---
    title_len = len(title)
    if 40 <= title_len <= 70:
        score += 25
        details_parts.append(f"{title_len} chars (optimal)")
    elif 30 <= title_len < 40:
        score += 18
        details_parts.append(f"{title_len} chars (slightly short)")
        suggestions.append(
            f"Title is {title_len} chars. Aim for 40-70 characters for "
            f"optimal search visibility."
        )
    elif 70 < title_len <= 90:
        score += 15
        details_parts.append(f"{title_len} chars (slightly long)")
        suggestions.append(
            f"Title is {title_len} chars. YouTube truncates around 70 chars "
            f"in search results -- trim to keep your keyword visible."
        )
    elif title_len < 30:
        score += 8
        details_parts.append(f"{title_len} chars (too short)")
        suggestions.append(
            f"Title is only {title_len} chars. Expand to 40-70 characters "
            f"with descriptive keywords."
        )
    else:
        score += 5
        details_parts.append(f"{title_len} chars (too long)")
        suggestions.append(
            f"Title is {title_len} chars. Shorten to under 70 characters "
            f"so it doesn't get truncated in search."
        )

    # --- ALL CAPS spam check (15 points) ---
    # Count uppercase words (>3 chars to ignore acronyms like "SEO", "AI")
    words = title.split()
    long_upper_words = [w for w in words if len(w) > 3 and w.isupper()]
    caps_ratio = len(long_upper_words) / max(len(words), 1)

    if caps_ratio == 0:
        score += 15
    elif caps_ratio < 0.3:
        score += 10
        details_parts.append("some ALL CAPS")
    else:
        score += 3
        details_parts.append("excessive ALL CAPS")
        suggestions.append(
            "Avoid ALL CAPS in your title -- YouTube may suppress overly "
            "spammy-looking titles in recommendations."
        )

    # --- Power words (20 points) ---
    power_categories_found: List[str] = []
    for category, phrases in _POWER_WORD_CATEGORIES.items():
        for phrase in phrases:
            if phrase.lower() in title_lower:
                power_categories_found.append(category)
                break

    if len(power_categories_found) >= 2:
        score += 20
        details_parts.append(f"power words: {', '.join(power_categories_found[:3])}")
    elif len(power_categories_found) == 1:
        score += 14
        details_parts.append(f"power word: {power_categories_found[0]}")
    else:
        score += 5
        details_parts.append("no power words")
        suggestions.append(
            "Consider adding a power phrase to your title (e.g., 'how to', "
            "'complete guide', 'vs', 'honest review') to improve CTR."
        )

    return FactorScore(
        name="Title Optimization",
        score=min(100.0, score),
        weight=0.25,
        details="; ".join(details_parts),
        suggestions=suggestions,
    )


def _score_description(
    description: str,
    target_keyword: str,
) -> FactorScore:
    """
    Score description quality (20% weight).

    Checks:
    - Length (200+ words ideal)
    - Keyword in first 2 sentences
    - Structured content (paragraphs, not just links)
    - Timestamps/chapters present
    """
    score = 0.0
    details_parts: List[str] = []
    suggestions: List[str] = []
    desc_lower = description.lower()
    keyword_lower = target_keyword.lower()

    # --- Word count (30 points) ---
    word_count = len(description.split())
    if word_count >= 200:
        score += 30
        details_parts.append(f"{word_count} words (excellent)")
    elif word_count >= 100:
        score += 22
        details_parts.append(f"{word_count} words (good)")
        suggestions.append(
            f"Your description is {word_count} words. Aim for 200+ words "
            f"with natural keyword usage for better search indexing."
        )
    elif word_count >= 50:
        score += 12
        details_parts.append(f"{word_count} words (thin)")
        suggestions.append(
            f"Your description is only {word_count} words. YouTube indexes "
            f"description text for search -- aim for 200+ words with a "
            f"natural summary of the video content."
        )
    else:
        score += 5
        details_parts.append(f"{word_count} words (very thin)")
        suggestions.append(
            f"Your description is only {word_count} words -- this is a major "
            f"SEO missed opportunity. Write 200+ words summarizing the video, "
            f"including your target keyword naturally."
        )

    # --- Keyword in first 2 sentences (25 points) ---
    if keyword_lower:
        # Get first ~200 chars as proxy for "first 2 sentences"
        first_section = desc_lower[:200]
        if keyword_lower in first_section:
            score += 25
            details_parts.append("keyword in opening")
        elif keyword_lower in desc_lower:
            score += 12
            details_parts.append("keyword present (not in opening)")
            suggestions.append(
                f"Move '{target_keyword}' to the first 1-2 sentences of your "
                f"description. YouTube heavily weights the opening text."
            )
        else:
            details_parts.append("keyword not in description")
            suggestions.append(
                f"Include '{target_keyword}' in your description, especially "
                f"in the first 2 sentences. This is critical for search ranking."
            )

    # --- Structured content (20 points) ---
    # Check for paragraph breaks, not just a wall of links
    lines = description.strip().split('\n')
    non_empty_lines = [l.strip() for l in lines if l.strip()]
    has_paragraphs = len(non_empty_lines) >= 3
    link_count = description.count("http://") + description.count("https://")
    text_lines = [l for l in non_empty_lines
                  if not l.startswith("http") and len(l) > 20]
    text_ratio = len(text_lines) / max(len(non_empty_lines), 1)

    if has_paragraphs and text_ratio >= 0.5:
        score += 20
        details_parts.append("well-structured")
    elif has_paragraphs:
        score += 12
        details_parts.append("has structure")
    else:
        score += 5
        details_parts.append("unstructured")
        suggestions.append(
            "Structure your description with paragraphs: a summary, key "
            "takeaways, and relevant links. Avoid link-only descriptions."
        )

    # --- Timestamps/chapters (25 points) ---
    has_timestamps = bool(_TIMESTAMP_PATTERN.search(description))
    has_zero_timestamp = "0:00" in description

    if has_timestamps and has_zero_timestamp:
        score += 25
        details_parts.append("chapters present")
    elif has_timestamps:
        score += 15
        details_parts.append("timestamps (no 0:00 start)")
        suggestions.append(
            "Start your timestamps with 0:00 to enable YouTube's automatic "
            "chapter feature (Key Moments in search)."
        )
    else:
        details_parts.append("no chapters")
        suggestions.append(
            "Add timestamps/chapters to your description (start with 0:00). "
            "YouTube uses these for Key Moments in search results, which "
            "significantly increases click-through rate."
        )

    return FactorScore(
        name="Description Quality",
        score=min(100.0, score),
        weight=0.20,
        details="; ".join(details_parts),
        suggestions=suggestions,
    )


def _score_captions(
    has_captions: bool,
) -> FactorScore:
    """
    Score captions/transcript availability (10% weight).

    YouTube's NLP processes captions to understand video content for
    search ranking. Having captions (auto or manual) enables this.
    """
    if has_captions:
        return FactorScore(
            name="Captions/Transcript",
            score=100.0,
            weight=0.10,
            details="captions available (enables YouTube NLP indexing)",
        )
    else:
        return FactorScore(
            name="Captions/Transcript",
            score=20.0,
            weight=0.10,
            details="no captions detected",
            suggestions=[
                "Enable captions on your video. YouTube's auto-captions are "
                "acceptable, but manual/corrected captions are better. "
                "Captions enable YouTube's NLP to deeply understand your "
                "content for search ranking."
            ],
        )


def _score_video_metadata(
    duration_seconds: int,
    category_id: str,
    published_at: str,
) -> FactorScore:
    """
    Score video metadata (10% weight).

    Checks:
    - Appropriate duration (not too short for educational content)
    - Category set correctly
    - Publish time (minor signal)
    """
    score = 0.0
    details_parts: List[str] = []
    suggestions: List[str] = []

    # --- Duration (40 points) ---
    minutes = duration_seconds / 60.0
    if 8 <= minutes <= 20:
        score += 40
        details_parts.append(f"{minutes:.0f}min (ideal range)")
    elif 5 <= minutes < 8:
        score += 32
        details_parts.append(f"{minutes:.0f}min (good)")
    elif 20 < minutes <= 45:
        score += 28
        details_parts.append(f"{minutes:.0f}min (long)")
    elif 2 <= minutes < 5:
        score += 20
        details_parts.append(f"{minutes:.1f}min (short)")
        suggestions.append(
            f"Video is only {minutes:.1f} minutes. For most topics, 8-20 "
            f"minutes tends to perform best in search (more content for "
            f"YouTube to index, higher watch time potential)."
        )
    elif minutes < 2:
        score += 10
        details_parts.append(f"{minutes:.1f}min (very short)")
        suggestions.append(
            f"Very short video ({minutes:.1f}min). Consider whether this "
            f"should be a YouTube Short instead, or expand the content."
        )
    else:
        score += 22
        details_parts.append(f"{minutes:.0f}min (very long)")

    # --- Category (35 points) ---
    if category_id:
        cat_name = _CATEGORY_NAMES.get(category_id, f"ID:{category_id}")
        score += 35
        details_parts.append(f"category: {cat_name}")
    else:
        score += 5
        details_parts.append("no category set")
        suggestions.append(
            "Set a video category. This helps YouTube's algorithm classify "
            "your content and show it to relevant audiences."
        )

    # --- Publish time (25 points) ---
    # We can't deeply analyze this without more context, but we check it exists
    if published_at:
        score += 25
        # Parse hour if possible for a basic check
        try:
            hour_match = re.search(r'T(\d{2}):', published_at)
            if hour_match:
                hour = int(hour_match.group(1))
                # Prime hours: 14-18 UTC (morning US, evening EU)
                if 14 <= hour <= 18:
                    details_parts.append(f"published at {hour}:00 UTC (good)")
                else:
                    details_parts.append(f"published at {hour}:00 UTC")
        except (ValueError, AttributeError):
            details_parts.append("publish time present")
    else:
        score += 15
        details_parts.append("no publish time data")

    return FactorScore(
        name="Video Metadata",
        score=min(100.0, score),
        weight=0.10,
        details="; ".join(details_parts),
        suggestions=suggestions,
    )


def _score_technical_signals(
    description: str,
) -> FactorScore:
    """
    Score technical signals (10% weight).

    Checks:
    - Has chapters/timestamps (0:00 pattern in description)
    - Custom thumbnail (marked N/A -- API can't reliably detect)
    - Has end screen / cards (if detectable)
    """
    score = 0.0
    details_parts: List[str] = []
    suggestions: List[str] = []

    # --- Chapters/timestamps (50 points) ---
    timestamps = _TIMESTAMP_PATTERN.findall(description)
    has_zero = "0:00" in description

    if len(timestamps) >= 3 and has_zero:
        score += 50
        details_parts.append(f"{len(timestamps)} chapters detected")
    elif len(timestamps) >= 2:
        score += 30
        details_parts.append(f"{len(timestamps)} timestamps (needs 0:00 start)")
        suggestions.append(
            "Add a 0:00 timestamp to enable YouTube's automatic chapter "
            "generation. You have timestamps but chapters won't activate "
            "without a 0:00 marker."
        )
    elif len(timestamps) == 1:
        score += 15
        details_parts.append("1 timestamp (insufficient for chapters)")
        suggestions.append(
            "Add at least 3 timestamps starting with 0:00 to enable "
            "YouTube chapters. Chapters appear as Key Moments in search "
            "and significantly boost CTR."
        )
    else:
        details_parts.append("no timestamps")
        suggestions.append(
            "Add timestamps/chapters starting with 0:00. Minimum 3 "
            "timestamps needed. YouTube uses these for Key Moments in "
            "search results."
        )

    # --- Links to related content (20 points) ---
    link_count = description.count("http://") + description.count("https://")
    if link_count >= 3:
        score += 20
        details_parts.append(f"{link_count} links")
    elif link_count >= 1:
        score += 12
        details_parts.append(f"{link_count} link(s)")
    else:
        score += 5
        details_parts.append("no links")
        suggestions.append(
            "Add relevant links to your description (social media, website, "
            "related videos, resources). This adds context signals."
        )

    # --- Custom thumbnail (30 points -- marked as partial/N/A) ---
    # YouTube API doesn't reliably indicate custom vs auto thumbnails.
    # We give a baseline score and note the limitation.
    score += 20  # assume likely custom for any serious creator
    details_parts.append("thumbnail: N/A (API limitation)")

    return FactorScore(
        name="Technical Signals",
        score=min(100.0, score),
        weight=0.10,
        details="; ".join(details_parts),
        suggestions=suggestions,
    )


def _score_tags(
    tags: List[str],
    target_keyword: str,
) -> FactorScore:
    """
    Score tags (5% weight -- reduced from legacy).

    Tags have minimal impact on YouTube SEO in 2024+. We only check
    basic hygiene: reasonable count and basic relevance.
    """
    tag_count = len(tags)
    keyword_lower = target_keyword.lower()
    details_parts: List[str] = []
    suggestions: List[str] = []
    score = 0.0

    # --- Tag count (50 points) ---
    if 5 <= tag_count <= 15:
        score += 50
        details_parts.append(f"{tag_count} tags (reasonable)")
    elif 1 <= tag_count < 5:
        score += 30
        details_parts.append(f"{tag_count} tags (few)")
    elif 15 < tag_count <= 30:
        score += 35
        details_parts.append(f"{tag_count} tags (many)")
    elif tag_count > 30:
        score += 20
        details_parts.append(f"{tag_count} tags (excessive)")
        suggestions.append(
            "You have too many tags. YouTube recommends 5-15 focused tags. "
            "Excessive tags can dilute relevance signals."
        )
    else:
        score += 10
        details_parts.append("no tags")
        suggestions.append(
            "Add 5-15 relevant tags. While tags have reduced importance, "
            "they still help YouTube understand video content."
        )

    # --- Basic relevance (50 points) ---
    if tags and keyword_lower:
        tag_text = " ".join(t.lower() for t in tags)
        keyword_words = set(keyword_lower.split())
        tag_words = set(tag_text.split())
        overlap = keyword_words & tag_words

        if keyword_lower in tag_text:
            score += 50
            details_parts.append("keyword in tags")
        elif len(overlap) >= 1:
            score += 30
            details_parts.append(f"{len(overlap)} keyword words in tags")
        else:
            score += 10
            details_parts.append("tags don't match keyword")
            suggestions.append(
                f"Include your target keyword '{target_keyword}' as a tag."
            )
    elif tags:
        score += 25
        details_parts.append("tags present (no keyword to check against)")

    return FactorScore(
        name="Tags",
        score=min(100.0, score),
        weight=0.05,
        details="; ".join(details_parts),
        suggestions=suggestions,
    )


def _score_engagement(
    views: int,
    likes: int,
    comments: int,
    subscriber_count: int,
) -> FactorScore:
    """
    Score post-publish engagement (20% weight).

    Clearly labeled as post-publish performance feedback, not pre-publish
    optimization. Checks:
    - Like ratio (likes / views)
    - Comment rate (comments / views)
    - View-to-subscriber ratio
    """
    score = 0.0
    details_parts: List[str] = []
    suggestions: List[str] = []

    if views <= 0:
        return FactorScore(
            name="Engagement (post-publish)",
            score=0.0,
            weight=0.20,
            details="no views yet",
            suggestions=["Video has no views yet. Engagement data unavailable."],
        )

    # --- Like ratio (40 points) ---
    like_ratio = likes / views
    if like_ratio >= 0.04:  # 4%+ is excellent
        score += 40
        details_parts.append(f"like ratio: {like_ratio:.2%} (excellent)")
    elif like_ratio >= 0.02:  # 2-4% is good
        score += 30
        details_parts.append(f"like ratio: {like_ratio:.2%} (good)")
    elif like_ratio >= 0.01:  # 1-2% is average
        score += 18
        details_parts.append(f"like ratio: {like_ratio:.2%} (average)")
    else:
        score += 8
        details_parts.append(f"like ratio: {like_ratio:.2%} (low)")
        suggestions.append(
            "Low like ratio. Consider adding a call-to-action asking viewers "
            "to like the video if they found it helpful."
        )

    # --- Comment rate (30 points) ---
    comment_rate = comments / views
    if comment_rate >= 0.005:  # 0.5%+ is high engagement
        score += 30
        details_parts.append(f"comment rate: {comment_rate:.3%} (high)")
    elif comment_rate >= 0.001:  # 0.1% is decent
        score += 20
        details_parts.append(f"comment rate: {comment_rate:.3%} (decent)")
    elif comment_rate >= 0.0002:
        score += 10
        details_parts.append(f"comment rate: {comment_rate:.3%} (low)")
        suggestions.append(
            "Low comment engagement. Ask a question at the end of your video "
            "to encourage discussion in the comments."
        )
    else:
        score += 3
        details_parts.append(f"comment rate: {comment_rate:.4%} (very low)")
        suggestions.append(
            "Very low comment rate. Try asking viewers a direct question "
            "or creating a poll to boost engagement signals."
        )

    # --- View-to-sub ratio (30 points) ---
    if subscriber_count > 0:
        vts_ratio = views / subscriber_count
        if vts_ratio >= 1.0:  # Views >= subs = strong performance
            score += 30
            details_parts.append(f"views/subs: {vts_ratio:.2f}x (strong)")
        elif vts_ratio >= 0.3:
            score += 22
            details_parts.append(f"views/subs: {vts_ratio:.2f}x (healthy)")
        elif vts_ratio >= 0.1:
            score += 12
            details_parts.append(f"views/subs: {vts_ratio:.2f}x (moderate)")
        else:
            score += 5
            details_parts.append(f"views/subs: {vts_ratio:.2f}x (low reach)")
            suggestions.append(
                "Video is reaching fewer viewers than your subscriber base. "
                "This could indicate the title/thumbnail aren't compelling "
                "enough for your audience."
            )
    else:
        # No subscriber data -- give partial credit
        score += 15
        details_parts.append("subscriber data unavailable")

    return FactorScore(
        name="Engagement (post-publish)",
        score=min(100.0, score),
        weight=0.20,
        details="; ".join(details_parts),
        suggestions=suggestions,
    )


# ---------------------------------------------------------------------------
# Grade Assignment
# ---------------------------------------------------------------------------

def _assign_grade(score: float) -> str:
    """Map overall score to letter grade."""
    if score >= 90:
        return "A"
    elif score >= 75:
        return "B"
    elif score >= 60:
        return "C"
    elif score >= 40:
        return "D"
    else:
        return "F"


# ---------------------------------------------------------------------------
# Main Scorer Class
# ---------------------------------------------------------------------------

class SEOScorer:
    """
    YouTube SEO scoring engine.

    Scores a video's search optimization across 7 weighted factors,
    producing both pre-publish and post-publish scores plus actionable
    suggestions.

    Usage:
        scorer = SEOScorer()
        result = scorer.score(video_data, target_keyword="python tutorial")
    """

    # Legacy class-level WEIGHTS dict for backward compatibility
    # Maps to the new factor system
    WEIGHTS = {
        "title_optimization": 25,
        "description_quality": 20,
        "captions_transcript": 10,
        "video_metadata": 10,
        "technical_signals": 10,
        "tags": 5,
        "engagement_rate": 20,
    }

    def score(
        self,
        video_data: Dict[str, Any],
        target_keyword: str = "",
    ) -> SEOResult:
        """
        Score a video's SEO optimization.

        Parameters
        ----------
        video_data : dict
            Raw YouTube API video resource (snippet, statistics, contentDetails).
        target_keyword : str
            The keyword to score against. If empty, inferred from title.

        Returns
        -------
        SEOResult with overall score, pre/post-publish scores, factor
        breakdown, and actionable suggestions.

        The result also supports dict-style access for backward compatibility:
            result["overall_score"]  # works
            result["breakdown"]      # works (returns legacy format)
            result["suggestions"]    # works
            result["grade"]          # works
        """
        snippet = video_data.get("snippet", {})
        stats = video_data.get("statistics", {})
        content = video_data.get("contentDetails", {})

        title = snippet.get("title", "")
        description = snippet.get("description", "")
        tags = snippet.get("tags", [])
        category_id = snippet.get("categoryId", "")
        published_at = snippet.get("publishedAt", "")

        views = int(stats.get("viewCount", 0))
        likes = int(stats.get("likeCount", 0))
        comments = int(stats.get("commentCount", 0))

        # Subscriber count (from channel data if available)
        subscriber_count = 0
        channel_stats = video_data.get("channelStatistics", {})
        if channel_stats:
            subscriber_count = int(channel_stats.get("subscriberCount", 0))

        # Duration parsing
        duration_str = content.get("duration", "PT0S")
        duration_seconds = self._parse_duration(duration_str)

        # Caption availability
        has_captions = content.get("caption", "false") == "true"

        # Keyword handling
        keyword_detected = bool(target_keyword.strip())
        if not keyword_detected:
            target_keyword = _infer_keyword(title, description)

        # --- Score each factor ---
        factors: Dict[str, FactorScore] = {}

        factors["title_optimization"] = _score_title(title, target_keyword)
        factors["description_quality"] = _score_description(description, target_keyword)
        factors["captions_transcript"] = _score_captions(has_captions)
        factors["video_metadata"] = _score_video_metadata(
            duration_seconds, category_id, published_at
        )
        factors["technical_signals"] = _score_technical_signals(description)
        factors["tags"] = _score_tags(tags, target_keyword)
        factors["engagement_rate"] = _score_engagement(
            views, likes, comments, subscriber_count
        )

        # --- Compute composite scores ---
        pre_publish_keys = [
            "title_optimization", "description_quality", "captions_transcript",
            "video_metadata", "technical_signals", "tags",
        ]
        post_publish_keys = ["engagement_rate"]

        pre_weighted_sum = sum(
            factors[k].weighted_score for k in pre_publish_keys
        )
        pre_weight_total = sum(
            factors[k].weight for k in pre_publish_keys
        )
        pre_publish_score = round(
            pre_weighted_sum / pre_weight_total if pre_weight_total > 0 else 0.0, 1
        )

        post_weighted_sum = sum(
            factors[k].weighted_score for k in post_publish_keys
        )
        post_weight_total = sum(
            factors[k].weight for k in post_publish_keys
        )
        post_publish_score = round(
            post_weighted_sum / post_weight_total if post_weight_total > 0 else 0.0, 1
        )

        # Overall: weighted sum of all factors
        overall_weighted = sum(f.weighted_score for f in factors.values())
        overall_score = round(overall_weighted, 1)

        # Collect all suggestions
        all_suggestions: List[str] = []
        for f in factors.values():
            all_suggestions.extend(f.suggestions)

        # Add keyword inference suggestion if applicable
        if not keyword_detected:
            all_suggestions.insert(0,
                f"Keyword '{target_keyword}' was auto-detected from the title. "
                f"Re-run with an explicit target keyword for more accurate scoring."
            )

        grade = _assign_grade(overall_score)

        return SEOResult(
            overall_score=overall_score,
            pre_publish_score=pre_publish_score,
            post_publish_score=post_publish_score,
            factor_breakdown=factors,
            suggestions=all_suggestions,
            target_keyword=target_keyword,
            keyword_detected=keyword_detected,
            grade=grade,
        )

    @staticmethod
    def _parse_duration(iso_duration: str) -> int:
        """Parse ISO 8601 duration (PT1H2M3S) to total seconds."""
        if not iso_duration:
            return 0
        match = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", iso_duration)
        if not match:
            return 0
        h, m, s = match.groups()
        return int(h or 0) * 3600 + int(m or 0) * 60 + int(s or 0)
