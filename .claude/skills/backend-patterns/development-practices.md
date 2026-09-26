# Backend Development Practices

TDD workflow, git worktrees, and safety patterns for backend development.

## Test-Driven Development (TDD)

### The TDD Cycle

```
1. RED: Write a failing test for desired behavior
2. GREEN: Write minimal code to make test pass
3. REFACTOR: Improve code while keeping tests green
```

### API Endpoint TDD

```python
# 1. RED - Write test first
def test_create_user_returns_201():
    response = client.post("/users", json={"email": "test@example.com"})
    assert response.status_code == 201
    assert "id" in response.json()

# 2. GREEN - Minimal implementation
@app.post("/users", status_code=201)
def create_user(user: UserCreate):
    new_user = db.users.create(user)
    return {"id": new_user.id}

# 3. REFACTOR - Add validation, error handling
```

### Database Migration TDD

```python
# 1. RED - Test migration behavior
def test_add_verification_status_column():
    apply_migration("add_verification_status")
    result = db.execute("SELECT verification_status FROM users LIMIT 1")
    assert result is not None

# 2. GREEN - Create migration
# ALTER TABLE users ADD COLUMN verification_status text DEFAULT 'pending';
```

### Test Commands

**FastAPI/Python:**
```bash
pytest --watch src/tests/
pytest src/tests/test_users.py -v
pytest --cov=src --cov-report=html
```

**Node.js/Express:**
```bash
npm test -- --watch
npm test -- users.test.ts
npm test -- --coverage
```

**Go:**
```bash
go test ./...
go test -cover ./...
go test -v ./handlers/...
```

### TDD Anti-Patterns

**AVOID:**
- Writing implementation first
- Too many tests before any implementation
- Testing implementation details
- Skipping refactor step
- Tests depending on other tests' state

**DO:**
- Test public API/behavior
- Use fixtures and factories
- Keep tests isolated
- Run tests frequently
- Refactor both code AND tests

---

## Git Worktrees

Work on multiple branches simultaneously without switching.

### Why Worktrees?

- Fix hotfix while feature in progress
- Run tests on one branch while developing another
- Keep main deployable in separate directory
- No stashing, no context switching

### Basic Commands

```bash
# Create worktree for existing branch
git worktree add ../project-feature-auth feature/auth

# Create new branch in worktree
git worktree add -b feature/payments ../project-payments

# List worktrees
git worktree list

# Remove worktree (after merging)
git worktree remove ../project-feature-auth

# Prune stale references
git worktree prune
```

### Directory Structure

```
~/projects/
├── my-api/              # Main (main branch)
├── my-api-feature-auth/ # Feature worktree
└── my-api-hotfix/       # Hotfix worktree
```

### Hotfix Workflow

```bash
# Deep in feature work... urgent bug reported!

# Create hotfix worktree (don't lose feature context)
git worktree add -b hotfix/auth-bypass ../api-hotfix main

# Fix in hotfix worktree
cd ../api-hotfix
# ... fix, test, commit ...
git push origin hotfix/auth-bypass

# Return to feature work - context preserved
cd ../my-api
```

### Best Practices

**DO:**
- Use descriptive directory names
- Remove worktrees after merge
- Keep worktrees in sibling directories
- Use separate .env files per worktree

**DON'T:**
- Create worktrees inside main repo
- Forget to remove worktrees
- Share node_modules/venv between worktrees

---

## Backend Safety Patterns

### Database Operation Safety

| Operation | Risk | Safeguard |
|-----------|------|-----------|
| `DROP TABLE` | Data loss | Backup + confirmation |
| `DELETE FROM` (no WHERE) | Data loss | Always require WHERE |
| `TRUNCATE TABLE` | Data loss | Backup first |
| `ALTER TABLE DROP COLUMN` | Schema change | Test on copy first |
| `UPDATE` (no WHERE) | Data corruption | Always require WHERE |

### Pre-Migration Safety

```bash
# ALWAYS backup before migration
pg_dump -Fc $DATABASE_URL > backup_$(date +%Y%m%d_%H%M%S).dump

# Test migration on local first
supabase db reset  # Only on local!
supabase migration up

# Verify with lint
supabase db lint
```

### Safe DELETE Pattern

```sql
-- Step 1: Count affected rows
SELECT COUNT(*) FROM users WHERE created_at < '2024-01-01';

-- Step 2: Preview data to delete
SELECT * FROM users WHERE created_at < '2024-01-01' LIMIT 10;

-- Step 3: Delete in transaction (can rollback)
BEGIN;
DELETE FROM users WHERE created_at < '2024-01-01';
-- Verify: SELECT COUNT(*) FROM users;
-- If wrong: ROLLBACK;
-- If correct: COMMIT;
```

### Git Safety

```bash
# Before force push - create safety branch
git branch safety-backup-$(date +%Y%m%d) HEAD
git push --force origin feature-branch  # Never force push main!

# Before hard reset - preserve changes
git stash push -m "pre-reset-$(date +%Y%m%d)"
git reset --hard origin/main

# Recovery
git reflog  # Find lost commits
git stash list  # Find stashed changes
```

### Deployment Safety Checklist

```markdown
### Pre-Deploy
- [ ] All tests passing locally
- [ ] Migration tested on staging
- [ ] Database backup created
- [ ] Rollback plan documented
- [ ] Feature flags in place

### During Deploy
- [ ] Monitor error rates
- [ ] Watch performance
- [ ] Verify critical paths

### Post-Deploy
- [ ] Smoke test production
- [ ] Monitor for 15 minutes
- [ ] Confirm rollback not needed
```

### Rollback Commands

```bash
# Vercel rollback
vercel rollback [deployment-url]

# Database rollback
supabase migration repair --status reverted <version>

# Feature flag emergency disable
curl -X POST api/feature-flags/disable -d '{"flag": "new-feature"}'
```

### Environment Safety

```bash
# Add to shell profile
production_guard() {
  if [[ "$DATABASE_URL" == *"production"* ]] || [[ "$NODE_ENV" == "production" ]]; then
    echo "PRODUCTION DETECTED - Confirm? [yes/N]"
    read confirm
    [[ "$confirm" == "yes" ]] || return 1
  fi
}

# Usage
production_guard && psql -c "DELETE FROM logs WHERE created_at < NOW() - INTERVAL '30 days'"
```

### Recovery Procedures

```bash
# Database recovery
pg_restore -d $DATABASE_URL backup.dump

# Git recovery
git reflog
git checkout -b recovered <commit-hash>

# Recover from bad merge
git reset --hard HEAD~1  # Undo last commit
# Or revert (keeps history)
git revert HEAD
```
