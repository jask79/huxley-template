"""
Resource guards for CPU, memory, and time limits.

Enforces resource constraints to prevent runaway loops.
"""

import time
from dataclasses import dataclass

import psutil


@dataclass
class ResourceLimits:
    """Resource limit configuration."""

    max_memory_mb: int = 2048
    max_cpu_percent: float = 80.0
    timeout_seconds: int = 1800  # 30 minutes
    per_validation_timeout: int = 300  # 5 minutes per validation


class ResourceGuard:
    """
    Enforces resource limits for agentic loops.

    Tracks and limits:
    - Memory usage
    - CPU usage
    - Total execution time
    - Per-validation timeouts
    """

    def __init__(self, limits: ResourceLimits | None = None):
        """
        Initialize resource guard.

        Args:
            limits: Resource limits configuration
        """
        self.limits = limits or ResourceLimits()
        self.start_time = time.time()
        self.validation_start_time: float | None = None
        self.process = psutil.Process()

    def check_resources(self) -> tuple[bool, str | None]:
        """
        Check if resource limits are exceeded.

        Returns:
            Tuple of (within_limits, violation_message)
        """
        # Check memory
        memory_mb = self.process.memory_info().rss / 1024 / 1024
        if memory_mb > self.limits.max_memory_mb:
            return (
                False,
                f"Memory limit exceeded: {memory_mb:.1f}MB > {self.limits.max_memory_mb}MB",
            )

        # Check CPU (average over last second)
        cpu_percent = self.process.cpu_percent(interval=0.1)
        if cpu_percent > self.limits.max_cpu_percent:
            return False, f"CPU limit exceeded: {cpu_percent:.1f}% > {self.limits.max_cpu_percent}%"

        # Check total time
        elapsed = time.time() - self.start_time
        if elapsed > self.limits.timeout_seconds:
            return False, f"Total timeout exceeded: {elapsed:.1f}s > {self.limits.timeout_seconds}s"

        # Check validation timeout
        if self.validation_start_time is not None:
            validation_elapsed = time.time() - self.validation_start_time
            if validation_elapsed > self.limits.per_validation_timeout:
                return (
                    False,
                    f"Validation timeout: {validation_elapsed:.1f}s > {self.limits.per_validation_timeout}s",
                )

        return True, None

    def start_validation(self) -> None:
        """Mark start of validation phase."""
        self.validation_start_time = time.time()

    def end_validation(self) -> None:
        """Mark end of validation phase."""
        self.validation_start_time = None

    def get_resource_usage(self) -> dict:
        """
        Get current resource usage stats.

        Returns:
            Dictionary with usage metrics
        """
        memory_mb = self.process.memory_info().rss / 1024 / 1024
        cpu_percent = self.process.cpu_percent(interval=0.1)
        elapsed = time.time() - self.start_time

        return {
            "memory_mb": round(memory_mb, 1),
            "memory_percent": round(memory_mb / self.limits.max_memory_mb * 100, 1),
            "cpu_percent": round(cpu_percent, 1),
            "elapsed_seconds": round(elapsed, 1),
            "elapsed_percent": round(elapsed / self.limits.timeout_seconds * 100, 1),
        }

    def get_budget_remaining(self) -> dict:
        """
        Get remaining resource budget.

        Returns:
            Dictionary with remaining resources
        """
        usage = self.get_resource_usage()

        return {
            "memory_mb": self.limits.max_memory_mb - usage["memory_mb"],
            "time_seconds": self.limits.timeout_seconds - usage["elapsed_seconds"],
            "memory_percent_remaining": 100 - usage["memory_percent"],
            "time_percent_remaining": 100 - usage["elapsed_percent"],
        }

    def is_resource_healthy(self) -> bool:
        """
        Check if resources are in healthy range (not critical).

        Returns:
            True if resource usage is healthy
        """
        usage = self.get_resource_usage()

        # Check if any resource is above 90% usage
        if usage["memory_percent"] > 90:
            return False
        if usage["elapsed_percent"] > 90:
            return False
        if usage["cpu_percent"] > 90:
            return False

        return True

    def reset(self) -> None:
        """Reset resource tracking."""
        self.start_time = time.time()
        self.validation_start_time = None
