"""
Trace schema for capturing remediation attempts.

Records success and failure patterns for learning.
"""

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class TraceType(Enum):
    """Type of remediation trace."""

    SUCCESS = "success"
    FAILURE = "failure"
    PARTIAL = "partial"  # Some progress but didn't complete


@dataclass
class RemediationTrace:
    """
    Record of a remediation attempt for learning.

    Captures context, actions taken, and outcome.
    """

    # Identification (required fields first)
    trace_id: str
    trace_type: TraceType
    agent_name: str
    task_description: str
    initial_error: str
    error_category: str

    # Optional fields with defaults
    timestamp: float = field(default_factory=time.time)

    # Actions taken
    skill_ids_applied: list[str] = field(default_factory=list)
    files_modified: list[str] = field(default_factory=list)
    iterations_count: int = 0

    # Outcome
    final_success: bool = False
    validation_results: dict[str, bool] = field(default_factory=dict)
    time_to_resolution_seconds: float | None = None

    # Learning signals
    what_worked: list[str] = field(default_factory=list)
    what_failed: list[str] = field(default_factory=list)
    stuck_signals: list[dict[str, Any]] = field(default_factory=list)

    # Metadata
    resource_usage: dict[str, float] = field(default_factory=dict)
    escalation_triggered: bool = False
    escalation_reason: str | None = None

    def add_skill_applied(self, skill_id: str, success: bool) -> None:
        """
        Record skill application.

        Args:
            skill_id: ID of skill applied
            success: Whether it helped
        """
        self.skill_ids_applied.append(skill_id)

        if success:
            self.what_worked.append(f"skill:{skill_id}")
        else:
            self.what_failed.append(f"skill:{skill_id}")

    def add_file_modified(self, file_path: str) -> None:
        """
        Record file modification.

        Args:
            file_path: Path to modified file
        """
        if file_path not in self.files_modified:
            self.files_modified.append(file_path)

    def add_stuck_signal(self, signal_type: str, severity: float, description: str) -> None:
        """
        Record stuck detection signal.

        Args:
            signal_type: Type of stuck signal
            severity: Signal severity (0-1)
            description: Human-readable description
        """
        self.stuck_signals.append(
            {
                "type": signal_type,
                "severity": severity,
                "description": description,
                "timestamp": time.time(),
            }
        )

    def record_escalation(self, reason: str) -> None:
        """
        Record escalation event.

        Args:
            reason: Why escalation was triggered
        """
        self.escalation_triggered = True
        self.escalation_reason = reason

    def finalize(self, success: bool, validation_results: dict[str, bool]) -> None:
        """
        Finalize trace with outcome.

        Args:
            success: Whether remediation succeeded
            validation_results: Final validation state
        """
        self.final_success = success
        self.validation_results = validation_results

        if self.timestamp:
            self.time_to_resolution_seconds = time.time() - self.timestamp

        # Set trace type
        if success:
            self.trace_type = TraceType.SUCCESS
        elif self.iterations_count > 0:
            self.trace_type = TraceType.PARTIAL
        else:
            self.trace_type = TraceType.FAILURE

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "trace_id": self.trace_id,
            "trace_type": self.trace_type.value,
            "timestamp": self.timestamp,
            "agent_name": self.agent_name,
            "task_description": self.task_description,
            "initial_error": self.initial_error,
            "error_category": self.error_category,
            "skill_ids_applied": self.skill_ids_applied,
            "files_modified": self.files_modified,
            "iterations_count": self.iterations_count,
            "final_success": self.final_success,
            "validation_results": self.validation_results,
            "time_to_resolution_seconds": self.time_to_resolution_seconds,
            "what_worked": self.what_worked,
            "what_failed": self.what_failed,
            "stuck_signals": self.stuck_signals,
            "resource_usage": self.resource_usage,
            "escalation_triggered": self.escalation_triggered,
            "escalation_reason": self.escalation_reason,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RemediationTrace":
        """Create trace from dictionary."""
        return cls(
            trace_id=data["trace_id"],
            trace_type=TraceType(data["trace_type"]),
            timestamp=data["timestamp"],
            agent_name=data["agent_name"],
            task_description=data["task_description"],
            initial_error=data["initial_error"],
            error_category=data["error_category"],
            skill_ids_applied=data.get("skill_ids_applied", []),
            files_modified=data.get("files_modified", []),
            iterations_count=data.get("iterations_count", 0),
            final_success=data.get("final_success", False),
            validation_results=data.get("validation_results", {}),
            time_to_resolution_seconds=data.get("time_to_resolution_seconds"),
            what_worked=data.get("what_worked", []),
            what_failed=data.get("what_failed", []),
            stuck_signals=data.get("stuck_signals", []),
            resource_usage=data.get("resource_usage", {}),
            escalation_triggered=data.get("escalation_triggered", False),
            escalation_reason=data.get("escalation_reason"),
        )
