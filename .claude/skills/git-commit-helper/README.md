# Git Commit Helper - User Guide

## Quick Start

When you're ready to commit changes:

```bash
# 1. Stage your changes
git add [files]

# 2. Ask {{ORCHESTRATOR_NAME}} for help
"Help me write a commit message"
# or
"Ready to commit"

# 3. {{ORCHESTRATOR_NAME}} analyzes your diff and suggests a conventional commit message

# 4. Review and commit
git commit -m "[suggested message]"
```

## What You Get

**Conventional commit messages** following industry best practices:
- Clear type classification (feat, fix, docs, refactor, etc.)
- Specific scope (based on your capsule context)
- Concise, imperative summary (<50 characters)
- Optional explanatory body
- Breaking change notation when needed

## Format

```
<type>(<scope>): <description>

[optional body explaining why, not what]

[optional footer with breaking changes or issue refs]
```

## Examples

### Simple Feature
```
feat(scraper): add rate limit handling
```

### Bug Fix with Explanation
```
fix(checkout): prevent duplicate order submissions

Race condition allowed users to submit payment twice
if they clicked the button rapidly. Now disables button
immediately on first click.

Fixes #123
```

### Breaking Change
```
refactor(api): migrate to JWT authentication

BREAKING CHANGE: Session cookies replaced with JWT tokens.
All API clients must include Authorization header.

Migration guide in docs/AUTH_MIGRATION.md
```

## Capsule-Specific Scopes

{{ORCHESTRATOR_NAME}} knows your capsule context and suggests appropriate scopes:

**example-social-capsule:** scraper, content, posting, engagement
**example-web-capsule:** products, checkout, inventory, shipping

Full scope mappings in `scope_mappings.yaml`

## Commit Types

| Type | Use When |
|------|----------|
| `feat` | Adding new feature |
| `fix` | Fixing a bug |
| `docs` | Documentation only |
| `style` | Formatting (no code change) |
| `refactor` | Code restructuring |
| `test` | Adding tests |
| `chore` | Maintenance |
| `perf` | Performance improvement |

## Best Practices

✅ **DO:**
- Use imperative mood: "add" not "added"
- Keep summary under 50 characters
- Explain motivation in body
- Reference issues: "Fixes #123"
- Mark breaking changes

❌ **DON'T:**
- Be vague: "update stuff"
- Use past tense: "added feature"
- Exceed 50 chars in summary
- Forget scope when obvious
- Skip body for complex changes

## Why This Matters

**Better history:**
```bash
git log --oneline
feat(auth): add OAuth2 login
fix(scraper): handle rate limits
docs(readme): update setup guide
```

**Easy changelog generation:**
```bash
# All features added
git log --grep="^feat"

# All bug fixes
git log --grep="^fix"
```

**Clear communication:**
Team (or future you) knows exactly what changed and why.

## Integration

Commit messages become part of Huxley quality gates:
- Required for capsule completion
- Used in changelog generation
- Tracked in metrics
- Enables automated release notes
