"""Trigger heuristic: should this session produce a skill proposal?

ALL of the following must hold:

1. Volume:    >= 8 tool calls
2. Diversity: >= 3 distinct tool types
3. Success signal: explicit positive keyword in last user message
                   OR clean exit + no error markers in the last 3 assistant turns
4. Dedupe:    handled by deduper.py, not here

This module is dependency-free (stdlib only) so it stays unit-testable.
"""

from __future__ import annotations

from dataclasses import dataclass

from .extractor import SessionSummary

MIN_TOOL_CALLS = 8
MIN_DISTINCT_TOOLS = 3

# Case-insensitive substring match. Whole-word matching avoids "perfect" inside
# "imperfect", but for common approval phrasing these are
# substrings to be matched as standalone tokens — checked at use site.
POSITIVE_KEYWORDS = (
    "ship it",
    "shipped",
    "perfect",
    "done",
    "great",
    "thanks",
    "thank you",
    "yes",
    "looks good",
    "nice work",
    "nailed it",
    "love it",
    "awesome",
)

# Markers that indicate the recent assistant turns were error-laden. If any
# of these appears in the last 3 assistant text blocks, "clean exit" is false.
ERROR_MARKERS = (
    "i encountered an error",
    "this failed",
    "<tool_use_error>",
    "traceback (most recent call last)",
    "exception:",
    "errno",
    "permission denied",
    "i wasn't able to",
    "i was unable to",
    "couldn't complete",
    "could not complete",
)


@dataclass
class TriggerDecision:
    propose: bool
    reasons: list[str]  # Always populated — explains why we did or didn't propose


def _has_positive_signal(text: str) -> bool:
    if not text:
        return False
    lower = text.lower().strip()
    # Tokenize on whitespace+punctuation to avoid matching "yes" inside "eyes".
    # Cheap approach: check standalone matches on word-boundary-ish neighbors.
    for kw in POSITIVE_KEYWORDS:
        if kw not in lower:
            continue
        # Ensure the match is a standalone token, not embedded mid-word.
        idx = lower.find(kw)
        while idx != -1:
            before_ok = idx == 0 or not lower[idx - 1].isalnum()
            end = idx + len(kw)
            after_ok = end == len(lower) or not lower[end].isalnum()
            if before_ok and after_ok:
                return True
            idx = lower.find(kw, idx + 1)
    return False


def _has_error_markers(text_blocks: list[str]) -> bool:
    blob = "\n".join(text_blocks).lower()
    return any(marker in blob for marker in ERROR_MARKERS)


def evaluate(summary: SessionSummary) -> TriggerDecision:
    """Decide whether to propose a skill from this session.

    Pure function — no I/O. Caller composes this with deduper.has_duplicate().
    """
    reasons: list[str] = []

    # Gate 1: Volume
    if summary.tool_call_count < MIN_TOOL_CALLS:
        reasons.append(
            f"volume: {summary.tool_call_count} tool calls < {MIN_TOOL_CALLS}"
        )
        return TriggerDecision(propose=False, reasons=reasons)
    reasons.append(f"volume ok: {summary.tool_call_count} tool calls")

    # Gate 2: Diversity
    distinct = summary.distinct_tool_types
    if len(distinct) < MIN_DISTINCT_TOOLS:
        reasons.append(
            f"diversity: {len(distinct)} distinct tools < {MIN_DISTINCT_TOOLS}"
        )
        return TriggerDecision(propose=False, reasons=reasons)
    reasons.append(f"diversity ok: {len(distinct)} distinct tools")

    # Gate 3: Success signal — EITHER explicit positive OR clean exit.
    explicit_positive = _has_positive_signal(summary.last_user_message)
    clean_exit = not _has_error_markers(summary.last_assistant_blocks)

    if explicit_positive:
        reasons.append("success: explicit positive keyword in last user message")
    elif clean_exit:
        reasons.append("success: clean exit (no error markers in last 3 assistant turns)")
    else:
        reasons.append(
            "success: neither explicit positive nor clean exit — error markers present"
        )
        return TriggerDecision(propose=False, reasons=reasons)

    return TriggerDecision(propose=True, reasons=reasons)
