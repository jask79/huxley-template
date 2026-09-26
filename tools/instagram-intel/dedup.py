"""Multi-key and fuzzy caption deduplication for Instagram Intelligence.

Pure functions — take lists/dicts in, return deduplicated lists out.
No side effects, no API calls, no pip dependencies.

Implements:
  #7 Fuzzy Caption Dedup — trigram Jaccard similarity + multi-key exact dedup
"""

from typing import Any, Dict, List, Optional, Set, Tuple


# ---------------------------------------------------------------------------
# #7a — Multi-Key Exact Dedup
# ---------------------------------------------------------------------------

# Fields to check for ID-based dedup, in priority order
_ID_FIELDS = [
    "media_id",
    "reel_id",
    "audio_id",
    "permalink",
]


def dedup_multi_key(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Remove exact duplicates using multiple ID fields.

    Checks each ID field in priority order. An item is a duplicate if ANY
    of its ID fields match a previously seen value for that field.
    Items without any ID fields are kept.

    Args:
        items: List of item dicts.

    Returns:
        Deduplicated list preserving original order.
    """
    if not items:
        return []

    seen: Dict[str, Set[str]] = {field: set() for field in _ID_FIELDS}
    result = []

    for item in items:
        is_dup = False
        ids_found = []

        for field in _ID_FIELDS:
            val = item.get(field, "")
            if val:
                val_str = str(val)
                if val_str in seen[field]:
                    is_dup = True
                    break
                ids_found.append((field, val_str))

        if not is_dup:
            result.append(item)
            for field, val_str in ids_found:
                seen[field].add(val_str)

    return result


# ---------------------------------------------------------------------------
# #7b — Trigram Jaccard Similarity
# ---------------------------------------------------------------------------

def _trigrams(text: str) -> Set[str]:
    """Generate character trigrams from a string.

    Preprocessing: lowercase, strip whitespace normalization.
    Padding with spaces at boundaries for better boundary matching.

    Examples:
        "hello" -> {"  h", " he", "hel", "ell", "llo", "lo ", "o  "}
    """
    if not text:
        return set()

    # Normalize: lowercase, collapse whitespace
    normalized = " ".join(text.lower().split())
    padded = f"  {normalized}  "

    return {padded[i:i + 3] for i in range(len(padded) - 2)}


def trigram_similarity(a: str, b: str) -> float:
    """Compute Jaccard similarity between two strings using trigrams.

    Returns a value between 0.0 (completely different) and 1.0 (identical).
    """
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0

    tg_a = _trigrams(a)
    tg_b = _trigrams(b)

    if not tg_a and not tg_b:
        return 1.0
    if not tg_a or not tg_b:
        return 0.0

    intersection = len(tg_a & tg_b)
    union = len(tg_a | tg_b)

    return intersection / union if union > 0 else 0.0


def dedup_fuzzy(
    items: List[Dict[str, Any]],
    threshold: float = 0.7,
    caption_field: str = "caption",
) -> List[Dict[str, Any]]:
    """Remove near-duplicate items based on fuzzy caption similarity.

    Uses trigram Jaccard similarity to detect captions that are
    substantially similar. Keeps the first occurrence.

    Complexity: O(N^2) pairwise comparison. For typical Instagram
    result sets (20-100 items), this is negligible (<1ms for 100 items).

    Args:
        items: List of item dicts.
        threshold: Jaccard similarity threshold (0.0-1.0). Items above
                   this threshold are considered duplicates. Default 0.7.
        caption_field: Dict key containing the caption text.

    Returns:
        Deduplicated list preserving original order.
    """
    if not items:
        return []

    result = []
    kept_captions: List[str] = []

    for item in items:
        caption = item.get(caption_field, "") or ""

        # Empty captions: skip fuzzy check (keep item)
        if not caption.strip():
            result.append(item)
            continue

        # Compare against already-kept captions
        is_dup = False
        for kept in kept_captions:
            if trigram_similarity(caption, kept) >= threshold:
                is_dup = True
                break

        if not is_dup:
            result.append(item)
            kept_captions.append(caption)

    return result


def dedup_full(
    items: List[Dict[str, Any]],
    fuzzy_threshold: float = 0.7,
    caption_field: str = "caption",
) -> List[Dict[str, Any]]:
    """Full deduplication pipeline: exact IDs first, then fuzzy captions.

    Args:
        items: List of item dicts.
        fuzzy_threshold: Jaccard similarity threshold for fuzzy dedup.
        caption_field: Dict key for caption text.

    Returns:
        Deduplicated list.
    """
    # Stage 1: exact ID dedup (fast, O(N))
    stage1 = dedup_multi_key(items)
    # Stage 2: fuzzy caption dedup (O(N^2) but N is small after stage 1)
    stage2 = dedup_fuzzy(stage1, threshold=fuzzy_threshold, caption_field=caption_field)
    return stage2
