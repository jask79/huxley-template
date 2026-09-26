#!/usr/bin/env python3
"""
SDK Events Viewer - Observability Tool for SDK Workflows

Query and view SDK workflow observations, metrics, and patterns from builder-memory.
Provides CLI interface for debugging and monitoring SDK workflow execution.

Features:
- View workflow history and observations
- Query workflow metrics (success rate, duration, etc.)
- Search patterns learned from workflows
- Real-time event streaming (tail mode)
- JSON export for integration

Usage:
    # View recent workflow history
    ./view_sdk_events.py --workflow daily_audit

    # View workflow metrics
    ./view_sdk_events.py --metrics daily_audit

    # List all workflows
    ./view_sdk_events.py --list

    # Search for specific observations
    ./view_sdk_events.py --search "failed"

    # Export to JSON
    ./view_sdk_events.py --workflow daily_audit --export events.json
"""

import sys
import json
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
import argparse

# Add SDK tools to path
SDK_DIR = Path(__file__).parent
sys.path.insert(0, str(SDK_DIR))

from sdk_memory_bridge import SDKMemoryBridge


class SDKEventsViewer:
    """
    Observability tool for SDK workflow events.
    """

    def __init__(self):
        """Initialize events viewer"""
        self.bridge = SDKMemoryBridge()

    def list_workflows(self) -> List[str]:
        """
        List all workflows with observations.

        Returns:
            List of workflow names
        """
        if "observations" not in self.bridge.mcp_memory:
            return []

        return list(self.bridge.mcp_memory["observations"].keys())

    def view_workflow_history(
        self,
        workflow_name: str,
        days: int = 7,
        limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        View workflow execution history.

        Args:
            workflow_name: Name of workflow
            days: Number of days to look back
            limit: Optional limit on number of results

        Returns:
            List of workflow observations
        """
        history = self.bridge.get_workflow_history(workflow_name, days=days)

        if limit:
            history = history[-limit:]

        return history

    def view_workflow_metrics(self, workflow_name: str) -> Dict[str, Any]:
        """
        View workflow metrics.

        Args:
            workflow_name: Name of workflow

        Returns:
            Metrics dictionary
        """
        return self.bridge.get_workflow_metrics(workflow_name)

    def search_observations(
        self,
        query: str,
        days: int = 7
    ) -> List[Dict[str, Any]]:
        """
        Search observations by text query.

        Args:
            query: Search query text
            days: Number of days to look back

        Returns:
            List of matching observations
        """
        if "observations" not in self.bridge.mcp_memory:
            return []

        query_lower = query.lower()
        results = []
        threshold = datetime.now() - timedelta(days=days)

        for workflow_name, observations in self.bridge.mcp_memory["observations"].items():
            for obs in observations:
                obs_time = datetime.fromisoformat(obs["timestamp"])
                if obs_time < threshold:
                    continue

                # Search in observation text and metadata
                obs_text = obs.get("observation", "").lower()
                metadata_text = json.dumps(obs.get("metadata", {})).lower()

                if query_lower in obs_text or query_lower in metadata_text:
                    results.append(obs)

        # Sort by timestamp descending
        results.sort(key=lambda x: x["timestamp"], reverse=True)

        return results

    def get_summary(self) -> Dict[str, Any]:
        """
        Get overall SDK events summary.

        Returns:
            Summary dictionary
        """
        workflows = self.list_workflows()

        # Get metrics for each workflow
        workflow_metrics = {}
        total_runs = 0
        total_successes = 0

        for workflow in workflows:
            metrics = self.view_workflow_metrics(workflow)
            workflow_metrics[workflow] = metrics
            total_runs += metrics.get("run_count", 0)

            # Calculate successes
            success_rate = metrics.get("success_rate", 0) / 100
            total_successes += int(metrics.get("run_count", 0) * success_rate)

        overall_success_rate = (total_successes / total_runs * 100) if total_runs > 0 else 0

        return {
            "total_workflows": len(workflows),
            "total_runs": total_runs,
            "overall_success_rate": round(overall_success_rate, 1),
            "workflows": workflow_metrics,
            "last_updated": datetime.now().isoformat()
        }

    def format_observation(self, obs: Dict[str, Any], verbose: bool = False) -> str:
        """
        Format observation for display.

        Args:
            obs: Observation dictionary
            verbose: If True, include full metadata

        Returns:
            Formatted string
        """
        timestamp = datetime.fromisoformat(obs["timestamp"]).strftime("%Y-%m-%d %H:%M:%S")
        workflow = obs.get("workflow", "unknown")
        text = obs.get("observation", "")

        output = f"[{timestamp}] {workflow}: {text}"

        if verbose:
            metadata = obs.get("metadata", {})
            if metadata:
                output += f"\n  Metadata: {json.dumps(metadata, indent=2)}"

        return output

    def export_to_json(
        self,
        workflow_name: str,
        output_file: Path,
        days: int = 7
    ):
        """
        Export workflow events to JSON file.

        Args:
            workflow_name: Name of workflow
            output_file: Output file path
            days: Number of days to export
        """
        history = self.view_workflow_history(workflow_name, days=days)
        metrics = self.view_workflow_metrics(workflow_name)

        export_data = {
            "workflow": workflow_name,
            "metrics": metrics,
            "history": history,
            "exported_at": datetime.now().isoformat()
        }

        with open(output_file, 'w') as f:
            json.dump(export_data, f, indent=2)

        print(f"✓ Exported {len(history)} events to: {output_file}")


def main():
    """CLI entry point"""
    parser = argparse.ArgumentParser(description="SDK Events Viewer")

    # Viewing commands
    parser.add_argument("--list", action="store_true",
                       help="List all workflows")
    parser.add_argument("--workflow", metavar="NAME",
                       help="View specific workflow history")
    parser.add_argument("--metrics", metavar="NAME",
                       help="View workflow metrics")
    parser.add_argument("--summary", action="store_true",
                       help="View overall SDK events summary")

    # Search
    parser.add_argument("--search", metavar="QUERY",
                       help="Search observations by text")

    # Options
    parser.add_argument("--days", type=int, default=7,
                       help="Number of days to look back (default: 7)")
    parser.add_argument("--limit", type=int,
                       help="Limit number of results")
    parser.add_argument("--verbose", action="store_true",
                       help="Show verbose output with metadata")

    # Export
    parser.add_argument("--export", metavar="FILE",
                       help="Export to JSON file")

    args = parser.parse_args()

    viewer = SDKEventsViewer()

    try:
        # List workflows
        if args.list:
            workflows = viewer.list_workflows()
            if workflows:
                print("SDK Workflows:")
                for wf in workflows:
                    print(f"  • {wf}")
            else:
                print("No workflows found")

        # View workflow history
        elif args.workflow:
            history = viewer.view_workflow_history(
                args.workflow,
                days=args.days,
                limit=args.limit
            )

            if history:
                print(f"Workflow History: {args.workflow} (last {args.days} days)")
                print("=" * 70)
                for obs in history:
                    print(viewer.format_observation(obs, verbose=args.verbose))
                print(f"\nTotal observations: {len(history)}")
            else:
                print(f"No history found for workflow: {args.workflow}")

            # Export if requested
            if args.export:
                viewer.export_to_json(args.workflow, Path(args.export), days=args.days)

        # View workflow metrics
        elif args.metrics:
            metrics = viewer.view_workflow_metrics(args.metrics)
            print(f"Workflow Metrics: {args.metrics}")
            print("=" * 70)
            print(f"  Run Count: {metrics.get('run_count', 0)}")
            print(f"  Success Rate: {metrics.get('success_rate', 0)}%")
            print(f"  Avg Duration: {metrics.get('avg_duration_ms', 0):.1f}ms")

            last_run = metrics.get('last_run')
            if last_run:
                last_run_time = datetime.fromisoformat(last_run)
                print(f"  Last Run: {last_run_time.strftime('%Y-%m-%d %H:%M:%S')}")

            recent_obs = metrics.get('recent_observations', [])
            if recent_obs:
                print(f"\n  Recent Observations:")
                for obs in recent_obs[-3:]:
                    print(f"    • {obs.get('observation', 'N/A')}")

        # Search observations
        elif args.search:
            results = viewer.search_observations(args.search, days=args.days)
            if results:
                print(f"Search Results: '{args.search}' (last {args.days} days)")
                print("=" * 70)
                for obs in results[:args.limit] if args.limit else results:
                    print(viewer.format_observation(obs, verbose=args.verbose))
                print(f"\nTotal matches: {len(results)}")
            else:
                print(f"No matches found for: {args.search}")

        # View summary
        elif args.summary:
            summary = viewer.get_summary()
            print("SDK Events Summary")
            print("=" * 70)
            print(f"Total Workflows: {summary['total_workflows']}")
            print(f"Total Runs: {summary['total_runs']}")
            print(f"Overall Success Rate: {summary['overall_success_rate']}%")
            print(f"\nWorkflow Breakdown:")
            for wf, metrics in summary['workflows'].items():
                print(f"  • {wf}:")
                print(f"    - Runs: {metrics.get('run_count', 0)}")
                print(f"    - Success: {metrics.get('success_rate', 0)}%")

        else:
            parser.print_help()

    except Exception as e:
        print(f"✗ Error: {e}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
