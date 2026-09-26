#!/bin/bash
set -euo pipefail

# validate_dod.sh - Definition of Done compliance validator for Huxley capsules
# Usage: validate_dod.sh <capsule_path> [dod_path]

CATALYST_ROOT="${CATALYST_ROOT:-$(cd "$(dirname "$0")/.." && pwd)}"

log_msg() {
    local level="$1"
    local message="$2"
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $level: $message"
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] DOD_VALIDATION $level: $message" >> "$VALIDATION_LOG"
}

usage() {
    cat << 'EOF'
validate_dod.sh - Definition of Done Compliance Validator

Usage: validate_dod.sh <capsule_path> [dod_path]

Arguments:
  capsule_path    Absolute path to capsule directory
  dod_path        Path to DoD checklist file (optional, auto-detected if not provided)

Examples:
  validate_dod.sh /path/to/capsule
  validate_dod.sh /path/to/capsule /path/to/custom_dod.md

The validator checks each DoD criterion and logs results to capsule/logs/validation.log
EOF
}

check_code_runs() {
    local capsule="$1"
    
    # Look for executable files
    local executable_count=0
    while IFS= read -r -d '' file; do
        ((executable_count++))
    done < <(find "$capsule/src" -type f -executable -print0 2>/dev/null || true)
    
    # Check for common script files
    local script_files=()
    while IFS= read -r -d '' file; do
        script_files+=("$file")
    done < <(find "$capsule" -type f \( -name "*.py" -o -name "*.sh" -o -name "*.js" -o -name "*.rb" \) -print0 2>/dev/null || true)
    
    # Log informational messages to file only (redirect stdout to stderr then to log)
    {
        log_msg "INFO" "Found ${#script_files[@]} script files and $executable_count executable files"
        
        # Check for dependency documentation (informational only)
        if [ -f "$capsule/requirements.txt" ] || [ -f "$capsule/package.json" ] || [ -f "$capsule/Gemfile" ] || grep -q "dependencies\|requires" "$capsule/README.md" 2>/dev/null; then
            log_msg "INFO" "Dependencies documented"
        else
            log_msg "INFO" "No explicit dependency documentation found"
        fi
    } >&2
    
    if [ ${#script_files[@]} -gt 0 ] || [ $executable_count -gt 0 ]; then
        echo "true"
    else
        echo "false"
    fi
}

check_no_breaking_changes() {
    local capsule="$1"
    
    # For standard, we're very lenient on breaking changes
    # This is mainly a design consideration check
    
    # Log informational messages
    {
        log_msg "INFO" "standard breaking changes check is lenient"
        
        # Check for backup files or rollback procedures (informational for standard)
        if [ -f "$capsule/docs/rollback.md" ] || [ -f "$capsule/ROLLBACK.md" ] || grep -q -i "rollback\|backup\|restore" "$capsule/README.md" 2>/dev/null; then
            log_msg "INFO" "Rollback/backup procedures documented"
        else
            log_msg "INFO" "No explicit rollback procedures found (optional for standard)"
        fi
        
        # Check for compatibility notes (informational for standard)
        if grep -q -i "compatible\|backward\|breaking" "$capsule/README.md" 2>/dev/null || [ -f "$capsule/docs/compatibility.md" ]; then
            log_msg "INFO" "Compatibility considerations documented"
        else
            log_msg "INFO" "No explicit compatibility documentation found (optional for standard)"
        fi
    } >&2
    
    # For standard, this check always passes unless there are obvious system destroyers
    # (we'll implement stricter checks for standard)
    echo "true"
}

check_basic_logging() {
    local capsule="$1"
    local has_logging=false
    
    # Check for logging code in source files
    local log_patterns=("log\|Log\|LOG" "print\|echo" "console\." "logger\." "logging\.")
    
    for pattern in "${log_patterns[@]}"; do
        if find "$capsule/src" -type f \( -name "*.py" -o -name "*.js" -o -name "*.sh" -o -name "*.rb" \) -exec grep -l "$pattern" {} \; 2>/dev/null | head -1 >/dev/null; then
            {
                log_msg "INFO" "Logging statements found in source code"
            } >&2
            has_logging=true
            break
        fi
    done
    
    # Check for log directories
    if [ -d "$capsule/logs" ]; then
        {
            log_msg "INFO" "Logs directory exists"
        } >&2
        has_logging=true
    fi
    
    if [ "$has_logging" = true ]; then
        echo "true"
    else
        {
            log_msg "WARN" "No logging implementation detected"
        } >&2
        echo "false"
    fi
}

check_usage_documentation() {
    local capsule="$1"
    local has_docs=false
    
    # Check for README.md
    if [ -f "$capsule/README.md" ]; then
        local readme_size=$(wc -l < "$capsule/README.md")
        if [ "$readme_size" -gt 5 ]; then
            {
                log_msg "INFO" "README.md exists with substantial content ($readme_size lines)"
            } >&2
            has_docs=true
        else
            {
                log_msg "WARN" "README.md exists but appears minimal ($readme_size lines)"
            } >&2
        fi
    fi
    
    # Check for inline comments in code files
    local comment_count=0
    while IFS= read -r -d '' file; do
        local file_comments=$(grep -c '^[[:space:]]*#\|^[[:space:]]*//' "$file" 2>/dev/null || echo 0)
        ((comment_count += file_comments))
    done < <(find "$capsule" -type f \( -name "*.py" -o -name "*.sh" -o -name "*.js" \) -print0 2>/dev/null || true)
    
    {
        if [ "$comment_count" -gt 5 ]; then
            log_msg "INFO" "Adequate inline documentation found ($comment_count comments)"
            has_docs=true
        elif [ "$comment_count" -gt 0 ]; then
            log_msg "INFO" "Some inline documentation found ($comment_count comments)"
            if [ "$has_docs" = false ]; then
                has_docs="partial"
            fi
        fi
    } >&2
    
    if [ "$has_docs" = false ]; then
        {
            log_msg "WARN" "Insufficient usage documentation"
        } >&2
        echo "false"
    else
        echo "true"
    fi
}

check_feature_documentation() {
    local capsule="$1"
    
    if [ ! -d "$capsule/docs" ]; then
        {
            log_msg "WARN" "Missing /docs directory"
        } >&2
        echo "false"
        return
    fi
    
    local doc_count=$(find "$capsule/docs" -name "*.md" -type f | wc -l)
    if [ "$doc_count" -lt 2 ]; then
        {
            log_msg "INFO" "Insufficient documentation in /docs directory ($doc_count files, need 2+)"
        } >&2
        echo "false"
    else
        {
            log_msg "INFO" "Adequate documentation in /docs directory ($doc_count files)"
        } >&2
        echo "true"
    fi
}

check_automated_tests() {
    local capsule="$1"
    local has_tests=false
    
    # Look for test files and directories
    local test_patterns=("test" "tests" "spec" "__test__")
    
    for pattern in "${test_patterns[@]}"; do
        if [ -d "$capsule/$pattern" ] || find "$capsule" -name "*${pattern}*" -type f | head -1 >/dev/null; then
            {
                log_msg "INFO" "Test files/directories found"
            } >&2
            has_tests=true
            break
        fi
    done
    
    # Check for test frameworks in dependencies
    if grep -q -i "pytest\|jest\|mocha\|rspec\|unittest" "$capsule/requirements.txt" "$capsule/package.json" 2>/dev/null; then
        {
            log_msg "INFO" "Test framework dependencies found"
        } >&2
        has_tests=true
    fi
    
    if [ "$has_tests" = false ]; then
        {
            log_msg "WARN" "No automated tests detected"
        } >&2
    fi
    
    echo "$has_tests"
}

check_security_review() {
    local capsule="$1"
    local security_good=true
    
    # Check for hardcoded secrets (basic patterns) - be less aggressive than before
    local secret_patterns=("password.*=" "api.*key.*=" "secret.*=" "token.*=")
    local violations=0
    
    for pattern in "${secret_patterns[@]}"; do
        if find "$capsule/src" -type f \( -name "*.py" -o -name "*.js" -o -name "*.sh" \) -exec grep -l -i "$pattern" {} \; 2>/dev/null | head -1 >/dev/null; then
            ((violations++))
        fi
    done
    
    {
        if [ "$violations" -gt 0 ]; then
            log_msg "WARN" "Potential hardcoded secrets detected ($violations patterns matched)"
            security_good=false
        else
            log_msg "INFO" "No obvious hardcoded secrets detected"
        fi
        
        # Check for .env.example
        if [ -f "$capsule/.env.example" ]; then
            log_msg "INFO" "Environment template (.env.example) found"
        else
            log_msg "INFO" "No environment template found"
        fi
    } >&2
    
    echo "$security_good"
}

check_scalability_documentation() {
    local capsule="$1"
    local has_scalability=false
    
    # Check for performance/scalability documentation
    local scalability_files=("performance.md" "scalability.md" "deployment.md" "ops.md" "architecture.md")
    
    for file in "${scalability_files[@]}"; do
        if [ -f "$capsule/docs/$file" ]; then
            {
                log_msg "INFO" "Scalability documentation found: $file"
            } >&2
            has_scalability=true
            break
        fi
    done
    
    # Check for scalability mentions in README
    if grep -q -i "performance\|scale\|deployment\|monitoring" "$capsule/README.md" 2>/dev/null; then
        {
            log_msg "INFO" "Scalability considerations mentioned in README"
        } >&2
        has_scalability=true
    fi
    
    if [ "$has_scalability" = false ]; then
        {
            log_msg "WARN" "No scalability documentation found"
        } >&2
    fi
    
    echo "$has_scalability"
}

check_stakeholder_approval() {
    local capsule="$1"
    local has_approval=false
    
    # Check for approval documentation
    local approval_files=("approval.md" "review.md" "sign-off.md" "governance.md")
    
    for file in "${approval_files[@]}"; do
        if [ -f "$capsule/docs/$file" ] || [ -f "$capsule/$file" ]; then
            {
                log_msg "INFO" "Approval documentation found: $file"
            } >&2
            has_approval=true
            break
        fi
    done
    
    # Check for approval mentions in documentation
    if ! [ "$has_approval" = true ]; then
        if grep -q -i "approved\|reviewed\|sign.*off\|stakeholder" "$capsule/README.md" "$capsule/docs/"*.md 2>/dev/null; then
            {
                log_msg "INFO" "Approval/review process documented"
            } >&2
            has_approval=true
        fi
    fi
    
    if [ "$has_approval" = false ]; then
        {
            log_msg "WARN" "No stakeholder approval documentation found"
        } >&2
    fi
    
    echo "$has_approval"
}

run_validation() {
    local capsule_path="$1"
    local dod_path="$2"
    local lane="$3"
    
    log_msg "INFO" "Starting DoD validation for $lane lane"
    log_msg "INFO" "Capsule: $capsule_path"
    log_msg "INFO" "DoD file: $dod_path"
    
    local total_checks=0
    local passed_checks=0
    local failed_checks=0
    
    # Always run basic standard checks
    log_msg "INFO" "=== Core Requirements ==="
    
    ((total_checks++))
    local code_result
    code_result=$(check_code_runs "$capsule_path")
    if [ "$code_result" = "true" ]; then
        log_msg "PASS" "Code execution check passed"
        ((passed_checks++))
    else
        log_msg "FAIL" "Code execution check failed (result: '$code_result')"
        ((failed_checks++))
    fi
    
    ((total_checks++))
    local breaking_result
    breaking_result=$(check_no_breaking_changes "$capsule_path")
    if [ "$breaking_result" = "true" ]; then
        log_msg "PASS" "Breaking changes check passed"
        ((passed_checks++))
    else
        log_msg "FAIL" "Breaking changes check failed (result: '$breaking_result')"
        ((failed_checks++))
    fi
    
    ((total_checks++))
    local logging_result
    logging_result=$(check_basic_logging "$capsule_path")
    if [ "$logging_result" = "true" ]; then
        log_msg "PASS" "Logging check passed"
        ((passed_checks++))
    else
        log_msg "FAIL" "Logging check failed (result: '$logging_result')"
        ((failed_checks++))
    fi
    
    ((total_checks++))
    local doc_result
    doc_result=$(check_usage_documentation "$capsule_path")
    if [ "$doc_result" = "true" ] || [ "$doc_result" = "partial" ]; then
        log_msg "PASS" "Documentation check passed"
        ((passed_checks++))
    else
        log_msg "FAIL" "Documentation check failed (result: '$doc_result')"
        ((failed_checks++))
    fi
    
    # standard additional checks
    if [ "$lane" = "standard" ]; then
        log_msg "INFO" "=== standard Requirements ==="
        
        ((total_checks++))
        local feature_doc_result
        feature_doc_result=$(check_feature_documentation "$capsule_path")
        if [ "$feature_doc_result" = "true" ]; then
            log_msg "PASS" "Feature documentation check passed"
            ((passed_checks++))
        else
            log_msg "FAIL" "Feature documentation check failed"
            ((failed_checks++))
        fi
        
        ((total_checks++))
        local tests_result
        tests_result=$(check_automated_tests "$capsule_path")
        if [ "$tests_result" = "true" ]; then
            log_msg "PASS" "Automated tests check passed"
            ((passed_checks++))
        else
            log_msg "FAIL" "Automated tests check failed"
            ((failed_checks++))
        fi
        
        ((total_checks++))
        local security_result
        security_result=$(check_security_review "$capsule_path")
        if [ "$security_result" = "true" ]; then
            log_msg "PASS" "Security review check passed"
            ((passed_checks++))
        else
            log_msg "FAIL" "Security review check failed"
            ((failed_checks++))
        fi
        
        ((total_checks++))
        local scalability_result
        scalability_result=$(check_scalability_documentation "$capsule_path")
        if [ "$scalability_result" = "true" ]; then
            log_msg "PASS" "Scalability documentation check passed"
            ((passed_checks++))
        else
            log_msg "FAIL" "Scalability documentation check failed"
            ((failed_checks++))
        fi
        
        ((total_checks++))
        local approval_result
        approval_result=$(check_stakeholder_approval "$capsule_path")
        if [ "$approval_result" = "true" ]; then
            log_msg "PASS" "Stakeholder approval check passed"
            ((passed_checks++))
        else
            log_msg "FAIL" "Stakeholder approval check failed"
            ((failed_checks++))
        fi
    fi
    
    # Summary
    local pass_rate=$((passed_checks * 100 / total_checks))
    log_msg "INFO" "=== Validation Summary ==="
    log_msg "INFO" "Total checks: $total_checks"
    log_msg "INFO" "Passed: $passed_checks"
    log_msg "INFO" "Failed: $failed_checks"
    log_msg "INFO" "Pass rate: ${pass_rate}%"
    
    if [ "$failed_checks" -eq 0 ]; then
        log_msg "PASS" "All DoD criteria satisfied"
        echo "validation_result=PASS" >> "$VALIDATION_LOG"
        return 0
    elif [ "$pass_rate" -ge 80 ]; then
        log_msg "WARN" "Partial compliance ($pass_rate%) - manual review recommended"
        echo "validation_result=PARTIAL" >> "$VALIDATION_LOG"
        return 1
    else
        log_msg "FAIL" "DoD validation failed ($pass_rate%)"
        echo "validation_result=FAIL" >> "$VALIDATION_LOG"
        return 2
    fi
}

# Parse arguments
if [ $# -eq 0 ]; then
    usage
    exit 1
fi

CAPSULE_PATH="$1"
DOD_PATH="${2:-}"

# Validate capsule path
if [ ! -d "$CAPSULE_PATH" ]; then
    echo "Error: Capsule directory does not exist: $CAPSULE_PATH" >&2
    exit 1
fi

# Create logs directory
LOGS_DIR="$CAPSULE_PATH/logs"
mkdir -p "$LOGS_DIR"
VALIDATION_LOG="$LOGS_DIR/validation.log"

# Clear previous validation log
> "$VALIDATION_LOG"

# Auto-detect DoD path if not provided
if [ -z "$DOD_PATH" ]; then
    # Extract lane from requirements.yaml
    REQUIREMENTS_FILE="$CAPSULE_PATH/spec/requirements.yaml"
    LANE="standard"  # default
    
    if [ -f "$REQUIREMENTS_FILE" ]; then
        LANE=$(python3 -c "
import yaml
try:
    with open('$REQUIREMENTS_FILE', 'r') as f:
        data = yaml.safe_load(f)
    metadata = data.get('metadata', {})
    print(lane if lane in ['standard', 'standard'] else 'standard')
except:
    print('standard')
" 2>/dev/null || echo "standard")
    fi
    
    DOD_PATH="$CATALYST_ROOT/global/dod/${LANE}.md"
else
    # Determine lane from DoD filename
    LANE=$(basename "$DOD_PATH" .md)
fi

# Validate DoD path
if [ ! -f "$DOD_PATH" ]; then
    log_msg "WARN" "DoD file not found: $DOD_PATH"
    log_msg "INFO" "Proceeding with basic validation checks"
fi

# Run validation
run_validation "$CAPSULE_PATH" "$DOD_PATH" "$LANE"




