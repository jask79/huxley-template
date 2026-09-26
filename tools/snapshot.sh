#!/bin/bash
# ${CATALYST_ROOT:-{{CATALYST_ROOT}}}/tools/snapshot.sh
# Git commit helper to snapshot Huxley context and configuration changes

set -euo pipefail

cd ${CATALYST_ROOT:-{{CATALYST_ROOT}}}

# Check if this is a git repository
if [ ! -d ".git" ]; then
    echo "⚠️  Not a git repository. Initialize with:"
    echo "   git init"
    echo "   git add ."
    echo "   git commit -m 'Initial Huxley'"
    exit 1
fi

# Add context files and configuration
echo "📸 Snapshotting Huxley changes..."

# Stage context files
git add global/*.md 2>/dev/null || true
git add global/config/*.json 2>/dev/null || true
git add tools/*.sh 2>/dev/null || true
git add README.md 2>/dev/null || true

# Check if there are changes to commit
if git diff --staged --quiet; then
    echo "ℹ️  No changes to commit"
    exit 0
fi

# Show what will be committed
echo ""
echo "📋 Changes to be committed:"
git diff --staged --name-only | sed 's/^/  /'
echo ""

# Create commit with timestamp
TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')
COMMIT_MSG="snapshot: Huxley update - $TIMESTAMP"

if git commit -m "$COMMIT_MSG"; then
    echo "✅ Snapshot committed: $COMMIT_MSG"
else
    echo "❌ Commit failed"
    exit 1
fi

# Show recent commits
echo ""
echo "📚 Recent commits:"
git log --oneline -5

