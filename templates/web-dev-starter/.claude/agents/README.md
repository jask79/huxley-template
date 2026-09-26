# Agent Overrides and Hints

This directory allows capsule-specific agent customization and guidance.

## Agent Override Files

Create agent-specific files to override global agents for this capsule:

```
agents/
├── README.md                    # This file
├── {agent-name}.md             # Agent override (replaces global)
├── {agent-name}.{branch}.md    # Branch-specific variant
└── {agent-name}.{lane}.md      # Lane-specific variant
```

## Agent Selection Guidance

Based on your capsule's branch and requirements:

### Automation Branch
- **Primary**: `automation-specialist.md`
- **Supporting**: `security-auditor.md`, `test-automator.md`
- **MCPs**: n8n, applescript, filesystem

### Web Development Branch  
- **Primary**: `frontend-specialist.md`, `javascript-pro.md`
- **Supporting**: `backend-architect.md`, `security-auditor.md`
- **MCPs**: shadcn-ui, shopify, cms, filesystem, git, http

### App Development Branch
- **iOS**: `ios-specialist.md`
- **macOS**: `macos-specialist.md` 
- **Supporting**: `security-auditor.md`, `test-automator.md`
- **MCPs**: xcodebuild, ios-sim, applescript, filesystem

### Backend/Infrastructure Branch
- **Primary**: `backend-architect.md`, `devops-troubleshooter.md`
- **Supporting**: `deployment-engineer.md`, `security-auditor.md`
- **MCPs**: git, http, filesystem

## Lane-Specific Agents

### standard (Production)
- Always includes: `code-reviewer.md`, `security-auditor.md`
- Enhanced DoD validation and quality gates
- Comprehensive testing and documentation requirements

### standard (Rapid Development)
- Streamlined agent selection
- Minimal but sufficient quality checks
- Optimized for quick iteration

## Custom Agent Creation

To create a capsule-specific agent:

1. Copy from global agents: `{{CATALYST_ROOT}}/.claude/agents/`
2. Customize for your specific domain/requirements
3. Update the frontmatter with capsule-specific tools and MCPs
4. Add domain-specific knowledge and patterns

## Agent Precedence

Agent selection follows this precedence:
1. Capsule-specific (this directory)
2. Project-level global agents
3. User-level agents
4. System default agents

The Huxley system will automatically select the most specific agent available.