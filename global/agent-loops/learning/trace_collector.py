"""
Trace collector for capturing remediation patterns.

Stores success/failure traces and extracts learning patterns.
"""

import json
import uuid
from collections import Counter
from pathlib import Path
from typing import Any

from .trace_schema import RemediationTrace, TraceType


class TraceCollector:
    """
    Collects and stores remediation traces for learning.

    Maintains separate files for success and failure traces.
    """

    def __init__(self, storage_dir: Path | None = None):
        """
        Initialize trace collector.

        Args:
            storage_dir: Directory for trace storage (default: registry/traces/)
        """
        if storage_dir is None:
            base_dir = Path(__file__).parent.parent.parent.parent  # Huxley root
            storage_dir = base_dir / "registry" / "traces"

        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)

        self.success_file = self.storage_dir / "success_traces.jsonl"
        self.failure_file = self.storage_dir / "failure_traces.jsonl"

        # Create files if they don't exist
        self.success_file.touch(exist_ok=True)
        self.failure_file.touch(exist_ok=True)

    def create_trace(
        self, agent_name: str, task_description: str, initial_error: str, error_category: str
    ) -> RemediationTrace:
        """
        Create new remediation trace.

        Args:
            agent_name: Name of agent
            task_description: Task being attempted
            initial_error: Initial error message
            error_category: Error category

        Returns:
            New RemediationTrace
        """
        trace_id = str(uuid.uuid4())

        return RemediationTrace(
            trace_id=trace_id,
            trace_type=TraceType.FAILURE,  # Will be updated on finalize
            agent_name=agent_name,
            task_description=task_description,
            initial_error=initial_error,
            error_category=error_category,
        )

    def store_trace(self, trace: RemediationTrace) -> None:
        """
        Store trace to appropriate file.

        Args:
            trace: Trace to store
        """
        # Choose file based on success/failure
        if trace.trace_type == TraceType.SUCCESS:
            target_file = self.success_file
        else:
            target_file = self.failure_file

        # Append as JSONL
        with open(target_file, "a") as f:
            f.write(json.dumps(trace.to_dict()) + "\n")

    def load_recent_traces(
        self, trace_type: TraceType | None = None, limit: int = 100
    ) -> list[RemediationTrace]:
        """
        Load recent traces.

        Args:
            trace_type: Filter by trace type (None = all)
            limit: Maximum traces to load

        Returns:
            List of traces
        """
        traces = []

        # Determine which files to read
        files_to_read = []
        if trace_type is None or trace_type == TraceType.SUCCESS:
            files_to_read.append(self.success_file)
        if trace_type is None or trace_type != TraceType.SUCCESS:
            files_to_read.append(self.failure_file)

        # Read traces
        for file_path in files_to_read:
            if not file_path.exists():
                continue

            with open(file_path) as f:
                lines = f.readlines()

            # Get most recent lines
            recent_lines = lines[-limit:]

            for line in recent_lines:
                try:
                    data = json.loads(line)
                    trace = RemediationTrace.from_dict(data)
                    traces.append(trace)
                except json.JSONDecodeError:
                    continue

        return traces[-limit:]

    def extract_successful_patterns(self) -> dict[str, Any]:
        """
        Extract patterns from successful remediations.

        Returns:
            Dictionary of success patterns
        """
        success_traces = self.load_recent_traces(trace_type=TraceType.SUCCESS, limit=200)

        if not success_traces:
            return {
                "total_successes": 0,
                "common_skills": [],
                "avg_iterations": 0,
                "avg_time_seconds": 0,
            }

        # Extract common skills
        all_skills = []
        for trace in success_traces:
            all_skills.extend(trace.skill_ids_applied)

        skill_counts = Counter(all_skills)
        common_skills = skill_counts.most_common(10)

        # Calculate averages
        total_iterations = sum(t.iterations_count for t in success_traces)
        avg_iterations = total_iterations / len(success_traces)

        times = [
            t.time_to_resolution_seconds for t in success_traces if t.time_to_resolution_seconds
        ]
        avg_time = sum(times) / len(times) if times else 0

        return {
            "total_successes": len(success_traces),
            "common_skills": [
                {"skill_id": skill, "count": count} for skill, count in common_skills
            ],
            "avg_iterations": avg_iterations,
            "avg_time_seconds": avg_time,
            "success_by_category": self._group_by_category(success_traces),
        }

    def extract_failure_patterns(self) -> dict[str, Any]:
        """
        Extract patterns from failed remediations.

        Returns:
            Dictionary of failure patterns
        """
        failure_traces = self.load_recent_traces(trace_type=TraceType.FAILURE, limit=200)

        if not failure_traces:
            return {"total_failures": 0, "common_errors": [], "escalation_reasons": []}

        # Extract common errors
        error_counts = Counter(t.error_category for t in failure_traces)
        common_errors = error_counts.most_common(10)

        # Extract escalation reasons
        escalation_reasons = [
            t.escalation_reason
            for t in failure_traces
            if t.escalation_triggered and t.escalation_reason
        ]
        escalation_counts = Counter(escalation_reasons)

        # Extract stuck signals
        stuck_signal_types = []
        for trace in failure_traces:
            for signal in trace.stuck_signals:
                stuck_signal_types.append(signal["type"])

        stuck_counts = Counter(stuck_signal_types)

        return {
            "total_failures": len(failure_traces),
            "common_errors": [{"category": cat, "count": count} for cat, count in common_errors],
            "escalation_reasons": [
                {"reason": reason, "count": count}
                for reason, count in escalation_counts.most_common(10)
            ],
            "stuck_signals": [
                {"type": sig_type, "count": count}
                for sig_type, count in stuck_counts.most_common(10)
            ],
        }

    def check_avoidance_patterns(self, error_category: str) -> list[str]:
        """
        Check for patterns to avoid based on past failures.

        Args:
            error_category: Error category to check

        Returns:
            List of avoidance recommendations
        """
        failure_traces = self.load_recent_traces(trace_type=TraceType.FAILURE, limit=100)

        # Filter by category
        relevant_failures = [t for t in failure_traces if t.error_category == error_category]

        if not relevant_failures:
            return []

        avoidance_recommendations = []

        # Find commonly failing skills for this category
        failed_skills = []
        for trace in relevant_failures:
            failed_skills.extend(trace.what_failed)

        skill_failure_counts = Counter(failed_skills)

        for skill, count in skill_failure_counts.most_common(5):
            if count >= 3:  # Failed at least 3 times
                avoidance_recommendations.append(
                    f"Avoid {skill} for {error_category} (failed {count} times)"
                )

        return avoidance_recommendations

    def _group_by_category(self, traces: list[RemediationTrace]) -> dict[str, int]:
        """Group traces by error category."""
        category_counts = Counter(t.error_category for t in traces)
        return dict(category_counts)

    def get_statistics(self) -> dict[str, Any]:
        """
        Get overall statistics.

        Returns:
            Dictionary of stats
        """
        all_traces = self.load_recent_traces(limit=1000)

        if not all_traces:
            return {"total_traces": 0, "success_rate": 0.0}

        successes = len([t for t in all_traces if t.trace_type == TraceType.SUCCESS])
        success_rate = successes / len(all_traces)

        return {
            "total_traces": len(all_traces),
            "successes": successes,
            "failures": len(all_traces) - successes,
            "success_rate": success_rate,
            "success_patterns": self.extract_successful_patterns(),
            "failure_patterns": self.extract_failure_patterns(),
        }
