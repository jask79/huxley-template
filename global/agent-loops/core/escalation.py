"""
Escalation decision logic for agentic loops.

Determines when to escalate to human or higher authority.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Any


class EscalationPriority(Enum):
    """Priority level for escalation."""

    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4

    def __lt__(self, other):
        """Allow priority comparison."""
        if self.__class__ is other.__class__:
            return self.value < other.value
        return NotImplemented

    def __le__(self, other):
        """Allow priority comparison."""
        if self.__class__ is other.__class__:
            return self.value <= other.value
        return NotImplemented

    def __gt__(self, other):
        """Allow priority comparison."""
        if self.__class__ is other.__class__:
            return self.value > other.value
        return NotImplemented

    def __ge__(self, other):
        """Allow priority comparison."""
        if self.__class__ is other.__class__:
            return self.value >= other.value
        return NotImplemented


@dataclass
class EscalationDecision:
    """Escalation decision with reasoning."""

    should_escalate: bool
    priority: EscalationPriority
    reason: str
    contributing_factors: list[str]
    recommended_action: str


class EscalationDecider:
    """
    Decides when to escalate based on multiple signals.

    Considers:
    - Deterministic blockers
    - Stuck detection
    - Resource exhaustion
    - Iteration limits
    - Safety concerns
    """

    def __init__(self):
        """Initialize escalation decider."""
        self.escalation_thresholds = {
            "stuck_severity": 0.7,
            "resource_critical": 0.9,
            "max_iterations_factor": 0.9,  # 90% of max
        }

    def should_escalate(
        self,
        feedback: Any,  # NormalizedFeedback
        stuck_summary: dict[str, Any],
        resource_usage: dict[str, Any],
        iteration_progress: dict[str, Any],
    ) -> EscalationDecision:
        """
        Determine if escalation is needed.

        Args:
            feedback: Current feedback from validation
            stuck_summary: Stuck detector summary
            resource_usage: Resource usage metrics
            iteration_progress: Progress tracking info

        Returns:
            EscalationDecision
        """
        factors = []
        priority = EscalationPriority.LOW

        # Check for deterministic blockers (immediate escalation)
        if feedback.is_deterministic_blocker:
            return EscalationDecision(
                should_escalate=True,
                priority=EscalationPriority.CRITICAL,
                reason=f"Deterministic blocker: {feedback.blocker_type.value}",
                contributing_factors=["deterministic_blocker"],
                recommended_action="Human intervention required - unrecoverable error",
            )

        # Check stuck detection
        if stuck_summary.get("is_stuck"):
            factors.append("stuck_detected")
            priority = max(priority, EscalationPriority.HIGH)

        # Check resource exhaustion
        resource_health = (
            resource_usage.get("memory_percent", 0) < 90
            and resource_usage.get("elapsed_percent", 0) < 90
        )

        if not resource_health:
            factors.append("resource_exhaustion")
            priority = max(priority, EscalationPriority.HIGH)

        # Check iteration limits
        progress = iteration_progress.get("progress_rate", 0)
        remaining_pct = iteration_progress.get("remaining", 1) / max(
            iteration_progress.get("current_limit", 1), 1
        )

        if remaining_pct < 0.2 and progress < 0.3:  # <20% iterations left, <30% progress
            factors.append("iteration_limit_approaching")
            priority = max(priority, EscalationPriority.MEDIUM)

        # Check error quality
        if hasattr(feedback, "signal_quality_score"):
            if feedback.signal_quality_score < 0.3:  # Very noisy feedback
                factors.append("low_signal_quality")
                priority = max(priority, EscalationPriority.MEDIUM)

        # Make decision
        should_escalate = len(factors) >= 2 or priority == EscalationPriority.CRITICAL

        if not should_escalate:
            return EscalationDecision(
                should_escalate=False,
                priority=EscalationPriority.LOW,
                reason="No escalation needed - continuing loop",
                contributing_factors=factors,
                recommended_action="Continue remediation attempts",
            )

        # Build escalation reason
        reason_parts = []
        if "stuck_detected" in factors:
            reason_parts.append("Loop appears stuck with no progress")
        if "resource_exhaustion" in factors:
            reason_parts.append("Resources critically low")
        if "iteration_limit_approaching" in factors:
            reason_parts.append("Approaching iteration limit with poor progress")
        if "low_signal_quality" in factors:
            reason_parts.append("Feedback quality too low to act on")

        reason = "; ".join(reason_parts)

        # Recommend action based on factors
        if "stuck_detected" in factors:
            action = "Review remediation approach - may need different strategy"
        elif "resource_exhaustion" in factors:
            action = "Allocate more resources or simplify task scope"
        else:
            action = "Human review needed to unblock progress"

        return EscalationDecision(
            should_escalate=True,
            priority=priority,
            reason=reason,
            contributing_factors=factors,
            recommended_action=action,
        )

    def check_safety_escalation(
        self, feedback: Any, task_context: dict[str, Any]
    ) -> EscalationDecision | None:
        """
        Check for safety-related escalation needs.

        Args:
            feedback: Current feedback
            task_context: Task context

        Returns:
            EscalationDecision if safety concern, None otherwise
        """
        safety_keywords = [
            "permission denied",
            "access denied",
            "security",
            "authentication",
            "credentials",
            "private key",
            "password",
        ]

        # Check if error involves safety concerns
        primary_error = (
            feedback.get_primary_error() if hasattr(feedback, "get_primary_error") else None
        )

        if primary_error:
            error_lower = primary_error.message.lower()

            for keyword in safety_keywords:
                if keyword in error_lower:
                    return EscalationDecision(
                        should_escalate=True,
                        priority=EscalationPriority.CRITICAL,
                        reason=f"Safety concern detected: {keyword}",
                        contributing_factors=["safety_violation"],
                        recommended_action="Human review required for security/permissions",
                    )

        return None
