# SuperClaude Framework Template

Advanced Claude Code framework for complex software engineering projects.

## What is SuperClaude?

SuperClaude is an enhanced framework that extends Claude Code with:

- **Advanced Command System**: Wave orchestration for multi-stage operations
- **Intelligent Personas**: 11 specialized AI personalities for different domains
- **MCP Server Coordination**: Integration with Context7, Sequential, Magic, Playwright
- **Quality Gates**: 8-step validation cycles with evidence-based completion
- **Performance Optimization**: Token efficiency and resource management

## When to Use SuperClaude

Use SuperClaude for projects that need:
- Complex multi-domain operations (architecture + security + performance)
- Large-scale refactoring or modernization
- Enterprise-level quality standards
- Advanced delegation and parallel processing
- Comprehensive analysis and validation

## Installation

### For a Specific Project
```bash
# Navigate to your project
cd /path/to/your/project

# Ensure .claude directory exists
mkdir -p .claude

# Copy SuperClaude framework
cp ~/.claude/templates/superclaude/* .claude/

# Verify installation
ls .claude/
```

### Verification
Your project's `.claude/` directory should contain:
- `CLAUDE.md` - Framework entry point
- `COMMANDS.md` - Command system
- `FLAGS.md` - Flag reference
- `PRINCIPLES.md` - Development principles
- `RULES.md` - Operational rules
- `MCP.md` - MCP server integration
- `PERSONAS.md` - AI personalities
- `ORCHESTRATOR.md` - Routing system
- `MODES.md` - Operational modes

## Framework vs Native Comparison

| Feature | Native Claude Code | SuperClaude Framework |
|---------|-------------------|----------------------|
| Sub-Agents | 6 specialized agents | 11 personas + agents |
| Commands | Built-in commands | 15+ advanced commands |
| MCP Integration | Basic | Advanced coordination |
| Quality Gates | Standard | 8-step validation |
| Wave Mode | No | Multi-stage orchestration |
| Token Optimization | Basic | Advanced compression |
| Delegation | Simple | Parallel + intelligent |

## Usage Examples

### Native (Default)
```
# Simple code review
"Review this function for issues"

# Basic debugging  
"Help debug this error"
```

### SuperClaude (Project-Specific)
```
# Advanced analysis with wave mode
"/analyze @src/ --wave-mode --focus security"

# Comprehensive improvement
"/improve @components/ --loop --persona-frontend"

# Multi-domain orchestration
"/build --wave-strategy enterprise --delegate auto"
```

## Deactivation

To return to native Claude Code:
```bash
# Remove SuperClaude from project
rm .claude/COMMANDS.md .claude/FLAGS.md .claude/PRINCIPLES.md .claude/RULES.md .claude/MCP.md .claude/PERSONAS.md .claude/ORCHESTRATOR.md .claude/MODES.md

# Update CLAUDE.md to reference native agents only
echo "# Native Claude Code Configuration" > .claude/CLAUDE.md
```

## Support

- **Native Issues**: Standard Claude Code documentation
- **SuperClaude Issues**: Framework-specific behavior and advanced features

The framework is designed to be additive - it enhances rather than replaces Claude Code's native capabilities.