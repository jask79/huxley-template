---
description: "👾 Debugger to hunt and fix bugs."
---

# Recent Changes Debug Command

Hunt for and fix bugs in the most recent file changes from the immediately prior message using the Debugger agent.

## Task

Perform proactive bug hunting on the files modified in your LAST action - not the whole session, just what you did moments ago.

## Your Role ({{ORCHESTRATOR_NAME}} Orchestration)

1. **Identify JUST the Most Recent Changes:**
   - Look at the LAST assistant message (immediately prior to this command)
   - Extract files from ONLY that message's tool calls (Edit/Write/NotebookEdit)
   - If no files modified in last message, report "No recent file changes"

2. **Get File Context:**
   - Run `git diff HEAD -- file1 file2 file3` to capture recent changes
   - For untracked files, read the full content directly
   - Understand what functionality was added/modified

3. **Prepare Debug Context:**
   - files_changed: ONLY the files from last message
   - change_context: What was implemented/modified
   - file_content: Full content of changed files
   - focus_areas: Areas most likely to have bugs

4. **Invoke Debugger Agent:**
   - Use Task tool with subagent_type="👾 Debugger"
   - Pass file paths and change context
   - Agent has full session context for understanding
   - But debug scope is ONLY the immediate prior changes

5. **Debugger Actions (Automatic):**
   - Hunt for common bug patterns:
     * Logic errors
     * Edge case failures
     * Null/undefined issues
     * Missing error handling
     * Race conditions
     * Performance problems
   - **Fix simple bugs directly** (Debugger has tools access)
   - **Delegate complex bugs** to specialists (Backend Dev, Frontend Dev, etc.)
   - Use Context7 for language-specific debugging techniques

6. **Present Results:**
   - Show bugs found count
   - Show bugs fixed count
   - List bugs fixed with file:line references
   - List complex bugs delegated to specialists
   - Include before/after code snippets for fixes

7. **NO Blocking:**
   - This is a fix operation, not a gate
   - Always complete successfully
   - Report any unfixable bugs for manual review

## Debug Scope

**Focus on the most recent changes:**
- NEW code is more likely to have bugs
- MODIFIED logic may have introduced issues
- Focus on areas touched in last message

**Common bug patterns to check:**
- Missing null/undefined checks
- Array index out of bounds
- Division by zero
- Unhandled promise rejections
- Missing error handling (try/catch)
- Resource leaks (unclosed files, connections)
- Race conditions in async code
- Type coercion issues
- Off-by-one errors

## Output Format

**If files were modified:**
```
👾 Recent Changes Debug Hunt
📝 Files Modified in Last Message: X
🔍 Debugging: [file1, file2, ...]

[Invoking 👾 Debugger agent...]

📊 Debug Results:
🐛 Bugs found: X
✅ Bugs fixed: Y
🔧 Delegated: Z

**Bugs Fixed:**
✅ [Bug description]
   📍 Location: file.py:123
   🔧 Fix: [Brief description of fix applied]
   📝 Before: [code snippet]
   📝 After: [code snippet]

**Complex Bugs Delegated:**
🔧 [Bug description]
   📍 Location: file.py:456
   👤 Delegated to: Backend Developer
   📝 Reason: [Why delegation was needed]

💡 Summary:
[Overall assessment of code stability after fixes]
```

**If no files modified in last message:**
```
👾 Recent Changes Debug Hunt
⚠️  No file modifications detected in the immediately prior message.

This command debugs only file changes from the last assistant action.
Use after Edit/Write/NotebookEdit operations.
```

## Example Usage

```bash
# After implementing a feature, hunt for bugs and fix them
/debug

# After fixing issues from code review, verify no new bugs
/debug

# After making changes, proactively find and fix issues
/debug
```

## When to Use

- Immediately after implementing new features
- After making complex logic changes
- After code review fixes (to catch introduced bugs)
- Before committing changes
- When you want proactive bug detection and fixes
- After refactoring code

## Debug Strategy

**Assume bugs exist:**
- New code almost always has bugs
- Proactively hunt rather than wait for failures
- Fix simple issues immediately
- Get specialist help for complex issues

**Language-specific debugging:**
- Use Context7 for language best practices
- Apply language-specific bug patterns
- Consider framework-specific issues

## Relationship to Code Review

**Proper workflow order:**
1. Implement feature
2. `/code-review` - Check code quality
3. Fix code quality issues
4. `/debug` - Hunt and fix bugs
5. `/validate` - Test functionality
6. Commit when all pass

**Why this order:**
- Quality issues make debugging harder
- Clean code is easier to debug
- Fix bugs before testing
- Validation confirms everything works

## Notes

- **Laser-focused** - ONLY the immediate prior message's file changes
- **Manual trigger only** - on-demand debugging when you want it
- **Automatic fixing** - Debugger fixes simple bugs directly
- **Smart delegation** - Complex bugs go to specialists
- **Context-aware** - Debugger has full session context
- **Language-agnostic** - Uses Context7 for any language
- **Proactive** - Assumes bugs exist and hunts for them

Proceed with proactive bug hunt and fix on most recent file modifications.
