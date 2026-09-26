"""
Agent-specific loop implementations.

Each agent can have a specialized loop class that extends FoundationLoopExecutor
with agent-specific validation, remediation, and iteration strategies.
"""

from .frontend_dev_loop import FrontendDevLoop

__all__ = ["FrontendDevLoop"]
