# SuperClaude Framework - Project Configuration

This project uses the SuperClaude framework for enhanced Claude Code capabilities.

## Framework Components

@COMMANDS.md
@FLAGS.md
@PRINCIPLES.md
@RULES.md
@MCP.md
@PERSONAS.md
@ORCHESTRATOR.md
@MODES.md

## Usage

The SuperClaude framework provides:
- Advanced command system with wave orchestration
- Intelligent persona activation
- MCP server coordination
- Advanced delegation and parallel processing
- Quality gates and validation frameworks

## Enabling SuperClaude

To use SuperClaude in this project, copy these files to your project's `.claude/` directory:

```bash
cp ~/.claude/templates/superclaude/* ./project/.claude/
```

## Native Claude Code Fallback

If SuperClaude components are not present, Claude Code will use its native sub-agent system located in `~/.claude/agents/`.