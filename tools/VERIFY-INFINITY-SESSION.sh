#!/bin/bash
# Quick verification script to check if you're in an Infinity session

echo "=== Infinity Mode Verification ==="
echo ""

# Check environment variable
if [ -z "$ANTHROPIC_BASE_URL" ]; then
    echo "❌ ANTHROPIC_BASE_URL is NOT set"
    echo "   This session is using Claude SUBSCRIPTION"
    echo ""
    echo "To use Infinity mode:"
    echo "   1. Exit this Claude session"
    echo "   2. Run: {{CATALYST_ROOT}}/tools/run-infinity.sh"
    exit 1
else
    echo "✅ ANTHROPIC_BASE_URL is set to: $ANTHROPIC_BASE_URL"
fi

# Check if it's pointing to Router
if [ "$ANTHROPIC_BASE_URL" = "http://127.0.0.1:3456" ]; then
    echo "✅ Correctly pointing to Claude Code Router"
else
    echo "⚠️  ANTHROPIC_BASE_URL is set but not pointing to Router"
    echo "   Expected: http://127.0.0.1:3456"
    echo "   Got: $ANTHROPIC_BASE_URL"
fi

# Check Router connectivity
if curl -s http://127.0.0.1:3456/health > /dev/null 2>&1; then
    echo "✅ Router is responding on port 3456"
else
    echo "❌ Router is NOT responding on port 3456"
fi

# Check Bifrost connectivity
if curl -s http://localhost:8083/v1/models > /dev/null 2>&1; then
    echo "✅ Bifrost is responding on port 8083"
else
    echo "❌ Bifrost is NOT responding on port 8083"
fi

echo ""
echo "=== Result ==="
if [ "$ANTHROPIC_BASE_URL" = "http://127.0.0.1:3456" ] && \
   curl -s http://127.0.0.1:3456/health > /dev/null 2>&1 && \
   curl -s http://localhost:8083/v1/models > /dev/null 2>&1; then
    echo "✅ This session IS using Infinity mode (API)"
    echo "   Your requests go: Claude CLI → Router (:3456) → Bifrost (:8083) → OpenAI"
    echo ""
    echo "📊 To monitor routing in real-time, run in a separate terminal:"
    echo "   tail -f ~/.claude-code-router/logs/ccr-*.log | grep 'bifrost,openai'"
elif [ -z "$ANTHROPIC_BASE_URL" ]; then
    echo "❌ This session is NOT using Infinity mode"
    echo "   ANTHROPIC_BASE_URL is not set - using Anthropic subscription"
    echo ""
    echo "To use Infinity mode:"
    echo "   1. Exit this Claude session (Ctrl+D or type 'exit')"
    echo "   2. Run: {{CATALYST_ROOT}}/tools/run-infinity.sh"
    echo "   3. In the new shell, run: claude"
else
    echo "⚠️  Partial Infinity mode setup detected"
    echo "   ANTHROPIC_BASE_URL is set but services may not be running"
    echo "   Check the individual service status above"
fi
echo ""
