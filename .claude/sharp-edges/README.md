# Sharp Edges - Huxley Agent Gotcha Detection

Sharp Edges is a formalized system for documenting and detecting common gotchas, anti-patterns, and production pitfalls that agents should watch for.

## Concept

Inspired by VibeSHIP Spawner Skills, each agent has a corresponding sharp-edges file that documents:
- **Critical gotchas** that cause production failures
- **Warning patterns** that indicate potential issues
- **Info-level anti-patterns** that could lead to problems

## File Structure

```
.claude/sharp-edges/
├── README.md              # This file
├── _schema.yaml           # Schema definition
├── _loader.py             # Python loader utility
├── backend.yaml           # Backend Developer sharp edges
├── frontend.yaml          # Frontend Developer sharp edges
├── mobile.yaml            # Mobile Developer sharp edges
├── security.yaml          # Security Analyst sharp edges
├── automation.yaml        # Automator sharp edges
├── database.yaml          # Database patterns (shared)
└── api.yaml               # API patterns (shared)
```

## Schema

Each sharp-edge entry contains:

```yaml
- id: unique-identifier
  severity: critical | warning | info
  category: security | performance | correctness | maintainability | reliability
  pattern: "Human-readable description of what to watch for"
  detection:
    - type: regex | ast | semantic
      value: "detection pattern or description"
      files: ["*.py", "*.ts"]  # File patterns where applicable
  why: "Explanation of why this is a problem"
  fix: "How to fix or avoid this issue"
  examples:
    bad: "Example of problematic code"
    good: "Example of correct code"
  references:
    - "URL or documentation reference"
```

## Severity Levels

| Severity | Description | Code Review Action |
|----------|-------------|-------------------|
| **critical** | Will cause production failures, security vulnerabilities, or data loss | Block commit, require immediate fix |
| **warning** | Likely to cause bugs, performance issues, or maintenance problems | Flag for review, strong recommendation to fix |
| **info** | Could lead to issues, not following best practices | Note in review, optional fix |

## Categories

- **security**: Authentication, authorization, injection, secrets
- **performance**: N+1 queries, memory leaks, inefficient algorithms
- **correctness**: Logic errors, race conditions, null safety
- **maintainability**: Code smells, complexity, readability
- **reliability**: Error handling, timeouts, retry logic

## Integration with Code Reviewer

The Code Reviewer agent loads sharp-edges relevant to the files being reviewed:

1. Identify file types in the diff
2. Load applicable sharp-edges files
3. Apply detection patterns to changed code
4. Elevate findings based on severity
5. Include sharp-edge context in review output

## Adding New Sharp Edges

When adding new patterns:

1. Identify the appropriate agent file (or create new)
2. Use the schema format
3. Include detection patterns when possible
4. Document real examples from production
5. Test detection against known bad code

## Loading Sharp Edges (Python)

```python
from sharp_edges import load_sharp_edges, filter_for_files

# Load all sharp edges
edges = load_sharp_edges()

# Filter for specific file patterns
applicable = filter_for_files(edges, ['api/routes/user.py', 'lib/auth.ts'])

# Get by severity
critical = [e for e in applicable if e['severity'] == 'critical']
```

## Relationship to Heuristics

Sharp Edges complement the existing `reviewer_heuristics.json` system:

| System | Purpose | Source |
|--------|---------|--------|
| **Sharp Edges** | Known gotchas from industry/experience | Manually curated |
| **Heuristics** | Learned patterns from Huxley history | Auto-generated from quality.db |

Both are loaded during code review for comprehensive pattern detection.
