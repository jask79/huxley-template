"""
Learning system for agentic loops.

Captures success/failure traces for continuous improvement.
"""

from .trace_collector import TraceCollector
from .trace_schema import RemediationTrace, TraceType

__all__ = ["RemediationTrace", "TraceType", "TraceCollector"]
