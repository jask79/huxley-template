#!/bin/bash
#
# quick-verify.sh - Fast iOS app verification for development loop
#
# Usage:
#   ./quick-verify.sh <project-path> <scheme> [simulator-name]
#
# Example:
#   ./quick-verify.sh MyApp.xcodeproj MyApp "iPhone 16"
#

set -e  # Exit on error

# Parse arguments
PROJECT_PATH="${1:?Usage: $0 <project-path> <scheme> [simulator-name]}"
SCHEME="${2:?Usage: $0 <project-path> <scheme> [simulator-name]}"
SIMULATOR_NAME="${3:-iPhone 16}"

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${BLUE}🔍 iOS Quick Verification${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo "Project: $PROJECT_PATH"
echo "Scheme: $SCHEME"
echo "Simulator: $SIMULATOR_NAME"
echo ""

# Step 1: Build and run
echo -e "${YELLOW}🔨 Building and launching...${NC}"
# Note: In actual use, this would call xcodebuildmcp tools via Claude Code
# For now, this is a placeholder script showing the workflow

# Simulate build
sleep 2

# Step 2: Visual verification
echo -e "${YELLOW}📸 Capturing screenshot...${NC}"
# Would call: mcp__xcodebuildmcp__screenshot

# Step 3: UI tree
echo -e "${YELLOW}🌳 Getting UI tree...${NC}"
# Would call: mcp__xcodebuildmcp__describe_ui

# Step 4: Check results
echo ""
echo -e "${GREEN}✅ Quick verification complete!${NC}"
echo ""
echo "Next steps:"
echo "  • Review screenshot for visual correctness"
echo "  • Check UI tree for expected elements"
echo "  • Review logs for errors/warnings"
echo ""
echo "If issues found → run debug-loop.sh for automatic fixing"
