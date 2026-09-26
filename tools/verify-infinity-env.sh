#!/bin/bash
# Verification script for Infinity Mode environment setup
# Tests that ANTHROPIC_BASE_URL is properly set when Claude Infinity profile launches

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🔍 Infinity Mode Environment Verification"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Check 1: Init file exists
echo "✓ Checking for ~/.zsh_infinity_init..."
if [ -f "$HOME/.zsh_infinity_init" ]; then
    echo "  ✅ Init file exists"
    echo "  Contents:"
    cat "$HOME/.zsh_infinity_init" | sed 's/^/    /'
else
    echo "  ❌ Init file missing"
    exit 1
fi
echo ""

# Check 2: .zshrc sources the init file
echo "✓ Checking ~/.zshrc for sourcing logic..."
if grep -q "zsh_infinity_init" "$HOME/.zshrc"; then
    echo "  ✅ .zshrc sources infinity init file"
else
    echo "  ❌ .zshrc does not source infinity init file"
    exit 1
fi
echo ""

# Check 3: Gateway stack is running
echo "✓ Checking gateway stack health..."
BIFROST_HEALTHY=false
ROUTER_HEALTHY=false

if curl -s --max-time 2 http://localhost:8083/v1/models > /dev/null 2>&1; then
    echo "  ✅ Bifrost gateway running (port 8083)"
    BIFROST_HEALTHY=true
else
    echo "  ❌ Bifrost gateway not responding"
fi

if curl -s --max-time 2 http://127.0.0.1:3456/health > /dev/null 2>&1; then
    echo "  ✅ Claude Code Router running (port 3456)"
    ROUTER_HEALTHY=true
else
    echo "  ❌ Claude Code Router not responding"
fi
echo ""

# Check 4: Current environment (if running in Infinity context)
echo "✓ Current shell environment:"
if [ -n "$ANTHROPIC_BASE_URL" ]; then
    echo "  ✅ ANTHROPIC_BASE_URL=$ANTHROPIC_BASE_URL"
else
    echo "  ⚠️  ANTHROPIC_BASE_URL not set in current shell"
    echo "     (This is normal if not running from Claude Infinity profile)"
fi

if [ -n "$CLAUDE_GATEWAY_MODE" ]; then
    echo "  ✅ CLAUDE_GATEWAY_MODE=$CLAUDE_GATEWAY_MODE"
fi
echo ""

# Check 5: iTerm profile exists
echo "✓ Checking iTerm profile..."
if python3 -c "import plistlib; p=plistlib.load(open('$HOME/Library/Preferences/com.googlecode.iterm2.plist', 'rb')); bookmarks=[b for b in p.get('New Bookmarks', []) if 'Claude (Infinity)' in b.get('Name', '')]; exit(0 if bookmarks else 1)" 2>/dev/null; then
    echo "  ✅ 'Claude (Infinity) - Huxley' profile found"
    echo "  Profile launches: {{CATALYST_ROOT}}/tools/run-infinity.sh"
else
    echo "  ❌ 'Claude (Infinity) - Huxley' profile not found"
fi
echo ""

# Summary
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
if [ "$BIFROST_HEALTHY" = true ] && [ "$ROUTER_HEALTHY" = true ]; then
    echo "✅ Infinity Mode is properly configured and gateway is healthy"
else
    echo "⚠️  Configuration is correct but gateway may need to be started"
    echo "   Run: {{CATALYST_ROOT}}/tools/start-infinity-gateway.sh"
fi
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
