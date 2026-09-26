"""
Normalizer for mypy type checking output.

Parses mypy output and extracts structured type error information.
"""

import re
import time
from typing import Any

from core.feedback_schema import (
    DeterministicBlocker,
    FeedbackCategory,
    NormalizedFeedback,
    SalientFragment,
)
from feedback.normalizers.base import FeedbackNormalizer


class MypyNormalizer(FeedbackNormalizer):
    """Parse and normalize mypy type checking output."""

    # mypy output format: filename:line: error: message
    ERROR_PATTERN = re.compile(
        r"^(?P<file>[^:]+):(?P<line>\d+):\s*(?P<type>error|warning|note):\s*(?P<message>.+)$"
    )

    ERROR_CATEGORIES = {
        "incompatible": "type_mismatch",
        "has no attribute": "missing_attribute",
        "Cannot determine type": "type_inference_failure",
        "Missing type annotation": "missing_annotation",
        "Argument .* has incompatible type": "argument_type_error",
        "incompatible return value": "return_type_error",
        "has incompatible type": "assignment_error",
        "Unexpected keyword argument": "signature_error",
        "Too many arguments": "signature_error",
        "Missing positional argument": "signature_error",
        "imported but unused": "unused_import",
        "defined but never used": "unused_variable",
    }

    def normalize(self, raw_output: dict[str, Any]) -> NormalizedFeedback:
        """
        Normalize mypy output into structured feedback.

        Args:
            raw_output: Dict with 'stdout', 'stderr', 'exit_code'

        Returns:
            NormalizedFeedback with parsed type errors
        """
        stdout = raw_output.get("stdout", "")
        stderr = raw_output.get("stderr", "")
        exit_code = raw_output.get("exit_code", 0)

        # Combine stdout and stderr
        output = stdout + "\n" + stderr

        # Parse errors
        errors = self._parse_errors(output)
        salient_fragments = self._extract_salient_fragments(errors)

        # Determine category
        category = self._determine_category(errors, exit_code)

        # Check for deterministic blockers
        is_blocker, blocker_type = self._check_deterministic_blockers(output)

        # Compute quality score
        has_file_info = any(f.file_path is not None for f in salient_fragments)
        signal_quality = self._compute_base_quality(salient_fragments, output, has_file_info)

        # Generate summary if needed
        auto_summary = self._generate_summary(errors) if len(output) > 2000 else ""

        return NormalizedFeedback(
            success=exit_code == 0,
            exit_code=exit_code,
            category=category,
            is_deterministic_blocker=is_blocker,
            blocker_type=blocker_type,
            salient_fragments=salient_fragments,
            suggested_scope=self._suggest_scope(errors),
            signal_quality_score=signal_quality,
            feedback_source="mypy",
            stdout=stdout,
            stderr=stderr,
            timestamp=time.time(),
            tool_version=self._get_mypy_version(output),
            auto_summary=auto_summary,
        )

    def compute_signal_quality(self, feedback: NormalizedFeedback) -> float:
        """Compute quality score for mypy feedback."""
        has_file_info = any(f.file_path is not None for f in feedback.salient_fragments)
        return self._compute_base_quality(
            feedback.salient_fragments, feedback.stdout + feedback.stderr, has_file_info
        )

    def _parse_errors(self, output: str) -> list[dict[str, Any]]:
        """Parse mypy errors from output."""
        errors = []

        for line in output.splitlines():
            match = self.ERROR_PATTERN.match(line.strip())
            if not match:
                continue

            error_data = match.groupdict()

            errors.append(
                {
                    "file": error_data["file"],
                    "line": int(error_data["line"]),
                    "type": error_data["type"],
                    "message": error_data["message"],
                    "category": self._categorize_error(error_data["message"]),
                }
            )

        return errors

    def _extract_salient_fragments(self, errors: list[dict]) -> list[SalientFragment]:
        """Convert errors to salient fragments."""
        fragments = []

        for error in errors:
            severity = "error" if error["type"] == "error" else "warning"

            fragments.append(
                SalientFragment(
                    message=error["message"],
                    severity=severity,
                    line_number=error.get("line"),
                    file_path=error.get("file"),
                    context=error.get("category", ""),
                )
            )

        return fragments

    def _check_deterministic_blockers(
        self, output: str
    ) -> tuple[bool, DeterministicBlocker | None]:
        """Check for blockers that require immediate escalation."""
        # No specific deterministic blockers for mypy
        return False, None

    def _determine_category(self, errors: list[dict], exit_code: int) -> FeedbackCategory:
        """Determine failure category from errors."""
        if exit_code == 0:
            return FeedbackCategory.UNKNOWN

        # All mypy errors are type errors
        if len(errors) > 0:
            return FeedbackCategory.TYPE_ERROR

        return FeedbackCategory.UNKNOWN

    def _suggest_scope(self, errors: list[dict]) -> str | None:
        """Suggest which file to focus on."""
        if len(errors) == 0:
            return None

        # If all errors in same file, suggest that file
        files = set(e.get("file") for e in errors if e.get("file"))
        if len(files) == 1:
            return list(files)[0]

        # If multiple files, suggest the one with most errors
        if len(files) > 1:
            file_counts = {}
            for e in errors:
                file_path = e.get("file")
                if file_path:
                    file_counts[file_path] = file_counts.get(file_path, 0) + 1

            most_common = max(file_counts.items(), key=lambda x: x[1])
            return most_common[0]

        return None

    def _generate_summary(self, errors: list[dict]) -> str:
        """Generate summary for sprawling output."""
        if len(errors) == 0:
            return "No mypy errors detected"

        # Group by category
        categories = {}
        for e in errors:
            cat = e.get("category", "unknown")
            categories[cat] = categories.get(cat, 0) + 1

        # Create summary
        summary = f"{len(errors)} mypy error(s): "

        # List top 3 categories
        top_cats = sorted(categories.items(), key=lambda x: x[1], reverse=True)[:3]
        cat_summary = [f"{cat} ({count}x)" for cat, count in top_cats]
        summary += ", ".join(cat_summary)

        if len(categories) > 3:
            summary += f" and {len(categories) - 3} more types"

        return summary

    def _get_mypy_version(self, output: str) -> str | None:
        """Extract mypy version from output."""
        # Pattern: mypy 1.8.0
        match = re.search(r"mypy\s+(\d+\.\d+\.\d+)", output)
        return match.group(1) if match else None

    def _categorize_error(self, message: str) -> str:
        """Categorize error based on message content."""
        for pattern, category in self.ERROR_CATEGORIES.items():
            if re.search(pattern, message, re.IGNORECASE):
                return category
        return "unknown_type_error"
