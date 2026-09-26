"""
TypeScript compiler (tsc) output normalizer.

Converts TypeScript compiler error output into structured NormalizedFeedback.
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


class TscNormalizer(FeedbackNormalizer):
    """Normalize TypeScript compiler output to structured feedback."""

    def normalize(self, raw_output: dict[str, Any]) -> NormalizedFeedback:
        """
        Parse tsc output.

        Expected raw_output format:
        {
            'exit_code': int,
            'stdout': str,
            'stderr': str,
            'tool': 'tsc' (optional)
        }
        """
        exit_code = raw_output["exit_code"]
        stdout = raw_output.get("stdout", "")
        stderr = raw_output.get("stderr", "")

        # TypeScript errors typically go to stdout
        combined_output = stdout + "\n" + stderr

        # Parse errors
        errors = self._parse_errors(combined_output)
        salient_fragments = self._extract_salient_fragments(errors)

        # Determine category
        category = self._determine_category(errors, combined_output, exit_code)

        # Check for deterministic blockers
        is_blocker, blocker_type = self._check_deterministic_blockers(combined_output)

        # Compute quality score
        has_file_info = any(f.file_path is not None for f in salient_fragments)
        signal_quality = self._compute_base_quality(
            salient_fragments, combined_output, has_file_info
        )

        # Generate summary if needed
        auto_summary = self._generate_summary(errors) if len(combined_output) > 2000 else ""

        return NormalizedFeedback(
            success=exit_code == 0,
            exit_code=exit_code,
            category=category,
            is_deterministic_blocker=is_blocker,
            blocker_type=blocker_type,
            salient_fragments=salient_fragments,
            suggested_scope=self._suggest_scope(errors),
            signal_quality_score=signal_quality,
            feedback_source="tsc",
            stdout=stdout,
            stderr=stderr,
            timestamp=time.time(),
            tool_version=self._get_tsc_version(combined_output),
            auto_summary=auto_summary,
        )

    def compute_signal_quality(self, feedback: NormalizedFeedback) -> float:
        """Compute quality score for TypeScript compiler feedback."""
        has_file_info = any(f.file_path is not None for f in feedback.salient_fragments)
        return self._compute_base_quality(
            feedback.salient_fragments, feedback.stdout + feedback.stderr, has_file_info
        )

    def _parse_errors(self, output: str) -> list[dict[str, Any]]:
        """
        Extract error information from tsc output.

        Returns list of dicts with keys: file, line, col, code, message
        """
        errors = []

        # Pattern 1: src/Button.tsx(45,10): error TS2322: Type 'string' is not assignable to type 'number'.
        error_pattern = r"([^\s(]+)\((\d+),(\d+)\):\s+error\s+(TS\d+):\s+(.+?)(?=\n|$)"

        for match in re.finditer(error_pattern, output, re.MULTILINE):
            file_path = match.group(1).strip()
            line_num = int(match.group(2))
            col_num = int(match.group(3))
            error_code = match.group(4).strip()
            message = match.group(5).strip()

            errors.append(
                {
                    "file": file_path,
                    "line": line_num,
                    "col": col_num,
                    "code": error_code,
                    "message": message,
                    "severity": "error",
                }
            )

        # Pattern 2: Generic format without parentheses
        # src/Button.tsx:45:10 - error TS2322: Type 'string' is not assignable to type 'number'.
        alt_pattern = r"([^\s:]+):(\d+):(\d+)\s+-\s+error\s+(TS\d+):\s+(.+?)(?=\n|$)"

        for match in re.finditer(alt_pattern, output, re.MULTILINE):
            file_path = match.group(1).strip()
            line_num = int(match.group(2))
            col_num = int(match.group(3))
            error_code = match.group(4).strip()
            message = match.group(5).strip()

            errors.append(
                {
                    "file": file_path,
                    "line": line_num,
                    "col": col_num,
                    "code": error_code,
                    "message": message,
                    "severity": "error",
                }
            )

        # Pattern 3: Configuration errors (no file/line)
        # error TS5023: Unknown compiler option 'target'.
        config_error_pattern = r"error\s+(TS\d+):\s+(.+?)(?=\n|$)"

        for match in re.finditer(config_error_pattern, output, re.MULTILINE):
            error_code = match.group(1).strip()
            message = match.group(2).strip()

            # Skip if already captured in other patterns
            if any(e["code"] == error_code for e in errors):
                continue

            errors.append(
                {
                    "file": None,
                    "line": None,
                    "col": None,
                    "code": error_code,
                    "message": message,
                    "severity": "error",
                }
            )

        return errors

    def _extract_salient_fragments(self, errors: list[dict]) -> list[SalientFragment]:
        """Convert errors to salient fragments."""
        fragments = []

        for error in errors:
            # Create detailed message with error code
            full_message = f"{error['code']}: {error['message']}"

            fragments.append(
                SalientFragment(
                    message=full_message,
                    severity=error.get("severity", "error"),
                    line_number=error.get("line"),
                    file_path=error.get("file"),
                    context=error.get("code", ""),
                )
            )

        return fragments

    def _check_deterministic_blockers(
        self, output: str
    ) -> tuple[bool, DeterministicBlocker | None]:
        """Check for blockers that require immediate escalation."""

        # Configuration errors that can't be auto-fixed
        config_errors = [
            "TS5023",  # Unknown compiler option
            "TS5024",  # Compiler option requires a value
            "TS5025",  # Unknown command line option
            "TS18003",  # No inputs were found
        ]

        for error_code in config_errors:
            if error_code in output:
                # These are configuration issues, not code issues
                return True, DeterministicBlocker.MISSING_EXTERNAL_DEP

        # Module resolution errors (missing @types packages)
        if "Cannot find module" in output and "@types/" in output:
            return True, DeterministicBlocker.MISSING_EXTERNAL_DEP

        # File system errors
        if "EACCES" in output or "Permission denied" in output:
            return True, DeterministicBlocker.PERMISSION_DENIED

        return False, None

    def _determine_category(
        self, errors: list[dict], output: str, exit_code: int
    ) -> FeedbackCategory:
        """Determine failure category from errors."""

        if exit_code == 0:
            return FeedbackCategory.UNKNOWN

        # Check for module/import errors
        if any("Cannot find module" in e.get("message", "") for e in errors):
            return FeedbackCategory.MISSING_DEPENDENCY

        # Check for permission errors
        if "Permission denied" in output:
            return FeedbackCategory.PERMISSION_DENIED

        # All other TypeScript errors are type errors
        if len(errors) > 0:
            return FeedbackCategory.TYPE_ERROR

        return FeedbackCategory.UNKNOWN

    def _suggest_scope(self, errors: list[dict]) -> str | None:
        """Suggest which file/function to focus on."""
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
            return "No TypeScript errors detected"

        # Group by error code
        error_codes = {}
        for e in errors:
            code = e.get("code", "Unknown")
            error_codes[code] = error_codes.get(code, 0) + 1

        # Create summary
        summary = f"{len(errors)} TypeScript error(s): "

        # List top 3 error codes
        top_codes = sorted(error_codes.items(), key=lambda x: x[1], reverse=True)[:3]
        code_summary = [f"{code} ({count}x)" for code, count in top_codes]
        summary += ", ".join(code_summary)

        if len(error_codes) > 3:
            summary += f" and {len(error_codes) - 3} more types"

        return summary

    def _get_tsc_version(self, output: str) -> str | None:
        """Extract TypeScript version from output."""
        # Pattern: Version 5.3.3
        match = re.search(r"[Vv]ersion\s+(\d+\.\d+\.\d+)", output)
        return match.group(1) if match else None

    def _categorize_error_code(self, code: str) -> str:
        """
        Categorize error code into high-level groups.

        Useful for skill matching and remediation.
        """
        # Type mismatch errors
        if code in ["TS2322", "TS2345", "TS2416"]:
            return "type_mismatch"

        # Property errors
        if code in ["TS2339", "TS2551", "TS2564"]:
            return "property_error"

        # Import/module errors
        if code in ["TS2307", "TS2305", "TS2792"]:
            return "module_error"

        # Generic errors
        if code in ["TS2304", "TS2693"]:
            return "undefined_error"

        # Declaration errors
        if code in ["TS2451", "TS2300", "TS2374"]:
            return "declaration_error"

        # Function/method errors
        if code in ["TS2554", "TS2555", "TS2556"]:
            return "function_error"

        return "unknown"
