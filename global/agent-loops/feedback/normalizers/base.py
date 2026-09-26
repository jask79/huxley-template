"""
Base class for tool-specific feedback normalizers.

All tool normalizers inherit from FeedbackNormalizer and implement
the normalize() method to convert raw tool output into structured feedback.
"""

from abc import ABC, abstractmethod
from typing import Any

from core.feedback_schema import NormalizedFeedback, SalientFragment


class FeedbackNormalizer(ABC):
    """Base class for tool-specific feedback normalizers."""

    @abstractmethod
    def normalize(self, raw_output: dict[str, Any]) -> NormalizedFeedback:
        """
        Convert tool output to normalized feedback.

        Args:
            raw_output: Dictionary with keys:
                - exit_code: int
                - stdout: str
                - stderr: str
                - tool: str (optional, normalizer name)

        Returns:
            NormalizedFeedback with structured error information
        """
        pass

    @abstractmethod
    def compute_signal_quality(self, feedback: NormalizedFeedback) -> float:
        """
        Compute quality score for this feedback.

        Args:
            feedback: The normalized feedback to score

        Returns:
            Quality score between 0.0 and 1.0
        """
        pass

    def _compute_base_quality(
        self, fragments: list[SalientFragment], full_output: str, has_file_info: bool = False
    ) -> float:
        """
        Compute base quality score from fragments.

        Args:
            fragments: List of salient fragments
            full_output: Full output text for noise detection
            has_file_info: Whether fragments have file/line information

        Returns:
            Quality score between 0.0 and 1.0
        """
        if len(fragments) == 0:
            return 0.1  # No useful info

        # Start with base score
        score = 0.5

        # Boost for specific error messages
        if all(len(f.message) > 10 for f in fragments):
            score += 0.2

        # Boost for file/line information
        if has_file_info:
            score += 0.2

        # Reduce score if output is extremely long (noisy)
        if len(full_output) > 10000:
            score *= 0.7
        elif len(full_output) > 50000:
            score *= 0.4

        # Reduce score if too many fragments (noisy)
        if len(fragments) > 20:
            score *= 0.8

        return min(1.0, max(0.0, score))

    def _extract_file_from_path(self, path: str) -> str:
        """
        Extract clean file path from various formats.

        Args:
            path: File path string (may include line numbers, etc.)

        Returns:
            Clean file path
        """
        # Remove line numbers like "file.py:123"
        if ":" in path:
            path = path.split(":")[0]

        # Remove whitespace
        path = path.strip()

        return path

    def _truncate_context(self, context: str, max_lines: int = 5) -> str:
        """
        Truncate context to reasonable size.

        Args:
            context: Full context string
            max_lines: Maximum number of lines to keep

        Returns:
            Truncated context
        """
        lines = context.split("\n")
        if len(lines) <= max_lines:
            return context

        return "\n".join(lines[:max_lines]) + f"\n... ({len(lines) - max_lines} more lines)"
