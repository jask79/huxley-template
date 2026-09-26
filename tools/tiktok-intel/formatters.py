"""Terminal table formatting and JSON output.

Formatting conventions:
  - _visible_len()  — strip ANSI codes for width calc
  - _format_table() — box-drawing tables
  - _json_output()  — json.dumps with indent=2
  - _truncate()     — ellipsis truncation
Plus:
  - parse_human_number() — "1.2M" -> 1200000
  - print_header() / print_footer() — branded CLI chrome
"""

import json
import re
from typing import Any, List

from .config import BOLD, CYAN, DIM, GREEN, MAGENTA, RED, RESET, YELLOW, VERSION


# ---------------------------------------------------------------------------
# ANSI helpers
# ---------------------------------------------------------------------------

def _visible_len(s: str) -> int:
    """Length of string excluding ANSI escape codes."""
    return len(re.sub(r"\033\[[0-9;]*m", "", s))


def _truncate(s: str, max_len: int) -> str:
    """Truncate string with ellipsis if too long."""
    if _visible_len(s) <= max_len:
        return s
    return s[: max_len - 1] + "\u2026"


# ---------------------------------------------------------------------------
# Table formatting (mirrors tiktok.py _format_table exactly)
# ---------------------------------------------------------------------------

def format_table(headers: List[str], rows: List[List[str]], separator: str = "\u2502") -> str:
    """Format a table with box-drawing separators."""
    if not rows:
        return "  (no results)"

    col_widths = [len(h) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            if i < len(col_widths):
                col_widths[i] = max(col_widths[i], _visible_len(str(cell)))

    def _pad(text: str, width: int) -> str:
        pad = width - _visible_len(text)
        return text + " " * max(0, pad)

    header_parts = [_pad(h, col_widths[i]) for i, h in enumerate(headers)]
    header_line = f" {separator} ".join(header_parts)

    sep_parts = ["\u2500" * (w + 1) for w in col_widths]
    sep_line = f"\u2500{separator}\u2500".join(sep_parts)

    lines = [f" {header_line}", f" {sep_line}"]

    for row in rows:
        parts = []
        for i in range(len(headers)):
            cell = str(row[i] if i < len(row) else "")
            parts.append(_pad(cell, col_widths[i]))
        lines.append(f" {f' {separator} '.join(parts)}")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# JSON output
# ---------------------------------------------------------------------------

def json_output(data: Any) -> None:
    """Print JSON-formatted output."""
    print(json.dumps(data, indent=2, default=str))


# ---------------------------------------------------------------------------
# Human number parsing
# ---------------------------------------------------------------------------

_SUFFIXES = {
    "K": 1_000,
    "M": 1_000_000,
    "B": 1_000_000_000,
    "T": 1_000_000_000_000,
}


def parse_human_number(s: str) -> int:
    """Convert human-readable number strings to integers.

    Examples:
        "1.2M"   -> 1200000
        "500K"   -> 500000
        "3.5B"   -> 3500000000
        "1,234"  -> 1234
        "42"     -> 42
        ""       -> 0
    """
    if not s or not isinstance(s, str):
        return 0

    s = s.strip().replace(",", "").replace(" ", "")

    # Handle suffixed numbers (1.2M, 500K, etc.)
    upper = s.upper()
    for suffix, multiplier in _SUFFIXES.items():
        if upper.endswith(suffix):
            try:
                num = float(upper[: -len(suffix)])
                return int(num * multiplier)
            except ValueError:
                return 0

    # Plain number
    try:
        return int(float(s))
    except ValueError:
        return 0


# ---------------------------------------------------------------------------
# CLI chrome (header / footer)
# ---------------------------------------------------------------------------

def print_header(command: str, filters: dict = None) -> None:
    """Print a branded header for terminal output."""
    print(f"\n{BOLD}{MAGENTA}TikTok Intel{RESET} {DIM}v{VERSION}{RESET}")
    print(f"{CYAN}{command}{RESET}")
    if filters:
        parts = [f"{k}={v}" for k, v in filters.items() if v]
        if parts:
            print(f"{DIM}{', '.join(parts)}{RESET}")
    print()


def print_footer(count: int, cached: bool = False) -> None:
    """Print result count footer."""
    cache_tag = f" {DIM}(cached){RESET}" if cached else ""
    print(f"\n{DIM}{count} result(s){cache_tag}{RESET}\n")


def print_error(message: str, hint: str = "") -> None:
    """Print a formatted error message."""
    print(f"\n{RED}Error: {message}{RESET}")
    if hint:
        print(f"{YELLOW}{hint}{RESET}")
    print()
