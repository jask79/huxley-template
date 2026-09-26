# Operating Specifications (Lazy-Loaded Section)
<!-- Last updated: 2026-02-24 -->

## Operating Specifications

### Completion Requirements
**Quality Standards:**
- Meets functional requirements
- Complete documentation & handoff
- Passes validation and performance tests

### Apple Development Pipeline
- iOS/macOS apps **automatically** get Xcode projects created
- Always link source files, never copy (use `/tools/create_linked_xcode_project.py`)

### Specification Tools (GitHub Spec-Kit Enhanced)
**Schema Validation:**
- Validate specs: `tools/validate_specs.py <capsule>` or `--all`
- Checks required fields, data types, cross-file consistency

**Documentation Generation:**
- Generate docs: `tools/generate_spec_docs.py <capsule>` or `--all`
- Creates `docs/SPECIFICATIONS.md` from YAML specifications


---

## Huxley Cost Analysis Framework

**CRITICAL:** Claude Code handles ALL development. **Never calculate labor costs.**

### What to Include

**Real costs only:**
- API fees (per-request, subscriptions)
- Infrastructure (hosting, servers, storage)
- Software subscriptions

**Time as context (NOT cost):**
- Claude hours needed
- Complexity (simple/moderate/complex)
- Maintenance burden (low/medium/high)

**NEVER include:**
- ❌ Developer hourly rates
- ❌ "Time = money" calculations
- ❌ Hypothetical consulting fees

### Key Principles

1. **Real costs only** - What comes out of bank account?
2. **Time = context** - Hours needed, not dollar value
3. **Growth awareness** - When will free tier be exceeded?
4. **Maintenance burden** - Ongoing work needed
