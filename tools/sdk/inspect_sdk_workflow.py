#!/usr/bin/env python3
"""
SDK Workflow Inspector - Observability Tool for Huxley

Provides detailed inspection of SDK workflow execution state, performance,
and debugging information. Enables {{ORCHESTRATOR_NAME}} governance oversight by making
SDK workflows transparent and auditable.

Usage:
    # Show latest workflow execution
    ./inspect_sdk_workflow.py

    # Inspect specific workflow by ID
    ./inspect_sdk_workflow.py --workflow-id abc123

    # Show performance metrics
    ./inspect_sdk_workflow.py --metrics

    # Show hook execution history
    ./inspect_sdk_workflow.py --hooks

    # Live monitoring mode
    ./inspect_sdk_workflow.py --watch
"""

import json
import sys
from pathlib import Path
from typing import Optional, Dict, Any, List
from datetime import datetime
from dataclasses import dataclass, asdict
import time


@dataclass
class WorkflowMetrics:
    """Performance metrics for SDK workflow"""
    workflow_id: str
    capsule: str
    start_time: datetime
    end_time: Optional[datetime]
    duration_seconds: Optional[float]
    tool_calls: int
    hooks_called: int
    errors: int
    status: str  # running, completed, failed, blocked


@dataclass
class ToolCallRecord:
    """Record of a tool call during workflow"""
    timestamp: datetime
    tool_name: str
    input_summary: str
    output_summary: str
    duration_ms: float
    success: bool


@dataclass
class HookRecord:
    """Record of hook execution during workflow"""
    timestamp: datetime
    hook_name: str
    result: str  # success, warning, blocked
    message: str
    duration_ms: float


class SDKWorkflowInspector:
    """Inspects SDK workflow execution state for observability"""

    def __init__(self, state_dir: Optional[Path] = None):
        """
        Initialize inspector.

        Args:
            state_dir: Directory where SDK workflow state is stored
                      (defaults to ~/.cache/catalyst/sdk_workflows/)
        """
        if state_dir is None:
            self.state_dir = Path.home() / ".cache/catalyst/sdk_workflows"
        else:
            self.state_dir = Path(state_dir)

        self.state_dir.mkdir(parents=True, exist_ok=True)

    def get_workflow_state(self, workflow_id: str) -> Optional[Dict[str, Any]]:
        """
        Read workflow state from disk.

        Args:
            workflow_id: Workflow identifier

        Returns:
            Workflow state dictionary or None if not found
        """
        state_file = self.state_dir / f"{workflow_id}.json"
        if not state_file.exists():
            return None

        try:
            with open(state_file, 'r') as f:
                return json.load(f)
        except Exception as e:
            print(f"⚠ Error reading workflow state: {e}", file=sys.stderr)
            return None

    def get_latest_workflow(self) -> Optional[str]:
        """
        Get ID of most recently modified workflow.

        Returns:
            Workflow ID or None if no workflows found
        """
        workflow_files = sorted(
            self.state_dir.glob("*.json"),
            key=lambda p: p.stat().st_mtime,
            reverse=True
        )

        if not workflow_files:
            return None

        return workflow_files[0].stem

    def get_metrics(self, workflow_id: str) -> Optional[WorkflowMetrics]:
        """
        Get performance metrics for workflow.

        Args:
            workflow_id: Workflow identifier

        Returns:
            WorkflowMetrics or None if not found
        """
        state = self.get_workflow_state(workflow_id)
        if not state:
            return None

        start_time = datetime.fromisoformat(state.get("start_time", ""))
        end_time_str = state.get("end_time")
        end_time = datetime.fromisoformat(end_time_str) if end_time_str else None

        duration = None
        if end_time:
            duration = (end_time - start_time).total_seconds()

        return WorkflowMetrics(
            workflow_id=workflow_id,
            capsule=state.get("capsule", "unknown"),
            start_time=start_time,
            end_time=end_time,
            duration_seconds=duration,
            tool_calls=len(state.get("tool_calls", [])),
            hooks_called=len(state.get("hooks", [])),
            errors=len(state.get("errors", [])),
            status=state.get("status", "unknown")
        )

    def get_tool_calls(self, workflow_id: str) -> List[ToolCallRecord]:
        """
        Get tool call history for workflow.

        Args:
            workflow_id: Workflow identifier

        Returns:
            List of ToolCallRecord objects
        """
        state = self.get_workflow_state(workflow_id)
        if not state:
            return []

        records = []
        for call in state.get("tool_calls", []):
            records.append(ToolCallRecord(
                timestamp=datetime.fromisoformat(call["timestamp"]),
                tool_name=call["tool_name"],
                input_summary=call.get("input_summary", ""),
                output_summary=call.get("output_summary", ""),
                duration_ms=call.get("duration_ms", 0.0),
                success=call.get("success", True)
            ))

        return records

    def get_hooks(self, workflow_id: str) -> List[HookRecord]:
        """
        Get hook execution history for workflow.

        Args:
            workflow_id: Workflow identifier

        Returns:
            List of HookRecord objects
        """
        state = self.get_workflow_state(workflow_id)
        if not state:
            return []

        records = []
        for hook in state.get("hooks", []):
            records.append(HookRecord(
                timestamp=datetime.fromisoformat(hook["timestamp"]),
                hook_name=hook["hook_name"],
                result=hook.get("result", "unknown"),
                message=hook.get("message", ""),
                duration_ms=hook.get("duration_ms", 0.0)
            ))

        return records

    def format_metrics(self, metrics: WorkflowMetrics) -> str:
        """Format metrics for display"""
        output = []
        output.append("=" * 60)
        output.append(f"Workflow: {metrics.workflow_id}")
        output.append("=" * 60)
        output.append(f"Capsule:       {metrics.capsule}")
        output.append(f"Status:        {metrics.status}")
        output.append(f"Start:         {metrics.start_time.strftime('%Y-%m-%d %H:%M:%S')}")

        if metrics.end_time:
            output.append(f"End:           {metrics.end_time.strftime('%Y-%m-%d %H:%M:%S')}")
            output.append(f"Duration:      {metrics.duration_seconds:.2f}s")
        else:
            output.append("End:           [RUNNING]")

        output.append(f"Tool Calls:    {metrics.tool_calls}")
        output.append(f"Hooks Called:  {metrics.hooks_called}")
        output.append(f"Errors:        {metrics.errors}")

        return "\n".join(output)

    def format_tool_calls(self, calls: List[ToolCallRecord]) -> str:
        """Format tool call history for display"""
        if not calls:
            return "No tool calls recorded"

        output = []
        output.append("\nTool Call History:")
        output.append("-" * 60)

        for i, call in enumerate(calls, 1):
            status = "✓" if call.success else "✗"
            output.append(f"{i}. [{call.timestamp.strftime('%H:%M:%S')}] {status} {call.tool_name}")
            output.append(f"   Input:  {call.input_summary[:60]}")
            output.append(f"   Output: {call.output_summary[:60]}")
            output.append(f"   Time:   {call.duration_ms:.0f}ms")
            output.append("")

        return "\n".join(output)

    def format_hooks(self, hooks: List[HookRecord]) -> str:
        """Format hook execution history for display"""
        if not hooks:
            return "No hooks executed"

        output = []
        output.append("\nHook Execution History:")
        output.append("-" * 60)

        for i, hook in enumerate(hooks, 1):
            result_icon = {
                "success": "✓",
                "warning": "⚠",
                "blocked": "✗"
            }.get(hook.result, "?")

            output.append(f"{i}. [{hook.timestamp.strftime('%H:%M:%S')}] {result_icon} {hook.hook_name}")
            output.append(f"   Result: {hook.result}")
            output.append(f"   Message: {hook.message}")
            output.append(f"   Time: {hook.duration_ms:.0f}ms")
            output.append("")

        return "\n".join(output)

    def list_workflows(self) -> List[str]:
        """
        List all workflow IDs, newest first.

        Returns:
            List of workflow IDs
        """
        workflow_files = sorted(
            self.state_dir.glob("*.json"),
            key=lambda p: p.stat().st_mtime,
            reverse=True
        )

        return [f.stem for f in workflow_files]

    def watch_workflow(self, workflow_id: str, interval: float = 2.0):
        """
        Watch workflow execution in real-time.

        Args:
            workflow_id: Workflow identifier
            interval: Polling interval in seconds
        """
        print(f"Watching workflow: {workflow_id}")
        print("Press Ctrl+C to stop\n")

        try:
            last_tool_count = 0
            last_hook_count = 0

            while True:
                metrics = self.get_metrics(workflow_id)
                if not metrics:
                    print("⚠ Workflow not found", file=sys.stderr)
                    return

                # Show summary
                print(f"\r{metrics.status.upper()} | Tools: {metrics.tool_calls} | Hooks: {metrics.hooks_called} | Errors: {metrics.errors}", end="")

                # Show new activity
                if metrics.tool_calls > last_tool_count:
                    calls = self.get_tool_calls(workflow_id)
                    new_calls = calls[last_tool_count:]
                    for call in new_calls:
                        print(f"\n→ Tool: {call.tool_name} ({call.duration_ms:.0f}ms)")

                if metrics.hooks_called > last_hook_count:
                    hooks = self.get_hooks(workflow_id)
                    new_hooks = hooks[last_hook_count:]
                    for hook in new_hooks:
                        print(f"\n→ Hook: {hook.hook_name} - {hook.result}")

                last_tool_count = metrics.tool_calls
                last_hook_count = metrics.hooks_called

                # Stop if workflow completed
                if metrics.status in ["completed", "failed", "blocked"]:
                    print(f"\n\nWorkflow {metrics.status}")
                    break

                time.sleep(interval)

        except KeyboardInterrupt:
            print("\n\nWatch stopped")


def main():
    """CLI entry point"""
    import argparse

    parser = argparse.ArgumentParser(description="SDK Workflow Inspector")
    parser.add_argument("--workflow-id", help="Workflow ID to inspect")
    parser.add_argument("--metrics", action="store_true", help="Show performance metrics")
    parser.add_argument("--tools", action="store_true", help="Show tool call history")
    parser.add_argument("--hooks", action="store_true", help="Show hook execution history")
    parser.add_argument("--watch", action="store_true", help="Watch workflow in real-time")
    parser.add_argument("--list", action="store_true", help="List all workflows")

    args = parser.parse_args()

    inspector = SDKWorkflowInspector()

    # List workflows
    if args.list:
        workflows = inspector.list_workflows()
        if not workflows:
            print("No workflows found")
            return 0

        print("Recent Workflows:")
        for i, wf_id in enumerate(workflows[:10], 1):
            metrics = inspector.get_metrics(wf_id)
            if metrics:
                print(f"{i}. {wf_id} - {metrics.status} - {metrics.capsule}")
        return 0

    # Get workflow ID
    workflow_id = args.workflow_id or inspector.get_latest_workflow()
    if not workflow_id:
        print("No workflows found. Run an SDK workflow first.", file=sys.stderr)
        return 1

    # Watch mode
    if args.watch:
        inspector.watch_workflow(workflow_id)
        return 0

    # Show metrics
    if args.metrics or (not args.tools and not args.hooks):
        metrics = inspector.get_metrics(workflow_id)
        if not metrics:
            print(f"Workflow not found: {workflow_id}", file=sys.stderr)
            return 1
        print(inspector.format_metrics(metrics))

    # Show tool calls
    if args.tools:
        calls = inspector.get_tool_calls(workflow_id)
        print(inspector.format_tool_calls(calls))

    # Show hooks
    if args.hooks:
        hooks = inspector.get_hooks(workflow_id)
        print(inspector.format_hooks(hooks))

    return 0


if __name__ == "__main__":
    sys.exit(main())
