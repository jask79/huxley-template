#!/bin/bash
# PRD Validation Helper
# Validates PRD structure and provides helpful error messages

set -euo pipefail

PRD_FILE="$1"

if [ ! -f "$PRD_FILE" ]; then
    echo "❌ File not found: $PRD_FILE"
    exit 1
fi

# Check JSON validity
if ! jq empty "$PRD_FILE" 2>/dev/null; then
    echo "❌ Invalid JSON format"
    exit 1
fi

echo "✅ Valid JSON"

# Check required fields
FEATURE=$(jq -r '.feature // "MISSING"' "$PRD_FILE")
if [ "$FEATURE" = "MISSING" ]; then
    echo "❌ Missing required field: feature"
    exit 1
fi
echo "✅ Feature: $FEATURE"

# Check tasks array
TASK_COUNT=$(jq '.tasks | length' "$PRD_FILE")
if [ "$TASK_COUNT" -eq 0 ]; then
    echo "❌ No tasks defined"
    exit 1
fi
echo "✅ Tasks: $TASK_COUNT"

# Validate each task
for i in $(seq 0 $((TASK_COUNT - 1))); do
    TASK_ID=$(jq -r ".tasks[$i].id // \"MISSING\"" "$PRD_FILE")
    TASK_TITLE=$(jq -r ".tasks[$i].title // \"MISSING\"" "$PRD_FILE")
    TASK_SPECIALIST=$(jq -r ".tasks[$i].specialist // \"MISSING\"" "$PRD_FILE")
    TASK_PRIORITY=$(jq -r ".tasks[$i].priority // \"MISSING\"" "$PRD_FILE")
    
    if [ "$TASK_ID" = "MISSING" ]; then
        echo "❌ Task $i missing 'id' field"
        exit 1
    fi
    if [ "$TASK_TITLE" = "MISSING" ]; then
        echo "❌ Task $TASK_ID missing 'title' field"
        exit 1
    fi
    if [ "$TASK_SPECIALIST" = "MISSING" ]; then
        echo "❌ Task $TASK_ID missing 'specialist' field"
        exit 1
    fi
    if [ "$TASK_PRIORITY" = "MISSING" ]; then
        echo "❌ Task $TASK_ID missing 'priority' field"
        exit 1
    fi
    
    CRITERIA_COUNT=$(jq ".tasks[$i].acceptanceCriteria | length" "$PRD_FILE")
    if [ "$CRITERIA_COUNT" -eq 0 ]; then
        echo "❌ Task $TASK_ID has no acceptance criteria"
        exit 1
    fi
    
    echo "  ✅ $TASK_ID: $TASK_TITLE (specialist: $TASK_SPECIALIST, priority: $TASK_PRIORITY, criteria: $CRITERIA_COUNT)"
done

echo ""
echo "✅ PRD is valid and ready for feature loop"
