# Global Coding Standards - Agent OS Base

These are the foundational coding standards that apply across all capsules in the Huxley system, providing consistent context for AI agents.

## Core Principles

### 1. Clarity Over Cleverness
- **Readable code** - Code should be self-documenting through clear naming and structure
- **Explicit intent** - Prefer explicit operations over implicit behavior
- **Consistent patterns** - Use established patterns rather than inventing new approaches

### 2. Function Design
- **Single Responsibility** - Each function should have one clear purpose
- **Pure Functions Preferred** - Minimize side effects, prefer pure functions where possible
- **Keep Functions Short** - Maximum 50 lines, prefer 10-20 lines
- **Clear Parameters** - Use typed parameters where language supports it

### 3. Error Handling
- **Fail Fast** - Validate inputs early and fail with clear messages
- **Explicit Error Handling** - Don't ignore errors, handle or propagate explicitly
- **Meaningful Error Messages** - Include context about what went wrong and why

### 4. Dependencies and Imports
- **Explicit Dependencies** - Make all dependencies clear and documented
- **Minimal Dependencies** - Only include dependencies that provide significant value
- **Version Pinning** - Pin dependency versions for reproducibility
- **Security Scanning** - All dependencies must pass security scanning

## Language-Agnostic Standards

### Naming Conventions
```
// Variables and functions: camelCase or snake_case (language convention)
userAccount, user_account

// Constants: UPPER_CASE
MAX_RETRY_COUNT, API_TIMEOUT

// Classes/Types: PascalCase
UserAccount, PaymentProcessor

// Files: kebab-case for multi-word files
user-account.js, payment-processor.py
```

### Documentation Requirements
- **Public APIs** - Must have comprehensive documentation
- **Complex Logic** - Explain the "why" not just the "what"
- **Configuration** - Document all configuration options and defaults
- **README Requirements** - Every module/component needs usage examples

### Testing Requirements
- **Unit Test Coverage** - Minimum 80% line coverage for business logic
- **Integration Tests** - Critical user flows must have integration test coverage
- **Error Scenarios** - Test error conditions and edge cases
- **Performance Tests** - Performance-critical code needs benchmark tests

## Security Standards (Non-Negotiable)

### Input Validation
- **Validate All Inputs** - Never trust external input
- **Parameterized Queries** - Use prepared statements for database queries
- **Output Encoding** - Encode output appropriately for context (HTML, JSON, etc.)

### Secrets Management
- **No Hardcoded Secrets** - Use environment variables or secure secret management
- **Rotate Credentials** - Regular rotation schedule for API keys and passwords
- **Principle of Least Privilege** - Grant minimum necessary permissions

### Dependencies
- **Vulnerability Scanning** - All dependencies scanned for known vulnerabilities
- **Regular Updates** - Keep dependencies updated with security patches
- **License Compliance** - Verify all dependency licenses are compatible

## Code Review Requirements

### Mandatory Reviews
- **All production code** - No code reaches production without review
- **Security-sensitive changes** - Additional security review required
- **Architecture changes** - Architectural review for significant changes

### Review Checklist
- [ ] Code follows established patterns and conventions
- [ ] Error handling is comprehensive and appropriate
- [ ] Tests cover new functionality and edge cases
- [ ] Documentation is updated for public APIs
- [ ] Security implications have been considered
- [ ] Performance impact has been evaluated

## AI Agent Context

### For Code Generation
- Follow these standards when generating code
- Include appropriate error handling and validation
- Generate accompanying tests for new functionality
- Add documentation for complex logic

### For Code Review
- Validate adherence to these standards
- Flag security concerns immediately
- Suggest improvements for clarity and maintainability
- Verify test coverage meets requirements

These standards provide the foundation for consistent, maintainable, and secure code across all Huxley capsules while enabling productive AI agent collaboration.