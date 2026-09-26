---
type: workflow
scope: global
priority: high
inheritable: true
---

# Agent Handoff Protocol

## Purpose
Standardize context preservation and knowledge transfer when transitioning work between different AI agents in the Huxley system.

## When Handoffs Occur

### Planned Handoffs
- **Role Transition** - Security Analyst → Frontend Dev → Performance Optimizer
- **Phase Transition** - Design phase → Implementation phase → Testing phase
- **Specialization** - General agent → Specialized agent for specific task
- **Escalation** - Current agent → More specialized agent for complex issues

### Unplanned Handoffs
- **Session Boundaries** - End of conversation session
- **Context Limits** - When conversation context becomes too large
- **Capability Boundaries** - When task exceeds current agent's capabilities
- **Error Recovery** - When current approach needs fresh perspective

## Handoff Information Requirements

### Project Context Preservation
```markdown
# Project Context Handoff

## Current Project
- **Capsule**: {capsule-name}
- **Lane**: standard | standard
- **Branch**: web | mobile | desktop | automation
- **Phase**: ideation | design | build | deploy

## Current Task
- **Objective**: What we're trying to accomplish
- **Context**: Why this task matters
- **Constraints**: Technical, time, or resource limitations
- **Progress**: What's been completed so far

## Technical State
- **Files Modified**: List of files changed/created
- **Dependencies**: New dependencies added or changed
- **Configuration**: Environment or config changes made
- **Database**: Schema changes or data migrations

## Quality Status
- **Standards Applied**: Which coding standards were used
- **Tests**: Testing approach and current coverage
- **Security**: Security considerations addressed
- **Documentation**: Documentation updated or needed
```

### Decision Context
```markdown
# Decision Context Handoff

## Decisions Made
- **Architecture Choices**: Key architectural decisions with rationale
- **Technology Selections**: Libraries, frameworks, tools chosen
- **Trade-offs**: Alternatives considered and why rejected
- **Assumptions**: Assumptions made that affect implementation

## Open Questions
- **Unresolved Issues**: Problems that need resolution
- **Research Needed**: Areas requiring further investigation
- **Stakeholder Input**: Decisions waiting for human input
- **Risk Areas**: Potential problems identified

## Next Steps
- **Immediate Actions**: What should be done next
- **Validation Needed**: What needs to be tested or verified
- **Dependencies**: What external dependencies block progress
- **Success Criteria**: How to know when task is complete
```

### Code Context
```markdown
# Code Context Handoff

## Current Implementation
- **Entry Points**: Main functions, classes, or modules
- **Data Flow**: How data moves through the system
- **Error Handling**: Current error handling approach
- **Integration Points**: External systems or APIs used

## Code Quality Status
- **Standards Compliance**: Which standards applied and any deviations
- **Test Coverage**: Current test coverage and approach
- **Performance**: Known performance characteristics or concerns
- **Security**: Security measures implemented

## Technical Debt
- **Known Issues**: Technical debt or temporary solutions
- **Improvement Opportunities**: Code that could be enhanced
- **Refactoring Needs**: Areas that need restructuring
- **Monitoring**: What needs monitoring or alerting
```

## Handoff Procedures

### Sending Agent Responsibilities
1. **Context Compilation** - Compile comprehensive handoff information
2. **State Preservation** - Ensure current state is saved and documented
3. **Knowledge Transfer** - Document all relevant decisions and context
4. **Quality Validation** - Verify work meets current standards
5. **Next Steps Planning** - Provide clear next steps for receiving agent

### Receiving Agent Responsibilities
1. **Context Validation** - Verify understanding of handed-off context
2. **Continuity Check** - Ensure no critical information was lost
3. **Standard Alignment** - Confirm applicable standards and requirements
4. **Approach Validation** - Validate previous decisions or suggest improvements
5. **Progress Planning** - Plan immediate next steps based on received context

### Human Oversight Points
- **Critical Decisions** - Major architectural or approach changes require human approval
- **Quality Gates** - DoD validations require human review
- **Risk Escalation** - High-risk changes need human oversight
- **Resource Allocation** - Significant time or resource commitments need approval

## Context Storage and Retrieval

### MCP Memory Integration
```python
# Store handoff context in MCP memory
handoff_context = {
    "timestamp": current_timestamp,
    "from_agent": current_agent_role,
    "to_agent": target_agent_role,
    "project_context": project_context,
    "technical_state": technical_state,
    "decisions_made": decisions_made,
    "next_steps": next_steps
}

# Tag with [HANDOFF] for easy retrieval
store_memory(f"[HANDOFF] {capsule_name} - {current_task}", handoff_context)
```

### Documentation Updates
- **CLAUDE.md Updates** - Update project-specific context
- **Decision Log** - Record key decisions in project decision log
- **Technical Documentation** - Update technical docs with changes
- **Progress Tracking** - Update project progress and status

## Quality Assurance

### Handoff Validation Checklist
- [ ] All project context accurately captured
- [ ] Technical state completely documented
- [ ] Key decisions and rationale preserved
- [ ] Open questions and blockers clearly identified
- [ ] Next steps are specific and actionable
- [ ] Quality status and standards compliance noted
- [ ] Risk areas and concerns highlighted

### Continuity Verification
- [ ] Receiving agent demonstrates understanding of context
- [ ] No critical information lost in transition
- [ ] Approach remains aligned with project goals
- [ ] Standards and quality requirements maintained
- [ ] Timeline and milestones remain realistic

## Examples

### Successful Handoff Example
```markdown
From: Security Analyst
To: Frontend Dev
Task: Implement secure user authentication UI

# Context Handoff

## Security Requirements Established
- OAuth 2.0 + PKCE flow implemented
- Token storage using httpOnly cookies
- CSRF protection via double-submit cookies
- Password policies: 12+ chars, complexity requirements

## Frontend Requirements
- Design system: shadcn/ui components
- Framework: Next.js 14 with App Router
- State management: Zustand for auth state
- Form validation: react-hook-form + zod

## Next Steps for Frontend Dev
1. Create login/register components using established auth flow
2. Implement form validation with security requirements
3. Add accessibility (WCAG 2.1 AA compliance)
4. Test authentication flow end-to-end

## Files to Review
- `/src/lib/auth.ts` - Auth utilities and types
- `/src/app/api/auth/` - API routes (reference only)
- `/spec/security-requirements.md` - Detailed security specs
```

This handoff protocol ensures context continuity and knowledge preservation, enabling seamless collaboration between specialized agents while maintaining the Huxley system's quality standards.