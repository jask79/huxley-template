#!/usr/bin/env python3
"""
SDK Memory Bridge - In-Process MCP Integration

Provides direct builder-memory integration for SDK workflows without subprocess overhead.
Bridges SDK workflow events to MCP memory for persistent context and pattern learning.

Features:
- Direct MCP memory read/write (no subprocess calls)
- Automatic workflow observation logging
- Pattern learning from workflow outcomes
- Entity creation for workflow tracking
- Relation mapping between workflow components
- Fast in-memory caching

Usage:
    from sdk_memory_bridge import SDKMemoryBridge

    bridge = SDKMemoryBridge()

    # Log workflow observation
    bridge.observe_workflow("daily_audit", "completed successfully", {"duration_ms": 1250})

    # Query workflow history
    history = bridge.get_workflow_history("daily_audit", days=7)

    # Learn from workflow outcome
    bridge.learn_from_workflow("daily_audit", success=True, metrics={...})
"""

import json
import sys
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
import hashlib

# Add parent tools directory to path for SimpleMemoryBridge
TOOLS_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(TOOLS_DIR))

from simple_memory_bridge import SimpleMemoryBridge


class SDKMemoryBridge:
    """
    In-process MCP memory bridge for SDK workflows.

    Provides direct access to builder-memory MCP without subprocess overhead,
    enabling SDK workflows to persist observations, learn patterns, and
    maintain cross-session context.
    """

    def __init__(self, workflow_id: Optional[str] = None):
        """
        Initialize SDK memory bridge.

        Args:
            workflow_id: Optional workflow identifier for tracking
        """
        self.workflow_id = workflow_id or "sdk_workflow"
        self.session_id = f"{self.workflow_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        # Initialize underlying memory bridge
        self.memory = SimpleMemoryBridge()

        # Load current MCP memory state
        self.mcp_memory = self._load_mcp_memory()

        # Session cache for fast reads
        self._cache = {
            "entities": {},
            "observations": [],
            "patterns": {},
            "relations": {}
        }

    def _load_mcp_memory(self) -> Dict[str, Any]:
        """Load current MCP memory state from disk"""
        if self.memory.mcp_memory_path.exists():
            try:
                with open(self.memory.mcp_memory_path, 'r') as f:
                    return json.load(f)
            except Exception as e:
                print(f"⚠️ Could not load MCP memory: {e}", file=sys.stderr)
                return {"entities": {}, "relations": {}, "observations": {}}
        else:
            return {"entities": {}, "relations": {}, "observations": {}}

    def _save_mcp_memory(self):
        """Save MCP memory state to disk"""
        try:
            # Ensure directory exists
            self.memory.mcp_memory_path.parent.mkdir(parents=True, exist_ok=True)

            # Write atomic update
            temp_path = self.memory.mcp_memory_path.with_suffix('.tmp')
            with open(temp_path, 'w') as f:
                json.dump(self.mcp_memory, f, indent=2)

            # Atomic replace
            temp_path.replace(self.memory.mcp_memory_path)

        except Exception as e:
            print(f"⚠️ Could not save MCP memory: {e}", file=sys.stderr)

    def observe_workflow(
        self,
        workflow_name: str,
        observation: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Log observation from SDK workflow.

        Args:
            workflow_name: Name of workflow (e.g., "daily_audit")
            observation: Human-readable observation text
            metadata: Optional metadata (metrics, context, etc.)

        Returns:
            Observation ID
        """
        # Generate observation ID
        obs_id = hashlib.md5(
            f"{workflow_name}{observation}{datetime.now()}".encode()
        ).hexdigest()[:12]

        # Create observation record
        observation_record = {
            "id": obs_id,
            "workflow": workflow_name,
            "observation": observation,
            "timestamp": datetime.now().isoformat(),
            "session_id": self.session_id,
            "metadata": metadata or {}
        }

        # Add to MCP memory observations
        if "observations" not in self.mcp_memory:
            self.mcp_memory["observations"] = {}

        if workflow_name not in self.mcp_memory["observations"]:
            self.mcp_memory["observations"][workflow_name] = []

        self.mcp_memory["observations"][workflow_name].append(observation_record)

        # Keep only last 100 observations per workflow
        self.mcp_memory["observations"][workflow_name] = \
            self.mcp_memory["observations"][workflow_name][-100:]

        # Cache observation
        self._cache["observations"].append(observation_record)

        # Persist to disk
        self._save_mcp_memory()

        return obs_id

    def create_workflow_entity(
        self,
        workflow_name: str,
        workflow_type: str,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """
        Create or update workflow entity in MCP memory.

        Args:
            workflow_name: Name of workflow
            workflow_type: Type (e.g., "audit", "build", "test")
            metadata: Optional metadata
        """
        entity_id = f"workflow_{workflow_name}"

        # Create entity record
        entity = {
            "type": workflow_type,
            "name": workflow_name,
            "created": metadata.get("created", datetime.now().isoformat()),
            "last_run": datetime.now().isoformat(),
            "run_count": metadata.get("run_count", 1),
            "metadata": metadata or {}
        }

        # Add to MCP memory entities
        if "entities" not in self.mcp_memory:
            self.mcp_memory["entities"] = {}

        self.mcp_memory["entities"][entity_id] = entity

        # Cache entity
        self._cache["entities"][entity_id] = entity

        # Persist to disk
        self._save_mcp_memory()

    def learn_from_workflow(
        self,
        workflow_name: str,
        success: bool,
        metrics: Optional[Dict[str, Any]] = None,
        notes: Optional[str] = None
    ) -> str:
        """
        Learn from workflow execution outcome.

        Args:
            workflow_name: Name of workflow
            success: Whether workflow succeeded
            metrics: Optional metrics (duration, resources, etc.)
            notes: Optional notes about execution

        Returns:
            Pattern ID
        """
        # Prepare interaction content
        outcome = "success" if success else "failure"
        content = f"Workflow '{workflow_name}' {outcome}"

        if metrics:
            content += f" | Metrics: {json.dumps(metrics)}"
        if notes:
            content += f" | Notes: {notes}"

        # Use underlying memory bridge to learn
        pattern_id = self.memory.learn_from_interaction(
            interaction_type=f"workflow_{workflow_name}",
            content=content,
            outcome=outcome
        )

        # Also observe in MCP memory
        self.observe_workflow(
            workflow_name,
            f"Workflow {outcome} - learned pattern {pattern_id}",
            {"success": success, "metrics": metrics, "pattern_id": pattern_id}
        )

        return pattern_id

    def get_workflow_history(
        self,
        workflow_name: str,
        days: int = 7
    ) -> List[Dict[str, Any]]:
        """
        Get workflow execution history.

        Args:
            workflow_name: Name of workflow
            days: Number of days to look back

        Returns:
            List of workflow observations
        """
        if "observations" not in self.mcp_memory:
            return []

        if workflow_name not in self.mcp_memory["observations"]:
            return []

        # Filter by time threshold
        threshold = datetime.now() - timedelta(days=days)

        history = []
        for obs in self.mcp_memory["observations"][workflow_name]:
            obs_time = datetime.fromisoformat(obs["timestamp"])
            if obs_time >= threshold:
                history.append(obs)

        return history

    def get_workflow_metrics(self, workflow_name: str) -> Dict[str, Any]:
        """
        Get aggregated metrics for workflow.

        Args:
            workflow_name: Name of workflow

        Returns:
            Aggregated metrics dictionary
        """
        history = self.get_workflow_history(workflow_name, days=30)

        if not history:
            return {
                "run_count": 0,
                "success_rate": 0.0,
                "avg_duration_ms": 0.0,
                "last_run": None
            }

        # Calculate metrics
        run_count = len(history)
        success_count = sum(1 for obs in history if obs.get("metadata", {}).get("success", False))
        success_rate = success_count / run_count if run_count > 0 else 0.0

        # Duration metrics
        durations = [
            obs.get("metadata", {}).get("duration_ms", 0)
            for obs in history
            if obs.get("metadata", {}).get("duration_ms")
        ]
        avg_duration = sum(durations) / len(durations) if durations else 0.0

        # Last run
        last_run = history[-1]["timestamp"] if history else None

        return {
            "run_count": run_count,
            "success_rate": round(success_rate * 100, 1),
            "avg_duration_ms": round(avg_duration, 1),
            "last_run": last_run,
            "recent_observations": history[-5:]  # Last 5 observations
        }

    def create_workflow_relation(
        self,
        from_workflow: str,
        to_workflow: str,
        relation_type: str
    ):
        """
        Create relation between workflows.

        Args:
            from_workflow: Source workflow
            to_workflow: Target workflow
            relation_type: Type of relation (e.g., "depends_on", "triggers", "validates")
        """
        if "relations" not in self.mcp_memory:
            self.mcp_memory["relations"] = {}

        from_id = f"workflow_{from_workflow}"
        to_id = f"workflow_{to_workflow}"

        if from_id not in self.mcp_memory["relations"]:
            self.mcp_memory["relations"][from_id] = []

        self.mcp_memory["relations"][from_id].append({
            "to": to_id,
            "type": relation_type,
            "created": datetime.now().isoformat()
        })

        # Persist to disk
        self._save_mcp_memory()

    def query_patterns(self, workflow_name: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Query learned patterns from memory.

        Args:
            workflow_name: Optional filter by workflow

        Returns:
            List of matching patterns
        """
        metrics = self.memory.get_system_metrics()

        # For now, return summary metrics
        # In future, could query pattern database directly
        return [{
            "source": "memory_intelligence",
            "total_patterns": metrics.get("patterns_learned", 0),
            "knowledge_docs": metrics.get("knowledge_documents", 0),
            "search_success_rate": metrics.get("search_success_rate", "N/A"),
            "system_maturity": metrics.get("system_maturity", "N/A")
        }]

    def get_session_summary(self) -> Dict[str, Any]:
        """
        Get summary of current session activity.

        Returns:
            Session summary dictionary
        """
        return {
            "session_id": self.session_id,
            "workflow_id": self.workflow_id,
            "observations_logged": len(self._cache["observations"]),
            "entities_created": len(self._cache["entities"]),
            "timestamp": datetime.now().isoformat()
        }


def main():
    """CLI entry point for testing"""
    import argparse

    parser = argparse.ArgumentParser(description="SDK Memory Bridge")
    parser.add_argument("--observe", nargs=2, metavar=("WORKFLOW", "OBSERVATION"),
                       help="Log observation")
    parser.add_argument("--history", metavar="WORKFLOW",
                       help="Get workflow history")
    parser.add_argument("--metrics", metavar="WORKFLOW",
                       help="Get workflow metrics")
    parser.add_argument("--learn", nargs=3, metavar=("WORKFLOW", "SUCCESS", "NOTES"),
                       help="Learn from workflow outcome")

    args = parser.parse_args()

    bridge = SDKMemoryBridge()

    if args.observe:
        workflow, observation = args.observe
        obs_id = bridge.observe_workflow(workflow, observation)
        print(f"✓ Observation logged: {obs_id}")

    elif args.history:
        history = bridge.get_workflow_history(args.history)
        print(f"Workflow history for '{args.history}' (last 7 days):")
        print(json.dumps(history, indent=2))

    elif args.metrics:
        metrics = bridge.get_workflow_metrics(args.metrics)
        print(f"Metrics for '{args.metrics}':")
        print(json.dumps(metrics, indent=2))

    elif args.learn:
        workflow, success_str, notes = args.learn
        success = success_str.lower() in ("true", "yes", "1")
        pattern_id = bridge.learn_from_workflow(workflow, success, notes=notes)
        print(f"✓ Learned from workflow: {pattern_id}")


if __name__ == "__main__":
    main()
