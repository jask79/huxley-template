#!/bin/bash
# ${CATALYST_ROOT:-{{CATALYST_ROOT}}}/tools/standardize_capsules.sh
# Fix capsule structure issues by creating missing files

set -euo pipefail

readonly CATALYST_ROOT="${CATALYST_ROOT:-{{CATALYST_ROOT}}}"
readonly CAPSULES_DIR="$CATALYST_ROOT/capsules"
readonly TEST_CAPSULES_DIR="$CATALYST_ROOT/testing/capsules"

create_capsule_json() {
    local capsule_path="$1"
    local capsule_name="$(basename "$capsule_path")"
    local capsule_json="$capsule_path/capsule.json"
    local is_test="$2"
    
    # Skip if already exists
    if [[ -f "$capsule_json" ]]; then
        return 0
    fi
    
    echo "  Creating capsule.json for: $capsule_name"
    
    # Determine lane from requirements.yaml if available
    local lane="standard"
    local requirements_file="$capsule_path/spec/requirements.yaml"
    if [[ -f "$requirements_file" ]]; then
        local yaml_lane=$(grep "^lane:" "$requirements_file" 2>/dev/null | cut -d' ' -f2 | tr -d '"' | tr -d ' ' || echo "")
        if [[ -n "$yaml_lane" ]]; then
            lane="$yaml_lane"
        fi
    fi
    
    # Determine type based on capsule characteristics
    local type="automation"
    if [[ "$capsule_name" =~ test ]]; then
        type="test"
    elif [[ "$capsule_name" =~ system ]]; then
        type="system-agent"
    elif [[ "$capsule_name" =~ mobile ]]; then
        type="mobile-app"
    elif [[ "$capsule_name" =~ web ]]; then
        type="web-app"
    fi
    
    # Create capsule.json
    cat > "$capsule_json" <<EOF
{
  "name": "$capsule_name",
  "version": "1.0.0",
  "type": "$type",
  "description": "Auto-generated capsule configuration - update as needed",
  "created": "$(date '+%Y-%m-%d')",
  "owner": "Huxley",
  "status": "$([ "$is_test" = "true" ] && echo "test" || echo "active")",
  "dependencies": {
    "claude": ">=3.0",
    "bash": ">=4.0"
  },
  "outputs": {
    "logs": "runs/logs/",
    "data": "runs/data/"
  }
}
EOF
    
    echo "    ✅ Created $capsule_json"
}

create_requirements_yaml() {
    local capsule_path="$1"
    local capsule_name="$(basename "$capsule_path")"
    local requirements_file="$capsule_path/spec/requirements.yaml"
    
    # Create spec directory if needed
    mkdir -p "$capsule_path/spec"
    
    # Skip if already exists
    if [[ -f "$requirements_file" ]]; then
        return 0
    fi
    
    echo "  Creating requirements.yaml for: $capsule_name"
    
    # Determine lane from capsule.json if available
    local lane="standard"
    local capsule_json="$capsule_path/capsule.json"
    if [[ -f "$capsule_json" ]] && command -v jq >/dev/null 2>&1; then
        local json_lane=$(jq -r '.lane // ""' "$capsule_json" 2>/dev/null)
        if [[ -n "$json_lane" ]]; then
            lane="$json_lane"
        fi
    fi
    
    cat > "$requirements_file" <<EOF
lane: $lane
priority: normal
schedule: manual

description: |
  Auto-generated requirements for $capsule_name capsule.
  Update this description with specific requirements and goals.

goals:
  - Define specific goals for this capsule
  - Update goals based on capsule purpose
  - Ensure goals are measurable and achievable

success_criteria:
  - Define measurable success criteria
  - Include performance benchmarks if applicable
  - Specify quality thresholds

constraints:
  - List technical constraints
  - Include resource limitations
  - Note any platform-specific requirements

integration_points:
  - Define how this capsule integrates with Huxley
  - Specify input/output interfaces
  - Note dependencies on other capsules
EOF
    
    echo "    ✅ Created $requirements_file"
}

create_missing_directories() {
    local capsule_path="$1"
    local capsule_name="$(basename "$capsule_path")"
    
    local expected_dirs=("spec" "src" "runs" "runs/logs" "runs/data")
    local created_dirs=()
    
    for dir in "${expected_dirs[@]}"; do
        if [[ ! -d "$capsule_path/$dir" ]]; then
            mkdir -p "$capsule_path/$dir"
            created_dirs+=("$dir")
        fi
    done
    
    if [[ ${#created_dirs[@]} -gt 0 ]]; then
        echo "  Created directories for $capsule_name: ${created_dirs[*]}"
    fi
}

standardize_capsule() {
    local capsule_path="$1"
    local is_test="$2"
    local capsule_name="$(basename "$capsule_path")"
    
    echo "🔧 Standardizing: $capsule_name"
    
    # Create missing directories first
    create_missing_directories "$capsule_path"
    
    # Create capsule.json if missing
    create_capsule_json "$capsule_path" "$is_test"
    
    # Create requirements.yaml if missing
    create_requirements_yaml "$capsule_path"
    
    echo "   ✅ Standardization complete"
}

echo "🛠️  Huxley Capsule Standardization"
echo "===================================="

# Standardize production capsules
if [[ -d "$CAPSULES_DIR" ]]; then
    echo ""
    echo "🏭 Production Capsules:"
    for capsule_dir in "$CAPSULES_DIR"/*; do
        if [[ -d "$capsule_dir" ]]; then
            standardize_capsule "$capsule_dir" "false"
        fi
    done
else
    echo "❌ Production capsules directory not found: $CAPSULES_DIR"
fi

# Standardize test capsules
if [[ -d "$TEST_CAPSULES_DIR" ]]; then
    echo ""
    echo "🧪 Test Capsules:"
    for capsule_dir in "$TEST_CAPSULES_DIR"/*; do
        if [[ -d "$capsule_dir" ]]; then
            standardize_capsule "$capsule_dir" "true"
        fi
    done
else
    echo "⚠️  Test capsules directory not found: $TEST_CAPSULES_DIR"
fi

echo ""
echo "✅ Capsule standardization completed"
echo ""
echo "🧪 Running validation to verify fixes..."
echo ""

# Run validation to check results
if [[ -x "$CATALYST_ROOT/tools/validate_capsules.sh" ]]; then
    "$CATALYST_ROOT/tools/validate_capsules.sh"
else
    echo "⚠️  Validation script not found"
fi

