#!/bin/bash
# Huxley — Health Check
# Verifies your installation is correctly configured and ready to use.
#
# Usage:
#   ./catalyst-doctor.sh          # Run all checks
#   ./catalyst-doctor.sh --fix    # Attempt auto-fixes where possible

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
CATALYST_ROOT="$SCRIPT_DIR"
CONFIG_FILE="$CATALYST_ROOT/.catalyst-config"
FIX_MODE="${1:-}"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

PASS=0
WARN=0
FAIL=0

check_pass() { echo -e "  ${GREEN}PASS${NC} $1"; PASS=$((PASS + 1)); }
check_warn() { echo -e "  ${YELLOW}WARN${NC} $1"; WARN=$((WARN + 1)); }
check_fail() { echo -e "  ${RED}FAIL${NC} $1"; FAIL=$((FAIL + 1)); }

echo ""
echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  Huxley — Health Check               ${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# ─── 1. Prerequisites ─────────────────────────────────────────────────────────

echo -e "${BLUE}Prerequisites${NC}"

# Claude Code
if command -v claude >/dev/null 2>&1; then
    check_pass "Claude Code installed"
else
    check_fail "Claude Code not found — install from https://claude.ai/claude-code"
fi

# Node.js
if command -v node >/dev/null 2>&1; then
    NODE_VER=$(node --version | sed 's/v//')
    NODE_MAJOR=$(echo "$NODE_VER" | cut -d. -f1)
    if [[ "$NODE_MAJOR" -ge 18 ]]; then
        check_pass "Node.js $NODE_VER (>= 18)"
    else
        check_warn "Node.js $NODE_VER (recommend >= 18)"
    fi
else
    check_fail "Node.js not found — install from https://nodejs.org"
fi

# Python 3
if command -v python3 >/dev/null 2>&1; then
    PY_VER=$(python3 --version | sed 's/Python //')
    PY_MINOR=$(echo "$PY_VER" | cut -d. -f2)
    if [[ "$PY_MINOR" -ge 9 ]]; then
        check_pass "Python $PY_VER (>= 3.9)"
    else
        check_warn "Python $PY_VER (recommend >= 3.9)"
    fi
else
    check_warn "Python 3 not found — some tools won't work"
fi

# Git
if command -v git >/dev/null 2>&1; then
    check_pass "Git installed"
else
    check_fail "Git not found"
fi

echo ""

# ─── 2. Setup Status ──────────────────────────────────────────────────────────

echo -e "${BLUE}Setup${NC}"

# .catalyst-config
if [[ -f "$CONFIG_FILE" ]]; then
    check_pass ".catalyst-config exists"
    # shellcheck source=/dev/null
    source "$CONFIG_FILE"
else
    check_fail ".catalyst-config not found — run ./setup.sh first"
    echo ""
    echo -e "  ${YELLOW}Run ./setup.sh to personalize your Huxley installation.${NC}"
    echo ""
    echo -e "${RED}$FAIL check(s) failed.${NC} Fix the issues above and re-run."
    exit 1
fi

# Personalization applied
# On a fully personalized tree grep finds nothing and exits 1 — the
# `|| true` keeps that SUCCESS case from tripping set -e/pipefail and
# aborting the whole doctor mid-run.
UNRESOLVED=$( { grep -rlIE --exclude-dir=.git --exclude-dir=node_modules --exclude-dir=.venv \
    --exclude=setup.sh --exclude=.catalyst-config \
    '[{]{2}(CATALYST_ROOT|HOME_DIR|USER_NAME|ORCHESTRATOR_NAME|ORCHESTRATOR_NAME_UPPER|ORCHESTRATOR_NAME_LOWER|ASSISTANT_NAME|USER_EMAIL|USER_LOGIN|GITHUB_USER|CLAUDE_PROJECT_SLUG|MACHINE_HOST|TELEGRAM_BOT|TELEGRAM_CHAT_ID|BRAND)[}]{2}' \
    "$CATALYST_ROOT" 2>/dev/null || true; } | wc -l | tr -d ' ')

if [[ "$UNRESOLVED" -eq 0 ]]; then
    check_pass "Personalization applied (no unresolved setup placeholders in the tree)"
else
    check_fail "Unresolved placeholders found — run: ./setup.sh --apply"
    if [[ "$FIX_MODE" == "--fix" ]]; then
        echo -e "  ${BLUE}Fixing: running setup.sh --apply${NC}"
        "$CATALYST_ROOT/setup.sh" --apply
    fi
fi

# .env file
if [[ -f "$CATALYST_ROOT/.env" ]]; then
    if grep -q '^ANTHROPIC_API_KEY=.' "$CATALYST_ROOT/.env" 2>/dev/null; then
        check_pass ".env exists with ANTHROPIC_API_KEY"
    else
        check_warn ".env exists but ANTHROPIC_API_KEY is empty"
    fi
else
    check_warn "No .env file — copy from .env.example and add your API keys"
    if [[ "$FIX_MODE" == "--fix" ]] && [[ -f "$CATALYST_ROOT/.env.example" ]]; then
        cp "$CATALYST_ROOT/.env.example" "$CATALYST_ROOT/.env"
        echo -e "  ${BLUE}Fixed: created .env from .env.example${NC}"
    fi
fi

# Python venv with tool dependencies (setup.sh creates it; the shipped tools
# and LaunchAgents run .venv/bin/python3). PyYAML is the one dependency the
# capsule/spec pipeline cannot start without.
if [[ -x "$CATALYST_ROOT/.venv/bin/python3" ]]; then
    if "$CATALYST_ROOT/.venv/bin/python3" -c "import yaml" 2>/dev/null; then
        check_pass ".venv exists with PyYAML (capsule/spec tools ready)"
    else
        check_fail ".venv is missing PyYAML — run: .venv/bin/pip install -r tools/requirements.txt"
        if [[ "$FIX_MODE" == "--fix" ]]; then
            echo -e "  ${BLUE}Fixing: .venv/bin/pip install -r tools/requirements.txt${NC}"
            "$CATALYST_ROOT/.venv/bin/pip" install --quiet -r "$CATALYST_ROOT/tools/requirements.txt" || true
        fi
    fi
else
    check_warn "No .venv — run ./setup.sh (or: python3 -m venv .venv && .venv/bin/pip install -r tools/requirements.txt)"
fi

echo ""

# ─── 3. Core Files ────────────────────────────────────────────────────────────

echo -e "${BLUE}Core Files${NC}"

for f in CLAUDE.md SOUL.md .mcp.json; do
    if [[ -f "$CATALYST_ROOT/$f" ]]; then
        check_pass "$f exists"
    else
        check_fail "$f missing"
    fi
done

# Agents directory
AGENT_COUNT=$( { find "$CATALYST_ROOT/.claude/agents/" -name "*.md" 2>/dev/null || true; } | wc -l | tr -d ' ')
if [[ "$AGENT_COUNT" -gt 0 ]]; then
    check_pass "$AGENT_COUNT agent(s) in .claude/agents/"
else
    check_fail "No agents found in .claude/agents/"
fi

# Skills directory
SKILL_COUNT=$( { find "$CATALYST_ROOT/.claude/skills/" -maxdepth 1 -type d -o -type l 2>/dev/null || true; } | wc -l | tr -d ' ')
SKILL_COUNT=$((SKILL_COUNT - 1))  # subtract the directory itself
if [[ "$SKILL_COUNT" -gt 0 ]]; then
    check_pass "$SKILL_COUNT skill(s) in .claude/skills/"
else
    check_warn "No skills found — run ./setup-skills.sh to install community skills"
fi

# Context files
if [[ -d "$CATALYST_ROOT/.claude-context" ]]; then
    check_pass ".claude-context/ directory exists"
else
    check_warn ".claude-context/ missing — context loading won't work"
fi

echo ""

# ─── 4. MCP Servers ───────────────────────────────────────────────────────────

echo -e "${BLUE}MCP Servers${NC}"

if [[ -f "$CATALYST_ROOT/.mcp.json" ]]; then
    # Check if .mcp.json has unresolved placeholders. The pattern is written
    # substitution-proof ([{]{2}...[}]{2}) — a literal {{...}} here would be
    # rewritten by setup.sh itself and then match resolved paths forever.
    if grep -qE '[{]{2}(CATALYST_ROOT|HOME_DIR)[}]{2}' "$CATALYST_ROOT/.mcp.json" 2>/dev/null; then
        check_fail ".mcp.json has unresolved path placeholders — run: ./setup.sh --apply"
    else
        check_pass ".mcp.json paths resolved"
    fi

    # Check npx-based servers (always available if node is installed)
    NPX_SERVERS=$(python3 -c "
import json, sys
try:
    with open('$CATALYST_ROOT/.mcp.json') as f:
        data = json.load(f)
    for name, cfg in data.get('mcpServers', {}).items():
        if cfg.get('command') == 'npx':
            print(f'npx:{name}')
        else:
            args = cfg.get('args', [])
            path = args[0] if args else cfg.get('command', '')
            print(f'local:{name}:{path}')
except Exception as e:
    print(f'error:{e}', file=sys.stderr)
" 2>/dev/null)

    while IFS= read -r line; do
        if [[ "$line" == npx:* ]]; then
            SERVER_NAME="${line#npx:}"
            check_pass "MCP: $SERVER_NAME (npx — auto-install)"
        elif [[ "$line" == local:* ]]; then
            SERVER_NAME=$(echo "$line" | cut -d: -f2)
            SERVER_PATH=$(echo "$line" | cut -d: -f3-)
            if [[ -f "$SERVER_PATH" ]]; then
                check_pass "MCP: $SERVER_NAME ($SERVER_PATH)"
            else
                check_warn "MCP: $SERVER_NAME — path not found: $SERVER_PATH"
            fi
        fi
    done <<< "$NPX_SERVERS"
else
    check_warn "No .mcp.json found"
fi

echo ""

# ─── 5. Optional Tools ────────────────────────────────────────────────────────

echo -e "${BLUE}Optional Tools${NC}"

# Ollama (for file organizer, local AI)
if command -v ollama >/dev/null 2>&1; then
    check_pass "Ollama installed (local AI inference)"
else
    check_warn "Ollama not installed — file organizer and local AI won't work"
fi

# FFmpeg/PyAV (for media engine)
if python3 -c "import av" 2>/dev/null; then
    check_pass "PyAV installed (media engine video processing)"
else
    check_warn "PyAV not installed — media engine video features won't work"
fi

# Playwright (for browser automation)
if python3 -c "import playwright" 2>/dev/null; then
    check_pass "Playwright installed (browser automation)"
else
    check_warn "Playwright not installed — Bowser agent won't work"
fi

echo ""

# ─── Summary ──────────────────────────────────────────────────────────────────

echo -e "${BLUE}========================================${NC}"
TOTAL=$((PASS + WARN + FAIL))
echo -e "  ${GREEN}$PASS passed${NC}  ${YELLOW}$WARN warnings${NC}  ${RED}$FAIL failed${NC}  ($TOTAL checks)"
echo -e "${BLUE}========================================${NC}"
echo ""

if [[ "$FAIL" -gt 0 ]]; then
    echo -e "${RED}Some checks failed.${NC} Fix the issues above and re-run."
    echo "  Tip: ./catalyst-doctor.sh --fix  (auto-fix what's possible)"
    exit 1
elif [[ "$WARN" -gt 0 ]]; then
    echo -e "${YELLOW}Warnings are optional${NC} — Huxley will work but some features may be limited."
    echo "  Your system is ready. Run: claude"
    exit 0
else
    echo -e "${GREEN}Everything looks good!${NC} Run: claude"
    exit 0
fi
