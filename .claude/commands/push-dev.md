---
description: Push to Development Branch
---

# Push to Development Branch

Commit changes and push to the development branch with secret detection and explicit file staging.

## Workflow

1. **Check branch** — ensure we're on or can reach `development`
2. **Scan for secrets** — abort if sensitive files detected in unstaged changes
3. **Review and stage explicitly** — no `git add -A`, stage files by name
4. **Commit** with conventional commit message
5. **Pull with rebase** from `origin/development`
6. **Push** to `origin/development`

## Step 1: Check State

```bash
git branch --show-current
git status --porcelain
```

If on a different branch, switch to `development` first:
```bash
git checkout development
```

## Step 2: Secret & Dangerous File Check (MANDATORY)

Before staging ANYTHING, scan the working tree for files that must NEVER be committed:

**Block patterns (abort and warn if found in changes):**
- `.env`, `.env.*` (except `.env.example`)
- `*.pem`, `*.key`, `*.p12`, `*.pfx` (private keys / certs)
- `credentials.json`, `service-account*.json`
- `tokens.json`, `*-token.json`, `*.keystore`
- `id_rsa`, `id_ed25519`, `*.pub` (SSH keys)
- Any file containing `sk-`, `sk_live_`, `AKIA`, `ghp_`, `gho_`, `xoxb-`, `xoxp-` patterns

**Warn patterns (flag but allow with user confirmation):**
- `node_modules/`, `__pycache__/`, `.venv/`, `venv/`
- `*.profraw`, `*.tgz`, `*.tar.gz`, `*.zip` (build artifacts)
- `*.sqlite`, `*.db` (databases)
- Files larger than 5MB

If ANY block-pattern file is found in the changeset:
1. List the offending files
2. **STOP. Do not stage or commit.**
3. Suggest adding them to `.gitignore`

## Step 3: Explicit File Staging

**NEVER use `git add -A` or `git add .`**

Instead:
1. Run `git status --porcelain` to get the full changelist
2. Review modified (`M`), added (`A`), deleted (`D`), and untracked (`??`) files
3. Stage files explicitly by name: `git add file1.py file2.ts ...`
4. For bulk staging of safe files, group by directory: `git add src/ lib/ tests/`
5. Show `git diff --cached --stat` to confirm what's staged

## Step 4: Commit

```bash
git diff --cached --stat
```

Generate a conventional commit message based on staged changes:
- `feat:` for new functionality
- `fix:` for bug fixes
- `chore:` for maintenance, cleanup, config
- `docs:` for documentation changes
- `refactor:` for restructuring without behavior change

Use HEREDOC format:
```bash
git commit -m "$(cat <<'EOF'
type: concise description

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>
EOF
)"
```

## Step 5: Pull with Rebase

```bash
git pull --rebase origin development
```

If conflicts occur:
1. Show conflicting files
2. Help resolve each conflict
3. `git rebase --continue` after each resolution
4. Never use `--abort` without asking

## Step 6: Push

```bash
git push origin development
```

Confirm successful push. Report the commit hash and branch state.
