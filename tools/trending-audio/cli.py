#!/usr/bin/env python3
"""
Trending Audio Unified CLI — cross-platform trending music intelligence.

Aggregates trending audio from YouTube, TikTok, and Instagram in parallel,
normalizes track data into a common model, and cross-references results to
surface songs trending across multiple platforms.

Platform CLIs called (must be reachable from the Huxley root):
  - tools/youtube-intel/cli.py trending-music --limit N --json
  - tools/tiktok-intel/cli.py trends --type songs --limit N --json
  - tools/instagram-intel/cli.py trending-audio --limit N --json

Matching strategy:
  1. Exact normalized key (artist::title, both lowercased, non-alphanum stripped)
  2. Artist match + title substring
  3. difflib.SequenceMatcher fuzzy title similarity >= 0.75 (same artist)

Scoring:
  - 1 platform  → base 30
  - 2 platforms → base 65
  - 3 platforms → base 100
  + Per-platform rank bonus: higher rank = more points (up to +20 each)

Dependencies: stdlib only.
Auth (--ai flag): Keychain service "anthropic-api-key", account "huxley".

Exit codes:
  0 — success
  1 — expected error (no data, bad args)
  2 — unexpected error
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import subprocess
import sys
import unicodedata
import urllib.error
import urllib.request
from concurrent.futures import (
    ThreadPoolExecutor,
    as_completed,
)
from concurrent.futures import (
    TimeoutError as FuturesTimeout,
)
from datetime import UTC, datetime
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_TOOL_DIR = Path(__file__).resolve().parent
_CATALYST_ROOT = _TOOL_DIR.parent.parent  # tools/ -> Huxley/

_LIB_DIR = _CATALYST_ROOT / "global" / "lib"
if str(_LIB_DIR) not in sys.path:
    sys.path.insert(0, str(_LIB_DIR))
from secret_provider import get_secret

_TOOLS_DIR = _CATALYST_ROOT / "tools"

_YOUTUBE_CLI = _TOOLS_DIR / "youtube-intel" / "cli.py"
_TIKTOK_CLI = _TOOLS_DIR / "tiktok-intel" / "cli.py"
_INSTAGRAM_CLI = _TOOLS_DIR / "instagram-intel" / "cli.py"

for _cli_path in [_YOUTUBE_CLI, _TIKTOK_CLI, _INSTAGRAM_CLI]:
    if not _cli_path.exists():
        logging.getLogger("trending-audio").warning("Sub-CLI not found: %s", _cli_path)

# ---------------------------------------------------------------------------
# ANSI colours (inline — no deps)
# ---------------------------------------------------------------------------

RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
CYAN = "\033[36m"
RED = "\033[31m"
MAGENTA = "\033[35m"
BLUE = "\033[34m"

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logger = logging.getLogger("trending-audio")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

VERSION = "1.0.0"
FUZZY_THRESHOLD = 0.75  # SequenceMatcher fallback threshold
JACCARD_THRESHOLD = 0.60  # Token Jaccard similarity threshold (fix #1)

# Cross-platform score bases (kept for reference but superseded by smooth formula)
_SCORE_BASE = {1: 30, 2: 65, 3: 100}

# Max rank bonus points per platform (rank 1 gives full bonus, rank N gives 0)
_MAX_RANK_BONUS = 20

# CLI fetch timeout seconds (each platform)
_FETCH_TIMEOUT = 60

# ---------------------------------------------------------------------------
# Normalisation helpers
# ---------------------------------------------------------------------------

# Strip junk from titles before matching (fix #1 — added sped up / slowed / remix / acoustic)
_STRIP_PATTERNS = [
    r"\s*\(official\s*(music\s*)?video\)",
    r"\s*\(official\s*audio\)",
    r"\s*\(lyrics?\)",
    r"\s*\(lyric\s*video\)",
    r"\s*\(visualizer\)",
    r"\s*\(audio\)",
    r"\s*\(live\)",
    r"\s*\(\s*(?:feat|ft)\.?\s*[^)]+\)",
    r"\s*#shorts?\b",
    r"\s*#music\b",
    r"\s*\[.*?\]",
    r"\s*-\s*official.*$",
    r"\s*\|\s*official.*$",
    # Cross-platform variant patterns (fix #1)
    r"\s*\(sped\s*up\)",
    r"\s*\(slowed(?:\s*[\+&]\s*reverb)?\)",
    r"\s*\(remix\)",
    r"\s*\(acoustic(?:\s*version)?\)",
    r"\s*\(nightcore\)",
    # F3: Bare featuring/collab credits NOT enclosed in parentheses/brackets.
    # These must use $ anchors so we only strip trailing credits, not mid-title content.
    # Order matters: feat/ft/featuring before w/ before "x Name" to avoid over-matching.
    # Pattern captures: "feat. Artist Name", "ft Artist", "featuring Artist", "with Artist"
    r"\s+feat(?:uring)?\.?\s+[\w\s&,]{2,}$",
    r"\s+ft\.?\s+[\w\s&,]{2,}$",
    r"\s+with\s+[\w\s&,]{2,}$",
    r"\s+w/\s+[\w\s&,]{2,}$",
]

# Finding 14: single compiled alternation — one regex pass instead of 13 sequential passes
_STRIP_COMBINED = re.compile(r"|".join(_STRIP_PATTERNS), flags=re.IGNORECASE)


def _strip_noise(text: str) -> str:
    """Strip common music-title noise phrases (single compiled regex pass)."""
    return _STRIP_COMBINED.sub("", text).strip()


def _unicode_normalize(text: str) -> str:
    """NFKD decompose. Strips combining diacritical marks (category Mn) but preserves
    non-Latin base characters (Hangul, CJK, Arabic, Cyrillic, etc.).

    F9: The previous encode("ascii","ignore") approach dropped entire Korean/Japanese/Arabic
    titles to empty strings, causing all non-Latin tracks to collide at the same empty
    exact_index key. Now we only strip combining marks so accents decompose correctly
    (é -> e, ñ -> n) while Korean/CJK/Arabic characters are preserved intact.
    """
    s = unicodedata.normalize("NFKD", text)
    # Drop combining diacritical marks only (Unicode category Mn = Mark, Nonspacing)
    return "".join(c for c in s if unicodedata.category(c) != "Mn")


def _normalize(text: str) -> str:
    """Lowercase, unicode-normalize, strip noise, remove non-alphanumeric, collapse spaces."""
    s = _unicode_normalize(_strip_noise(text)).lower()
    s = re.sub(r"[^\w\s]", "", s)  # remove punctuation
    s = re.sub(r"\s+", " ", s)  # collapse whitespace
    return s.strip()


def _norm_key(artist: str, title: str) -> str:
    """Canonical dedup key."""
    return f"{_normalize(artist)}::{_normalize(title)}"


def _token_jaccard(a: str, b: str) -> float:
    """Token-level Jaccard similarity between two normalized strings (fix #1)."""
    if not a or not b:
        return 0.0
    tokens_a = set(a.split())
    tokens_b = set(b.split())
    if not tokens_a and not tokens_b:
        return 1.0
    if not tokens_a or not tokens_b:
        return 0.0
    intersection = len(tokens_a & tokens_b)
    union = len(tokens_a | tokens_b)
    return intersection / union if union > 0 else 0.0


def _fuzzy_ratio(a: str, b: str) -> float:
    """Hybrid fuzzy similarity: max(token Jaccard, SequenceMatcher ratio) (fix #1)."""
    if not a or not b:
        return 0.0
    jaccard = _token_jaccard(a, b)
    seq = SequenceMatcher(None, a, b).ratio()
    return max(jaccard, seq)


# ---------------------------------------------------------------------------
# Platform fetchers
# ---------------------------------------------------------------------------


def _run_cli(args: list[str], timeout: int = _FETCH_TIMEOUT) -> dict | None:
    """
    Run a CLI command via subprocess and parse its JSON stdout.

    Returns None on any failure (non-zero exit, timeout, bad JSON).
    Stderr is captured and logged at DEBUG level.
    """
    try:
        result = subprocess.run(
            [sys.executable] + args,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        if result.stderr:
            logger.debug("CLI stderr (%s): %s", args[0], result.stderr[:500])

        if result.returncode not in (0, 1):
            logger.debug("CLI exit %d: %s", result.returncode, args[:2])

        stdout = result.stdout.strip()
        if not stdout:
            return None

        return json.loads(stdout)

    except subprocess.TimeoutExpired:
        logger.warning("Timeout fetching from %s (>%ds)", args[0], timeout)
        return None
    except json.JSONDecodeError as e:
        logger.debug("JSON parse error from %s: %s", args[0], e)
        return None
    except Exception as e:
        logger.debug("Subprocess error: %s", e)
        return None


def _fetch_youtube(limit: int) -> tuple[str, list[dict[str, Any]]]:
    """
    Fetch YouTube trending music.

    Returns ("youtube", list_of_normalized_tracks).
    YouTube JSON structure: {"results": [{song_title, artist, rank, view_count, ...}]}
    """
    data = _run_cli([str(_YOUTUBE_CLI), "trending-music", "--limit", str(limit), "--json"])
    if not data or "results" not in data:
        return "youtube", []

    tracks = []
    for item in data["results"]:
        title = item.get("song_title", "") or ""
        artist = item.get("artist", "") or ""
        rank = item.get("rank", 0) or 0
        if not title:
            continue
        tracks.append(
            {
                "title": title,
                "artist": artist,
                "rank": rank,
                "view_count": item.get("view_count", 0),
                "trending_score": item.get("trending_score", 0),
                "video_url": item.get("video_url", ""),
                "source": item.get("source", ""),
            }
        )

    return "youtube", tracks


def _fetch_tiktok(limit: int) -> tuple[str, list[dict[str, Any]]]:
    """
    Fetch TikTok trending songs.

    Returns ("tiktok", list_of_normalized_tracks).
    TikTok JSON structure: {"success": true, "data": [{title, artist, rank, posts, ...}]}
    """
    data = _run_cli(
        [str(_TIKTOK_CLI), "trends", "--type", "songs", "--limit", str(limit), "--json"]
    )
    if not data:
        return "tiktok", []

    # Handle both {"data": [...]} and {"success": true, "data": [...]}
    items = data.get("data", [])
    if not items and "error" in data:
        logger.debug("TikTok trends error: %s", data.get("error", ""))
        return "tiktok", []

    tracks = []
    for item in items:
        if isinstance(item, dict):
            title = item.get("title", "") or ""
            artist = item.get("artist", "") or ""
            rank = item.get("rank", 0) or 0
        else:
            # Dataclass fallback (shouldn't happen with --json, but be safe)
            title = getattr(item, "title", "") or ""
            artist = getattr(item, "artist", "") or ""
            rank = getattr(item, "rank", 0) or 0

        if not title:
            continue
        tracks.append(
            {
                "title": title,
                "artist": artist,
                "rank": rank,
                "posts": item.get("posts", "")
                if isinstance(item, dict)
                else getattr(item, "posts", ""),
                "duration": item.get("duration", "")
                if isinstance(item, dict)
                else getattr(item, "duration", ""),
                "trend_change": item.get("trend_change", "")
                if isinstance(item, dict)
                else getattr(item, "trend_change", ""),
            }
        )

    return "tiktok", tracks


def _fetch_instagram(limit: int) -> tuple[str, list[dict[str, Any]]]:
    """
    Fetch Instagram trending audio.

    Returns ("instagram", list_of_normalized_tracks).
    Instagram JSON structure: {"success": true, "data": [{name, artist, usage_count, audio_score, ...}]}
    """
    data = _run_cli([str(_INSTAGRAM_CLI), "trending-audio", "--limit", str(limit), "--json"])
    if not data:
        return "instagram", []

    items = data.get("data", [])
    if not items and "error" in data:
        logger.debug("Instagram trending-audio error: %s", data.get("error", ""))
        return "instagram", []

    tracks = []
    for i, item in enumerate(items):
        if isinstance(item, dict):
            # Instagram uses "name" not "title"
            title = (
                item.get("name", "") or item.get("title", "") or item.get("audio_name", "") or ""
            )
            artist = item.get("artist", "") or ""
            usage_count = item.get("usage_count", 0) or 0
            audio_score = item.get("audio_score", 0) or 0
            rank = item.get("rank", i + 1) or (i + 1)
        else:
            title = getattr(item, "name", "") or getattr(item, "title", "") or ""
            artist = getattr(item, "artist", "") or ""
            usage_count = getattr(item, "usage_count", 0) or 0
            audio_score = getattr(item, "audio_score", 0) or 0
            rank = getattr(item, "rank", i + 1) or (i + 1)

        if not title:
            continue
        tracks.append(
            {
                "title": title,
                "artist": artist,
                "rank": rank,
                "usage_count": usage_count,
                "audio_score": audio_score,
            }
        )

    return "instagram", tracks


# ---------------------------------------------------------------------------
# Parallel fetch coordinator
# ---------------------------------------------------------------------------


def fetch_all_platforms(limit: int, verbose: bool = False) -> dict[str, list[dict[str, Any]]]:
    """
    Fetch trending audio from all three platforms in parallel.

    Returns {"youtube": [...], "tiktok": [...], "instagram": [...]}.
    Failed platforms return empty lists — never raises.
    """
    fetchers = {
        "youtube": lambda: _fetch_youtube(limit),
        "tiktok": lambda: _fetch_tiktok(limit),
        "instagram": lambda: _fetch_instagram(limit),
    }

    results: dict[str, list] = {"youtube": [], "tiktok": [], "instagram": []}

    with ThreadPoolExecutor(max_workers=3) as pool:
        futures = {pool.submit(fn): name for name, fn in fetchers.items()}

        for future in as_completed(futures, timeout=_FETCH_TIMEOUT + 10):
            name = futures[future]
            try:
                _platform, tracks = future.result()
                results[_platform] = tracks
                if verbose:
                    status = (
                        f"{GREEN}{len(tracks)} tracks{RESET}"
                        if tracks
                        else f"{YELLOW}no data{RESET}"
                    )
                    print(f"  {DIM}{name.capitalize():12}{RESET} {status}", flush=True)
            except FuturesTimeout:
                if verbose:
                    print(f"  {YELLOW}{name.capitalize():12} timeout{RESET}", flush=True)
            except Exception as e:
                logger.debug("Platform %s fetch exception: %s", name, e)
                if verbose:
                    print(
                        f"  {YELLOW}{name.capitalize():12} failed: {e}{RESET}",
                        flush=True,
                    )

    return results


# ---------------------------------------------------------------------------
# Cross-platform matching
# ---------------------------------------------------------------------------


def _tracks_match(a_title: str, a_artist: str, b_title: str, b_artist: str) -> bool:
    """
    Determine whether two tracks are the same song.

    Strategy (in order):
      1. Exact normalized key match (artist + title)
      2. Title substring containment (normalized), same artist
      3. Fuzzy title similarity >= FUZZY_THRESHOLD, same artist (or both artists empty)
    """
    na_title = _normalize(a_title)
    na_artist = _normalize(a_artist)
    nb_title = _normalize(b_title)
    nb_artist = _normalize(b_artist)
    return _tracks_match_prenorm(na_title, na_artist, nb_title, nb_artist)


def _tracks_match_prenorm(na_title: str, na_artist: str, nb_title: str, nb_artist: str) -> bool:
    """
    Core matching logic operating on already-normalized strings (Finding 2).

    Called by _tracks_match (which normalizes) and _find_match (which uses
    pre-cached normalized keys from merged entries to avoid redundant work).
    """

    # 1. Exact key match
    if na_title == nb_title and (na_artist == nb_artist or not na_artist or not nb_artist):
        return True

    # Artist similarity gate: both artists must plausibly refer to the same act.
    # F2: The original "any shared word of len > 2" test was too permissive — "Drake" and
    # "Drake Bell" share the token "drake" and would pass even though they are different
    # artists. Strengthened to require Jaccard >= 0.5 or fuzzy >= 0.75 for known artists,
    # with a proportional word-overlap fallback for cases like "Taylor Swift" vs
    # "Taylor Swift feat. Post Malone" (after feat-stripping the feat is already gone, but
    # the fallback handles edge cases where stripping didn't fire).
    def _artists_compatible(x: str, y: str) -> bool:
        if not x or not y:
            return True  # one unknown — give benefit of doubt
        # Strong signal: high Jaccard or high sequence similarity.
        # Check Jaccard first (cheaper); only compute fuzzy if Jaccard misses.
        jac = _token_jaccard(x, y)
        if jac >= 0.5 or (jac < 0.5 and _fuzzy_ratio(x, y) >= 0.75):
            return True
        # Fallback: at least half of the shorter artist's meaningful words appear in the longer
        # (handles "Taylor Swift" vs "Taylor Swift & Post Malone" where Jaccard is 0.4).
        # Use len > 3 (not > 2) so that "the" (len=3) is excluded — "The Weeknd" and
        # "The National" both contain "the" which would otherwise create a false overlap.
        # Short acronym artists (BTS, SZA, EXO, IVE) produce empty word sets here and
        # fall through to the Jaccard gate below, which correctly handles them via
        # exact token matching (Jaccard("bts","bts") = 1.0).
        x_words = {w for w in x.split() if len(w) > 3}
        y_words = {w for w in y.split() if len(w) > 3}
        if not x_words or not y_words:
            # Short/acronym artist names — use substring check first (catches "BTS" in
            # "BTS x Coldplay"), then fall back to Jaccard for non-substring cases.
            if len(x) >= 2 and (x in y or y in x):
                return True
            return _token_jaccard(x, y) >= JACCARD_THRESHOLD
        overlap = x_words & y_words
        shorter_len = min(len(x_words), len(y_words))
        return len(overlap) / shorter_len >= 0.5

    if not _artists_compatible(na_artist, nb_artist):
        return False

    # 2. Substring containment (normalized titles)
    # F1: Bare substring containment without a length guard causes "Love" to match
    # "Love Story", "Lovesick", "Lover", etc. Enforce: shorter title must be at least
    # MIN_SUBSTR_LEN characters AND at least 50% the length of the longer title.
    # This allows "Golden Hour" (11) to match "Golden Hour (Remix)" after strip while
    # blocking "Love" (4) from matching "Love Story" (10, ratio 0.40 < 0.50).
    _MIN_SUBSTR_LEN = 5
    if na_title and nb_title:
        shorter = na_title if len(na_title) <= len(nb_title) else nb_title
        longer = nb_title if len(na_title) <= len(nb_title) else na_title
        if (
            len(shorter) >= _MIN_SUBSTR_LEN
            and len(shorter) / len(longer) >= 0.5
            and shorter in longer
        ):
            return True

    # 3. Fuzzy title similarity (two independent gates — explicit threshold semantics)
    # F4: The original code called _fuzzy_ratio() then re-extracted Jaccard via a second
    # _token_jaccard() call, computing Jaccard twice. Simplified: Jaccard is the looser
    # gate (>= 0.60), raw SequenceMatcher is the stricter gate (>= 0.75). Both are
    # checked independently; whichever fires first wins.
    jaccard = _token_jaccard(na_title, nb_title)
    if jaccard >= JACCARD_THRESHOLD:
        return True
    seq = SequenceMatcher(None, na_title, nb_title).ratio()
    if seq >= FUZZY_THRESHOLD:
        return True

    return False


def _compute_platform_rank_bonus(rank: int, total_in_list: int) -> float:
    """
    Convert rank (1 = best) to a bonus score in [0, _MAX_RANK_BONUS].
    Rank 1 of 30 → full bonus. Rank 30 → 0 bonus.
    """
    if rank <= 0 or total_in_list <= 0:
        return 0.0
    # Linear decay: rank 1 → max, rank N → ~0
    fraction = max(0.0, (total_in_list - rank) / total_in_list)
    return round(fraction * _MAX_RANK_BONUS, 1)


def _compute_cross_platform_score(
    platform_data: dict[str, dict[str, Any]],
    platform_counts: dict[str, int],
) -> float:
    """
    Compute the cross-platform trending score using a smooth multiplier (fix #4).

    avg_rank_signal = mean of (1 - rank/total) across platforms, in [0, 1]
    multiplier      = 1.0 (1 platform) / 1.6 (2 platforms) / 2.0 (3 platforms)
    score           = avg_rank_signal * multiplier * 100, capped at [0, 100]

    This avoids the hard step-function of the old 30/65/100 base approach and
    continuously rewards both rank quality and platform breadth.
    """
    num_platforms = len(platform_data)
    if num_platforms == 0:
        return 0.0

    # Average normalized rank signal across platforms
    rank_signals = []
    for platform, pdata in platform_data.items():
        rank = pdata.get("rank", 0)
        total = platform_counts.get(platform, 30)
        if rank > 0 and total > 0:
            # fraction: rank 1 of 30 → 0.967; rank 30 of 30 → 0.0
            signal = max(0.0, (total - rank) / total)
        else:
            # F5: 0.5 (median) was too optimistic — an unknown-rank 3-platform track
            # scored higher than a rank-1 single-platform track. Use 0.3 (pessimistic)
            # because unknown-rank entries are typically tail items the API didn't rank.
            signal = 0.3  # conservative default for missing rank data
        rank_signals.append(signal)

    avg_signal = sum(rank_signals) / len(rank_signals) if rank_signals else 0.0

    # Smooth multiplier rewards breadth (fix #4)
    multiplier = {1: 1.0, 2: 1.6, 3: 2.0}.get(num_platforms, 1.0)

    score = min(100.0, avg_signal * multiplier * 100.0)
    return round(score, 1)


def _infer_spread(platform_data: dict[str, dict[str, Any]]) -> str:
    """
    Infer spread label from available signals (fix #5).

    - "viral"     : trending on 3 platforms
    - "spreading" : trending on 2 platforms, OR 1 platform with TikTok trend_change > 10
    - "emerging"  : only on 1 platform (no strong TikTok signal)
    """
    num = len(platform_data)
    if num >= 3:
        return "viral"

    # Check TikTok trend_change for a boost signal (applies to both 1- and 2-platform songs)
    tt = platform_data.get("tiktok", {})
    change_raw = str(tt.get("trend_change", "")).strip().lstrip("+")
    try:
        tiktok_change = float(change_raw)
    except (ValueError, TypeError):
        tiktok_change = 0.0

    if num == 2:
        return "spreading"
    # Single platform: check TikTok signal (fix #5)
    if tiktok_change > 10:
        return "spreading"
    return "emerging"


def _infer_momentum(platform_data: dict[str, dict[str, Any]]) -> str:
    """Backward-compat alias — delegates to _infer_spread (fix #5)."""
    return _infer_spread(platform_data)


# ---------------------------------------------------------------------------
# Merge and cross-reference
# ---------------------------------------------------------------------------


def _dedup_platform_tracks(tracks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Remove duplicate entries within a single platform's track list.

    F6: If a platform sub-CLI returns the same song twice (e.g., "As It Was" at rank 3
    and "As It Was (Harry Styles)" at rank 17), two entries with slightly different raw
    titles both survive normalization as different keys. The first becomes canonical;
    the second creates a spurious extra entry if artist is missing (because
    _artists_compatible returns True for unknown artists). This pre-merge dedup keeps
    only the highest-ranked (lowest rank number) entry per normalized key within a
    single platform, before cross-platform merging begins.
    """
    seen: dict[str, dict[str, Any]] = {}
    # Sort ascending by rank so the highest-ranked (lowest number) entry is seen first
    # Use `or 9999` (not default 9999) so rank=0 sentinels sort last, not first.
    # Some fetchers use rank=0 for "no rank data" — those shouldn't win over rank=1.
    for track in sorted(tracks, key=lambda t: t.get("rank") or 9999):
        key = _norm_key(track.get("artist", ""), track.get("title", ""))
        if key not in seen:
            seen[key] = track
    return list(seen.values())


def merge_platforms(
    platform_tracks: dict[str, list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    """
    Merge tracks from all platforms into a unified cross-referenced list.

    Algorithm:
      - Start with all YouTube tracks as seed (most structured data)
      - Then add TikTok tracks, matching against already-merged entries
      - Then add Instagram tracks, matching against already-merged entries
      - Unmatched tracks from each platform are added as platform-only entries
      - Compute cross_platform_score and momentum for every entry
    """
    platform_counts = {p: len(t) for p, t in platform_tracks.items()}

    # Each merged entry: {title, artist, _norm_title, _norm_artist, platforms, platform_data}
    # _norm_title / _norm_artist are cached at insertion time (Finding 2) to avoid
    # re-normalizing on every comparison inside _find_match.
    merged: list[dict[str, Any]] = []

    # Finding 1: two-level index for O(1) exact lookup before falling back to O(N) fuzzy scan.
    # Key: f"{norm_artist}::{norm_title}" → index into merged list.
    exact_index: dict[str, int] = {}

    def _find_match(norm_title: str, norm_artist: str) -> int | None:
        """
        Return index of matching entry in merged, or None.

        Level 1 — O(1) exact normalized key lookup via exact_index.
        Level 2 — O(N) fuzzy scan using pre-cached _norm_* fields (Finding 2).
        """
        # Level 1: exact match
        key = f"{norm_artist}::{norm_title}"
        if key in exact_index:
            return exact_index[key]

        # Level 2: fuzzy scan — uses pre-cached normalized fields to avoid re-normalization
        for i, entry in enumerate(merged):
            if _tracks_match_prenorm(
                norm_title, norm_artist, entry["_norm_title"], entry["_norm_artist"]
            ):
                return i
        return None

    # Seed order: youtube, tiktok, instagram
    for platform in ("youtube", "tiktok", "instagram"):
        # F6: Deduplicate within each platform before cross-platform merging.
        # Keeps the highest-ranked entry when the same song appears more than once
        # in a single platform's returned list (e.g., rank 3 + rank 17 duplicates).
        tracks = _dedup_platform_tracks(platform_tracks.get(platform, []))
        for track in tracks:
            title = track.get("title", "") or ""
            artist = track.get("artist", "") or ""
            if not title:
                continue

            # Pre-normalize once per incoming track (Finding 2)
            norm_title = _normalize(title)
            norm_artist = _normalize(artist)

            idx = _find_match(norm_title, norm_artist)

            # Build platform-specific payload (only relevant fields)
            pdata: dict[str, Any] = {"rank": track.get("rank", 0)}
            if platform == "youtube":
                pdata["view_count"] = track.get("view_count", 0)
                pdata["trending_score"] = track.get("trending_score", 0)
                pdata["video_url"] = track.get("video_url", "")
                pdata["source"] = track.get("source", "")
            elif platform == "tiktok":
                pdata["posts"] = track.get("posts", "")
                pdata["duration"] = track.get("duration", "")
                pdata["trend_change"] = track.get("trend_change", "")
            elif platform == "instagram":
                pdata["usage_count"] = track.get("usage_count", 0)
                pdata["audio_score"] = track.get("audio_score", 0)

            if idx is None:
                # New entry — store pre-normalized keys for future lookups (Finding 2)
                new_idx = len(merged)
                merged.append(
                    {
                        "title": title,
                        "artist": artist,
                        "_norm_title": norm_title,
                        "_norm_artist": norm_artist,
                        "platforms": [platform],
                        "platform_data": {platform: pdata},
                    }
                )
                # Register in exact index (Finding 1)
                exact_index[f"{norm_artist}::{norm_title}"] = new_idx
            else:
                # Merge into existing
                entry = merged[idx]
                if platform not in entry["platforms"]:
                    entry["platforms"].append(platform)
                    entry["platform_data"][platform] = pdata
                    # Prefer longer/more informative title + artist
                    if len(title) > len(entry["title"]) and entry["title"].lower() in title.lower():
                        pass  # keep existing (it's a substring of new — existing is cleaner)
                    elif len(artist) > len(entry["artist"]) and not entry["artist"]:
                        entry["artist"] = artist
                        # Update cached norm if artist was previously empty
                        entry["_norm_artist"] = norm_artist

    # Compute scores and spread label (fix #5: field renamed from "momentum" to "spread")
    for entry in merged:
        pd = entry["platform_data"]
        entry["cross_platform_score"] = _compute_cross_platform_score(pd, platform_counts)
        entry["spread"] = _infer_spread(pd)
        entry["momentum"] = entry["spread"]  # backward-compat alias

    # Sort: cross_platform_score desc, then number of platforms desc
    merged.sort(key=lambda e: (-e["cross_platform_score"], -len(e["platforms"])))

    # Assign unified rank
    for i, entry in enumerate(merged, 1):
        entry["rank"] = i

    return merged


# ---------------------------------------------------------------------------
# AI analysis
# ---------------------------------------------------------------------------

_ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
_ANTHROPIC_MODEL = "claude-sonnet-4-20250514"
_ANTHROPIC_VERSION = "2023-06-01"


def _call_claude(prompt: str, system: str = "", max_tokens: int = 1024) -> str | None:
    """Call Anthropic Messages API using stdlib urllib. Returns text or None."""
    try:
        api_key = get_secret("anthropic-api-key")
    except Exception:
        api_key = None
    if not api_key:
        logger.debug("Anthropic API key not found in Keychain")
        return None

    payload = {
        "model": _ANTHROPIC_MODEL,
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": prompt}],
    }
    if system:
        payload["system"] = system

    body = json.dumps(payload).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "x-api-key": api_key,
        "anthropic-version": _ANTHROPIC_VERSION,
    }

    req = urllib.request.Request(_ANTHROPIC_API_URL, data=body, method="POST", headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            result = json.loads(resp.read().decode("utf-8"))
        parts = [b.get("text", "") for b in result.get("content", []) if b.get("type") == "text"]
        text = "\n".join(parts).strip()
        return text or None
    except urllib.error.HTTPError as e:
        logger.warning("Anthropic API HTTP %d", e.code)
    except urllib.error.URLError as e:
        logger.warning("Anthropic API network error: %s", e.reason)
    except Exception as e:
        logger.warning("Anthropic API error: %s", e)
    return None


def run_ai_analysis(merged: list[dict[str, Any]], platform_tracks: dict[str, list]) -> str | None:
    """Generate trend analysis via Claude."""
    cross_platform = [e for e in merged if len(e["platforms"]) >= 2]
    top_n = merged[:20]

    summary_lines = []
    for e in top_n:
        plats = ", ".join(e["platforms"])
        score = e["cross_platform_score"]
        summary_lines.append(
            f"  #{e['rank']} {e['title']} — {e['artist']} | {plats} | score {score}"
        )

    platform_status = []
    for p, t in platform_tracks.items():
        platform_status.append(f"  {p}: {len(t)} tracks fetched")

    prompt = f"""You are a music trend analyst. Analyze these cross-platform trending audio results:

Platform data collected:
{chr(10).join(platform_status)}

Top {len(top_n)} trending tracks (ranked by cross-platform score):
{chr(10).join(summary_lines)}

Cross-platform hits (trending on 2+ platforms): {len(cross_platform)} songs

Provide:
1. 3-4 key insights about what these trends reveal about current music culture
2. Which genres or artists are dominating
3. Any notable songs that appear across all 3 platforms (biggest viral signals)
4. What content creators should know about using trending audio

Keep response concise (under 300 words). No bullet numbering needed — write naturally."""

    system = (
        "You are a music industry analyst specializing in social media trend intelligence. "
        "Be specific, insightful, and actionable. Avoid generic statements."
    )

    return _call_claude(prompt, system=system, max_tokens=600)


# ---------------------------------------------------------------------------
# Output formatters
# ---------------------------------------------------------------------------


def _truncate(s: str, max_len: int) -> str:
    """Truncate string with ellipsis."""
    s = str(s) if s else ""
    return s if len(s) <= max_len else s[: max_len - 1] + "\u2026"


def _platform_badge(platform: str) -> str:
    """Coloured platform badge."""
    badges = {
        "youtube": f"{RED}YT{RESET}",
        "tiktok": f"{CYAN}TT{RESET}",
        "instagram": f"{MAGENTA}IG{RESET}",
    }
    return badges.get(platform, platform[:2].upper())


def _format_platform_col(platform: str, platform_data: dict[str, Any], entries: list[dict]) -> str:
    """Format a platform column value: rank number or dash."""
    if platform not in platform_data:
        return f"{DIM}—{RESET}"
    rank = platform_data[platform].get("rank", 0)
    return str(rank) if rank else "?"


def _print_table(entries: list[dict[str, Any]], cross_only: bool = False) -> None:
    """Print the unified trending table."""
    if not entries:
        print(f"  {DIM}(no results){RESET}")
        return

    # Header
    print(
        f"\n  {'#':>3}  {'Song / Title':<38}  {'Artist':<24}  {'YT':>4}  {'TT':>4}  {'IG':>4}  {'Score':>7}  {'Spread'}"
    )
    print(
        f"  {'—' * 3}  {'—' * 38}  {'—' * 24}  {'—' * 4}  {'—' * 4}  {'—' * 4}  {'—' * 7}  {'—' * 8}"
    )

    cross_count = 0
    for entry in entries:
        rank = entry.get("rank", "")
        title = _truncate(entry.get("title", ""), 38)
        artist = _truncate(entry.get("artist", "Unknown"), 24)
        platforms = entry.get("platforms", [])
        pd = entry.get("platform_data", {})
        score = entry.get("cross_platform_score", 0)
        spread = entry.get("spread", entry.get("momentum", "emerging"))  # fix #5

        num_platforms = len(platforms)

        # Highlight multi-platform songs
        if num_platforms >= 2:
            cross_count += 1
            title_str = f"{BOLD}{title}{RESET}"
            score_str = f"{GREEN}{score:>7.1f}{RESET}"
        else:
            title_str = title
            score_str = f"{score:>7.1f}"

        yt_col = _format_platform_col("youtube", pd, entries)
        tt_col = _format_platform_col("tiktok", pd, entries)
        ig_col = _format_platform_col("instagram", pd, entries)

        # Spread label colour (fix #5: viral/spreading/emerging)
        spread_colours = {"viral": GREEN, "spreading": CYAN, "emerging": YELLOW}
        mc = spread_colours.get(spread, RESET)
        momentum_str = f"{mc}{spread}{RESET}"

        # Multi-platform indicator
        if num_platforms >= 3:
            marker = f" {GREEN}★{RESET}"
        elif num_platforms >= 2:
            marker = f" {CYAN}•{RESET}"
        else:
            marker = ""

        print(
            f"  {rank:>3}  {title_str:<38}  {artist:<24}  "
            f"{yt_col:>4}  {tt_col:>4}  {ig_col:>4}  {score_str}  {momentum_str}{marker}"
        )

    print()
    print(
        f"  {DIM}Legend: {GREEN}★{RESET}{DIM} = all 3 platforms  "
        f"{CYAN}•{RESET}{DIM} = 2 platforms  "
        f"Columns show rank on each platform (— = not trending there){RESET}"
    )
    print(
        f"  {DIM}Cross-platform hits: {BOLD}{cross_count}{RESET}{DIM} songs trending on 2+ platforms{RESET}"
    )


def _output_json(
    merged: list[dict[str, Any]],
    platform_tracks: dict[str, list],
    platform_errors: list[str],
    output_dir: str | None,
) -> None:
    """Output full structured JSON."""
    # F10: Strip internal cache fields (prefixed with "_") before JSON output.
    # Fields like _norm_title and _norm_artist are implementation details used during
    # cross-platform matching; they add noise and ~20-40 bytes per entry for consumers.
    clean_results = [
        {k: v for k, v in entry.items() if not k.startswith("_")}
        for entry in merged
    ]
    payload = {
        "generated_at": datetime.now(UTC).isoformat(),
        "platform_counts": {p: len(t) for p, t in platform_tracks.items()},
        "platform_errors": platform_errors,
        "cross_platform_count": sum(1 for e in merged if len(e["platforms"]) >= 2),
        "total_count": len(merged),
        "results": clean_results,
    }

    text = json.dumps(payload, indent=2, default=str)

    if output_dir:
        out_path = Path(output_dir)
        out_path.mkdir(parents=True, exist_ok=True)
        ts = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
        filename = out_path / f"trending_audio_{ts}.json"
        filename.write_text(text)
        print(str(filename))
    else:
        print(text)


# ---------------------------------------------------------------------------
# Argument parser
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="trending-audio",
        description=(
            f"Trending Audio Unified CLI v{VERSION}\n"
            "Cross-references trending music from YouTube, TikTok, and Instagram.\n"
            "Songs trending on 2+ platforms are the real viral signal."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python3 tools/trending-audio/cli.py --limit 30\n"
            "  python3 tools/trending-audio/cli.py --cross-only\n"
            "  python3 tools/trending-audio/cli.py --platform youtube\n"
            "  python3 tools/trending-audio/cli.py --ai\n"
            "  python3 tools/trending-audio/cli.py --json --output-dir /tmp/\n"
        ),
    )

    parser.add_argument(
        "--limit",
        type=int,
        default=30,
        help="Max tracks to fetch from each platform (default: 30)",
    )
    parser.add_argument(
        "--platform",
        choices=["youtube", "tiktok", "instagram"],
        help="Filter output to a single platform only",
    )
    parser.add_argument(
        "--cross-only",
        action="store_true",
        help="Only show songs trending on 2+ platforms",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output full structured JSON",
    )
    parser.add_argument(
        "--ai",
        action="store_true",
        help="Pipe results through Claude for trend analysis",
    )
    parser.add_argument(
        "--output-dir",
        help="Save JSON output to this directory (implies --json)",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Verbose logging and fetch status",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be fetched without running",
    )

    return parser


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    log_level = logging.DEBUG if args.verbose else logging.WARNING
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    output_json = args.json or bool(args.output_dir)

    # Dry run
    if args.dry_run:
        print(f"\n{BOLD}{CYAN}Trending Audio Unified CLI — Dry Run{RESET}")
        platforms = [args.platform] if args.platform else ["youtube", "tiktok", "instagram"]
        for p in platforms:
            print(f"  {DIM}Would fetch:{RESET} {p} trending audio (--limit {args.limit})")
        print(f"  {DIM}Cross-only:{RESET} {args.cross_only}")
        print(f"  {DIM}AI analysis:{RESET} {args.ai}")
        if args.output_dir:
            print(f"  {DIM}Output dir:{RESET} {args.output_dir}")
        return 0

    # Header
    if not output_json:
        print(
            f"\n{BOLD}{CYAN}Trending Audio — Cross-Platform Intelligence{RESET}  {DIM}v{VERSION}{RESET}"
        )
        print(
            f"  {DIM}Fetching from YouTube, TikTok, Instagram in parallel...{RESET}",
            flush=True,
        )

    # Fetch from all platforms in parallel
    try:
        if args.platform:
            # Single-platform mode: only fetch the requested one
            fetcher_map = {
                "youtube": lambda: _fetch_youtube(args.limit),
                "tiktok": lambda: _fetch_tiktok(args.limit),
                "instagram": lambda: _fetch_instagram(args.limit),
            }
            _platform, tracks = fetcher_map[args.platform]()
            platform_tracks = {
                "youtube": [],
                "tiktok": [],
                "instagram": [],
                args.platform: tracks,
            }
        else:
            platform_tracks = fetch_all_platforms(args.limit, verbose=args.verbose)
    except Exception as e:
        logger.exception("Unexpected fetch error")
        if output_json:
            print(json.dumps({"error": str(e), "type": "unexpected_error"}))
        else:
            print(f"\n{RED}Error: {e}{RESET}")
        return 2

    # Collect error info for any empty platforms
    platform_errors: list[str] = []
    for p, t in platform_tracks.items():
        if not t:
            platform_errors.append(f"{p}: no data returned (may be down or blocked)")

    total_fetched = sum(len(t) for t in platform_tracks.values())

    if not output_json:
        print()
        for p, t in platform_tracks.items():
            if t:
                print(f"  {GREEN}✓{RESET} {p.capitalize():<12} {len(t)} tracks")
            else:
                print(f"  {YELLOW}✗{RESET} {p.capitalize():<12} {DIM}no data{RESET}")
        print()

    if total_fetched == 0:
        if output_json:
            print(
                json.dumps(
                    {
                        "error": "No data from any platform.",
                        "platform_errors": platform_errors,
                    }
                )
            )
        else:
            print(f"  {RED}No data retrieved from any platform.{RESET}")
            print(f"  {DIM}Check platform CLI tools individually for diagnostics.{RESET}\n")
        return 1

    # Merge and cross-reference
    if not output_json:
        print(f"  {DIM}Cross-referencing across platforms...{RESET}", flush=True)

    merged = merge_platforms(platform_tracks)

    # Apply filters
    display = merged

    if args.cross_only:
        display = [e for e in display if len(e["platforms"]) >= 2]

    if args.platform and not args.cross_only:
        # Single platform: show only entries from that platform, re-sorted by rank
        display = [e for e in display if args.platform in e["platforms"]]
        display.sort(
            key=lambda e: e.get("platform_data", {}).get(args.platform, {}).get("rank", 999)
        )

    display = display[: args.limit]

    # Output
    if output_json:
        _output_json(display, platform_tracks, platform_errors, args.output_dir)
    else:
        _print_table(display, cross_only=args.cross_only)

        # Summary stats
        cross_count = sum(1 for e in merged if len(e["platforms"]) >= 2)
        all_three = sum(1 for e in merged if len(e["platforms"]) >= 3)
        print()
        print(f"  {BOLD}Summary:{RESET} {len(merged)} unique tracks found across all platforms")
        print(
            f"  {GREEN}{cross_count}{RESET} trending on 2+ platforms  ·  {GREEN}{all_three}{RESET} trending on all 3"
        )
        if platform_errors:
            print(f"\n  {YELLOW}Platform warnings:{RESET}")
            for err in platform_errors:
                print(f"    {DIM}{err}{RESET}")
        print()

    # AI analysis
    if args.ai:
        if output_json:
            logger.debug("--ai is a no-op in --json mode")
        else:
            print(
                f"\n  {BOLD}{CYAN}AI Trend Analysis{RESET}  {DIM}(claude-sonnet-4-20250514){RESET}"
            )
            print(f"  {DIM}Analyzing {len(merged)} tracks...{RESET}\n", flush=True)
            analysis = run_ai_analysis(merged, platform_tracks)
            if analysis:
                for line in analysis.splitlines():
                    print(f"  {line}")
                print()
            else:
                print(
                    f"  {YELLOW}AI analysis unavailable — check Anthropic API key in Keychain.{RESET}\n"
                )

    return 0


if __name__ == "__main__":
    sys.exit(main())
