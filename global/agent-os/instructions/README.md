# Agent OS Instructions Layer

This directory contains the Agent OS instructions system that enhances prompt engineering and agent context management throughout the Huxley system.

## Instructions Hierarchy

### 1. Global Instructions (`/global/agent-os/instructions/`)
- **Base context** - Foundational context for all AI agents
- **Role templates** - Reusable role-based instruction templates  
- **Workflow patterns** - Standard development workflow instructions
- **Handoff protocols** - Agent-to-agent context transfer procedures

### 2. Lane Instructions (`/global/agent-os/instructions/lanes/`)
- **standard/** - Instructions optimized for rapid development
- **standard/** - Instructions for comprehensive, production-ready development

### 3. Branch Instructions (`/global/agent-os/instructions/branches/`)
- **web/** - Web development specific agent instructions
- **mobile/** - Mobile development context and patterns
- **desktop/** - Desktop application development instructions
- **automation/** - Workflow automation specific context

### 4. Agent Role Instructions (`/global/agent-os/instructions/roles/`)
- **security-analyst/** - Security-focused agent instructions
- **frontend-specialist/** - Frontend development specific context
- **system-architect/** - Architecture and design instructions
- **performance-optimizer/** - Performance-focused agent context

### 5. Capsule Instructions (`capsule/.agent-os/instructions/`)
- Inherits from global → lane → branch → role hierarchy
- Adds project-specific context and constraints
- Customizes workflow for specific project needs

## Instruction Categories

### Context Instructions
- **Project Background** - Business context, goals, constraints
- **Technical Context** - Architecture, dependencies, integration points
- **Quality Requirements** - Standards, testing, documentation requirements
- **Success Criteria** - Definition of done, acceptance criteria

### Behavioral Instructions
- **Communication Style** - How agents should communicate and collaborate
- **Decision Making** - Decision frameworks and escalation procedures
- **Risk Management** - How to identify and handle risks
- **Quality Assurance** - Quality gates and validation procedures

### Workflow Instructions
- **Development Process** - Step-by-step development workflows
- **Review Procedures** - Code review and approval processes
- **Testing Protocols** - Testing strategies and requirements
- **Deployment Procedures** - Release and deployment workflows

### Handoff Instructions
- **Context Preservation** - How to maintain context between agents
- **Knowledge Transfer** - Structured knowledge transfer protocols
- **Status Communication** - Progress reporting and status updates
- **Escalation Procedures** - When and how to escalate issues

## Instruction Resolution

### Inheritance Chain
```yaml
# Instructions are resolved in this order:
1. capsule/.agent-os/instructions/{specific-instruction}
2. global/agent-os/instructions/roles/{role}/{instruction}
3. global/agent-os/instructions/branches/{branch}/{instruction}
4. global/agent-os/instructions/lanes/{lane}/{instruction}
5. global/agent-os/instructions/base/{instruction}
```

### Composition Rules
- **Additive**: Most instructions are additive (combine all applicable)
- **Override**: Security and compliance instructions override lower levels
- **Merge**: Context instructions merge with project-specific details
- **Prioritize**: Latest/most specific instructions take precedence

## Template Structure

### Standard Instruction Template
```markdown
---
type: context|behavioral|workflow|handoff
scope: global|lane|branch|role|capsule
priority: high|medium|low
inheritable: true|false
---

# Instruction Name

## Purpose
Clear explanation of what this instruction accomplishes.

## Context
Background information and constraints.

## Instructions
Specific, actionable instructions for AI agents.

## Success Criteria
How to know the instruction was followed successfully.

## Examples
Concrete examples of applying this instruction.

## Related Instructions
Links to related or prerequisite instructions.
```

## Integration with Huxleys

### Agent Selection
- Instructions influence which agents are selected for tasks
- Role-specific instructions help route to appropriate specialists
- Context instructions inform agent capabilities and limitations

### Prompt Engineering
- Instructions are automatically included in agent prompts
- Dynamic composition based on current task and context
- Consistent formatting and structure across all interactions

### Quality Assurance
- Instructions include quality checkpoints and validation
- Success criteria become part of Definition of Done
- Review procedures ensure instruction compliance

### Knowledge Management
- Instructions capture institutional knowledge and best practices
- Evolutionary improvement through experience and feedback
- Version control and change management for instruction updates

This instructions system transforms ad-hoc agent interactions into structured, consistent, and continuously improving AI collaboration patterns.