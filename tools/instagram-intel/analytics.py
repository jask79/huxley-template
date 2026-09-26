"""Timing analysis and content topic classification.

Pure functions — take lists/dicts in, return analysis results out.
No side effects, no API calls, no pip dependencies.

Implements:
  #6  Post Timing Analysis — 7x24 engagement heatmap from timestamps
  #9  Content Topic Classification — lightweight TF-IDF on captions
"""

import math
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple


# ---------------------------------------------------------------------------
# #6 — Post Timing Analysis
# ---------------------------------------------------------------------------

_DAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
_DAY_ABBR = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def _parse_timestamp_dt(ts: str) -> Optional[datetime]:
    """Parse ISO 8601 timestamp to datetime. Returns None on failure."""
    if not ts:
        return None
    try:
        clean = ts.replace("+0000", "+00:00").replace("Z", "+00:00")
        return datetime.fromisoformat(clean)
    except (ValueError, OSError):
        return None


def compute_posting_heatmap(
    items: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Build a 7x24 engagement heatmap from media item timestamps.

    Bins posts by (day_of_week, hour) and computes average engagement
    per bin. Returns the heatmap plus the top recommended posting times.

    Args:
        items: List of media item dicts with 'timestamp' and engagement
               fields (like_count/likes, comments_count/comments).

    Returns:
        Dict with:
          - heatmap: dict[str, dict[int, dict]] — day -> hour -> stats
          - best_times: list of (day, hour, avg_engagement) top 5 slots
          - total_posts: int
          - coverage: dict with day/hour distribution stats
    """
    if not items:
        return {
            "heatmap": {},
            "best_times": [],
            "total_posts": 0,
            "coverage": {"days_with_posts": 0, "hours_with_posts": 0},
        }

    # Collect (day, hour) -> list of engagement values
    bins: Dict[Tuple[int, int], List[float]] = defaultdict(list)

    for item in items:
        ts = item.get("timestamp", "")
        dt = _parse_timestamp_dt(ts)
        if dt is None:
            continue

        day = dt.weekday()  # 0=Mon, 6=Sun
        hour = dt.hour

        likes = _safe_int(item, "like_count", "likes")
        comments = _safe_int(item, "comments_count", "comments")
        engagement = likes + comments

        bins[(day, hour)].append(engagement)

    # Build heatmap
    heatmap: Dict[str, Dict[int, Dict[str, Any]]] = {}
    all_slots = []

    for day_idx in range(7):
        day_name = _DAY_NAMES[day_idx]
        heatmap[day_name] = {}
        for hour in range(24):
            values = bins.get((day_idx, hour), [])
            if values:
                avg = sum(values) / len(values)
                slot_data = {
                    "posts": len(values),
                    "avg_engagement": round(avg, 1),
                    "total_engagement": sum(values),
                }
                heatmap[day_name][hour] = slot_data
                all_slots.append((day_name, hour, avg, len(values)))

    # Find best times (top 5 by avg engagement, min 2 posts in slot)
    qualified = [s for s in all_slots if s[3] >= 2]
    if not qualified:
        # Fallback: use all slots if none have 2+ posts
        qualified = all_slots

    qualified.sort(key=lambda x: x[2], reverse=True)
    best_times = [
        {
            "day": s[0],
            "hour": s[1],
            "hour_label": f"{s[1]:02d}:00",
            "avg_engagement": round(s[2], 1),
            "sample_size": s[3],
        }
        for s in qualified[:5]
    ]

    # Coverage stats
    days_with_posts = len({k[0] for k in bins.keys()})
    hours_with_posts = len(bins)

    return {
        "heatmap": heatmap,
        "best_times": best_times,
        "total_posts": sum(len(v) for v in bins.values()),
        "coverage": {
            "days_with_posts": days_with_posts,
            "hours_with_posts": hours_with_posts,
        },
    }


def format_best_times(analysis: Dict[str, Any]) -> str:
    """Format best posting times as a readable string for terminal output."""
    best = analysis.get("best_times", [])
    if not best:
        return "  (not enough data to determine best posting times)"

    lines = []
    for i, slot in enumerate(best):
        lines.append(
            f"  {i + 1}. {slot['day']} {slot['hour_label']} "
            f"(avg engagement: {slot['avg_engagement']:.0f}, "
            f"n={slot['sample_size']})"
        )
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# #9 — Content Topic Classification (Lightweight TF-IDF)
# ---------------------------------------------------------------------------

# Common English stopwords (minimal set for caption analysis)
_STOPWORDS = frozenset({
    "a", "an", "the", "and", "or", "but", "in", "on", "at", "to", "for",
    "of", "with", "by", "from", "is", "it", "its", "was", "are", "be",
    "been", "being", "have", "has", "had", "do", "does", "did", "will",
    "would", "could", "should", "may", "might", "shall", "can",
    "this", "that", "these", "those", "i", "me", "my", "we", "our",
    "you", "your", "he", "she", "they", "them", "their", "his", "her",
    "not", "no", "so", "if", "as", "up", "out", "just", "than", "then",
    "also", "very", "too", "all", "any", "each", "more", "most", "some",
    "such", "into", "over", "after", "before", "about", "between",
    "through", "during", "here", "there", "when", "where", "how", "what",
    "which", "who", "whom", "why", "am", "us", "get", "got", "like",
    "new", "one", "two", "now", "day", "way", "go", "going",
    "make", "see", "know", "take", "come", "think", "look", "want",
    "give", "use", "find", "tell", "ask", "try", "need", "feel",
    "let", "keep", "put", "show", "call", "say", "said", "still",
    "back", "only", "even", "much", "because", "good", "well",
    "really", "many", "things", "thing", "something", "time",
})

# Regex for tokenization: extract words (3+ chars), hashtags preserved
_TOKEN_RE = re.compile(r"#?\w{3,}", re.UNICODE)

# Hashtag extraction
_HASHTAG_RE = re.compile(r"#(\w+)", re.UNICODE)


def _tokenize_caption(caption: str) -> List[str]:
    """Tokenize a caption into lowercase terms, removing stopwords."""
    if not caption:
        return []
    tokens = _TOKEN_RE.findall(caption.lower())
    return [t for t in tokens if t not in _STOPWORDS and not t.isdigit()]


def extract_topics(
    captions: List[str],
    top_k: int = 10,
) -> List[Tuple[str, float]]:
    """Extract top topics from a collection of captions using TF-IDF.

    Lightweight implementation: no external NLP libraries needed.
    Works by computing term frequency * inverse document frequency
    across the caption corpus.

    Args:
        captions: List of caption strings.
        top_k: Number of top topics to return.

    Returns:
        List of (term, tfidf_score) tuples, sorted descending by score.
    """
    if not captions:
        return []

    # Tokenize each caption (document)
    docs = [_tokenize_caption(c) for c in captions]
    n_docs = len(docs)

    if n_docs == 0:
        return []

    # Document frequency: how many documents contain each term
    df: Counter = Counter()
    for doc in docs:
        unique_terms = set(doc)
        for term in unique_terms:
            df[term] += 1

    # Compute TF-IDF for each term across the corpus
    tfidf_scores: Dict[str, float] = defaultdict(float)

    for doc in docs:
        tf = Counter(doc)
        doc_len = len(doc) or 1
        for term, count in tf.items():
            # Normalized TF * IDF
            normalized_tf = count / doc_len
            idf = math.log(1 + n_docs / (1 + df.get(term, 0)))
            tfidf_scores[term] += normalized_tf * idf

    # Average across corpus: terms appearing frequently in many documents
    # rank higher. This is intentional for topic extraction (corpus-level
    # trends) but differs from standard per-document TF-IDF.
    for term in tfidf_scores:
        tfidf_scores[term] /= n_docs

    # Sort and return top_k
    ranked = sorted(tfidf_scores.items(), key=lambda x: x[1], reverse=True)
    return ranked[:top_k]


def extract_hashtag_topics(
    captions: List[str],
    top_k: int = 10,
) -> List[Tuple[str, int]]:
    """Extract the most frequent hashtags from captions.

    Complementary to TF-IDF — sometimes hashtags are more informative
    than general words for topic identification.

    Args:
        captions: List of caption strings.
        top_k: Number of top hashtags to return.

    Returns:
        List of (hashtag, count) tuples, sorted descending by frequency.
    """
    counter: Counter = Counter()
    for caption in captions:
        if not caption:
            continue
        tags = _HASHTAG_RE.findall(caption.lower())
        counter.update(tags)

    return counter.most_common(top_k)


def format_topics(topics: List[Tuple[str, float]], label: str = "Topics") -> str:
    """Format topic extraction results as a readable string."""
    if not topics:
        return f"  (no {label.lower()} detected)"

    lines = [f"  {label}:"]
    for i, (term, score) in enumerate(topics):
        if isinstance(score, float):
            lines.append(f"    {i + 1}. {term} ({score:.3f})")
        else:
            lines.append(f"    {i + 1}. #{term} ({score}x)")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _safe_int(item: Dict[str, Any], key: str, fallback: str = "") -> int:
    """Safely extract an integer from a dict."""
    val = item.get(key)
    if val is None and fallback:
        val = item.get(fallback)
    if val is None:
        return 0
    try:
        return int(val)
    except (ValueError, TypeError):
        return 0
