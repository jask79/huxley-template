"""
Algorithm module loader.

Loads algorithm submodules directly by file path to bypass the
algorithms/__init__.py which references stub class names that
don't exist yet (KeywordScorer, OutlierDetector).

Usage:
    from algo_loader import keyword_algo, outlier_algo, seo_algo

    result = keyword_algo.compute_keyword_competition(...)
    analysis = outlier_algo.compute_outlier_scores(...)
    scorer = seo_algo.SEOScorer()
"""

import importlib.util
import sys
from pathlib import Path

_ALGO_DIR = Path(__file__).resolve().parent / "algorithms"


def _load_module(name: str, file_path: Path):
    """Load a Python module from a file path without triggering __init__.py."""
    spec = importlib.util.spec_from_file_location(name, str(file_path))
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load {name} from {file_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


keyword_algo = _load_module("_yt_intel_keyword_algo", _ALGO_DIR / "keyword.py")
outlier_algo = _load_module("_yt_intel_outlier_algo", _ALGO_DIR / "outlier.py")
seo_algo = _load_module("_yt_intel_seo_algo", _ALGO_DIR / "seo.py")

# Re-export commonly used names for convenience
compute_keyword_competition = keyword_algo.compute_keyword_competition
compute_keyword_batch = keyword_algo.compute_keyword_batch
estimate_relative_volume = keyword_algo.estimate_relative_volume
SearchResultVideo = keyword_algo.SearchResultVideo
AutocompleteData = keyword_algo.AutocompleteData
KeywordResult = keyword_algo.KeywordResult

compute_outlier_scores = outlier_algo.compute_outlier_scores
VideoInput = outlier_algo.VideoInput
OutlierResult = outlier_algo.OutlierResult
OutlierAnalysis = outlier_algo.OutlierAnalysis

SEOScorer = seo_algo.SEOScorer
SEOResult = seo_algo.SEOResult
FactorScore = seo_algo.FactorScore
