---
name: git-commit-helper
description: Generate conventional commit messages by analyzing git diffs and Huxley capsule context
when: User has staged changes and is ready to commit, or asks for help with commit message
allowed-tools:
  - Bash
  - Read
metadata:
  version: "1.0.0"
  convention: "conventional-commits"
  governance: "Enforces Huxley commit quality standards"
  capsule_aware: true
  last_updated: "2025-10-20"
---

# Git Commit Helper

## Purpose
Analyze git diffs and generate high-quality conventional commit messages that follow Huxley standards and capsule-specific patterns.

## Trigger Conditions
- User stages changes: `git add [files]`
- User asks: "help me write a commit message"
- User says: "ready to commit"
- Before executing `git commit` in Huxley workflow

## Conventional Commits Format

```
<type>(<scope>): <description>

[optional body]

[optional footer]
```

### Commit Types

| Type | When to Use | Example |
|------|-------------|---------|
| `feat` | New feature or capability | `feat(auth): add OAuth2 login support` |
| `fix` | Bug fix | `fix(scraper): handle rate limit errors` |
| `docs` | Documentation only | `docs(readme): update installation steps` |
| `style` | Formatting, no code changes | `style(ui): adjust button spacing` |
| `refactor` | Code restructuring, same behavior | `refactor(api): extract validation logic` |
| `test` | Adding or updating tests | `test(checkout): add payment flow tests` |
| `chore` | Maintenance, dependencies | `chore(deps): update Python to 3.11` |
| `perf` | Performance improvements | `perf(db): add index on user_id` |
| `ci` | CI/CD changes | `ci(github): add automated testing` |
| `build` | Build system changes | `build(vite): configure path aliases` |

### Breaking Changes

Use `BREAKING CHANGE:` in footer for incompatible changes:

```
refactor(api): change authentication endpoint structure

BREAKING CHANGE: API endpoints moved from /auth/* to /api/v2/auth/*
Migration: Update all auth API calls to use new base path.
```

## Workflow

### Step 1: Analyze Staged Changes

```bash
# Check what's staged
git status

# Review the diff
git diff --staged

# If working in capsule, note capsule context
pwd  # e.g., {{CATALYST_ROOT}}/capsules/example-social-capsule
```

### Step 2: Identify Change Type and Scope

**Type Selection:**
- New functionality → `feat`
- Fixing broken behavior → `fix`
- Code cleanup/restructuring → `refactor`
- Adding tests → `test`
- Updating docs → `docs`
- Other maintenance → `chore`

**Scope Selection:**

**Capsule-Specific Scopes:**
```yaml
example-social-capsule:
  - scraper      # Scraping logic
  - content      # Content generation
  - posting      # Post scheduling/automation
  - engagement   # Likes, comments, follows

example-web-capsule:
  - products     # Product catalog
  - checkout     # Payment flow
  - inventory    # Stock management
  - shipping     # Order fulfillment

Huxley (system):
  - agents       # Agent definitions
  - skills       # Skill implementations
  - tools        # CLI tools
  - governance   # Governance framework
  - registry     # Agent registry
  - memory       # MCP memory system
  - workflow     # Workflow engine
```

**Generic Scopes (when no capsule-specific scope fits):**
- `core` - Core functionality
- `api` - API layer
- `ui` - User interface
- `db` - Database
- `auth` - Authentication
- `config` - Configuration
- `deps` - Dependencies

### Step 3: Compose Summary Line

**Rules:**
- **Imperative mood** - "add feature" not "added feature" or "adds feature"
- **Lowercase** - Start with lowercase after scope
- **No period** - Don't end with period
- **Under 50 chars** - Keep concise
- **Specific** - Avoid vague words like "update" or "fix stuff"

**Good Examples:**
```
feat(scraper): add rate limit handling
fix(checkout): prevent duplicate order submissions
refactor(api): extract validation to middleware
docs(readme): add deployment instructions
```

**Bad Examples:**
```
feat: update stuff                    # Too vague
Fix the Bug in checkout              # Not imperative, poor case
refactor(api): Refactored the code   # Not imperative
feat(checkout): adds a new feature that allows users to... # Too long
```

### Step 4: Add Optional Body

**When to add body:**
- Change is not obvious from summary
- Needs explanation of motivation
- Multiple files changed
- Complex refactoring

**Body Guidelines:**
- Explain **why**, not what (diff shows what)
- Wrap at 72 characters
- Separate from summary with blank line
- Use bullet points for multiple changes

**Example:**
```
feat(auth): add OAuth2 login support

Implements GitHub OAuth2 authentication flow as alternative
to username/password login. This reduces friction for new
users and improves security by leveraging GitHub's auth.

- Add OAuth2 client configuration
- Create callback handler route
- Store OAuth tokens in session
- Update login UI with GitHub button
```

### Step 5: Add Footer (if needed)

**Breaking Changes:**
```
BREAKING CHANGE: Authentication endpoints moved to /api/v2/auth/
Migration guide available in docs/MIGRATION.md
```

**Issue References:**
```
Closes #123
Fixes #456
See also #789
```

**Co-authors:**
```
Co-authored-by: Claude <noreply@anthropic.com>
```

## Huxley Integration

### Capsule-Aware Scopes

When working in a capsule, automatically suggest capsule-specific scopes:

```
[In {{CATALYST_ROOT}}/capsules/example-social-capsule]

User: "Ready to commit"

{{ORCHESTRATOR_NAME}} analyzes:
- Modified: src/scraper/instagram.py
- Capsule: example-social-capsule
- Scope options: scraper, content, posting, engagement

Suggests: fix(scraper): handle Instagram rate limit errors
```

### Quality Gate Integration

Commit messages become part of capsule quality standards:

```yaml
# capsules/example-social-capsule/ops/dod.yaml
commit_standards:
  - conventional_commits: required
  - scope_from_capsule: preferred
  - max_summary_length: 50
  - breaking_changes_documented: required
```

### Changelog Generation

Well-formed commits enable automatic changelog generation:

```bash
# Generate changelog from commits
git log --pretty=format:"%s" --grep="^feat" > CHANGELOG.md
```

## Advanced Patterns

### Interactive Staging

For precise, atomic commits:

```bash
# Stage changes selectively
git add -p

# Review what's staged
git diff --staged

# Commit this specific change
git commit  # skill generates appropriate message
```

### Amending Commits

```bash
# Amend last commit message
git commit --amend

# Skill helps rewrite with better format
```

### Multi-File Commits

When multiple files change for one logical purpose:

```
feat(user-profile): add avatar upload feature

Implements complete avatar upload workflow:
- Add ProfilePicture component (UI)
- Create ImageUploadService (API)
- Update UserModel with avatar_url field (DB)
- Add S3 integration for storage

All tests passing, ready for review.
```

## Examples

### Example 1: Feature Addition
```
feat(posting): add scheduled post queue

Implements post scheduling with configurable intervals.
Users can now queue posts for future publishing instead
of posting immediately.

- Add ScheduledPost model with timestamp
- Create queue processor background task
- Update UI with scheduling calendar picker

Closes #42
```

### Example 2: Bug Fix
```
fix(scraper): prevent timeout on large profiles

Instagram profiles with 10K+ followers were timing out
during scraping due to pagination limits. Now implements
chunked fetching with progress tracking.

Fixes #67
```

### Example 3: Refactoring
```
refactor(api): extract validation to middleware

Moves request validation from individual route handlers
to centralized middleware for consistency and DRY.
No behavior changes, purely structural cleanup.
```

### Example 4: Breaking Change
```
refactor(auth): migrate to JWT from session cookies

BREAKING CHANGE: Authentication now uses JWT tokens instead
of session cookies. Clients must include Authorization header
with Bearer token in all authenticated requests.

Migration guide:
1. Update API client to store JWT token from /login
2. Add Authorization: Bearer <token> to all requests
3. Handle 401 responses by re-authenticating

See docs/AUTH_MIGRATION.md for full details.
```

### Example 5: Documentation
```
docs(skills): document git-commit-helper workflow

Adds comprehensive guide for using git-commit-helper skill
including conventional commits format, scope selection,
and Huxley-specific patterns.
```

## Quality Checklist

Before finalizing commit message, verify:

- [ ] Type is appropriate (feat, fix, refactor, etc.)
- [ ] Scope is specific and accurate
- [ ] Summary is under 50 characters
- [ ] Summary uses imperative mood
- [ ] Summary is lowercase (except proper nouns)
- [ ] Summary doesn't end with period
- [ ] Body explains motivation, not implementation
- [ ] Body is wrapped at 72 characters
- [ ] Breaking changes are clearly marked
- [ ] Issue references are included
- [ ] Capsule-specific scope used (when applicable)

## Error Handling

### Common Issues

**Issue: Summary too long**
```
❌ feat(checkout): add a new payment processing system with Stripe integration and webhook handling
✅ feat(checkout): add Stripe payment processing
```

**Issue: Not imperative mood**
```
❌ fix(api): fixed the bug in validation
✅ fix(api): correct validation logic
```

**Issue: Too vague**
```
❌ chore: update stuff
✅ chore(deps): update Python to 3.11
```

**Issue: Missing scope when obvious**
```
❌ feat: add login
✅ feat(auth): add OAuth2 login
```

## Integration with Huxley Git Workflow

### Pre-Commit Hook (Optional)

```bash
#!/bin/bash
# .git/hooks/prepare-commit-msg

# If commit message is empty or default, trigger skill
if [ ! -s "$1" ] || grep -q "^#" "$1"; then
    echo "💡 {{ORCHESTRATOR_NAME}} suggests running git-commit-helper skill"
fi
```

### Capsule Template

New capsules include commit guidelines:

```
capsules/[new-capsule]/docs/CONTRIBUTING.md

# Commit Message Guidelines

This capsule follows Huxley conventional commits format.
Use git-commit-helper skill for assistance:

1. Stage your changes: `git add [files]`
2. Ask {{ORCHESTRATOR_NAME}}: "Help me write a commit message"
3. Review suggested message
4. Commit: `git commit -m "[suggested message]"`
```

## Metrics & Learning

Track commit quality over time:

```bash
# View commit history
git log --oneline --decorate --graph

# Count commits by type
git log --pretty=format:"%s" | grep -o "^[a-z]*" | sort | uniq -c

# Find commits without conventional format
git log --pretty=format:"%s" | grep -v "^[a-z]*("
```

## Future Enhancements

**Planned:**
1. Auto-detect scope from file paths
2. Suggest related issue numbers from context
3. Learning system: improve suggestions based on past commits
4. Integration with changelog generator
5. Commit message templates per capsule type

---

## Quick Reference

**Trigger:** Stage changes and ask for commit message help

**Workflow:**
1. `git diff --staged` - Review changes
2. Identify type (feat/fix/refactor/etc.)
3. Choose scope (capsule-specific if applicable)
4. Compose summary (<50 chars, imperative mood)
5. Add body if needed (explain why)
6. Mark breaking changes in footer

**Format:** `type(scope): description`

**Example:** `feat(scraper): add rate limit handling`
