#!/bin/bash
# {{CATALYST_ROOT}}/tools/mcp_audit.sh
# Comprehensive MCP configuration audit for Huxley

set -euo pipefail

readonly CATALYST_ROOT="${CATALYST_ROOT:-{{CATALYST_ROOT}}}"
readonly GLOBAL_MCP_CONFIG="$HOME/.claude/mcp_servers.json"
readonly PROJECT_MCP_CONFIG="$CATALYST_ROOT/.mcp.json"
readonly AUDIT_LOG="$CATALYST_ROOT/registry/mcp_audit_$(date '+%Y%m%d_%H%M%S').json"

echo "🔍 Huxley MCP Configuration Audit"
echo "==================================="

# Initialize audit results
AUDIT_RESULTS='{"timestamp":"'$(date -u +"%Y-%m-%dT%H:%M:%SZ")'","global_mcps":[],"project_mcps":[],"agent_mcps":[],"recommendations":[]}'

audit_global_mcps() {
    echo ""
    echo "🌍 Global MCP Servers (User-level):"
    
    if [[ ! -f "$GLOBAL_MCP_CONFIG" ]]; then
        echo "   ❌ No global MCP configuration found"
        return 1
    fi
    
    echo "   📁 Location: $GLOBAL_MCP_CONFIG"
    
    # Parse and display global MCPs
    if command -v jq >/dev/null 2>&1; then
        local mcp_count=$(jq '.mcpServers | length' "$GLOBAL_MCP_CONFIG" 2>/dev/null || echo "0")
        echo "   📊 Count: $mcp_count servers"
        
        echo "   🔌 Servers:"
        jq -r '.mcpServers | to_entries[] | "      • \(.key): \(.value.command // .value.url // "unknown")"' "$GLOBAL_MCP_CONFIG" 2>/dev/null || echo "      (parsing error)"
    fi
}

audit_project_mcps() {
    echo ""
    echo "🏗️  Project MCP Servers (Huxley-specific):"
    
    if [[ ! -f "$PROJECT_MCP_CONFIG" ]]; then
        echo "   ❌ No project MCP configuration found"
        return 1
    fi
    
    echo "   📁 Location: $PROJECT_MCP_CONFIG"
    
    # Parse and display project MCPs
    if command -v jq >/dev/null 2>&1; then
        local mcp_count=$(jq '.mcpServers | length' "$PROJECT_MCP_CONFIG" 2>/dev/null || echo "0")
        echo "   📊 Count: $mcp_count servers"
        
        echo "   🔌 Servers:"
        jq -r '.mcpServers | to_entries[] | "      • \(.key): \(.value.command // .value.url // "unknown")"' "$PROJECT_MCP_CONFIG" 2>/dev/null || echo "      (parsing error)"
        
        echo "   🎯 Huxley-specific MCPs identified:"
        jq -r '.mcpServers | to_entries[] | select(.key | test("shadcn|n8n|builder|github")) | "      ✓ \(.key) - \(.value.type // "stdio")"' "$PROJECT_MCP_CONFIG" 2>/dev/null || echo "      (none found)"
    fi
}

audit_agent_mcps() {
    echo ""
    echo "🤖 Agent-specific MCP Configurations:"
    
    local found_agent_mcps=false
    
    # Check for agent-specific .mcp.json files
    while IFS= read -r -d '' mcp_file; do
        found_agent_mcps=true
        local dir_path=$(dirname "$mcp_file")
        local relative_path=${dir_path#$CATALYST_ROOT/}
        
        echo "   📂 $relative_path/"
        
        if command -v jq >/dev/null 2>&1; then
            local mcp_count=$(jq '.mcpServers | length' "$mcp_file" 2>/dev/null || echo "0")
            echo "      📊 MCPs: $mcp_count"
            
            if [[ $mcp_count -gt 0 ]]; then
                jq -r '.mcpServers | to_entries[] | "         • \(.key)"' "$mcp_file" 2>/dev/null || echo "         (parsing error)"
            fi
        fi
    done < <(find "$CATALYST_ROOT" -name ".mcp.json" -not -path "$PROJECT_MCP_CONFIG" -print0 2>/dev/null)
    
    if [[ "$found_agent_mcps" = false ]]; then
        echo "   ℹ️  No agent-specific MCP configurations found"
    fi
}

check_active_mcps() {
    echo ""
    echo "🚀 Currently Active MCP Servers:"
    
    # Get currently running MCP servers
    if claude mcp list >/dev/null 2>&1; then
        claude mcp list | grep -E "✓|❌" | while read -r line; do
            echo "   $line"
        done
    else
        echo "   ❌ Unable to query active MCP servers"
    fi
}

generate_scope_recommendations() {
    echo ""
    echo "📋 MCP Scope Recommendations:"
    
    echo ""
    echo "   🌍 GLOBAL SCOPE (User-level ~/.claude/mcp_servers.json):"
    echo "      ✓ filesystem - Universal file access across all projects"
    echo "      ✓ applescript - macOS system automation (all projects)"
    echo "      ✓ iterm-mcp - Terminal integration (development workflow)"
    echo "      ✓ siri-shortcuts - iOS/macOS automation (personal productivity)"
    echo "      ✓ apple-doc-mcp - Apple documentation (iOS/macOS development)"
    echo "      ✓ builder-memory - Context persistence (core Huxley functionality)"
    echo ""
    echo "   🏗️  PROJECT SCOPE (repo root .mcp.json):"
    echo "      ✓ shadcn-ui - Web UI components (Huxley web projects)"
    echo "      ✓ n8n-mcp - Workflow automation (Huxley automation)"
    echo "      ✓ bridge-mcp - Custom Huxley integrations"
    echo "      ✓ External Docs via GitMCP - Documentation access"
    echo ""
    echo "   🤖 AGENT SCOPE (Capsule/.mcp.json):"
    echo "      • Shopify MCP - Only for e-commerce capsules"
    echo "      • iOS MCP - Only for iOS app capsules"
    echo "      • Database MCPs - Only for data-heavy capsules"
    echo "      • AI/ML MCPs - Only for AI-enhanced capsules"
    echo ""
    echo "   ⚠️  OVERLAPS DETECTED:"
    
    # Check for overlaps between global and project configs
    if [[ -f "$GLOBAL_MCP_CONFIG" && -f "$PROJECT_MCP_CONFIG" ]]; then
        local overlaps=""
        if command -v jq >/dev/null 2>&1; then
            # Find common MCP server names
            overlaps=$(jq -r --slurpfile global "$GLOBAL_MCP_CONFIG" --slurpfile project "$PROJECT_MCP_CONFIG" '
                ($global[0].mcpServers | keys) as $global_keys |
                ($project[0].mcpServers | keys) as $project_keys |
                ($global_keys + $project_keys | sort | group_by(.) | map(select(length > 1) | .[0])) | .[]
            ' 2>/dev/null || echo "")
            
            if [[ -n "$overlaps" ]]; then
                echo "$overlaps" | while read -r overlap; do
                    echo "      ⚠️  '$overlap' configured in both global and project scopes"
                done
            else
                echo "      ✅ No overlapping MCP configurations detected"
            fi
        fi
    fi
}

generate_action_items() {
    echo ""
    echo "🎯 Recommended Actions:"
    echo ""
    echo "   1. IMMEDIATE:"
    echo "      □ Move filesystem, applescript, iterm-mcp to global scope"
    echo "      □ Keep shadcn-ui, n8n-mcp in Huxley project scope"
    echo "      □ Resolve any overlapping configurations"
    echo ""
    echo "   2. OPTIMIZATION:"
    echo "      □ Create capsule-specific MCP configs for specialized needs"
    echo "      □ Document MCP scope strategy in CLAUDE.md"
    echo "      □ Add MCP health checks to daily audit"
    echo ""
    echo "   3. GOVERNANCE:"
    echo "      □ Establish MCP addition/removal process"
    echo "      □ Regular MCP audits (monthly)"
    echo "      □ Performance monitoring for MCP servers"
}

create_audit_log() {
    # Create detailed audit log
    mkdir -p "$(dirname "$AUDIT_LOG")"
    
    local audit_data="{
        \"timestamp\": \"$(date -u +"%Y-%m-%dT%H:%M:%SZ")\",
        \"global_mcp_config\": \"$GLOBAL_MCP_CONFIG\",
        \"project_mcp_config\": \"$PROJECT_MCP_CONFIG\",
        \"audit_log\": \"$AUDIT_LOG\"
    }"
    
    echo "$audit_data" | jq '.' > "$AUDIT_LOG" 2>/dev/null || echo "$audit_data" > "$AUDIT_LOG"
    
    echo ""
    echo "📊 Audit log: $AUDIT_LOG"
}

# Main audit execution
audit_global_mcps
audit_project_mcps
audit_agent_mcps
check_active_mcps
generate_scope_recommendations
generate_action_items
create_audit_log

echo ""
echo "✅ MCP audit completed"

