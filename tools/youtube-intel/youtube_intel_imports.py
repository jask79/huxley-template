"""
Import helper for youtube-intel.

The directory name 'youtube-intel' contains a hyphen, making it
non-importable as a Python package. This module re-exports the
key objects so cli.py and command modules can do clean imports.
"""

import sys
from pathlib import Path

# Ensure the tool directory is on sys.path
_TOOL_DIR = Path(__file__).resolve().parent
if str(_TOOL_DIR) not in sys.path:
    sys.path.insert(0, str(_TOOL_DIR))

from client import (
    YouTubeIntelClient,
    YouTubeIntelError,
    CredentialError,
    AuthError,
    APIError,
    youtube_autocomplete,
    extract_video_id,
    format_count,
    format_duration,
    format_table,
    visible_len,
    GREEN,
    RED,
    YELLOW,
    CYAN,
    BOLD,
    DIM,
    RESET,
)

from db import (
    get_connection,
    add_tracked_video,
    remove_tracked_video,
    list_tracked_videos,
    get_tracked_video,
    add_vph_snapshot,
    get_vph_snapshots,
    get_latest_vph_snapshot,
    calculate_vph,
    calculate_avg_vph,
    add_competitor,
    remove_competitor,
    list_competitors,
    get_competitor,
    add_competitor_snapshot,
    get_competitor_snapshots,
    cache_keyword,
    get_cached_keyword,
    save_seo_score,
    get_latest_seo_score,
)

# Use algo_loader to bypass broken algorithms/__init__.py stubs
# (references KeywordScorer/OutlierDetector which don't exist yet)
from algo_loader import (
    compute_keyword_competition,
    compute_keyword_batch,
    estimate_relative_volume,
    SearchResultVideo,
    AutocompleteData,
    KeywordResult,
    compute_outlier_scores,
    VideoInput,
    OutlierResult,
    OutlierAnalysis,
    SEOScorer,
)

__all__ = [
    "YouTubeIntelClient",
    "YouTubeIntelError",
    "CredentialError",
    "AuthError",
    "APIError",
    "youtube_autocomplete",
    "extract_video_id",
    "format_count",
    "format_duration",
    "format_table",
    "visible_len",
    "get_connection",
    "GREEN", "RED", "YELLOW", "CYAN", "BOLD", "DIM", "RESET",
]
