#!/usr/bin/env python3
"""
Autonomous Governance Engine for SDK Workflows

Implements risk classification and decision-making based on
autonomous_governance.yaml protocol. Ensures SDK workflows operate
within safety boundaries defined by {{ORCHESTRATOR_NAME}} governance framework.

Usage:
    from governance import GovernanceEngine, RiskLevel

    gov = GovernanceEngine()

    # Classify an operation
    risk = gov.classify_operation(
        operation="Update CLAUDE.md",
        scope="single_capsule",
        reversible=True,
        external_deps=False
    )

    if risk == RiskLevel.GREEN:
        # Auto-execute
        execute_workflow()
    elif risk == RiskLevel.YELLOW:
        # Queue and notify
        await_approval()
    else:
        # Block and alert
        alert_user()
"""

import yaml
import sys
from pathlib import Path
from typing import Optional, Dict, Any, List
from enum import Enum
from dataclasses import dataclass
from datetime import datetime


class RiskLevel(Enum):
    """Risk classification levels"""
    GREEN = "green"   # Auto-execute
    YELLOW = "yellow" # Queue and notify
    RED = "red"       # Block and alert


@dataclass
class ClassificationResult:
    """Result of operation classification"""
    risk_level: RiskLevel
    rationale: str
    approval_required: bool
    notification_type: str
    rollback_strategy: str
    decision_step: Optional[int] = None


@dataclass
class WorkflowDecision:
    """Decision for workflow execution"""
    workflow_name: str
    operation: str
    classification: ClassificationResult
    timestamp: datetime
    approved: bool = False
    executed: bool = False
    notes: str = ""


class GovernanceEngine:
    """
    Autonomous governance engine for SDK workflows.

    Loads autonomous_governance.yaml and provides risk classification,
    decision-making, and audit logging for SDK workflow operations.
    """

    def __init__(self, config_path: Optional[Path] = None):
        """
        Initialize governance engine.

        Args:
            config_path: Path to autonomous_governance.yaml
                        (defaults to tools/sdk/autonomous_governance.yaml)
        """
        if config_path is None:
            self.config_path = Path(__file__).parent / "autonomous_governance.yaml"
        else:
            self.config_path = Path(config_path)

        # Load governance configuration
        with open(self.config_path, 'r') as f:
            self.config = yaml.safe_load(f)

        self.risk_levels = self.config['risk_levels']
        self.green_criteria = self.config['green_criteria']
        self.yellow_criteria = self.config['yellow_criteria']
        self.red_criteria = self.config['red_criteria']
        self.decision_tree = self.config['decision_tree']
        self.workflow_overrides = self.config.get('workflow_overrides', {})

    def classify_operation(
        self,
        operation: str,
        scope: str = "single_capsule",
        reversible: bool = True,
        effort_hours: float = 1.0,
        external_deps: bool = False,
        modifies_specs: bool = False,
        modifies_framework: bool = False,
        involves_deletion: bool = False,
        involves_credentials: bool = False,
        involves_spend: bool = False,
        workflow_name: Optional[str] = None
    ) -> ClassificationResult:
        """
        Classify operation risk level using decision tree.

        Args:
            operation: Description of operation
            scope: "single_capsule", "cross_capsule", or "system_wide"
            reversible: Can operation be rolled back?
            effort_hours: Estimated completion time
            external_deps: Requires external APIs/services?
            modifies_specs: Modifies specs/*.yaml?
            modifies_framework: Modifies Huxley framework?
            involves_deletion: Deletes files/data?
            involves_credentials: Accesses credentials?
            involves_spend: External financial transactions?
            workflow_name: Optional workflow name for override lookup

        Returns:
            ClassificationResult with risk level and rationale
        """
        # Check for workflow-specific override
        if workflow_name and workflow_name in self.workflow_overrides:
            override = self.workflow_overrides[workflow_name]
            risk_level = RiskLevel(override['risk_level'])
            return ClassificationResult(
                risk_level=risk_level,
                rationale=f"Workflow override: {override['rationale']}",
                approval_required=self.risk_levels[risk_level.value]['approval_required'],
                notification_type=self.risk_levels[risk_level.value]['notification'],
                rollback_strategy=self.risk_levels[risk_level.value]['rollback_strategy']
            )

        # Execute decision tree (Step 1-5)
        decision_step = 1

        # Step 1: Check for HIGH RISK indicators
        if involves_deletion or involves_spend or involves_credentials:
            return self._classify_as(
                RiskLevel.RED,
                f"Operation involves deletion, spend, or credentials (Step {decision_step})",
                decision_step
            )

        decision_step = 2

        # Step 2: Check for framework or production modifications
        if modifies_framework or scope == "system_wide":
            return self._classify_as(
                RiskLevel.RED,
                f"Operation modifies Huxley framework or production systems (Step {decision_step})",
                decision_step
            )

        decision_step = 3

        # Step 3: Check for spec modifications
        if modifies_specs:
            return self._classify_as(
                RiskLevel.YELLOW,
                f"Operation modifies specs, product.yaml, or standards.yaml (Step {decision_step})",
                decision_step
            )

        decision_step = 4

        # Step 4: Check for cross-capsule or shared tool modifications
        if scope == "cross_capsule":
            return self._classify_as(
                RiskLevel.YELLOW,
                f"Operation affects multiple capsules or shared tools (Step {decision_step})",
                decision_step
            )

        decision_step = 5

        # Step 5: Check for GREEN criteria
        if (reversible and
            effort_hours < 4 and
            scope == "single_capsule" and
            not external_deps):
            return self._classify_as(
                RiskLevel.GREEN,
                f"Operation is reversible, <4h, single-capsule, no external deps (Step {decision_step})",
                decision_step
            )

        # Default to YELLOW if no clear classification
        return self._classify_as(
            RiskLevel.YELLOW,
            f"Operation does not meet GREEN criteria (Step {decision_step})",
            decision_step
        )

    def _classify_as(
        self,
        risk_level: RiskLevel,
        rationale: str,
        decision_step: int
    ) -> ClassificationResult:
        """Helper to create ClassificationResult"""
        level_config = self.risk_levels[risk_level.value]

        return ClassificationResult(
            risk_level=risk_level,
            rationale=rationale,
            approval_required=level_config['approval_required'],
            notification_type=level_config['notification'],
            rollback_strategy=level_config['rollback_strategy'],
            decision_step=decision_step
        )

    def check_workflow_allowed(self, workflow_name: str) -> bool:
        """
        Check if workflow is allowed based on emergency pause.

        Returns:
            True if workflow can execute, False if paused
        """
        pause_file = Path.home() / ".cache/catalyst/sdk_paused"
        if pause_file.exists():
            print(f"⚠️  SDK workflows paused - remove {pause_file} to resume")
            return False
        return True

    def log_decision(
        self,
        decision: WorkflowDecision,
        audit_file: Optional[Path] = None
    ):
        """
        Log workflow decision to audit file.

        Args:
            decision: WorkflowDecision to log
            audit_file: Path to audit log (defaults to registry/sdk_workflow_audit.log)
        """
        if audit_file is None:
            audit_file = Path("{{CATALYST_ROOT}}/registry/sdk_workflow_audit.log")

        audit_file.parent.mkdir(parents=True, exist_ok=True)

        import json
        audit_entry = {
            "timestamp": decision.timestamp.isoformat(),
            "workflow_name": decision.workflow_name,
            "operation": decision.operation,
            "risk_level": decision.classification.risk_level.value,
            "rationale": decision.classification.rationale,
            "decision_step": decision.classification.decision_step,
            "approval_required": decision.classification.approval_required,
            "approved": decision.approved,
            "executed": decision.executed,
            "notes": decision.notes
        }

        with open(audit_file, 'a') as f:
            f.write(json.dumps(audit_entry) + '\n')

    def get_approval_status(self, workflow_id: str) -> Optional[bool]:
        """
        Check approval status for pending workflow.

        Args:
            workflow_id: Workflow identifier

        Returns:
            True if approved, False if rejected, None if pending
        """
        # TODO: Implement approval tracking (could use MCP state)
        # For now, return None (pending)
        return None

    def format_notification(
        self,
        workflow_name: str,
        operation: str,
        classification: ClassificationResult
    ) -> Dict[str, str]:
        """
        Format notification message based on risk level.

        Args:
            workflow_name: Name of workflow
            operation: Operation description
            classification: Classification result

        Returns:
            Dictionary with title, message, and optional sound
        """
        if classification.risk_level == RiskLevel.RED:
            return {
                "title": "⚠️ SDK Workflow BLOCKED",
                "message": f"HIGH RISK: {workflow_name} attempted {operation}",
                "sound": "Basso",
                "critical": "true"
            }
        elif classification.risk_level == RiskLevel.YELLOW:
            return {
                "title": "SDK Workflow Pending Approval",
                "message": f"{workflow_name} requires review: {operation}",
                "sound": "",
                "critical": "false"
            }
        else:
            return {
                "title": "SDK Workflow Completed",
                "message": f"{workflow_name}: {operation}",
                "sound": "",
                "critical": "false"
            }


def main():
    """CLI for testing governance engine"""
    import argparse

    parser = argparse.ArgumentParser(description="Autonomous Governance Engine")
    parser.add_argument("operation", help="Operation description")
    parser.add_argument("--scope", default="single_capsule",
                       choices=["single_capsule", "cross_capsule", "system_wide"])
    parser.add_argument("--reversible", action="store_true", default=True)
    parser.add_argument("--effort-hours", type=float, default=1.0)
    parser.add_argument("--external-deps", action="store_true")
    parser.add_argument("--modifies-specs", action="store_true")
    parser.add_argument("--modifies-framework", action="store_true")
    parser.add_argument("--involves-deletion", action="store_true")
    parser.add_argument("--involves-credentials", action="store_true")
    parser.add_argument("--involves-spend", action="store_true")
    parser.add_argument("--workflow-name", help="Workflow name for override lookup")

    args = parser.parse_args()

    gov = GovernanceEngine()

    result = gov.classify_operation(
        operation=args.operation,
        scope=args.scope,
        reversible=args.reversible,
        effort_hours=args.effort_hours,
        external_deps=args.external_deps,
        modifies_specs=args.modifies_specs,
        modifies_framework=args.modifies_framework,
        involves_deletion=args.involves_deletion,
        involves_credentials=args.involves_credentials,
        involves_spend=args.involves_spend,
        workflow_name=args.workflow_name
    )

    # Print result
    print(f"\nOperation: {args.operation}")
    print(f"Risk Level: {result.risk_level.value.upper()}")
    print(f"Rationale: {result.rationale}")
    print(f"Approval Required: {result.approval_required}")
    print(f"Notification: {result.notification_type}")
    print(f"Rollback Strategy: {result.rollback_strategy}")

    if result.risk_level == RiskLevel.GREEN:
        print("\n✅ AUTO-EXECUTE APPROVED")
        sys.exit(0)
    elif result.risk_level == RiskLevel.YELLOW:
        print("\n⚠️  QUEUE FOR APPROVAL")
        sys.exit(1)
    else:
        print("\n🛑 BLOCKED - REQUIRES EXPLICIT APPROVAL")
        sys.exit(2)


if __name__ == "__main__":
    main()
