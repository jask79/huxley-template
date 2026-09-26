#!/usr/bin/env python3
"""
SDK Session Replay Tool

Replays SDK workflow sessions step-by-step for debugging and analysis.
Reads workflow state from inspect_sdk_workflow.py and provides:
- Step-by-step replay with timing
- Tool call inspection
- Hook execution analysis
- State diff visualization
- Error replay and analysis

Usage:
    # Replay latest workflow
    ./replay_sdk_session.py

    # Replay specific workflow
    ./replay_sdk_session.py --workflow-id abc123

    # Step-through mode (interactive)
    ./replay_sdk_session.py --step

    # Show only errors
    ./replay_sdk_session.py --errors-only

    # Export replay as JSON
    ./replay_sdk_session.py --export replay.json
"""

import json
import sys
from pathlib import Path
from typing import Optional, Dict, Any, List
from datetime import datetime
from dataclasses import dataclass
import time


@dataclass
class ReplayStep:
    """Single step in workflow replay"""
    step_number: int
    timestamp: datetime
    step_type: str  # "tool_call", "hook", "state_change", "error"
    description: str
    details: Dict[str, Any]
    success: bool
    duration_ms: float


class SDKSessionReplayer:
    """
    Replays SDK workflow sessions for debugging.

    Loads workflow state from ~/.cache/catalyst/sdk_workflows/
    and provides step-by-step replay with analysis.
    """

    def __init__(self, state_dir: Optional[Path] = None):
        """
        Initialize replayer.

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
        """Read workflow state from disk"""
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
        """Get ID of most recently modified workflow"""
        workflow_files = sorted(
            self.state_dir.glob("*.json"),
            key=lambda p: p.stat().st_mtime,
            reverse=True
        )

        if not workflow_files:
            return None

        return workflow_files[0].stem

    def build_replay_timeline(self, state: Dict[str, Any]) -> List[ReplayStep]:
        """
        Build timeline of replay steps from workflow state.

        Args:
            state: Workflow state dictionary

        Returns:
            List of ReplayStep objects in chronological order
        """
        steps = []
        step_number = 1

        # Add tool calls
        for tool_call in state.get("tool_calls", []):
            steps.append(ReplayStep(
                step_number=step_number,
                timestamp=datetime.fromisoformat(tool_call["timestamp"]),
                step_type="tool_call",
                description=f"Tool: {tool_call['tool_name']}",
                details=tool_call,
                success=tool_call.get("success", True),
                duration_ms=tool_call.get("duration_ms", 0.0)
            ))
            step_number += 1

        # Add hooks
        for hook in state.get("hooks", []):
            steps.append(ReplayStep(
                step_number=step_number,
                timestamp=datetime.fromisoformat(hook["timestamp"]),
                step_type="hook",
                description=f"Hook: {hook['hook_name']}",
                details=hook,
                success=hook.get("result", "success") == "success",
                duration_ms=hook.get("duration_ms", 0.0)
            ))
            step_number += 1

        # Add errors
        for error in state.get("errors", []):
            steps.append(ReplayStep(
                step_number=step_number,
                timestamp=datetime.fromisoformat(error.get("timestamp", state["start_time"])),
                step_type="error",
                description=f"Error: {error.get('type', 'Unknown')}",
                details=error,
                success=False,
                duration_ms=0.0
            ))
            step_number += 1

        # Sort by timestamp
        steps.sort(key=lambda s: s.timestamp)

        # Renumber after sorting
        for i, step in enumerate(steps, 1):
            step.step_number = i

        return steps

    def replay_workflow(
        self,
        workflow_id: str,
        step_mode: bool = False,
        errors_only: bool = False,
        playback_speed: float = 1.0
    ):
        """
        Replay workflow execution.

        Args:
            workflow_id: Workflow identifier
            step_mode: If True, wait for user input between steps
            errors_only: If True, only show error steps
            playback_speed: Speed multiplier for delays (1.0 = realtime, 2.0 = 2x speed)
        """
        state = self.get_workflow_state(workflow_id)
        if not state:
            print(f"Workflow not found: {workflow_id}", file=sys.stderr)
            return

        timeline = self.build_replay_timeline(state)

        if errors_only:
            timeline = [s for s in timeline if not s.success]

        print("=" * 70)
        print(f"Replaying Workflow: {workflow_id}")
        print("=" * 70)
        print(f"Capsule: {state.get('capsule', 'unknown')}")
        print(f"Status: {state.get('status', 'unknown')}")
        print(f"Total Steps: {len(timeline)}")
        print(f"Start: {state.get('start_time', 'unknown')}")
        print("=" * 70)

        if not timeline:
            print("\n⚠ No steps to replay")
            return

        prev_timestamp = None

        for step in timeline:
            # Calculate delay
            if prev_timestamp and not step_mode:
                delay_ms = (step.timestamp - prev_timestamp).total_seconds() * 1000
                delay_seconds = (delay_ms / 1000) / playback_speed
                if delay_seconds > 0.05:  # Minimum delay
                    time.sleep(delay_seconds)

            # Show step
            self._show_step(step)

            prev_timestamp = step.timestamp

            # Wait for user input in step mode
            if step_mode:
                try:
                    input("\nPress Enter for next step (Ctrl+C to exit)...")
                except KeyboardInterrupt:
                    print("\n\nReplay stopped by user")
                    return

        print("\n" + "=" * 70)
        print("✓ Replay complete")
        print("=" * 70)

    def _show_step(self, step: ReplayStep):
        """Display single replay step"""
        status_icon = "✓" if step.success else "✗"
        timestamp_str = step.timestamp.strftime("%H:%M:%S.%f")[:-3]

        print(f"\n[{step.step_number}] [{timestamp_str}] {status_icon} {step.description}")
        print(f"    Type: {step.step_type}")
        print(f"    Duration: {step.duration_ms:.0f}ms")

        # Show type-specific details
        if step.step_type == "tool_call":
            print(f"    Input: {step.details.get('input_summary', 'N/A')[:60]}")
            print(f"    Output: {step.details.get('output_summary', 'N/A')[:60]}")

        elif step.step_type == "hook":
            print(f"    Result: {step.details.get('result', 'unknown')}")
            print(f"    Message: {step.details.get('message', 'N/A')[:60]}")

        elif step.step_type == "error":
            print(f"    Error Type: {step.details.get('type', 'unknown')}")
            print(f"    Message: {step.details.get('message', 'N/A')}")
            if "traceback" in step.details:
                print(f"    Traceback:\n{step.details['traceback']}")

    def analyze_errors(self, workflow_id: str):
        """
        Analyze errors in workflow execution.

        Args:
            workflow_id: Workflow identifier
        """
        state = self.get_workflow_state(workflow_id)
        if not state:
            print(f"Workflow not found: {workflow_id}", file=sys.stderr)
            return

        errors = state.get("errors", [])
        timeline = self.build_replay_timeline(state)
        failed_steps = [s for s in timeline if not s.success]

        print("=" * 70)
        print(f"Error Analysis: {workflow_id}")
        print("=" * 70)

        if not errors and not failed_steps:
            print("✓ No errors found")
            return

        print(f"\nTotal Errors: {len(errors)}")
        print(f"Failed Steps: {len(failed_steps)}")

        if errors:
            print("\nError Details:")
            print("-" * 70)
            for i, error in enumerate(errors, 1):
                print(f"\n{i}. {error.get('type', 'Unknown Error')}")
                print(f"   Timestamp: {error.get('timestamp', 'unknown')}")
                print(f"   Message: {error.get('message', 'N/A')}")
                if "context" in error:
                    print(f"   Context: {error['context']}")

        if failed_steps:
            print("\nFailed Steps:")
            print("-" * 70)
            for step in failed_steps:
                print(f"\n{step.step_number}. {step.description}")
                print(f"   Time: {step.timestamp.strftime('%H:%M:%S')}")
                if step.step_type == "hook":
                    print(f"   Hook Result: {step.details.get('result', 'unknown')}")
                    print(f"   Message: {step.details.get('message', 'N/A')}")

    def export_replay(self, workflow_id: str, output_file: Path):
        """
        Export replay data as JSON.

        Args:
            workflow_id: Workflow identifier
            output_file: Path to export JSON file
        """
        state = self.get_workflow_state(workflow_id)
        if not state:
            print(f"Workflow not found: {workflow_id}", file=sys.stderr)
            return

        timeline = self.build_replay_timeline(state)

        export_data = {
            "workflow_id": workflow_id,
            "capsule": state.get("capsule", "unknown"),
            "status": state.get("status", "unknown"),
            "start_time": state.get("start_time"),
            "end_time": state.get("end_time"),
            "total_steps": len(timeline),
            "timeline": [
                {
                    "step_number": s.step_number,
                    "timestamp": s.timestamp.isoformat(),
                    "type": s.step_type,
                    "description": s.description,
                    "success": s.success,
                    "duration_ms": s.duration_ms,
                    "details": s.details
                }
                for s in timeline
            ]
        }

        with open(output_file, 'w') as f:
            json.dump(export_data, f, indent=2)

        print(f"✓ Replay exported to: {output_file}")


def main():
    """CLI entry point"""
    import argparse

    parser = argparse.ArgumentParser(description="SDK Session Replay Tool")
    parser.add_argument("--workflow-id", help="Workflow ID to replay")
    parser.add_argument("--step", action="store_true", help="Step-through mode (interactive)")
    parser.add_argument("--errors-only", action="store_true", help="Show only error steps")
    parser.add_argument("--speed", type=float, default=1.0, help="Playback speed multiplier")
    parser.add_argument("--analyze-errors", action="store_true", help="Analyze errors only")
    parser.add_argument("--export", help="Export replay to JSON file")

    args = parser.parse_args()

    replayer = SDKSessionReplayer()

    # Get workflow ID
    workflow_id = args.workflow_id or replayer.get_latest_workflow()
    if not workflow_id:
        print("No workflows found. Run an SDK workflow first.", file=sys.stderr)
        return 1

    # Export mode
    if args.export:
        replayer.export_replay(workflow_id, Path(args.export))
        return 0

    # Error analysis mode
    if args.analyze_errors:
        replayer.analyze_errors(workflow_id)
        return 0

    # Replay mode
    replayer.replay_workflow(
        workflow_id,
        step_mode=args.step,
        errors_only=args.errors_only,
        playback_speed=args.speed
    )

    return 0


if __name__ == "__main__":
    sys.exit(main())
