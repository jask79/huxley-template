# {capsule_name}

<!--
CAPSULE CLAUDE.md TEMPLATE
This template defines the standard structure for capsule-level CLAUDE.md files.

Options:
1. AUTO-GENERATE from YAML: Use `python3 tools/generate_claude_md.py <capsule>`
2. MANUAL: Copy this template and fill in sections

For auto-generation, create `specs/current.yaml` in your capsule directory first.
-->

## Purpose
{One paragraph describing what this capsule does and why it exists.}

## Current Status
- **Status:** {active|parked|archived}
- **Version:** {semantic version}

## Technical Overview

**Stack:**
- {Primary framework/platform}
- {Languages}
- {Key libraries/APIs}

**Dependencies:**

*External:*
- {External APIs, services}

*Internal (Huxley):*
- {Other capsules this depends on}
- {Huxley infrastructure used}

## Key Features
1. {Feature 1}
2. {Feature 2}
3. {Feature 3}

## Architecture Notes

**Components:**
- **{component_name}:** {Brief description}

**Integration Points:**
- {How this capsule connects to other systems}

## Quality Standards

**Performance Targets:**
- {Measurable performance requirements}

**Testing Requirements:**
- {What must be tested before deployment}

## Data & Storage

**Storage:**
- **{directory}/:** {What's stored here}

**Retention Policies:**
- {Data type}: {retention period and reason}

## Maintenance

**Schedule:** {continuous|daily|weekly|monthly|as-needed}

**Monitoring:**
- {What metrics are tracked}

**Automated Tasks:**
- {Scheduled jobs, cron tasks}

## Specialist Routing

When working in this capsule, route to:
- {Task type} → {Specialist agent}

---
*Capsule created: {date}*
*Last updated: {date}*
