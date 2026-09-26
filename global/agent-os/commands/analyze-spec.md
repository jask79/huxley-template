---
allowed-tools: [Read, Grep, Glob, WebSearch]
description: "Analyze project specifications using Agent OS structured patterns"
---

# /agent-os:analyze-spec - Specification Analysis

## Purpose
Analyze project specifications using Agent OS methodology to ensure comprehensive, structured specifications that enable productive AI development.

## Usage
```
/agent-os:analyze-spec [target] [--depth basic|comprehensive|expert] [--output json|md|yaml]
```

## Arguments
- `target` - Capsule directory or specification file to analyze
- `--depth` - Analysis depth (basic: structure, comprehensive: content, expert: agent readiness)
- `--output` - Output format for analysis results
- `--validate` - Run validation against Agent OS specification standards

## Execution Workflow

### 1. Specification Discovery
- Locate `spec/requirements.yaml`, `.agent-os/specs/`, and related specification files
- Identify specification completeness and structure
- Map dependencies and integration points

### 2. Agent OS Standards Validation
- Verify specification follows Agent OS structured format
- Check for essential context elements (purpose, constraints, success criteria)
- Validate agent-readable format and clarity

### 3. Context Completeness Analysis
- Assess specification detail level for AI agent consumption
- Identify missing context that could confuse agents
- Evaluate specification quality for different agent types

### 4. Integration Assessment  
- Check compatibility with Huxley capsule patterns
- Validate lane/branch routing compatibility
- Assess MCP integration requirements

## Output Structure

```yaml
analysis:
  specification_quality: high|medium|low
  agent_readiness_score: 0-100
  completeness_metrics:
    purpose_clarity: 0-100
    technical_detail: 0-100
    success_criteria: 0-100
    context_richness: 0-100
  
  gaps_identified:
    - missing_architecture_context
    - unclear_success_criteria
    - insufficient_technical_constraints
  
  recommendations:
    - action: "Add detailed API specification"
      priority: high
      agent_impact: "Enables accurate implementation"
    
improvement_plan:
  immediate_actions: []
  quality_enhancements: []
  agent_optimization: []
```

## Claude Code Integration
- Uses Glob for comprehensive specification discovery
- Leverages Grep for pattern analysis across specifications
- Applies Read for deep content analysis
- Maintains compatibility with Huxley capsule structure

This command ensures specifications meet Agent OS standards for productive AI development within the Huxley ecosystem.