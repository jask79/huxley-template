---
allowed-tools: [Read, Write, Edit, Bash, Glob]
description: "Set up Agent OS structure for new or existing capsules"
---

# /agent-os:capsule-setup - Capsule Agent OS Integration

## Purpose
Initialize or enhance capsule Agent OS structure, ensuring comprehensive context for AI agents while maintaining Huxley patterns.

## Usage
```
/agent-os:capsule-setup [capsule-path] [--mode init|enhance|validate] [--lane fast|deep] [--branch web|mobile|desktop|automation]
```

## Arguments
- `capsule-path` - Path to capsule directory
- `--mode` - Setup mode (init: create new, enhance: improve existing, validate: check structure)
- `--lane` - Target lane for optimization
- `--branch` - Technology branch for specialized setup

## Execution Workflow

### 1. Capsule Analysis
- Analyze existing capsule structure and metadata
- Identify lane, branch, and specialization requirements
- Assess current Agent OS integration level

### 2. Agent OS Structure Creation
```
capsule/
├── .agent-os/
│   ├── product/
│   │   ├── vision.md          # Project vision and goals
│   │   ├── architecture.md    # Technical architecture
│   │   ├── decisions.md       # Key architectural decisions
│   │   └── roadmap.md         # Development roadmap
│   ├── specs/
│   │   ├── functional-spec.md # Detailed functional requirements
│   │   ├── technical-spec.md  # Technical implementation details
│   │   └── api-spec.md        # API specifications (if applicable)
│   ├── standards/
│   │   ├── coding-standards.md # Project-specific coding standards
│   │   ├── review-checklist.md # Code review requirements
│   │   └── testing-strategy.md # Testing approach and requirements
│   └── instructions/
│       ├── agent-context.md   # Context for AI agents
│       ├── workflow-guide.md  # Development workflow instructions
│       └── handoff-protocol.md # Agent handoff procedures
```

### 3. Content Generation
- Generate context-rich documentation based on existing capsule content
- Create lane-specific standards and workflows
- Establish agent context and instructions

### 4. Integration with Huxleys
- Link with existing `spec/requirements.yaml`
- Integrate with capsule metadata (`capsule.json`)
- Ensure compatibility with Huxley DoD and validation systems

## Generated Content Templates

### Product Layer
- **Vision**: Clear project purpose, user value, success metrics
- **Architecture**: Technical approach, integration points, constraints
- **Decisions**: Key choices made, alternatives considered, rationale
- **Roadmap**: Development phases, milestones, dependencies

### Specs Layer  
- **Functional Spec**: User stories, acceptance criteria, edge cases
- **Technical Spec**: Implementation details, algorithms, data structures
- **API Spec**: Endpoints, schemas, integration patterns

### Standards Layer
- **Coding Standards**: Language-specific conventions, patterns, anti-patterns
- **Review Checklist**: Quality gates, security requirements, performance criteria
- **Testing Strategy**: Test types, coverage requirements, automation approach

### Instructions Layer
- **Agent Context**: Project background, constraints, success criteria
- **Workflow Guide**: Development process, tools, handoff points
- **Handoff Protocol**: Context preservation between agents

## Claude Code Integration
- Uses Write for creating structured documentation
- Leverages Edit for enhancing existing content
- Applies Bash for directory structure creation
- Maintains consistency with Huxley capsule patterns

This command ensures every capsule provides rich context for productive AI agent collaboration.