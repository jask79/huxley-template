# Enhanced Capsule Base Template

This is the enhanced capsule template with full Huxley v2 features:
- Agent routing with `.claude/agents/` overrides
- Rich metadata for lane/branch routing
- MCP configuration integration
- Event logging support
- Context persistence

## Template Structure

```
capsule-base/
├── README.md                    # This file
├── .claude/                     # Claude Code integration
│   ├── agents/                  # Agent overrides and hints
│   │   └── README.md           # Agent selection guidance
│   └── TEMPLATE.md             # Template instructions
├── spec/                       # Project specifications  
│   ├── requirements.yaml       # Core requirements and constraints
│   ├── context.jsonl          # Context and domain knowledge
│   ├── metadata.yaml          # Enhanced routing metadata
│   └── test_plan.md           # Testing strategy
├── ops/                       # Operations and configuration
│   ├── mcp.json              # MCP server configuration
│   ├── events.jsonl          # Event logging template
│   └── dod.yaml              # Definition of Done criteria
├── docs/                     # Documentation
│   ├── architecture.md       # System architecture
│   └── deployment.md         # Deployment guide
├── src/                      # Source code by branch
│   ├── automation/           # Automation branch
│   ├── web/                  # Web development branch  
│   ├── app/                  # App development branch
│   └── shared/               # Shared utilities
└── runs/                     # Runtime artifacts
    ├── logs/                 # Execution logs
    ├── tests/                # Test results
    └── deployments/          # Deployment artifacts
```

## Usage

1. Copy this template to start a new capsule
2. Customize `spec/requirements.yaml` with your project details
3. Set `spec/metadata.yaml` for proper agent routing
4. Configure `ops/mcp.json` with required MCP servers
5. Add agent-specific guidance in `.claude/agents/`

## Branch Routing

The template supports automatic routing based on:
- **Branch**: automation, web, app, backend, ops
- **Lane**: standard (quick builds) vs standard (production quality)
- **Targets**: Specific technologies or platforms
- **File Context**: File types and directories

## Lane Configuration

### standard
- Minimal validation
- Quick iteration
- Personal/prototype projects
- Basic DoD requirements

### standard  
- Full validation pipeline
- Production quality gates
- Business/customer projects
- Comprehensive DoD requirements

## MCP Integration

Configure MCP servers in `ops/mcp.json`:
- **default**: Basic filesystem, git, http
- **webdev**: Adds shopify, cms, shadcn-ui
- **automation**: Adds n8n, applescript
- **apple**: Adds xcodebuild, ios-sim

## Event Logging

The template includes `ops/events.jsonl` for standardized logging:
- Capsule lifecycle events
- Build and deployment status
- Error tracking and resolution
- Performance metrics

This enables the Huxley advisor system to provide intelligent recommendations.