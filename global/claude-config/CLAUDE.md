# Claude Code - Native Configuration

This is the default Claude Code configuration using native sub-agents.

## Claude Code Configuration
Claude Code configuration tasks can be handled directly without specialized sub-agents.

## Native Sub-Agents

Claude Code's native sub-agent system is located in:
- `~/.claude/agents/` - User-level sub-agents
- `./project/.claude/agents/` - Project-specific sub-agents

## 🌐 Huxley Agents

All agents are defined in `{{CATALYST_ROOT}}/.claude/agents/` (35 specialists).

**Authoritative agent list:** See main `CLAUDE.md` in Huxley project root.

**Note:** Legacy agents in `global/claude-config/agents/` have been archived to `_archived/` subdirectory.

## 🎨 Output Styles

Output styles modify how agents approach problems. Available globally:
- **debug-forensics** - Systematic incident investigation
- **gen-ui** - Interactive deliverables and visualizations
- ⚡ **performance** - Bottleneck identification and optimization
- 🧪 **testing** - Test-driven development with proof-of-work
- 🌐 **browser-automation** - Playwright and browser automation
- 🚀 **deployment** - Release engineering and deployment strategy
- 📊 **data-analysis** - Data exploration and metrics analysis

## SuperClaude Framework

For projects requiring advanced capabilities, use the SuperClaude framework template:

```bash
# Copy SuperClaude framework to a specific project
cp ~/.claude/templates/superclaude/* ./your-project/.claude/
```

## Default Behavior

Without project-specific SuperClaude configuration, Claude Code will:
1. Use native sub-agent delegation
2. Follow standard Claude Code patterns
3. Provide focused, efficient assistance
4. Maintain compatibility with all Claude Code features

## Claude Code Configuration Reference

### Quick Setup
```bash
# Install Claude Code
npm install -g @anthropic-ai/claude-code

# Set API key
export ANTHROPIC_API_KEY="your-key-here"

# Start Claude Code
claude
```

### Configuration Files Priority (Highest to Lowest)
1. Enterprise managed: `/Library/Application Support/ClaudeCode/managed-settings.json`
2. Command line arguments
3. Project local: `.claude/settings.local.json`
4. Project shared: `.claude/settings.json`
5. User settings: `~/.claude/settings.json`

### Essential Settings Structure
```json
{
  "permissions": {
    "allow": ["Bash(npm run lint)", "Bash(npm test)"],
    "deny": ["Bash(rm -rf *)"],
    "additionalDirectories": ["/path/to/allowed/dir"]
  },
  "env": {
    "CUSTOM_VAR": "value"
  },
  "hooks": {
    "user-prompt-submit": "scripts/validate.sh"
  }
}
```

### MCP Server Management
```bash
# Add stdio server (most common)
claude mcp add server-name /path/to/server

# Add with scope
claude mcp add --scope project shared-server /path/to/server
claude mcp add --scope local personal-server /path/to/server

# List servers
claude mcp list

# Remove server
claude mcp remove server-name
```

### Common Commands
- `claude` - Start interactive session
- `claude -c` - Continue recent conversation
- `claude commit` - Create AI-generated git commit
- `claude -p "query"` - Quick query mode
- `claude config list` - Show all settings
- `claude mcp` - Manage MCP servers

### Slash Commands
- `/help` - Show available commands
- `/clear` - Clear conversation history
- `/mcp` - Interactive MCP management
- `/config` - View/modify configuration
- `/memory` - Edit CLAUDE.md files
- `/agents` - Manage sub-agents

### Troubleshooting Claude Code Issues
1. **Authentication**: Ensure `ANTHROPIC_API_KEY` is set
2. **Permissions**: Check `permissions.allow` in settings
3. **MCP Servers**: Verify server paths and executability
4. **Configuration**: Validate JSON syntax in all config files
5. **Sub-agents**: Ensure prompt.md exists in agent directory

### Best Practices
- Use project settings for team consistency
- Keep sensitive configs in `.local.json` files
- Document custom commands in project CLAUDE.md
- Test configurations with `claude config list`

## Global Communication Standards
**STRICTLY PROHIBITED RESPONSES:**
- "You're absolutely right" - NEVER use this phrase
- "You're right" / "Absolutely" / "Exactly" / other empty validation tokens
- "That's a great point" / "Good thinking" without technical analysis
- Patronizing acknowledgment patterns
- Agreement without technical substance or reasoning

**REQUIRED APPROACH:**
- Engage with the technical substance of requests
- Provide reasoning for recommendations, not just compliance
- Offer alternatives when better approaches exist
- Focus on engineering trade-offs and implications
- Challenge assumptions when they conflict with best practices

