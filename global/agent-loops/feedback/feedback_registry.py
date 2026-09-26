"""
Feedback registry for routing tool output to normalizers.

Central registry that maps tool names to their respective normalizers.
"""

from typing import Any

from core.feedback_schema import NormalizedFeedback
from feedback.normalizers.base import FeedbackNormalizer
from feedback.normalizers.eslint_normalizer import ESLintNormalizer
from feedback.normalizers.mypy_normalizer import MypyNormalizer
from feedback.normalizers.pytest_normalizer import PytestNormalizer
from feedback.normalizers.tsc_normalizer import TscNormalizer
from feedback.normalizers.vitest_normalizer import VitestNormalizer
from feedback.normalizers.xcodebuild_normalizer import XcodeBuildNormalizer

from feedback.normalizers.ruff_normalizer import RuffNormalizer
from feedback.normalizers.api_test_normalizer import ApiTestNormalizer


class FeedbackRegistry:
    """Central registry of feedback normalizers."""

    def __init__(self):
        """Initialize registry with available normalizers."""
        self.normalizers: dict[str, FeedbackNormalizer] = {
            "pytest": PytestNormalizer(),
            "eslint": ESLintNormalizer(),
            "xcodebuild": XcodeBuildNormalizer(),
            "vitest": VitestNormalizer(),
            "tsc": TscNormalizer(),
            "mypy": MypyNormalizer(),
            "ruff": RuffNormalizer(),
            "pytest_api": ApiTestNormalizer(),
        }

    def register_normalizer(self, tool: str, normalizer: FeedbackNormalizer) -> None:
        """
        Register a new normalizer for a tool.

        Args:
            tool: Tool name (e.g., 'mypy', 'tsc')
            normalizer: Normalizer instance
        """
        self.normalizers[tool] = normalizer

    def get_normalizer(self, tool: str) -> FeedbackNormalizer:
        """
        Get normalizer for a specific tool.

        Args:
            tool: Tool name

        Returns:
            FeedbackNormalizer instance

        Raises:
            ValueError: If no normalizer registered for tool
        """
        if tool not in self.normalizers:
            raise ValueError(
                f"No normalizer registered for tool: {tool}. "
                f"Available tools: {', '.join(self.normalizers.keys())}"
            )
        return self.normalizers[tool]

    def has_normalizer(self, tool: str) -> bool:
        """
        Check if normalizer exists for tool.

        Args:
            tool: Tool name

        Returns:
            True if normalizer exists
        """
        return tool in self.normalizers

    def normalize(self, tool: str, raw_output: dict[str, Any]) -> NormalizedFeedback:
        """
        Normalize output from any tool.

        Args:
            tool: Tool name (e.g., 'pytest', 'eslint')
            raw_output: Raw output dictionary with keys:
                - exit_code: int
                - stdout: str
                - stderr: str

        Returns:
            NormalizedFeedback with structured error information

        Raises:
            ValueError: If no normalizer registered for tool
        """
        normalizer = self.get_normalizer(tool)
        return normalizer.normalize(raw_output)

    def list_tools(self) -> list:
        """
        Get list of all registered tools.

        Returns:
            List of tool names
        """
        return sorted(self.normalizers.keys())


# Global registry instance (singleton pattern)
_registry: FeedbackRegistry | None = None


def get_registry() -> FeedbackRegistry:
    """
    Get global feedback registry instance.

    Returns:
        Global FeedbackRegistry singleton
    """
    global _registry
    if _registry is None:
        _registry = FeedbackRegistry()
    return _registry
