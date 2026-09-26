"""
Normalizer for ruff linting output.

Parses ruff output and extracts structured linting violations.
"""

import json
import re
from typing import Any

from core.feedback_schema import (
    DeterministicBlocker,
    FeedbackCategory,
    NormalizedFeedback,
    SalientFragment,
)
from feedback.normalizers.base import FeedbackNormalizer


class RuffNormalizer(FeedbackNormalizer):
    """Parse and normalize ruff linting output."""

    # ruff output format: filename:line:col: CODE message
    ERROR_PATTERN = re.compile(
        r"^(?P<file>[^:]+):(?P<line>\d+):(?P<col>\d+):\s*(?P<code>[A-Z]+\d+)\s+(?P<message>.+)$"
    )

    # Codes that are blocking (errors) vs warnings
    BLOCKING_PREFIXES = {"F", "E9", "B9", "S"}

    # Auto-fixable codes
    AUTO_FIXABLE_CODES = {
        "F401",
        "I001",
        "E501",
        "W291",
        "W292",
        "Q000",
        "COM812",
    }

    def normalize(self, raw_output: dict[str, Any]) -> NormalizedFeedback:
        """
        Normalize ruff output into structured feedback.

        Args:
            raw_output: Dict with 'stdout', 'stderr', 'exit_code'

        Returns:
            NormalizedFeedback with parsed lint violations
        """
        stdout = raw_output.get("stdout", "")
        stderr = raw_output.get("stderr", "")
        exit_code = raw_output.get("exit_code", 0)

        # Try JSON format first (if --format json was used)
        if stdout.strip().startswith("[") or stdout.strip().startswith("{"):
            fragments = self._parse_json_format(stdout)
        else:
            fragments = self._parse_text_format(stdout + "\n" + stderr)

        success = exit_code == 0 and not any(f.severity == "error" for f in fragments)
        signal_quality = self.compute_signal_quality(
            NormalizedFeedback(
                success=success,
                exit_code=exit_code,
                category=FeedbackCategory.LINT_WARNING,
                is_deterministic_blocker=False,
                blocker_type=None,
                salient_fragments=fragments,
                suggested_scope=self._suggest_scope(fragments),
                signal_quality_score=0.5,  # placeholder
                feedback_source="ruff",
                stdout=stdout,
                stderr=stderr,
            )
        )

        return NormalizedFeedback(
            success=success,
            exit_code=exit_code,
            category=FeedbackCategory.LINT_WARNING,
            is_deterministic_blocker=False,
            blocker_type=None,
            salient_fragments=fragments,
            suggested_scope=self._suggest_scope(fragments),
            signal_quality_score=signal_quality,
            feedback_source="ruff",
            stdout=stdout,
            stderr=stderr,
        )

    def compute_signal_quality(self, feedback: NormalizedFeedback) -> float:
        """Compute quality score based on fragment detail."""
        has_file_info = any(
            f.file_path for f in feedback.salient_fragments
        )
        full_output = feedback.stdout + feedback.stderr
        return self._compute_base_quality(
            feedback.salient_fragments, full_output, has_file_info=has_file_info
        )

    def _parse_text_format(self, output: str) -> list[SalientFragment]:
        """Parse standard text output from ruff."""
        fragments = []
        for line in output.splitlines():
            match = self.ERROR_PATTERN.match(line.strip())
            if not match:
                continue
            data = match.groupdict()
            code = data["code"]
            severity = "error" if self._is_blocking(code) else "warning"
            fragments.append(
                SalientFragment(
                    message=f"{code}: {data['message']}",
                    severity=severity,
                    line_number=int(data["line"]),
                    file_path=data["file"],
                    context=f"col {data['col']}",
                )
            )
        return fragments

    def _parse_json_format(self, json_output: str) -> list[SalientFragment]:
        """Parse JSON format output from ruff."""
        try:
            data = json.loads(json_output)
        except json.JSONDecodeError:
            return [
                SalientFragment(
                    message="Failed to parse ruff JSON output",
                    severity="error",
                )
            ]

        fragments = []
        for item in data:
            code = item.get("code", "UNKNOWN")
            severity = "error" if self._is_blocking(code) else "warning"
            location = item.get("location", {})
            fragments.append(
                SalientFragment(
                    message=f"{code}: {item.get('message', '')}",
                    severity=severity,
                    line_number=location.get("row"),
                    file_path=item.get("filename", ""),
                    context=f"col {location.get('column', 0)}",
                )
            )
        return fragments

    def _is_blocking(self, code: str) -> bool:
        """Return True if this code should be treated as an error."""
        return any(code.startswith(prefix) for prefix in self.BLOCKING_PREFIXES)

    def _suggest_scope(self, fragments: list[SalientFragment]) -> str | None:
        """Return the file with the most violations."""
        if not fragments:
            return None
        counts: dict[str, int] = {}
        for f in fragments:
            if f.file_path:
                counts[f.file_path] = counts.get(f.file_path, 0) + 1
        if not counts:
            return None
        return max(counts, key=lambda k: counts[k])


# Register with feedback registry
def register(registry):
    """Register ruff normalizer with the feedback registry."""
    registry.register_normalizer("ruff", RuffNormalizer())
