#!/usr/bin/env python3
"""
Test Suite for Autonomous Governance Engine

Validates classification logic for GREEN/YELLOW/RED risk levels.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from governance import GovernanceEngine, RiskLevel


def test_green_operations():
    """Test operations that should be GREEN (auto-execute)"""
    print("→ Testing GREEN operations...")

    gov = GovernanceEngine()

    # Test 1: Update CLAUDE.md
    result = gov.classify_operation(
        operation="Update CLAUDE.md with learned patterns",
        scope="single_capsule",
        reversible=True,
        effort_hours=0.5,
        external_deps=False
    )
    assert result.risk_level == RiskLevel.GREEN, "CLAUDE.md update should be GREEN"
    assert not result.approval_required, "GREEN should not require approval"

    # Test 2: Daily audit workflow override
    result = gov.classify_operation(
        operation="Run daily audit",
        workflow_name="daily_audit"
    )
    assert result.risk_level == RiskLevel.GREEN, "daily_audit workflow should be GREEN"

    # Test 3: Context update
    result = gov.classify_operation(
        operation="Add session notes to context/",
        scope="single_capsule",
        reversible=True
    )
    assert result.risk_level == RiskLevel.GREEN, "Context updates should be GREEN"

    print("✓ All GREEN tests passed")


def test_yellow_operations():
    """Test operations that should be YELLOW (queue and notify)"""
    print("\n→ Testing YELLOW operations...")

    gov = GovernanceEngine()

    # Test 1: Spec modification
    result = gov.classify_operation(
        operation="Update specs/current.yaml",
        modifies_specs=True
    )
    assert result.risk_level == RiskLevel.YELLOW, "Spec modifications should be YELLOW"
    assert result.approval_required, "YELLOW should require approval"

    # Test 2: Cross-capsule change
    result = gov.classify_operation(
        operation="Update shared utility",
        scope="cross_capsule"
    )
    assert result.risk_level == RiskLevel.YELLOW, "Cross-capsule should be YELLOW"

    # Test 3: Product.yaml modification
    result = gov.classify_operation(
        operation="Update product roadmap",
        modifies_specs=True
    )
    assert result.risk_level == RiskLevel.YELLOW, "Product.yaml changes should be YELLOW"

    print("✓ All YELLOW tests passed")


def test_red_operations():
    """Test operations that should be RED (blocked)"""
    print("\n→ Testing RED operations...")

    gov = GovernanceEngine()

    # Test 1: Deletion
    result = gov.classify_operation(
        operation="Delete capsule files",
        involves_deletion=True
    )
    assert result.risk_level == RiskLevel.RED, "Deletions should be RED"
    assert result.approval_required, "RED should require approval"

    # Test 2: Credential access
    result = gov.classify_operation(
        operation="Read .env file",
        involves_credentials=True
    )
    assert result.risk_level == RiskLevel.RED, "Credential access should be RED"

    # Test 3: External spend
    result = gov.classify_operation(
        operation="Purchase API credits",
        involves_spend=True
    )
    assert result.risk_level == RiskLevel.RED, "External spend should be RED"

    # Test 4: Framework modification
    result = gov.classify_operation(
        operation="Modify CLAUDE.md governance rules",
        modifies_framework=True
    )
    assert result.risk_level == RiskLevel.RED, "Framework changes should be RED"

    # Test 5: System-wide scope
    result = gov.classify_operation(
        operation="Update Huxley global config",
        scope="system_wide"
    )
    assert result.risk_level == RiskLevel.RED, "System-wide changes should be RED"

    print("✓ All RED tests passed")


def test_decision_tree_steps():
    """Test decision tree step-by-step progression"""
    print("\n→ Testing decision tree steps...")

    gov = GovernanceEngine()

    # Step 1: Deletion/spend/credentials check
    result = gov.classify_operation(
        operation="Test deletion",
        involves_deletion=True
    )
    assert result.decision_step == 1, "Deletion should stop at step 1"
    assert result.risk_level == RiskLevel.RED

    # Step 2: Framework/production check (only if step 1 passes)
    result = gov.classify_operation(
        operation="Test framework modification",
        modifies_framework=True,
        involves_deletion=False  # Skip step 1
    )
    assert result.decision_step == 2, "Framework mod should stop at step 2"
    assert result.risk_level == RiskLevel.RED

    # Step 3: Spec modification check (only if steps 1-2 pass)
    result = gov.classify_operation(
        operation="Test spec modification",
        modifies_specs=True,
        involves_deletion=False,
        modifies_framework=False
    )
    assert result.decision_step == 3, "Spec mod should stop at step 3"
    assert result.risk_level == RiskLevel.YELLOW

    # Step 4: Cross-capsule check
    result = gov.classify_operation(
        operation="Test cross-capsule",
        scope="cross_capsule",
        modifies_specs=False
    )
    assert result.decision_step == 4, "Cross-capsule should stop at step 4"
    assert result.risk_level == RiskLevel.YELLOW

    # Step 5: GREEN criteria check
    result = gov.classify_operation(
        operation="Test GREEN criteria",
        scope="single_capsule",
        reversible=True,
        effort_hours=2.0,
        external_deps=False
    )
    assert result.decision_step == 5, "GREEN check should be at step 5"
    assert result.risk_level == RiskLevel.GREEN

    print("✓ All decision tree tests passed")


def test_notification_formatting():
    """Test notification message formatting"""
    print("\n→ Testing notification formatting...")

    gov = GovernanceEngine()

    # Test GREEN notification
    result = gov.classify_operation(
        operation="Update context",
        scope="single_capsule"
    )
    notification = gov.format_notification("test_workflow", "Update context", result)
    assert "Completed" in notification['title'], "GREEN should show completion"

    # Test YELLOW notification
    result = gov.classify_operation(
        operation="Update specs",
        modifies_specs=True
    )
    notification = gov.format_notification("test_workflow", "Update specs", result)
    assert "Pending Approval" in notification['title'], "YELLOW should show pending"

    # Test RED notification
    result = gov.classify_operation(
        operation="Delete files",
        involves_deletion=True
    )
    notification = gov.format_notification("test_workflow", "Delete files", result)
    assert "BLOCKED" in notification['title'], "RED should show blocked"
    assert notification['sound'] == "Basso", "RED should include sound alert"

    print("✓ All notification tests passed")


def test_workflow_overrides():
    """Test workflow-specific risk level overrides"""
    print("\n→ Testing workflow overrides...")

    gov = GovernanceEngine()

    # Test daily_audit override
    result = gov.classify_operation(
        operation="Any operation",
        workflow_name="daily_audit"
    )
    assert result.risk_level == RiskLevel.GREEN, "daily_audit should override to GREEN"

    # Test spec_validation override
    result = gov.classify_operation(
        operation="Any operation",
        workflow_name="spec_validation"
    )
    assert result.risk_level == RiskLevel.GREEN, "spec_validation should be GREEN"

    # Test production_deploy override
    result = gov.classify_operation(
        operation="Any operation",
        workflow_name="production_deploy"
    )
    assert result.risk_level == RiskLevel.RED, "production_deploy should be RED"

    print("✓ All workflow override tests passed")


def main():
    """Run all governance tests"""
    print("=" * 60)
    print("Autonomous Governance Engine - Test Suite")
    print("=" * 60)

    try:
        test_green_operations()
        test_yellow_operations()
        test_red_operations()
        test_decision_tree_steps()
        test_notification_formatting()
        test_workflow_overrides()

        print("\n" + "=" * 60)
        print("✓ ALL GOVERNANCE TESTS PASSED")
        print("=" * 60)
        return 0

    except AssertionError as e:
        print(f"\n✗ Test failed: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"\n✗ Unexpected error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
