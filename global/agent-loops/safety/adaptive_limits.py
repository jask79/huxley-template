"""
Adaptive iteration limits based on progress tracking.

Dynamically adjusts iteration caps based on history and progress.
"""

import time
from dataclasses import dataclass, field


@dataclass
class IterationRecord:
    """Record of a single iteration."""

    iteration_num: int
    timestamp: float
    success: bool
    progress_made: bool
    validation_results: dict[str, bool]
    error_category: str | None = None


@dataclass
class AdaptiveLimits:
    """
    Dynamically adjusts iteration limits based on progress.

    Increases limits when progress is steady, decreases when stuck.
    """

    # Base configuration
    default_max_iterations: int = 5
    min_iterations: int = 2
    absolute_max_iterations: int = 15

    # Progress tracking
    iterations_completed: int = 0
    history: list[IterationRecord] = field(default_factory=list)

    # Adaptive state
    current_max_iterations: int = field(init=False)

    def __post_init__(self):
        """Initialize current limit to default."""
        self.current_max_iterations = self.default_max_iterations

    def record_iteration(
        self,
        success: bool,
        progress_made: bool,
        validation_results: dict[str, bool],
        error_category: str | None = None,
    ) -> None:
        """
        Record iteration result and update limits.

        Args:
            success: Whether iteration succeeded
            progress_made: Whether any progress was made
            validation_results: Dict of validation outcomes
            error_category: Error category if failed
        """
        self.iterations_completed += 1

        record = IterationRecord(
            iteration_num=self.iterations_completed,
            timestamp=time.time(),
            success=success,
            progress_made=progress_made,
            validation_results=validation_results,
            error_category=error_category,
        )

        self.history.append(record)

        # Update adaptive limits based on history
        self._adjust_limits()

    def should_continue(self) -> bool:
        """
        Check if loop should continue based on limits.

        Returns:
            True if should continue iterating
        """
        # Always allow minimum iterations
        if self.iterations_completed < self.min_iterations:
            return True

        # Check against current adaptive limit
        if self.iterations_completed >= self.current_max_iterations:
            return False

        # Check against absolute maximum
        if self.iterations_completed >= self.absolute_max_iterations:
            return False

        return True

    def get_remaining_iterations(self) -> int:
        """
        Get number of iterations remaining.

        Returns:
            Number of iterations left
        """
        return max(0, self.current_max_iterations - self.iterations_completed)

    def _adjust_limits(self) -> None:
        """Adjust limits based on recent history."""
        if len(self.history) < 2:
            return

        # Look at last 3 iterations
        recent_window = self.history[-3:]

        # Calculate progress rate
        progress_count = sum(1 for r in recent_window if r.progress_made)
        progress_rate = progress_count / len(recent_window)

        # Adjust limits based on progress
        if progress_rate >= 0.67:
            # Good progress - allow more iterations
            self.current_max_iterations = min(
                self.current_max_iterations + 2, self.absolute_max_iterations
            )
        elif progress_rate <= 0.33:
            # Poor progress - reduce iterations
            self.current_max_iterations = max(self.current_max_iterations - 1, self.min_iterations)

    def get_progress_summary(self) -> dict[str, any]:
        """
        Get summary of progress so far.

        Returns:
            Dictionary with progress metrics
        """
        if not self.history:
            return {
                "iterations": 0,
                "success_rate": 0.0,
                "progress_rate": 0.0,
                "current_limit": self.current_max_iterations,
            }

        successes = sum(1 for r in self.history if r.success)
        progress = sum(1 for r in self.history if r.progress_made)

        return {
            "iterations": self.iterations_completed,
            "success_rate": successes / len(self.history),
            "progress_rate": progress / len(self.history),
            "current_limit": self.current_max_iterations,
            "remaining": self.get_remaining_iterations(),
        }

    def get_iteration_times(self) -> list[float]:
        """
        Calculate time between iterations.

        Returns:
            List of iteration durations in seconds
        """
        if len(self.history) < 2:
            return []

        times = []
        for i in range(1, len(self.history)):
            duration = self.history[i].timestamp - self.history[i - 1].timestamp
            times.append(duration)

        return times

    def is_making_steady_progress(self) -> bool:
        """
        Check if progress is steady and consistent.

        Returns:
            True if making steady progress
        """
        if len(self.history) < 3:
            return False

        recent = self.history[-3:]
        progress_count = sum(1 for r in recent if r.progress_made)

        return progress_count >= 2

    def reset(self) -> None:
        """Reset limits and history."""
        self.iterations_completed = 0
        self.history.clear()
        self.current_max_iterations = self.default_max_iterations
