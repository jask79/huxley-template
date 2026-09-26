#!/bin/bash

# SuperClaude Framework Activation Script
# Usage: ./activate.sh [project-directory]

PROJECT_DIR=${1:-.}
CLAUDE_DIR="$PROJECT_DIR/.claude"
TEMPLATE_DIR="$HOME/.claude/templates/superclaude"

echo "🚀 Activating SuperClaude Framework..."

# Check if template exists
if [ ! -d "$TEMPLATE_DIR" ]; then
    echo "❌ SuperClaude template not found at $TEMPLATE_DIR"
    echo "Please ensure the template is installed in ~/.claude/templates/superclaude/"
    exit 1
fi

# Create .claude directory if it doesn't exist
mkdir -p "$CLAUDE_DIR"

# Copy framework files
echo "📋 Copying framework files..."
cp "$TEMPLATE_DIR"/*.md "$CLAUDE_DIR/"

# Make sure we don't overwrite existing agents
if [ -d "$CLAUDE_DIR/agents" ]; then
    echo "ℹ️  Preserving existing agents directory"
else
    echo "👥 Creating default agents directory"
    mkdir -p "$CLAUDE_DIR/agents"
fi

echo "✅ SuperClaude Framework activated in $PROJECT_DIR"
echo ""
echo "Framework components installed:"
ls -1 "$CLAUDE_DIR"/*.md | sed 's/.*\//- /'
echo ""
echo "🎯 You can now use advanced SuperClaude commands like:"
echo "   /analyze --wave-mode"
echo "   /improve --loop --persona-refactorer" 
echo "   /build --wave-strategy enterprise"
echo ""
echo "📖 See .claude/README.md for full documentation"