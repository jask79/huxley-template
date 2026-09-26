#!/bin/bash
set -e

# test_agent_discovery.sh - Test Claude Code agent discovery system
# Validates that our enhanced find_prompt function correctly discovers agents

CATALYST_ROOT="${CATALYST_ROOT:-$(cd "$(dirname "$0")/.." && pwd)}"
cd "$CATALYST_ROOT"

# Source the find_prompt function from trigger_planner.sh
source_find_prompt() {
    # Extract just the find_prompt function
    sed -n '/^find_prompt() {/,/^}/p' tools/trigger_planner.sh > /tmp/find_prompt_func.sh
    source /tmp/find_prompt_func.sh
    rm /tmp/find_prompt_func.sh
}

source_find_prompt

echo "=== Agent Discovery Test ==="
echo

# Test cases: role, branch, lane, expected_agent
test_cases=(
    "security-analyst||standard|security-analyst.standard.md"
    "frontend-specialist|web||frontend-specialist.web.md"
    "automation-specialist|||automation-specialist.md"
    "shopify-specialist|web||shopify-specialist.md"
    "ios-specialist|mobile||ios-specialist.md"
    "macos-specialist|desktop||macos-specialist.md"
    "data-analyst|analytics||data-analyst.md"
    "backend-architect|backend||backend-architect.md"
    "devops-troubleshooter|ops||devops-troubleshooter.md"
    "deployment-engineer|ops||deployment-engineer.md"
    "test-automator|quality||test-automator.md"
    "security-auditor|security|standard|security-auditor.md"
    "python-pro|backend||python-pro.md"
    "javascript-pro|frontend||javascript-pro.md"
    "nonexistent|||NOT_FOUND"
)

test_capsule="$CATALYST_ROOT"  # Use Huxley root as test capsule
pass_count=0
total_count=${#test_cases[@]}

for test_case in "${test_cases[@]}"; do
    IFS='|' read -r role branch lane expected <<< "$test_case"
    
    printf "Testing: role=%-20s branch=%-10s lane=%-10s " "$role" "$branch" "$lane"
    
    if result=$(find_prompt "$role" "$branch" "$lane" "$test_capsule" 2>/dev/null); then
        found_agent=$(basename "$result")
        if [ "$expected" = "NOT_FOUND" ]; then
            echo "❌ FAIL (expected not found, but got $found_agent)"
        elif [ "$found_agent" = "$expected" ]; then
            echo "✅ PASS ($found_agent)"
            ((pass_count++))
        else
            echo "❌ FAIL (expected $expected, got $found_agent)"
        fi
    else
        if [ "$expected" = "NOT_FOUND" ]; then
            echo "✅ PASS (correctly not found)"
            ((pass_count++))
        else
            echo "❌ FAIL (expected $expected, but not found)"
        fi
    fi
done

echo
echo "=== Results ==="
echo "Passed: $pass_count/$total_count tests"

if [ "$pass_count" -eq "$total_count" ]; then
    echo "🎉 All agent discovery tests passed!"
    exit 0
else
    echo "❌ Some tests failed"
    exit 1
fi

