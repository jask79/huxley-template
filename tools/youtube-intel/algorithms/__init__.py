"""
YouTube Intel -- Scoring Algorithms

Outlier scoring, keyword competition analysis, and SEO optimization.
"""

from .keyword import (
    compute_keyword_competition,
    compute_keyword_batch,
    estimate_relative_volume,
    KeywordResult,
    KeywordBatchResult,
    KeywordConfig,
    SearchResultVideo,
    AutocompleteData,
    TrendData,
)
from .outlier import (
    compute_outlier_scores,
    interpolate_subscriber_counts,
    OutlierResult,
    OutlierAnalysis,
    OutlierConfig,
    VideoInput,
)
from .seo import SEOScorer, SEOResult, FactorScore

__all__ = [
    # Keyword
    "compute_keyword_competition",
    "compute_keyword_batch",
    "estimate_relative_volume",
    "KeywordResult",
    "KeywordBatchResult",
    "KeywordConfig",
    "SearchResultVideo",
    "AutocompleteData",
    "TrendData",
    # Outlier
    "compute_outlier_scores",
    "interpolate_subscriber_counts",
    "OutlierResult",
    "OutlierAnalysis",
    "OutlierConfig",
    "VideoInput",
    # SEO
    "SEOScorer",
    "SEOResult",
    "FactorScore",
]
