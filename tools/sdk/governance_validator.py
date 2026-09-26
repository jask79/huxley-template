#!/usr/bin/env python3
"""
SDK Governance Validator

Validates SDK workflows against governance framework requirements.
Integrates with existing governance engine to ensure workflows meet
quality, security, and operational standards.

Features:
- Workflow quality validation
- Risk assessment integration
- Performance standards enforcement
- Security requirements validation
- Operational readiness checks
- Compliance reporting

Usage:
    # Validate single workflow
    ./governance_validator.py validate daily_audit_workflow.py

    # Validate all SDK workflows
    ./governance_validator.py validate-all

    # Generate compliance report
    ./governance_validator.py report

    # Check workflow metrics against standards
    ./governance_validator.py check-metrics daily_audit
"""

import sys
import json
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, field
import argparse

# Add SDK tools to path
SDK_DIR = Path(__file__).parent
sys.path.insert(0, str(SDK_DIR))
sys.path.insert(0, str(SDK_DIR.parent))

from sdk_memory_bridge import SDKMemoryBridge
from view_sdk_events import SDKEventsViewer
from governance import GovernanceEngine, RiskLevel


@dataclass
class ValidationResult:
    """Result of governance validation"""
    workflow_name: str
    passed: bool
    risk_level: RiskLevel
    score: float  # 0-100
    issues: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


class GovernanceValidator:
    """
    Validates SDK workflows against governance standards.
    """

    # Quality standards
    MIN_SUCCESS_RATE = 80.0  # Minimum 80% success rate
    MAX_AVG_DURATION_MS = 300000  # Maximum 5 minutes average duration
    MIN_RUN_COUNT = 5  # Minimum runs required for statistical validation
    MAX_ERROR_RATE = 0.2  # Maximum 20% error rate

    def __init__(self):
        """Initialize validator"""
        self.governance = GovernanceEngine()
        self.memory = SDKMemoryBridge(workflow_id="governance_validator")
        self.viewer = SDKEventsViewer()

    def validate_workflow_file(self, workflow_path: Path) -> ValidationResult:
        """
        Validate workflow file structure and requirements.

        Args:
            workflow_path: Path to workflow file

        Returns:
            ValidationResult
        """
        workflow_name = workflow_path.stem
        issues = []
        warnings = []
        recommendations = []
        score = 100.0

        # Check file exists
        if not workflow_path.exists():
            issues.append(f"Workflow file not found: {workflow_path}")
            return ValidationResult(
                workflow_name=workflow_name,
                passed=False,
                risk_level=RiskLevel.RED,
                score=0.0,
                issues=issues
            )

        # Check file is executable or Python
        if not os.access(workflow_path, os.X_OK) and workflow_path.suffix != '.py':
            warnings.append("Workflow file is not executable")
            score -= 5

        # Check file size (detect suspiciously large files)
        file_size_kb = workflow_path.stat().st_size / 1024
        if file_size_kb > 500:  # Over 500KB
            warnings.append(f"Large workflow file: {file_size_kb:.1f}KB")
            recommendations.append("Consider refactoring into smaller modules")
            score -= 5

        # Try to read file and check for common patterns
        try:
            with open(workflow_path, 'r') as f:
                content = f.read()

                # Check for docstring
                if '"""' not in content and "'''" not in content:
                    warnings.append("Missing module docstring")
                    score -= 5

                # Check for main guard
                if "__main__" not in content:
                    warnings.append("Missing __main__ guard")
                    score -= 5

                # Check for error handling
                if "try:" not in content or "except" not in content:
                    warnings.append("Limited error handling detected")
                    recommendations.append("Add comprehensive try/except blocks")
                    score -= 10

                # Check for logging
                if "log" not in content.lower() and "print" not in content.lower():
                    warnings.append("No logging detected")
                    recommendations.append("Add logging for observability")
                    score -= 10

                # Check for governance integration
                if "governance" not in content.lower() and "RiskLevel" not in content:
                    warnings.append("No governance integration detected")
                    recommendations.append("Integrate with GovernanceEngine")
                    score -= 15

                # Check for memory bridge integration
                if "SDKMemoryBridge" not in content and "memory" not in content.lower():
                    warnings.append("No memory bridge integration detected")
                    recommendations.append("Integrate with SDKMemoryBridge for observability")
                    score -= 10

        except Exception as e:
            issues.append(f"Failed to read workflow file: {e}")
            score -= 20

        # Determine risk level and pass/fail
        if score >= 80:
            risk_level = RiskLevel.GREEN
            passed = True
        elif score >= 60:
            risk_level = RiskLevel.YELLOW
            passed = True
        else:
            risk_level = RiskLevel.RED
            passed = False

        return ValidationResult(
            workflow_name=workflow_name,
            passed=passed,
            risk_level=risk_level,
            score=score,
            issues=issues,
            warnings=warnings,
            recommendations=recommendations
        )

    def validate_workflow_metrics(self, workflow_name: str) -> ValidationResult:
        """
        Validate workflow execution metrics against standards.

        Args:
            workflow_name: Name of workflow

        Returns:
            ValidationResult
        """
        issues = []
        warnings = []
        recommendations = []
        score = 100.0

        # Get workflow metrics
        metrics = self.viewer.view_workflow_metrics(workflow_name)

        # Validate run count
        run_count = metrics.get('run_count', 0)
        if run_count < self.MIN_RUN_COUNT:
            warnings.append(f"Insufficient run history: {run_count} runs (minimum: {self.MIN_RUN_COUNT})")
            recommendations.append("Execute workflow more times to establish statistical baseline")
            score -= 15

        # Validate success rate
        success_rate = metrics.get('success_rate', 0.0)
        if success_rate < self.MIN_SUCCESS_RATE:
            issues.append(f"Low success rate: {success_rate}% (minimum: {self.MIN_SUCCESS_RATE}%)")
            score -= 30
        elif success_rate < 90:
            warnings.append(f"Moderate success rate: {success_rate}%")
            recommendations.append("Investigate and address failure patterns")
            score -= 10

        # Validate average duration
        avg_duration_ms = metrics.get('avg_duration_ms', 0.0)
        if avg_duration_ms > self.MAX_AVG_DURATION_MS:
            issues.append(f"Excessive duration: {avg_duration_ms:.0f}ms (maximum: {self.MAX_AVG_DURATION_MS}ms)")
            recommendations.append("Optimize workflow performance")
            score -= 20
        elif avg_duration_ms > self.MAX_AVG_DURATION_MS * 0.8:  # 80% of max
            warnings.append(f"High duration: {avg_duration_ms:.0f}ms")
            recommendations.append("Consider performance optimization")
            score -= 5

        # Check recent execution consistency
        history = self.viewer.view_workflow_history(workflow_name, days=7)
        if len(history) > 2:
            # Calculate error rate in recent history
            recent_errors = sum(
                1 for obs in history[-10:]
                if "fail" in obs.get("observation", "").lower() or
                   "error" in obs.get("observation", "").lower()
            )
            error_rate = recent_errors / min(len(history), 10)

            if error_rate > self.MAX_ERROR_RATE:
                issues.append(f"High recent error rate: {error_rate*100:.1f}%")
                score -= 25
            elif error_rate > 0.1:
                warnings.append(f"Moderate error rate: {error_rate*100:.1f}%")
                score -= 10

        # Determine risk level and pass/fail
        if score >= 80:
            risk_level = RiskLevel.GREEN
            passed = True
        elif score >= 60:
            risk_level = RiskLevel.YELLOW
            passed = True
        else:
            risk_level = RiskLevel.RED
            passed = False

        return ValidationResult(
            workflow_name=workflow_name,
            passed=passed,
            risk_level=risk_level,
            score=score,
            issues=issues,
            warnings=warnings,
            recommendations=recommendations
        )

    def validate_workflow_governance(self, workflow_name: str) -> ValidationResult:
        """
        Validate workflow against governance framework.

        Args:
            workflow_name: Name of workflow

        Returns:
            ValidationResult
        """
        issues = []
        warnings = []
        recommendations = []
        score = 100.0

        # Classify workflow with governance engine
        classification = self.governance.classify_operation(
            operation=f"Execute {workflow_name} workflow",
            workflow_name=workflow_name
        )

        # Check risk level
        if classification.risk_level == RiskLevel.RED:
            issues.append(f"RED risk classification: {classification.rationale}")
            score -= 50
        elif classification.risk_level == RiskLevel.YELLOW:
            warnings.append(f"YELLOW risk classification: {classification.rationale}")
            score -= 20

        # Check approval requirement
        if classification.approval_required:
            warnings.append("Workflow requires manual approval")
            recommendations.append("Consider refactoring to reduce risk level")
            score -= 10

        # Check safeguards (if attribute exists)
        if hasattr(classification, 'safeguards'):
            if not classification.safeguards:
                warnings.append("No safeguards recommended by governance engine")
                score -= 5
            else:
                # Verify safeguards are implemented
                # (This would require inspecting workflow code - simplified for now)
                recommendations.append(f"Verify safeguards: {', '.join(classification.safeguards)}")

        return ValidationResult(
            workflow_name=workflow_name,
            passed=(classification.risk_level != RiskLevel.RED),
            risk_level=classification.risk_level,
            score=score,
            issues=issues,
            warnings=warnings,
            recommendations=recommendations
        )

    def validate_workflow_complete(
        self,
        workflow_path: Optional[Path] = None,
        workflow_name: Optional[str] = None
    ) -> ValidationResult:
        """
        Complete workflow validation (file + metrics + governance).

        Args:
            workflow_path: Path to workflow file (optional)
            workflow_name: Name of workflow (optional)

        Returns:
            Combined ValidationResult
        """
        if workflow_path:
            workflow_name = workflow_path.stem

        if not workflow_name:
            raise ValueError("Must provide workflow_path or workflow_name")

        results = []

        # Validate file structure if path provided
        if workflow_path:
            file_result = self.validate_workflow_file(workflow_path)
            results.append(file_result)

        # Validate metrics
        try:
            metrics_result = self.validate_workflow_metrics(workflow_name)
            results.append(metrics_result)
        except Exception as e:
            print(f"Warning: Could not validate metrics: {e}", file=sys.stderr)

        # Validate governance
        try:
            governance_result = self.validate_workflow_governance(workflow_name)
            results.append(governance_result)
        except Exception as e:
            print(f"Warning: Could not validate governance: {e}", file=sys.stderr)

        # Combine results
        combined_score = sum(r.score for r in results) / len(results) if results else 0.0
        all_passed = all(r.passed for r in results)
        combined_issues = []
        combined_warnings = []
        combined_recommendations = []

        for r in results:
            combined_issues.extend(r.issues)
            combined_warnings.extend(r.warnings)
            combined_recommendations.extend(r.recommendations)

        # Determine overall risk level
        risk_levels = [r.risk_level for r in results]
        if RiskLevel.RED in risk_levels:
            combined_risk = RiskLevel.RED
        elif RiskLevel.YELLOW in risk_levels:
            combined_risk = RiskLevel.YELLOW
        else:
            combined_risk = RiskLevel.GREEN

        return ValidationResult(
            workflow_name=workflow_name,
            passed=all_passed,
            risk_level=combined_risk,
            score=combined_score,
            issues=combined_issues,
            warnings=combined_warnings,
            recommendations=combined_recommendations
        )

    def generate_compliance_report(self) -> Dict[str, Any]:
        """
        Generate compliance report for all workflows.

        Returns:
            Compliance report dictionary
        """
        workflows = self.viewer.list_workflows()
        results = []

        for workflow in workflows:
            try:
                result = self.validate_workflow_complete(workflow_name=workflow)
                results.append(result)
            except Exception as e:
                print(f"Warning: Could not validate {workflow}: {e}", file=sys.stderr)

        # Calculate summary statistics
        total_workflows = len(results)
        passed_workflows = sum(1 for r in results if r.passed)
        failed_workflows = total_workflows - passed_workflows

        green_workflows = sum(1 for r in results if r.risk_level == RiskLevel.GREEN)
        yellow_workflows = sum(1 for r in results if r.risk_level == RiskLevel.YELLOW)
        red_workflows = sum(1 for r in results if r.risk_level == RiskLevel.RED)

        avg_score = sum(r.score for r in results) / total_workflows if total_workflows > 0 else 0.0

        return {
            "timestamp": datetime.now().isoformat(),
            "summary": {
                "total_workflows": total_workflows,
                "passed": passed_workflows,
                "failed": failed_workflows,
                "average_score": round(avg_score, 1),
                "risk_distribution": {
                    "green": green_workflows,
                    "yellow": yellow_workflows,
                    "red": red_workflows
                }
            },
            "workflows": [
                {
                    "name": r.workflow_name,
                    "passed": r.passed,
                    "risk_level": r.risk_level.value,
                    "score": round(r.score, 1),
                    "issues_count": len(r.issues),
                    "warnings_count": len(r.warnings)
                }
                for r in results
            ],
            "compliance_status": "COMPLIANT" if failed_workflows == 0 else "NON_COMPLIANT"
        }

    def print_validation_result(self, result: ValidationResult):
        """Print validation result in human-readable format"""
        print("=" * 70)
        print(f"Workflow: {result.workflow_name}")
        print(f"Status: {'✓ PASSED' if result.passed else '✗ FAILED'}")
        print(f"Risk Level: {result.risk_level.value.upper()}")
        print(f"Score: {result.score:.1f}/100")
        print("=" * 70)

        if result.issues:
            print("\n❌ Issues:")
            for issue in result.issues:
                print(f"  • {issue}")

        if result.warnings:
            print("\n⚠️  Warnings:")
            for warning in result.warnings:
                print(f"  • {warning}")

        if result.recommendations:
            print("\n💡 Recommendations:")
            for rec in result.recommendations:
                print(f"  • {rec}")

        print("=" * 70)


def main():
    """CLI entry point"""
    parser = argparse.ArgumentParser(description="SDK Governance Validator")

    subparsers = parser.add_subparsers(dest="command", help="Command to execute")

    # Validate command
    validate_parser = subparsers.add_parser("validate", help="Validate single workflow")
    validate_parser.add_argument("workflow", help="Workflow file path or name")

    # Validate-all command
    subparsers.add_parser("validate-all", help="Validate all workflows")

    # Report command
    subparsers.add_parser("report", help="Generate compliance report")

    # Check-metrics command
    check_metrics_parser = subparsers.add_parser("check-metrics", help="Check workflow metrics")
    check_metrics_parser.add_argument("workflow_name", help="Workflow name")

    args = parser.parse_args()

    validator = GovernanceValidator()

    if args.command == "validate":
        # Check if workflow is a file path or name
        workflow_path = Path(args.workflow)
        if workflow_path.exists():
            result = validator.validate_workflow_complete(workflow_path=workflow_path)
        else:
            result = validator.validate_workflow_complete(workflow_name=args.workflow)

        validator.print_validation_result(result)
        sys.exit(0 if result.passed else 1)

    elif args.command == "validate-all":
        workflows = validator.viewer.list_workflows()
        results = []

        print(f"Validating {len(workflows)} workflows...\n")

        for workflow in workflows:
            result = validator.validate_workflow_complete(workflow_name=workflow)
            results.append(result)
            validator.print_validation_result(result)
            print()

        # Summary
        passed = sum(1 for r in results if r.passed)
        failed = len(results) - passed

        print("\n" + "=" * 70)
        print("Validation Summary")
        print("=" * 70)
        print(f"Total: {len(results)}")
        print(f"Passed: {passed}")
        print(f"Failed: {failed}")
        print("=" * 70)

        sys.exit(0 if failed == 0 else 1)

    elif args.command == "report":
        report = validator.generate_compliance_report()

        print("=" * 70)
        print("Governance Compliance Report")
        print("=" * 70)
        print(f"Generated: {report['timestamp']}")
        print(f"Status: {report['compliance_status']}")
        print()
        print("Summary:")
        print(f"  Total Workflows: {report['summary']['total_workflows']}")
        print(f"  Passed: {report['summary']['passed']}")
        print(f"  Failed: {report['summary']['failed']}")
        print(f"  Average Score: {report['summary']['average_score']}/100")
        print()
        print("Risk Distribution:")
        print(f"  🟢 GREEN: {report['summary']['risk_distribution']['green']}")
        print(f"  🟡 YELLOW: {report['summary']['risk_distribution']['yellow']}")
        print(f"  🔴 RED: {report['summary']['risk_distribution']['red']}")
        print()
        print("Workflows:")
        for wf in report['workflows']:
            status = "✓" if wf['passed'] else "✗"
            print(f"  {status} {wf['name']} - {wf['risk_level'].upper()} ({wf['score']}/100)")
        print("=" * 70)

        # Write JSON report
        report_file = Path("{{CATALYST_ROOT}}/registry/governance/compliance_report.json")
        report_file.parent.mkdir(parents=True, exist_ok=True)
        with open(report_file, 'w') as f:
            json.dump(report, f, indent=2)

        print(f"\nReport saved to: {report_file}")

    elif args.command == "check-metrics":
        result = validator.validate_workflow_metrics(args.workflow_name)
        validator.print_validation_result(result)
        sys.exit(0 if result.passed else 1)

    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    import os
    main()
