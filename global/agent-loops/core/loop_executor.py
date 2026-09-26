"""
Foundation loop executor - complete Phase 0 integration.

Orchestrates all Phase 0 components into a working agentic loop.
"""

import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from core.escalation import EscalationDecider
from core.feedback_schema import NormalizedFeedback
from feedback.feedback_registry import FeedbackRegistry
from learning.trace_collector import TraceCollector
from learning.trace_schema import RemediationTrace
from remediation.skill_composer import SkillComposer
from remediation.skill_library import SkillLibrary
from safety.adaptive_limits import AdaptiveLimits
from safety.resource_guards import ResourceGuard, ResourceLimits
from safety.state_isolation import StateIsolation
from safety.stuck_detector import StuckDetector


@dataclass
class LoopResult:
    """Result of loop execution."""

    success: bool
    iterations: int
    final_feedback: NormalizedFeedback | None
    escalation_triggered: bool
    escalation_reason: str | None
    trace_id: str
    execution_time: float


class FoundationLoopExecutor:
    """
    Complete agentic loop executor integrating all Phase 0 components.

    Workflow:
    1. Execute task
    2. Validate with tools
    3. Normalize feedback
    4. Evaluate progress
    5. Decide next action (fix, escalate, or complete)
    6. Repeat until success or escalation
    """

    def __init__(
        self,
        agent_name: str,
        max_iterations: int = 5,
        resource_limits: ResourceLimits | None = None,
        use_state_isolation: bool = False,
    ):
        """
        Initialize loop executor.

        Args:
            agent_name: Name of agent running loop
            max_iterations: Maximum iterations before escalation
            resource_limits: Optional custom resource limits
            use_state_isolation: Whether to use isolated temp directories
        """
        self.agent_name = agent_name

        # Initialize all Phase 0 components
        self.feedback_registry = FeedbackRegistry()
        self.skill_library = SkillLibrary()
        self.skill_composer = SkillComposer()
        self.adaptive_limits = AdaptiveLimits(default_max_iterations=max_iterations)
        self.stuck_detector = StuckDetector()
        self.resource_guard = ResourceGuard(resource_limits)
        self.state_isolation = StateIsolation() if use_state_isolation else None
        self.trace_collector = TraceCollector()
        self.escalation_decider = EscalationDecider()

        # Current trace
        self.current_trace: RemediationTrace | None = None

    def execute_loop(
        self,
        task: dict[str, Any],
        execute_fn: Callable,
        validate_fn: Callable,
        criteria: dict[str, bool],
    ) -> LoopResult:
        """
        Execute complete agentic loop.

        Args:
            task: Task description and context
            execute_fn: Function that executes the task (returns success: bool)
            validate_fn: Function that validates result (returns tool_name, raw_output)
            criteria: Success criteria (dict of required validations)

        Returns:
            LoopResult with outcome
        """
        start_time = time.time()
        loop_id = str(uuid.uuid4())
        loop_succeeded = False

        # Initialize state isolation if enabled
        if self.state_isolation:
            self.state_isolation.initialize()

        try:
            # Main loop
            while self.adaptive_limits.should_continue():
                # Check resources before iteration
                within_limits, violation = self.resource_guard.check_resources()
                if not within_limits:
                    return self._escalate(
                        loop_id, f"Resource limit exceeded: {violation}", start_time
                    )

                # Execute task
                iteration_start = time.time()
                execution_success = execute_fn(task)

                # Validate result
                self.resource_guard.start_validation()
                tool_name, raw_output = validate_fn()
                self.resource_guard.end_validation()

                # Normalize feedback
                feedback = self.feedback_registry.normalize(tool_name, raw_output)

                # Record in stuck detector
                self.stuck_detector.record_error(
                    feedback.get_primary_error().message
                    if feedback.get_primary_error()
                    else "Unknown",
                    feedback.category.value,
                )
                self.stuck_detector.record_validation(criteria)

                # Check for immediate escalation (deterministic blockers)
                if feedback.is_deterministic_blocker:
                    return self._escalate(
                        loop_id,
                        f"Deterministic blocker: {feedback.blocker_type.value}",
                        start_time,
                        feedback,
                    )

                # Evaluate progress
                progress_made = self._evaluate_progress(feedback, criteria)

                # Record iteration
                self.adaptive_limits.record_iteration(
                    success=feedback.success,
                    progress_made=progress_made,
                    validation_results=criteria,
                    error_category=feedback.category.value,
                )

                # Check if complete
                if feedback.success and self._meets_criteria(criteria):
                    loop_succeeded = True
                    return self._complete_success(loop_id, feedback, start_time)

                # Check stuck detection
                if self.stuck_detector.check_stuck():
                    return self._escalate(
                        loop_id, "Stuck detected: No progress being made", start_time, feedback
                    )

                # Check escalation decision
                escalation = self.escalation_decider.should_escalate(
                    feedback,
                    self.stuck_detector.get_stuck_summary(),
                    self.resource_guard.get_resource_usage(),
                    self.adaptive_limits.get_progress_summary(),
                )

                if escalation.should_escalate:
                    return self._escalate(loop_id, escalation.reason, start_time, feedback)

                # Generate remediation
                remediation = self._generate_remediation(feedback)

                # Apply remediation (would call agent's fix function)
                # For Phase 0, we just record what would be done
                if self.current_trace:
                    self.current_trace.iterations_count += 1

                # Record iteration time
                iteration_time = time.time() - iteration_start

            # Max iterations reached
            return self._escalate(loop_id, "Maximum iterations reached without success", start_time)

        finally:
            # Cleanup state isolation
            if self.state_isolation:
                self.state_isolation.cleanup(success=loop_succeeded)

    def _evaluate_progress(self, feedback: NormalizedFeedback, criteria: dict[str, bool]) -> bool:
        """
        Evaluate if progress was made in this iteration.

        Args:
            feedback: Current feedback
            criteria: Current criteria state

        Returns:
            True if progress detected
        """
        # Progress indicators:
        # 1. Fewer errors than before
        # 2. Better signal quality
        # 3. More criteria passing

        # For Phase 0, simple check: did anything improve?
        passing_count = sum(1 for passed in criteria.values() if passed)

        # Compare with previous iteration if available
        if len(self.adaptive_limits.history) > 0:
            prev_record = self.adaptive_limits.history[-1]
            prev_passing = sum(1 for passed in prev_record.validation_results.values() if passed)
            return passing_count > prev_passing

        # First iteration - progress if any criteria pass
        return passing_count > 0

    def _meets_criteria(self, criteria: dict[str, bool]) -> bool:
        """Check if all required criteria are met."""
        return all(criteria.values())

    def _generate_remediation(self, feedback: NormalizedFeedback) -> str | None:
        """
        Generate remediation using skills or LLM reasoning.

        Args:
            feedback: Current feedback

        Returns:
            Remediation instructions or None
        """
        primary_error = feedback.get_primary_error()
        if not primary_error:
            return None

        # Search for applicable skills
        candidate_skills = self.skill_library.search_by_error(
            primary_error.message, feedback.category.value, top_k=5
        )

        if candidate_skills:
            # Use skill composer to select best skill
            best_skill = self.skill_composer.select_best_skill(
                candidate_skills,
                {"error": primary_error.message, "category": feedback.category.value},
                feedback,
            )

            if best_skill:
                # Generate fix instructions
                return self.skill_composer.generate_fix_with_context(
                    best_skill, {"error": primary_error.message}, feedback
                )

        # Fallback to pure LLM reasoning
        return self.skill_composer.fallback_to_reasoning(
            {"error": primary_error.message, "category": feedback.category.value}, feedback
        )

    def _complete_success(
        self, loop_id: str, feedback: NormalizedFeedback, start_time: float
    ) -> LoopResult:
        """Handle successful completion."""
        execution_time = time.time() - start_time

        # Finalize trace
        if self.current_trace:
            self.current_trace.finalize(success=True, validation_results={})
            self.trace_collector.store_trace(self.current_trace)

        return LoopResult(
            success=True,
            iterations=self.adaptive_limits.iterations_completed,
            final_feedback=feedback,
            escalation_triggered=False,
            escalation_reason=None,
            trace_id=loop_id,
            execution_time=execution_time,
        )

    def _escalate(
        self,
        loop_id: str,
        reason: str,
        start_time: float,
        feedback: NormalizedFeedback | None = None,
    ) -> LoopResult:
        """Handle escalation."""
        execution_time = time.time() - start_time

        # Finalize trace
        if self.current_trace:
            self.current_trace.record_escalation(reason)
            self.current_trace.finalize(success=False, validation_results={})
            self.trace_collector.store_trace(self.current_trace)

        return LoopResult(
            success=False,
            iterations=self.adaptive_limits.iterations_completed,
            final_feedback=feedback,
            escalation_triggered=True,
            escalation_reason=reason,
            trace_id=loop_id,
            execution_time=execution_time,
        )

    def create_trace(self, task_description: str, initial_error: str, error_category: str) -> None:
        """Create trace for current loop execution."""
        self.current_trace = self.trace_collector.create_trace(
            agent_name=self.agent_name,
            task_description=task_description,
            initial_error=initial_error,
            error_category=error_category,
        )
