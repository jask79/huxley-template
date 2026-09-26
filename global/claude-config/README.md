# Claude Code Configuration & Resources

This directory contains Claude Code configurations and resources.

## Default: Native Sub-Agents

By default, Claude Code uses its native sub-agent system:

### Available Native Sub-Agents
- **Code Reviewer** - Code quality, security, best practices
- **Debugger** - Issue investigation, root cause analysis  
- **System Architect** - Design, scalability, planning
- **Security Analyst** - Threat modeling, vulnerability assessment
- **Performance Optimizer** - Bottleneck identification, optimization
- **Frontend Specialist** - UI/UX, accessibility, modern web tech

### Usage
Native sub-agents work automatically:
```
"Review this code for security issues"          → Code Reviewer
"Debug this performance problem"                → Debugger + Performance Optimizer  
"Design a scalable authentication system"      → System Architect + Security Analyst
"Create a responsive navigation component"      → Frontend Specialist
```

## Optional: SuperClaude Framework

For advanced projects requiring enhanced capabilities:

### When to Use SuperClaude
- Complex multi-domain operations
- Large-scale refactoring or modernization  
- Enterprise-level quality standards
- Advanced delegation and parallel processing
- Comprehensive analysis and validation

### Activation
```bash
# Activate SuperClaude for current project
~/.claude/templates/superclaude/activate.sh

# Or manually copy framework files
cp ~/.claude/templates/superclaude/*.md ./.claude/
```

### SuperClaude Features
- **Advanced Commands**: `/analyze`, `/improve`, `/build` with wave orchestration
- **Intelligent Personas**: 11 specialized AI personalities
- **MCP Coordination**: Context7, Sequential, Magic, Playwright integration
- **Quality Gates**: 8-step validation cycles
- **Token Optimization**: Advanced compression and efficiency

## Directory Structure

```
~/.claude/
├── CLAUDE.md                    # Main configuration (native by default)
├── agents/                      # Native sub-agents
│   ├── code-reviewer.md
│   ├── debugger.md
│   ├── architect.md
│   ├── security-analyst.md
│   ├── performance-optimizer.md
│   └── frontend-specialist.md
├── templates/
│   └── superclaude/            # SuperClaude framework template
│       ├── CLAUDE.md
│       ├── COMMANDS.md
│       ├── FLAGS.md
│       ├── PRINCIPLES.md
│       ├── RULES.md
│       ├── MCP.md
│       ├── PERSONAS.md
│       ├── ORCHESTRATOR.md
│       ├── MODES.md
│       ├── README.md
│       └── activate.sh
├── commands/                    # Slash commands from awesome-claude-code
├── examples/                    # CLAUDE.md examples for different stacks
├── hooks/                       # Hook examples
├── resources/                   # Additional resources
└── README.md                   # This file
```

## Slash Commands (From awesome-claude-code)

All commands are available as `/command-name` in Claude Code:
- `/commit` - Create conventional commits
- `/docs` - Generate documentation
- `/tdd` - Follow test-driven development
- `/prime` - Initialize project context
- `/check` - Run code quality checks
- `/todo` - Manage project todos

See the `commands/` directory for all available commands.

## CLAUDE.md Examples

Copy the appropriate CLAUDE.md example to your project root:
- Python projects: Use `examples/CLAUDE-python.md`
- TypeScript/Next.js: Use `examples/CLAUDE-typescript-nextjs.md`
- Go projects: Use `examples/CLAUDE-golang.md`
- General best practices: Use `examples/CLAUDE-general-best-practices.md`

## Configuration Philosophy

1. **Native by Default**: Claude Code's built-in capabilities are sufficient for most tasks
2. **Project-Specific Enhancement**: SuperClaude can be enabled per-project when needed
3. **Resource Collection**: Slash commands and examples from awesome-claude-code
4. **No Global Conflicts**: All systems coexist without interference

## Support

- **Native Sub-Agents**: Standard Claude Code documentation
- **SuperClaude Framework**: See `templates/superclaude/README.md`
- **Community Resources**: From awesome-claude-code repository

This approach ensures Claude Code remains fast and focused by default, with advanced capabilities and community resources available when specifically needed.