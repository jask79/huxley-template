"""
Unit tests for trace collector.
"""

import shutil
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from learning.trace_collector import TraceCollector
from learning.trace_schema import TraceType


@pytest.fixture
def temp_storage():
    """Create temporary storage directory."""
    temp_dir = Path(tempfile.mkdtemp())
    yield temp_dir
    shutil.rmtree(temp_dir)


def test_trace_creation(temp_storage):
    """Test creating a new trace."""
    collector = TraceCollector(storage_dir=temp_storage)

    trace = collector.create_trace(
        agent_name="Test Agent",
        task_description="Test task",
        initial_error="Test error",
        error_category="test_failure",
    )

    assert trace.agent_name == "Test Agent"
    assert trace.task_description == "Test task"
    assert trace.trace_type == TraceType.FAILURE  # Initial state


def test_trace_storage(temp_storage):
    """Test storing traces to disk."""
    collector = TraceCollector(storage_dir=temp_storage)

    # Create and finalize trace
    trace = collector.create_trace(
        agent_name="Test Agent",
        task_description="Test task",
        initial_error="Test error",
        error_category="test_failure",
    )

    trace.finalize(success=True, validation_results={"test": True})
    collector.store_trace(trace)

    # Load back
    traces = collector.load_recent_traces(limit=1)

    assert len(traces) == 1
    assert traces[0].agent_name == "Test Agent"
    assert traces[0].final_success is True


def test_successful_patterns_extraction(temp_storage):
    """Test extracting patterns from successful traces."""
    collector = TraceCollector(storage_dir=temp_storage)

    # Create multiple success traces
    for i in range(3):
        trace = collector.create_trace(
            agent_name="Test Agent",
            task_description=f"Task {i}",
            initial_error="Error",
            error_category="build_error",
        )

        trace.add_skill_applied("fix_import", success=True)
        trace.iterations_count = 2
        trace.finalize(success=True, validation_results={"test": True})
        collector.store_trace(trace)

    # Extract patterns
    patterns = collector.extract_successful_patterns()

    assert patterns["total_successes"] == 3
    assert len(patterns["common_skills"]) > 0
    assert patterns["avg_iterations"] == 2.0


def test_failure_patterns_extraction(temp_storage):
    """Test extracting patterns from failed traces."""
    collector = TraceCollector(storage_dir=temp_storage)

    # Create failure traces
    for i in range(2):
        trace = collector.create_trace(
            agent_name="Test Agent",
            task_description=f"Task {i}",
            initial_error="Persistent error",
            error_category="runtime_error",
        )

        trace.record_escalation("Max iterations reached")
        trace.finalize(success=False, validation_results={"test": False})
        collector.store_trace(trace)

    # Extract patterns
    patterns = collector.extract_failure_patterns()

    assert patterns["total_failures"] == 2
    assert len(patterns["escalation_reasons"]) > 0


def test_avoidance_patterns(temp_storage):
    """Test checking for avoidance patterns."""
    collector = TraceCollector(storage_dir=temp_storage)

    # Create traces with failing skill
    for i in range(3):
        trace = collector.create_trace(
            agent_name="Test Agent",
            task_description=f"Task {i}",
            initial_error="Error",
            error_category="type_error",
        )

        trace.add_skill_applied("bad_skill", success=False)
        trace.finalize(success=False, validation_results={"test": False})
        collector.store_trace(trace)

    # Check avoidance
    avoidances = collector.check_avoidance_patterns("type_error")

    assert len(avoidances) > 0
    assert "bad_skill" in avoidances[0]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
