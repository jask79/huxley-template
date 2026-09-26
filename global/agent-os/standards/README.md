# Agent OS Global Standards System

This directory contains the centralized standards enforcement system for Agent OS integration across all Huxley capsules.

## Standards Hierarchy

### 1. Global Standards (`/global/agent-os/standards/`)
- **Base coding standards** - Language-agnostic fundamental principles
- **Architecture patterns** - Standard architectural approaches
- **Security baseline** - Minimum security requirements
- **Documentation standards** - Consistent documentation patterns

### 2. Lane Standards (`/global/agent-os/standards/lanes/`)
- **standard/** - Standards for rapid prototyping and iteration
- **standard/** - Standards for production-ready, comprehensive development

### 3. Branch Standards (`/global/agent-os/standards/branches/`)
- **web/** - Web development specific standards
- **mobile/** - Mobile development (iOS/Android) standards  
- **desktop/** - Desktop application standards
- **automation/** - Workflow automation standards

### 4. Capsule-Specific Standards (`capsule/.agent-os/standards/`)
- Inherits from global → lane → branch hierarchy
- Adds project-specific customizations
- Cannot relax global security or quality requirements

## Standards Enforcement

### Automatic Inheritance
```yaml
# Standards resolution order:
1. capsule/.agent-os/standards/
2. global/agent-os/standards/branches/{branch}/
3. global/agent-os/standards/lanes/{lane}/
4. global/agent-os/standards/base/
```

### Validation Pipeline
- Pre-commit hooks validate against applicable standards
- Agent context includes relevant standards for each task
- DoD validation includes standards compliance checking

### Customization Rules
- **Security standards**: Cannot be relaxed at capsule level
- **Quality gates**: Cannot be bypassed, only enhanced
- **Documentation requirements**: Must meet minimums, can exceed
- **Testing standards**: Coverage minimums enforced globally

## Standards Categories

### Code Quality
- Formatting and style consistency
- Code complexity thresholds
- Naming conventions
- Comment and documentation requirements

### Security
- Authentication and authorization patterns  
- Data handling requirements
- Dependency management policies
- Vulnerability scanning thresholds

### Architecture
- Separation of concerns principles
- Integration patterns and APIs
- Error handling approaches
- Performance considerations

### Testing
- Coverage requirements by lane
- Test type requirements (unit, integration, e2e)
- Quality gates and automation
- Performance testing standards

This system ensures consistent, high-quality development across all capsules while allowing appropriate customization for specific project needs.