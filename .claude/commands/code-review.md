---
description: "🧐 Code Reviewer to check work."
---

# Recent Changes Code Review Command

Review ONLY the most recent file changes from the immediately prior message using the Code Reviewer agent.

## Task

Perform a focused code review of the files modified in your LAST action - not the whole session, just what you did moments ago.

## Your Role ({{ORCHESTRATOR_NAME}} Orchestration)

1. **Identify JUST the Most Recent Changes:**
   - Look at the LAST assistant message (immediately prior to this command)
   - Extract files from ONLY that message's tool calls (Edit/Write/NotebookEdit)
   - If no files modified in last message, report "No recent file changes"

2. **Get Precise Diffs:**
   - Run `git diff HEAD -- file1 file2 file3` to capture staged + unstaged
   - For untracked files, read the full content directly
   - Combine for complete picture of all local changes

3. **Prepare Focused Review Context:**
   - files_changed: ONLY the files from last message
   - git_diff: ONLY diffs/content for those files
   - context_level: Always "lightweight" (manual quick-check use case)
   - static_analysis: Optional, only on those files

4. **Invoke Code Reviewer Agent:**
   - Use Task tool with subagent_type="🧐 Code Reviewer"
   - Pass narrowly scoped review context
   - Agent still has full session context for understanding
   - But review scope is ONLY the immediate prior changes

5. **Present Findings:**
   - Show severity breakdown (Critical, Major, Minor)
   - Highlight actionable recommendations
   - Include file:line references
   - Report technical debt estimation

6. **NO Commit Blocking:**
   - This is informational only
   - DO NOT exit with error codes
   - Always allow user to proceed

## Context Level (Always Lightweight)

Manual `/code-review` **always uses lightweight review** because:
- User-triggered (not automatic gate)
- Informational only (no blocking)
- Immediate feedback loop (speed matters)
- Quick quality check on recent work

**Note:** Automatic pre-commit reviews use comprehensive mode for Huxley-specific files and large changes. This command is for fast manual checks.

## Static Analysis (Optional)

Run quick static checks on changed files if tools available:
```bash
for file in "${changed_files[@]}"; do
  case "$file" in
    *.py) ruff check "$file" 2>/dev/null || true ;;
    *.js|*.ts|*.jsx|*.tsx) eslint "$file" 2>/dev/null || true ;;
    *.sh) shellcheck "$file" 2>/dev/null || true ;;
  esac
done
```

**Pass results to reviewer if available, otherwise skip** - AI review is primary.

## Output Format

**If files were modified:**
```
🔍 Recent Changes Code Review
📝 Files Modified in Last Message: X
📊 Reviewing: [file1, file2, ...]

[Invoking 🧐 Code Reviewer agent...]

📋 Review Results:
✅ Critical: 0
⚠️  Major: Y
ℹ️  Minor: Z

[Detailed findings with file:line references...]

💡 Recommendations:
[Actionable next steps...]
```

**If no files modified in last message:**
```
🔍 Recent Changes Code Review
⚠️  No file modifications detected in the immediately prior message.

This command reviews only file changes from the last assistant action.
Use after Edit/Write/NotebookEdit operations.
```

## Example Usage

```bash
# After making some edits, review just those changes
/code-review

# That's it - no arguments needed
```

## When to Use

- Immediately after making file changes
- Quick quality check on your last action
- Before staging/committing specific changes
- When unsure about code you just wrote
- Learning opportunity to improve recent work

## Relationship to Automatic Reviews

- **This command (manual)**: User-triggered, informational, always lightweight, fast feedback
- **Stop hook (automatic)**: Codex diff review after each code-touching turn
- **Use both**: Run `/code-review` during development; the Stop hook reviews each turn automatically
- **Same agent**: Both use 🧐 Code Reviewer with same quality standards

## Notes

- **Laser-focused** - ONLY the immediate prior message's file changes
- **Manual trigger only** - not automatic like the Stop-hook review
- **No blocking behavior** - informational feedback only
- **Fast** - small scope + lightweight mode = quick review
- **Context-aware** - reviewer still has full session context for understanding
- **Uses same Code Reviewer agent** as automatic reviews
- **Respects project type** - personal vs commercial standards

Proceed with focused code review of most recent file modifications.
