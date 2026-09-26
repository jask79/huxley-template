# Apple App Starter Template

This is the specialized template for iOS and macOS application development with full Huxley v2 features:
- **Automatic Xcode project creation** (linked, not copied)
- Agent routing with `.claude/agents/` overrides optimized for Apple development
- Rich metadata for lane/branch routing with iOS/macOS targets
- MCP configuration integration with Apple-specific servers
- Event logging support for build and deployment tracking
- Context persistence for development sessions

## Template Structure

```
apple-app-starter/
├── README.md                    # This file - Apple app development guide
├── .claude/                     # Claude Code integration
│   ├── agents/                  # Agent overrides optimized for Apple development
│   │   ├── iOS Dev.md   # iOS-specific development guidance
│   │   ├── macos-specialist.md # macOS-specific development guidance
│   │   └── README.md          # Agent selection for Apple platforms
│   └── TEMPLATE.md            # Apple app template instructions
├── spec/                      # Project specifications  
│   ├── requirements.yaml      # Core requirements with Apple platform targets
│   ├── context.jsonl         # Apple development context and domain knowledge
│   ├── metadata.yaml         # Enhanced routing metadata (ios/macos targets)
│   └── test_plan.md          # Testing strategy for Apple platforms
├── ops/                      # Operations and configuration
│   ├── mcp.json             # MCP server configuration (includes xcodebuild, apple-doc)
│   ├── events.jsonl         # Event logging template for iOS/macOS builds
│   └── dod.yaml             # Definition of Done criteria for App Store readiness
├── docs/                    # Documentation
│   ├── architecture.md      # iOS/macOS app architecture
│   └── deployment.md        # App Store deployment guide
├── src/                     # Source code organized for Apple development
│   ├── ios/                 # iOS-specific Swift source files
│   ├── macos/               # macOS-specific Swift source files
│   ├── shared/              # Shared Swift code (business logic, models)
│   └── resources/           # Assets, localizations, configurations
└── runs/                    # Runtime artifacts
    ├── logs/                # Build and deployment logs
    ├── tests/               # XCTest results and coverage reports
    ├── builds/              # Xcode build artifacts and archives
    └── deployments/         # App Store Connect uploads and releases

## CRITICAL: Automatic Xcode Project Creation

When using this template, Xcode projects are created AUTOMATICALLY:
- NO prompting required - part of standard pipeline
- Projects LINK to source files (never copy)
- Compatible with all editors (Xcode, Cursor, terminal, Claude Code)
- Single source of truth maintained in src/ directories
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