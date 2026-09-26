"""
Normalized feedback schema for agentic loop validation.

Provides structured, quality-scored feedback from all validation tools.
"""

import time
from dataclasses import dataclass, field
from enum import Enum


class FeedbackCategory(Enum):
    """Standardized failure categories."""

    BUILD_ERROR = "build_error"
    TEST_FAILURE = "test_failure"
    LINT_WARNING = "lint_warning"
    TYPE_ERROR = "type_error"
    RUNTIME_ERROR = "runtime_error"
    TIMEOUT = "timeout"
    PERMISSION_DENIED = "permission_denied"
    MISSING_DEPENDENCY = "missing_dependency"
    NETWORK_ERROR = "network_error"
    CAPTCHA_FAILURE = "captcha_failure"
    VALIDATION_ERROR = "validation_error"
    UNKNOWN = "unknown"


class DeterministicBlocker(Enum):
    """Failures that require immediate escalation."""

    PERMISSION_DENIED = "permission_denied"
    MISSING_EXTERNAL_DEP = "missing_external_dependency"
    QUOTA_EXCEEDED = "quota_exceeded"
    SERVICE_DOWN = "service_down"
    SECURITY_VIOLATION = "security_violation"


@dataclass
class SalientFragment:
    """Key piece of error/warning information."""

    message: str
    severity: str  # error, warning, info
    line_number: int | None = None
    file_path: str | None = None
    context: str = ""  # Surrounding lines if relevant

    def __post_init__(self):
        """Validate severity values."""
        valid_severities = {"error", "warning", "info"}
        if self.severity not in valid_severities:
            raise ValueError(
                f"Invalid severity '{self.severity}'. Must be one of {valid_severities}"
            )


@dataclass
class NormalizedFeedback:
    """Structured feedback from validation tools."""

    # Core status
    success: bool
    exit_code: int

    # Categorization
    category: FeedbackCategory
    is_deterministic_blocker: bool
    blocker_type: DeterministicBlocker | None

    # Structured error info
    salient_fragments: list[SalientFragment]  # Only key errors, not full logs
    suggested_scope: str | None  # Which file/function to focus on

    # Quality metrics
    signal_quality_score: float  # 0.0-1.0, how actionable is this feedback
    feedback_source: str  # pytest, eslint, xcodebuild, etc.

    # Raw data (fallback)
    stdout: str
    stderr: str

    # Metadata
    timestamp: float = field(default_factory=time.time)
    tool_version: str | None = None

    # Summarization
    auto_summary: str = ""  # LLM-generated summary if logs are sprawling

    def __post_init__(self):
        """Validate quality score range."""
        if not 0.0 <= self.signal_quality_score <= 1.0:
            raise ValueError(
                f"signal_quality_score must be between 0.0 and 1.0, got {self.signal_quality_score}"
            )

    def is_actionable(self) -> bool:
        """Check if feedback is good enough to act on."""
        return self.signal_quality_score > 0.5

    def is_noisy(self) -> bool:
        """Check if feedback is too noisy to be useful."""
        return self.signal_quality_score < 0.3

    def get_primary_error(self) -> SalientFragment | None:
        """Get the most severe error fragment."""
        if not self.salient_fragments:
            return None

        # Prioritize errors over warnings
        errors = [f for f in self.salient_fragments if f.severity == "error"]
        if errors:
            return errors[0]

        # Fall back to first fragment
        return self.salient_fragments[0]

    def get_file_list(self) -> list[str]:
        """Get unique list of files mentioned in errors."""
        files = set()
        for fragment in self.salient_fragments:
            if fragment.file_path:
                files.add(fragment.file_path)
        return sorted(files)

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "success": self.success,
            "exit_code": self.exit_code,
            "category": self.category.value,
            "is_deterministic_blocker": self.is_deterministic_blocker,
            "blocker_type": self.blocker_type.value if self.blocker_type else None,
            "salient_fragments": [
                {
                    "message": f.message,
                    "severity": f.severity,
                    "line_number": f.line_number,
                    "file_path": f.file_path,
                    "context": f.context,
                }
                for f in self.salient_fragments
            ],
            "suggested_scope": self.suggested_scope,
            "signal_quality_score": self.signal_quality_score,
            "feedback_source": self.feedback_source,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "timestamp": self.timestamp,
            "tool_version": self.tool_version,
            "auto_summary": self.auto_summary,
        }
