# standard Standards - Agent OS

Standards for rapid prototyping and iteration in the Huxley system's standard, optimized for speed while maintaining essential quality.

## standard Philosophy

### Speed with Safety
- **Minimum Viable Quality** - Meet essential standards, optimize for iteration speed
- **Progressive Enhancement** - Start simple, add complexity as needed
- **Fail Fast, Learn Fast** - Prioritize rapid feedback over comprehensive planning

### Essential vs. Comprehensive
- **Security**: Non-negotiable baseline requirements
- **Functionality**: Working prototype over feature completeness
- **Documentation**: Minimal but sufficient for handoff
- **Testing**: Core path testing, comprehensive edge case testing can wait

## standard Coding Standards

### Simplified Requirements
- **Function Length** - Prefer short functions, but 100 lines acceptable if it works
- **Error Handling** - Handle critical paths, log others for later refinement
- **Documentation** - Inline comments for complex logic, full docs can wait
- **Naming** - Clear naming required, but consistency can be refined later

### Acceptable Technical Debt
- **TODO Comments** - Liberally use TODO comments to mark future improvements
- **Hardcoded Values** - Acceptable for prototyping, must be tracked for cleanup
- **Code Duplication** - Some duplication acceptable if it enables faster development
- **Performance Optimization** - Focus on correctness first, optimize later

### Still Required (Non-Negotiable)
- **Input Validation** - Never skip input validation, even in prototypes
- **Authentication/Authorization** - Security cannot be "added later"
- **Secret Management** - No hardcoded secrets, ever
- **Basic Error Handling** - Must handle critical error scenarios

## Testing Standards - standard

### Minimum Testing Requirements
- **Happy Path Tests** - Core functionality must have basic tests
- **Critical Error Scenarios** - Test what breaks the system
- **Integration Smoke Tests** - Basic integration points verified
- **Manual Testing** - Document manual test procedures for complex scenarios

### Deferred Testing (Document for Later)
- **Edge Case Coverage** - Document edge cases for future test implementation
- **Performance Testing** - Note performance requirements for later validation
- **Load Testing** - Plan for later implementation
- **Security Testing** - Beyond basic validation, plan comprehensive security testing

## Documentation Standards - standard

### Minimal Documentation Requirements
```markdown
# Project Name
## Purpose
What this does and why it exists.

## Quick Start
How to get it running in 2-3 steps.

## Key Decisions
Major technical decisions made (for future context).

## TODO/Known Issues
What needs to be done before production.
```

### Deferred Documentation
- **API Documentation** - Stub with basic examples, complete later
- **Architecture Diagrams** - Note key components, formalize later  
- **User Guides** - Basic usage examples sufficient
- **Deployment Guides** - Document deployment notes, formalize later

## Code Review - standard

### Streamlined Review Process
- **Focus on Safety** - Security, critical bugs, major architectural issues
- **Defer Polish** - Style, optimization, comprehensive error handling can wait
- **Document Decisions** - Capture reasoning for future enhancement
- **Quick Turnaround** - Reviews should not block rapid iteration

### standard Review Checklist
- [ ] Security basics covered (auth, input validation, secrets)
- [ ] Core functionality works as intended
- [ ] Critical error scenarios handled
- [ ] Technical debt is documented
- [ ] Next steps for production readiness noted

## Graduation to standard

### When to Transition
- Prototype proves concept and shows value
- Need for production deployment
- User base grows beyond initial testing
- Technical debt starts impacting development velocity

### Transition Requirements
- **Security Audit** - Comprehensive security review
- **Code Quality** - Refactor to meet standard standards
- **Documentation** - Complete all deferred documentation
- **Testing** - Implement comprehensive test coverage
- **Performance** - Address performance and scalability concerns

## AI Agent Guidelines for standard

### Code Generation
- Prioritize working code over perfect code
- Include TODO comments for future improvements
- Focus on core functionality, defer edge cases
- Generate basic tests for critical paths

### Code Review
- Flag security issues immediately
- Note technical debt without blocking
- Focus on functionality over style
- Suggest improvements for future enhancement

standard enables rapid innovation while maintaining the safety and quality foundations necessary for eventual production deployment.