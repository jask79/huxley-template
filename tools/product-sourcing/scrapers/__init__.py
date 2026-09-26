"""
Shared scraper utilities for Sourcerer.

Platform-specific scrapers live in sibling modules (e.g. alibaba.py, 1688.py).
This module provides common parsing helpers used across all scrapers.
"""

import re
import unicodedata
from typing import Optional, Tuple


def parse_price_range(text: str) -> Tuple[Optional[float], Optional[float]]:
    """
    Parse a price range string into (min, max) floats.

    Handles multiple formats:
        "$0.50 - $1.20"     -> (0.50, 1.20)
        "US $0.50-1.20"     -> (0.50, 1.20)
        "0.50 - 1.20"       -> (0.50, 1.20)
        "$3.50"             -> (3.50, 3.50)

    Returns (None, None) if parsing fails.
    """
    if not text or not text.strip():
        return None, None

    text = text.strip()

    # Remove currency symbols and prefixes
    text = re.sub(r"(?:US\s*)?[\$\u00a5\u20ac\u00a3\uffe5]", "", text)
    text = re.sub(r"(?:USD|CNY|EUR|GBP|RMB)\s*", "", text, flags=re.IGNORECASE)
    text = text.strip()

    # Try range pattern: "0.50 - 1.20" or "0.50-1.20"
    range_match = re.match(
        r"(\d+(?:\.\d+)?)\s*[-\u2013\u2014~]\s*(\d+(?:\.\d+)?)", text
    )
    if range_match:
        try:
            return float(range_match.group(1)), float(range_match.group(2))
        except ValueError:
            pass

    # Try single price: "3.50"
    single_match = re.match(r"(\d+(?:\.\d+)?)", text)
    if single_match:
        try:
            val = float(single_match.group(1))
            return val, val
        except ValueError:
            pass

    return None, None


def parse_moq(text: str) -> Tuple[Optional[int], str]:
    """
    Parse a MOQ (Minimum Order Quantity) string.

    Handles:
        "100 Pieces"    -> (100, "pieces")
        "500 Sets"      -> (500, "sets")
        "1,000 Units"   -> (1000, "units")
        "50"            -> (50, "pieces")

    Returns (None, "pieces") if parsing fails.
    """
    if not text or not text.strip():
        return None, "pieces"

    text = text.strip()

    # Extract number (with optional commas)
    num_match = re.match(r"([\d,]+)", text)
    if not num_match:
        return None, "pieces"

    try:
        quantity = int(num_match.group(1).replace(",", ""))
    except ValueError:
        return None, "pieces"

    # Extract unit (everything after the number, stripped)
    unit_text = text[num_match.end():].strip().lower()

    # Normalize common unit names
    unit_map = {
        "piece": "pieces",
        "pieces": "pieces",
        "pc": "pieces",
        "pcs": "pieces",
        "set": "sets",
        "sets": "sets",
        "unit": "units",
        "units": "units",
        "pair": "pairs",
        "pairs": "pairs",
        "dozen": "dozens",
        "dozens": "dozens",
        "box": "boxes",
        "boxes": "boxes",
        "carton": "cartons",
        "cartons": "cartons",
        "roll": "rolls",
        "rolls": "rolls",
        "meter": "meters",
        "meters": "meters",
        "yard": "yards",
        "yards": "yards",
        "ton": "tons",
        "tons": "tons",
        "kg": "kg",
        "kilogram": "kg",
        "kilograms": "kg",
    }

    # Try to match the unit
    unit = "pieces"  # default
    for key, normalized in unit_map.items():
        if unit_text.startswith(key):
            unit = normalized
            break

    return quantity, unit


def normalize_platform_id(platform: str, raw_id: str) -> str:
    """
    Create a normalized platform-prefixed ID.

    Examples:
        ("alibaba", "abc123")       -> "ali:abc123"
        ("1688", "678901")          -> "1688:678901"
        ("dhgate", "xyz456")       -> "dhg:xyz456"
        ("made-in-china", "mic1")  -> "mic:mic1"

    Platform prefixes:
        alibaba       -> ali
        1688          -> 1688
        dhgate        -> dhg
        made-in-china -> mic
    """
    prefix_map = {
        "alibaba": "ali",
        "1688": "1688",
        "dhgate": "dhg",
        "made-in-china": "mic",
        "aliexpress": "ae",
    }

    prefix = prefix_map.get(platform.lower(), platform.lower()[:3])
    # Clean the raw ID — alphanumeric, hyphens, underscores only
    clean_id = re.sub(r"[^a-zA-Z0-9_-]", "", raw_id)
    return f"{prefix}:{clean_id}"


def sanitize_filename(name: str) -> str:
    """
    Sanitize a string for use as a filename.

    Removes or replaces characters that are unsafe in filenames across
    macOS, Linux, and Windows. Preserves unicode letters (e.g. Chinese).

    Examples:
        "Shenzhen Mfg. Co., Ltd."  -> "shenzhen-mfg-co-ltd"
        "Product #42 (Special!)"   -> "product-42-special"
    """
    if not name:
        return "unnamed"

    # Normalize unicode
    name = unicodedata.normalize("NFKC", name)

    # Convert to lowercase
    name = name.lower()

    # Replace unsafe characters with hyphens
    name = re.sub(r"[^\w\s-]", "", name)
    name = re.sub(r"[\s_]+", "-", name)

    # Collapse multiple hyphens
    name = re.sub(r"-{2,}", "-", name)

    # Strip leading/trailing hyphens
    name = name.strip("-")

    return name or "unnamed"
