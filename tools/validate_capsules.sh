#!/bin/bash
# ${CATALYST_ROOT:-{{CATALYST_ROOT}}}/tools/validate_capsules.sh
# Validate capsule structure and ensure consistent capsule.json/requirements.yaml

set -euo pipefail

readonly CATALYST_ROOT="${CATALYST_ROOT:-{{CATALYST_ROOT}}}"
readonly CAPSULES_DIR="$CATALYST_ROOT/capsules"
readonly TEST_CAPSULES_DIR="$CATALYST_ROOT/testing/capsules"
readonly TIMESTAMP=$(date '+%Y%m%d_%H%M%S')
readonly VALIDATION_LOG="$CATALYST_ROOT/registry/validation-$TIMESTAMP.json"

# Initialize validation results
TOTAL_CAPSULES=0
VALID_CAPSULES=0
ISSUES_FOUND=0
VALIDATION_RESULTS='{"timestamp":"'$(date -u +"%Y-%m-%dT%H:%M:%SZ")'","capsules":[],"summary":{}}'

echo "🧪 Huxley Capsule Structure Validation"
echo "======================================"

# Validation functions
validate_capsule_json() {
    local capsule_path="$1"
    local capsule_name="$(basename "$capsule_path")"
    local capsule_json="$capsule_path/capsule.json"
    local issues=()
    
    if [[ ! -f "$capsule_json" ]]; then
        issues+=("Missing capsule.json")
        return 1
    fi
    
    # Validate JSON syntax
    if ! jq empty "$capsule_json" 2>/dev/null; then
        issues+=("Invalid JSON syntax in capsule.json")
        return 1
    fi
    
    # Check required fields
    for field in "${required_fields[@]}"; do
        if ! jq -e "has(\"$field\")" "$capsule_json" >/dev/null 2>&1; then
            issues+=("Missing required field: $field")
        fi
    done
    
    # Validate lane value
    local lane=$(jq -r '.lane // "unknown"' "$capsule_json" 2>/dev/null)
    if [[ "$lane" != "standard" && "$lane" != "standard" ]]; then
        issues+=("Invalid lane value: $lane (must be standard or standard)")
    fi
    
    # Validate name matches directory
    local json_name=$(jq -r '.name // ""' "$capsule_json" 2>/dev/null)
    if [[ "$json_name" != "$capsule_name" ]]; then
        issues+=("Name mismatch: directory=$capsule_name, json=$json_name")
    fi
    
    # Store issues for this capsule
    if [[ ${#issues[@]} -gt 0 ]]; then
        printf -v issues_str '"%s",' "${issues[@]}"
        issues_str="[${issues_str%,}]"
        echo "   Issues: ${issues[*]}"
        return 1
    fi
    
    return 0
}

validate_requirements_yaml() {
    local capsule_path="$1"
    local requirements_yaml="$capsule_path/spec/requirements.yaml"
    local issues=()
    
    if [[ ! -f "$requirements_yaml" ]]; then
        issues+=("Missing spec/requirements.yaml")
        return 1
    fi
    
    # Check if YAML is parseable (using python if available)
    if command -v python3 >/dev/null 2>&1; then
        if ! python3 -c "import yaml; yaml.safe_load(open('$requirements_yaml'))" 2>/dev/null; then
            issues+=("Invalid YAML syntax in requirements.yaml")
            return 1
        fi
    fi
    
    # Check for key sections (basic validation)
    for section in "${key_sections[@]}"; do
        if ! grep -q "^$section:" "$requirements_yaml" 2>/dev/null; then
            issues+=("Missing required section: $section")
        fi
    done
    
    # Validate lane consistency
    if [[ -f "$capsule_path/capsule.json" ]]; then
        local json_lane=$(jq -r '.lane // ""' "$capsule_path/capsule.json" 2>/dev/null)
        local yaml_lane=$(grep "^lane:" "$requirements_yaml" 2>/dev/null | cut -d' ' -f2 | tr -d '"' | tr -d ' ')
        if [[ -n "$json_lane" && -n "$yaml_lane" && "$json_lane" != "$yaml_lane" ]]; then
            issues+=("Lane mismatch: capsule.json=$json_lane, requirements.yaml=$yaml_lane")
        fi
    fi
    
    if [[ ${#issues[@]} -gt 0 ]]; then
        echo "   Issues: ${issues[*]}"
        return 1
    fi
    
    return 0
}

validate_directory_structure() {
    local capsule_path="$1"
    local issues=()
    
    # Check for expected directories
    local expected_dirs=("spec" "src" "runs")
    for dir in "${expected_dirs[@]}"; do
        if [[ ! -d "$capsule_path/$dir" ]]; then
            issues+=("Missing directory: $dir")
        fi
    done
    
    if [[ ${#issues[@]} -gt 0 ]]; then
        echo "   Issues: ${issues[*]}"
        return 1
    fi
    
    return 0
}

# Main validation function
validate_capsule() {
    local capsule_path="$1"
    local capsule_name="$(basename "$capsule_path")"
    local is_production="$2"
    
    echo "📦 Validating: $capsule_name $([ "$is_production" = "true" ] && echo "(production)" || echo "(test)")"
    
    local has_issues=false
    local capsule_issues=()
    
    # Validate capsule.json
    if ! validate_capsule_json "$capsule_path"; then
        has_issues=true
        ISSUES_FOUND=$((ISSUES_FOUND + 1))
    fi
    
    # Validate requirements.yaml
    if ! validate_requirements_yaml "$capsule_path"; then
        has_issues=true
        ISSUES_FOUND=$((ISSUES_FOUND + 1))
    fi
    
    # Validate directory structure
    if ! validate_directory_structure "$capsule_path"; then
        has_issues=true
        ISSUES_FOUND=$((ISSUES_FOUND + 1))
    fi
    
    if [[ "$has_issues" = false ]]; then
        echo "   ✅ Valid capsule structure"
        VALID_CAPSULES=$((VALID_CAPSULES + 1))
    else
        echo "   ❌ Issues found"
    fi
    
    TOTAL_CAPSULES=$((TOTAL_CAPSULES + 1))
}

# Create registry directory if it doesn't exist
mkdir -p "$CATALYST_ROOT/registry"

# Validate production capsules
if [[ -d "$CAPSULES_DIR" ]]; then
    echo ""
    echo "🏭 Production Capsules:"
    for capsule_dir in "$CAPSULES_DIR"/*; do
        if [[ -d "$capsule_dir" ]]; then
            validate_capsule "$capsule_dir" "true"
        fi
    done
else
    echo "❌ Production capsules directory not found: $CAPSULES_DIR"
fi

# Validate test capsules
if [[ -d "$TEST_CAPSULES_DIR" ]]; then
    echo ""
    echo "🧪 Test Capsules:"
    for capsule_dir in "$TEST_CAPSULES_DIR"/*; do
        if [[ -d "$capsule_dir" ]]; then
            validate_capsule "$capsule_dir" "false"
        fi
    done
else
    echo "⚠️  Test capsules directory not found: $TEST_CAPSULES_DIR"
fi

# Generate summary
echo ""
echo "📊 Validation Summary:"
echo "   Total capsules: $TOTAL_CAPSULES"
echo "   Valid capsules: $VALID_CAPSULES"
echo "   Issues found: $ISSUES_FOUND"
echo "   Success rate: $(( VALID_CAPSULES * 100 / TOTAL_CAPSULES ))%"

# Write validation log
cat > "$VALIDATION_LOG" <<EOF
{
  "timestamp": "$(date -u +"%Y-%m-%dT%H:%M:%SZ")",
  "total_capsules": $TOTAL_CAPSULES,
  "valid_capsules": $VALID_CAPSULES,
  "issues_found": $ISSUES_FOUND,
  "success_rate": $(( VALID_CAPSULES * 100 / TOTAL_CAPSULES )),
  "production_capsules_dir": "$CAPSULES_DIR",
  "test_capsules_dir": "$TEST_CAPSULES_DIR"
}
EOF

echo "   Log: $VALIDATION_LOG"

# Exit with error code if issues found
if [[ $ISSUES_FOUND -gt 0 ]]; then
    echo ""
    echo "❌ Validation completed with issues"
    exit 1
else
    echo ""
    echo "✅ All capsules passed validation"
    exit 0
fi

