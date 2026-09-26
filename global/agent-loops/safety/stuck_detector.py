"""
Stuck detection using multiple signals.

Detects when loop is making no progress using multiple heuristics.
"""

import difflib
from collections import Counter
from dataclasses import dataclass, field


@dataclass
class StuckSignal:
    """A signal indicating the loop might be stuck."""

    signal_type: str  # error_repetition, code_churn, zero_progress
    severity: float  # 0.0-1.0
    description: str
    timestamp: float


@dataclass
class StuckDetector:
    """
    Detects when agentic loop is stuck and making no progress.

    Uses multiple signals:
    - Error repetition (same errors multiple times)
    - Code churn (changing same lines repeatedly)
    - Zero progress (no validation improvements)
    """

    # Configuration
    error_repetition_threshold: int = 3
    code_churn_threshold: int = 3
    zero_progress_window: int = 4

    # State tracking
    error_history: list[str] = field(default_factory=list)
    file_change_history: dict[str, list[str]] = field(
        default_factory=dict
    )  # file -> [code snapshots]
    validation_history: list[dict[str, bool]] = field(default_factory=list)
    signals: list[StuckSignal] = field(default_factory=list)

    def record_error(self, error_message: str, category: str) -> None:
        """
        Record an error occurrence.

        Args:
            error_message: Error text
            category: Error category
        """
        # Normalize error message (remove line numbers, timestamps)
        normalized_error = self._normalize_error(error_message)
        self.error_history.append(normalized_error)

    def record_file_change(self, file_path: str, content: str) -> None:
        """
        Record file modification.

        Args:
            file_path: Path to modified file
            content: New file content
        """
        if file_path not in self.file_change_history:
            self.file_change_history[file_path] = []

        self.file_change_history[file_path].append(content)

    def record_validation(self, results: dict[str, bool]) -> None:
        """
        Record validation results.

        Args:
            results: Dictionary of validation outcomes
        """
        self.validation_history.append(results)

    def check_stuck(self) -> bool:
        """
        Check if loop appears to be stuck.

        Returns:
            True if stuck detected
        """
        import time

        signals_detected = []

        # Check error repetition
        if self._detect_error_repetition():
            signals_detected.append(
                StuckSignal(
                    signal_type="error_repetition",
                    severity=0.8,
                    description=f"Same error repeated {self.error_repetition_threshold}+ times",
                    timestamp=time.time(),
                )
            )

        # Check code churn
        churning_files = self._detect_code_churn()
        if churning_files:
            signals_detected.append(
                StuckSignal(
                    signal_type="code_churn",
                    severity=0.7,
                    description=f"High churn in files: {', '.join(churning_files)}",
                    timestamp=time.time(),
                )
            )

        # Check zero progress
        if self._detect_zero_progress():
            signals_detected.append(
                StuckSignal(
                    signal_type="zero_progress",
                    severity=0.9,
                    description=f"No validation improvement in {self.zero_progress_window} iterations",
                    timestamp=time.time(),
                )
            )

        # Store signals
        self.signals.extend(signals_detected)

        # Consider stuck if we have multiple high-severity signals
        high_severity = [s for s in signals_detected if s.severity >= 0.7]
        return len(high_severity) >= 2

    def _detect_error_repetition(self) -> bool:
        """
        Detect if same error repeats multiple times.

        Returns:
            True if error repetition detected
        """
        if len(self.error_history) < self.error_repetition_threshold:
            return False

        # Count occurrences of each error
        error_counts = Counter(self.error_history[-10:])  # Look at last 10 errors

        # Check if any error appears threshold+ times
        max_count = max(error_counts.values()) if error_counts else 0
        return max_count >= self.error_repetition_threshold

    def _detect_code_churn(self) -> list[str]:
        """
        Detect files with excessive modification churn.

        Returns:
            List of churning file paths
        """
        churning_files = []

        for file_path, versions in self.file_change_history.items():
            if len(versions) < self.code_churn_threshold:
                continue

            # Check if changes are oscillating (similar to older versions)
            recent_versions = versions[-5:]  # Last 5 versions

            # Compare latest with previous versions
            latest = recent_versions[-1]
            similarities = []

            for older_version in recent_versions[:-1]:
                similarity = difflib.SequenceMatcher(None, latest, older_version).ratio()
                similarities.append(similarity)

            # If latest is very similar to older versions, we're churning
            avg_similarity = sum(similarities) / len(similarities) if similarities else 0
            if avg_similarity > 0.8:  # More than 80% similar
                churning_files.append(file_path)

        return churning_files

    def _detect_zero_progress(self) -> bool:
        """
        Detect if no validation improvements are happening.

        Returns:
            True if zero progress detected
        """
        if len(self.validation_history) < self.zero_progress_window:
            return False

        recent = self.validation_history[-self.zero_progress_window :]

        # Count total passing validations for each iteration
        passing_counts = []
        for validation in recent:
            passing = sum(1 for passed in validation.values() if passed)
            passing_counts.append(passing)

        # Check if no improvement (all counts same or decreasing)
        if not passing_counts:
            return False

        first_count = passing_counts[0]
        no_improvement = all(count <= first_count for count in passing_counts)

        return no_improvement

    def _normalize_error(self, error_message: str) -> str:
        """
        Normalize error message for comparison.

        Args:
            error_message: Raw error text

        Returns:
            Normalized error string
        """
        import re

        # Remove line numbers
        normalized = re.sub(r"line \d+", "line X", error_message)

        # Remove file paths (keep just filename)
        normalized = re.sub(r"/[^\s:]+/([^/:\s]+)", r"\1", normalized)

        # Remove timestamps
        normalized = re.sub(r"\d{4}-\d{2}-\d{2}", "DATE", normalized)
        normalized = re.sub(r"\d{2}:\d{2}:\d{2}", "TIME", normalized)

        # Remove memory addresses
        normalized = re.sub(r"0x[0-9a-fA-F]+", "0xADDR", normalized)

        return normalized.lower().strip()

    def get_stuck_summary(self) -> dict[str, any]:
        """
        Get summary of stuck indicators.

        Calls private detection methods directly to avoid the side effect in
        check_stuck() that appends to self.signals on every call.

        Returns:
            Dictionary with stuck detection info
        """
        error_repetition = self._detect_error_repetition()
        churning_files = self._detect_code_churn()
        zero_progress = self._detect_zero_progress()

        # Mirror check_stuck()'s "multiple high-severity signals" logic without
        # recording new signals.
        high_severity_count = 0
        if error_repetition:
            high_severity_count += 1  # severity 0.8
        if churning_files:
            high_severity_count += 1  # severity 0.7
        if zero_progress:
            high_severity_count += 1  # severity 0.9
        is_stuck = high_severity_count >= 2

        return {
            "is_stuck": is_stuck,
            "error_repetition": len(set(self.error_history[-10:])) if self.error_history else 0,
            "churning_files": len(churning_files),
            "zero_progress_detected": zero_progress,
            "signals": [
                {"type": s.signal_type, "severity": s.severity, "description": s.description}
                for s in self.signals[-5:]  # Last 5 signals
            ],
        }

    def reset(self) -> None:
        """Reset detector state."""
        self.error_history.clear()
        self.file_change_history.clear()
        self.validation_history.clear()
        self.signals.clear()
