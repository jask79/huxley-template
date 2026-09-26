"""
Failure taxonomy with severity classification.

Maps failure categories to severity levels and escalation rules.
"""

from enum import Enum

from core.feedback_schema import FeedbackCategory


class FailureSeverity(Enum):
    """Severity classification for failures."""

    LOW = "low"  # Minor issues, easily fixable
    MEDIUM = "medium"  # Moderate issues, may need iteration
    HIGH = "high"  # Significant issues, likely need escalation
    CRITICAL = "critical"  # Immediate escalation needed


class FailureTaxonomy:
    """
    Maps error categories to severity levels.

    Provides classification and escalation guidance.
    """

    # Category -> Severity mapping
    SEVERITY_MAP: dict[FeedbackCategory, FailureSeverity] = {
        # Low severity - easily addressable
        FeedbackCategory.LINT_WARNING: FailureSeverity.LOW,
        # Medium severity - require iteration
        FeedbackCategory.TEST_FAILURE: FailureSeverity.MEDIUM,
        FeedbackCategory.TYPE_ERROR: FailureSeverity.MEDIUM,
        FeedbackCategory.BUILD_ERROR: FailureSeverity.MEDIUM,
        FeedbackCategory.VALIDATION_ERROR: FailureSeverity.MEDIUM,
        # High severity - likely need escalation
        FeedbackCategory.RUNTIME_ERROR: FailureSeverity.HIGH,
        FeedbackCategory.MISSING_DEPENDENCY: FailureSeverity.HIGH,
        FeedbackCategory.TIMEOUT: FailureSeverity.HIGH,
        # Critical severity - immediate escalation
        FeedbackCategory.PERMISSION_DENIED: FailureSeverity.CRITICAL,
        FeedbackCategory.NETWORK_ERROR: FailureSeverity.CRITICAL,
        FeedbackCategory.CAPTCHA_FAILURE: FailureSeverity.CRITICAL,
        # Unknown - treat as medium initially
        FeedbackCategory.UNKNOWN: FailureSeverity.MEDIUM,
    }

    @classmethod
    def get_severity(cls, category: FeedbackCategory) -> FailureSeverity:
        """
        Get severity for a feedback category.

        Args:
            category: FeedbackCategory value

        Returns:
            FailureSeverity level
        """
        return cls.SEVERITY_MAP.get(category, FailureSeverity.MEDIUM)

    @classmethod
    def should_auto_escalate(cls, category: FeedbackCategory) -> bool:
        """
        Check if category should trigger immediate escalation.

        Args:
            category: FeedbackCategory value

        Returns:
            True if should escalate immediately
        """
        severity = cls.get_severity(category)
        return severity == FailureSeverity.CRITICAL

    @classmethod
    def get_max_iterations(cls, category: FeedbackCategory) -> int:
        """
        Get recommended max iterations for category.

        Args:
            category: FeedbackCategory value

        Returns:
            Recommended max iterations
        """
        severity = cls.get_severity(category)

        if severity == FailureSeverity.LOW:
            return 2  # Low severity should resolve quickly
        elif severity == FailureSeverity.MEDIUM:
            return 5  # Standard iteration limit
        elif severity == FailureSeverity.HIGH:
            return 3  # High severity - escalate if not resolved quickly
        else:  # CRITICAL
            return 1  # Escalate immediately

    @classmethod
    def get_description(cls, category: FeedbackCategory) -> str:
        """
        Get human-readable description of category.

        Args:
            category: FeedbackCategory value

        Returns:
            Description string
        """
        descriptions = {
            FeedbackCategory.BUILD_ERROR: "Code fails to compile or build",
            FeedbackCategory.TEST_FAILURE: "Unit or integration tests failing",
            FeedbackCategory.LINT_WARNING: "Code style or linting violations",
            FeedbackCategory.TYPE_ERROR: "Type checking or annotation errors",
            FeedbackCategory.RUNTIME_ERROR: "Errors occurring during execution",
            FeedbackCategory.TIMEOUT: "Operation exceeded time limit",
            FeedbackCategory.PERMISSION_DENIED: "Insufficient permissions to complete action",
            FeedbackCategory.MISSING_DEPENDENCY: "Required package or module not found",
            FeedbackCategory.NETWORK_ERROR: "Network connectivity or API issues",
            FeedbackCategory.CAPTCHA_FAILURE: "CAPTCHA challenge could not be solved",
            FeedbackCategory.VALIDATION_ERROR: "Validation checks failed",
            FeedbackCategory.UNKNOWN: "Unclassified error",
        }

        return descriptions.get(category, "Unknown error category")

    @classmethod
    def get_suggested_actions(cls, category: FeedbackCategory) -> list:
        """
        Get suggested remediation actions for category.

        Args:
            category: FeedbackCategory value

        Returns:
            List of suggested actions
        """
        actions = {
            FeedbackCategory.BUILD_ERROR: [
                "Check syntax errors",
                "Verify imports are correct",
                "Review compilation errors",
            ],
            FeedbackCategory.TEST_FAILURE: [
                "Review test assertions",
                "Check test data and fixtures",
                "Verify implementation matches test expectations",
            ],
            FeedbackCategory.LINT_WARNING: [
                "Fix code style issues",
                "Remove unused imports/variables",
                "Adjust line length and formatting",
            ],
            FeedbackCategory.TYPE_ERROR: [
                "Add or correct type annotations",
                "Fix type mismatches",
                "Add type conversions where needed",
            ],
            FeedbackCategory.RUNTIME_ERROR: [
                "Add error handling",
                "Check for null/undefined values",
                "Verify runtime conditions",
            ],
            FeedbackCategory.MISSING_DEPENDENCY: [
                "Install missing package",
                "Add to requirements/package.json",
                "Check package name and version",
            ],
            FeedbackCategory.PERMISSION_DENIED: [
                "ESCALATE: Check file permissions",
                "ESCALATE: Verify access rights",
                "ESCALATE: Review security settings",
            ],
        }

        return actions.get(category, ["Review error details", "Search for similar errors"])
