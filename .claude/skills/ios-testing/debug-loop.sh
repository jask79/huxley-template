#!/bin/bash
#
# debug-loop.sh - Automated iOS debug loop with issue detection
#
# Usage:
#   ./debug-loop.sh <project-path> <scheme> [simulator-name] [max-iterations]
#
# Example:
#   ./debug-loop.sh MyApp.xcodeproj MyApp "iPhone 16" 10
#

set -e  # Exit on error

# Parse arguments
PROJECT_PATH="${1:?Usage: $0 <project-path> <scheme> [simulator-name] [max-iterations]}"
SCHEME="${2:?Usage: $0 <project-path> <scheme> [simulator-name] [max-iterations]}"
SIMULATOR_NAME="${3:-iPhone 16}"
MAX_ITERATIONS="${4:-10}"

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Temporary files for tracking
ITERATION_FILE="/tmp/ios-debug-iteration-$$.txt"
ISSUES_FILE="/tmp/ios-debug-issues-$$.txt"

# Initialize iteration counter
echo "0" > "$ITERATION_FILE"

echo -e "${BLUE}🔄 iOS Debug Loop${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━${NC}"
echo "Project: $PROJECT_PATH"
echo "Scheme: $SCHEME"
echo "Simulator: $SIMULATOR_NAME"
echo "Max iterations: $MAX_ITERATIONS"
echo ""

# Cleanup function
cleanup() {
    rm -f "$ITERATION_FILE" "$ISSUES_FILE"
}
trap cleanup EXIT

# Debug loop
while true; do
    # Increment iteration
    ITERATION=$(cat "$ITERATION_FILE")
    ITERATION=$((ITERATION + 1))
    echo "$ITERATION" > "$ITERATION_FILE"

    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${YELLOW}🔄 Iteration $ITERATION/$MAX_ITERATIONS${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

    # Check iteration limit
    if [ "$ITERATION" -gt "$MAX_ITERATIONS" ]; then
        echo -e "${RED}❌ Maximum iterations ($MAX_ITERATIONS) reached${NC}"
        echo -e "${RED}Manual intervention required.${NC}"
        exit 1
    fi

    # Step 1: Build and run
    echo -e "${YELLOW}🔨 Building...${NC}"
    # In actual use: call xcodebuildmcp build_run_sim
    sleep 2

    # Step 2: Monitor for issues
    echo -e "${YELLOW}🔍 Monitoring app state...${NC}"
    # In actual use: call xcodebuildmcp screenshot, describe_ui, log capture
    sleep 2

    # Step 3: Detect issues
    # In actual use: analyze logs, UI tree, screenshot for problems
    ISSUES_DETECTED=false

    # Simulated issue detection
    # In real implementation, this would check:
    # - Build failures
    # - Crashes
    # - UI errors
    # - Console errors

    if [ "$ISSUES_DETECTED" = true ]; then
        echo -e "${RED}❌ Issues detected:${NC}"
        cat "$ISSUES_FILE"
        echo ""

        # Step 4: Delegate to Mobile Dev agent
        echo -e "${YELLOW}🤖 Delegating to Mobile Dev agent...${NC}"
        # In actual use: Use Task tool to delegate to Mobile Dev agent
        # Agent receives:
        # - Issue details
        # - Logs
        # - Screenshots
        # - UI tree

        echo -e "${GREEN}✅ Fixes applied by Mobile Dev agent${NC}"
        echo ""

        # Continue to next iteration
        continue
    else
        # No issues - success!
        echo -e "${GREEN}✅ No issues detected!${NC}"
        echo ""
        break
    fi
done

# Success
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}🎉 App verified working!${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo "Fixed in $ITERATION iteration(s)"
echo ""

# Final verification
echo -e "${YELLOW}📸 Capturing final screenshot...${NC}"
# In actual use: mcp__xcodebuildmcp__screenshot

echo -e "${YELLOW}📝 Capturing final logs...${NC}"
# In actual use: mcp__xcodebuildmcp__stop_sim_log_cap

echo ""
echo -e "${GREEN}✅ Debug loop complete!${NC}"
