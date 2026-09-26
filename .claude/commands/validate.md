---
description: "🧪 Validator to test functionality."
---

# Functional Validation Command

Validate ONLY the most recent file changes from the immediately prior message using the Validator agent to test functionality.

## Task

Perform functional testing and validation of the features modified in your LAST action - not the whole session, just what you did moments ago.

## Your Role ({{ORCHESTRATOR_NAME}} Orchestration)

1. **Identify JUST the Most Recent Changes:**
   - Look at the LAST assistant message (immediately prior to this command)
   - Extract files from ONLY that message's tool calls (Edit/Write/NotebookEdit)
   - If no files modified in last message, report "No recent file changes"

2. **Determine Validation Scope:**
   - Identify platform/type from file extensions:
     - `.tsx`, `.jsx`, `.js`, `.ts`, `.html`, `.css` → Web application (frontend-testing skill)
     - `.swift`, `.m`, `.h` → iOS application (ios-testing skill)
     - `.py`, `.go`, `.rs`, `.java` → Backend API testing
     - `.json` (n8n workflows) → Workflow testing
   - Determine test scope based on changes

3. **Get Change Context:**
   - Run `git diff HEAD -- file1 file2 file3` to capture changes
   - For untracked files, read the full content directly
   - Understand what functionality changed

4. **Invoke Validator Agent:**
   - Use Task tool with subagent_type="🧪 Validator"
   - Pass validation context including:
     - files_changed: ONLY the files from last message
     - change_summary: What functionality was added/modified
     - platform: web/ios/backend/workflow
     - validation_type: functional/integration/e2e
   - Agent has full session context for understanding
   - Validator will automatically use appropriate testing skills

5. **Present Test Results:**
   - Show test execution summary (passed/failed/skipped)
   - Highlight any test failures with details
   - Include evidence (screenshots, logs, traces)
   - Provide actionable recommendations for fixes

6. **NO Blocking:**
   - This is informational only
   - DO NOT exit with error codes
   - Always allow user to proceed
   - Tests provide feedback, not gates

## Validation Scope (Platform-Specific)

**Web Applications:**
- Use frontend-testing skill automatically
- Run quick verification tests
- Check console errors
- Validate core functionality
- Screenshot evidence

**iOS Applications:**
- Use ios-testing skill automatically
- Build and run on simulator
- Test UI functionality
- Check for crashes/errors
- Capture simulator screenshots

**Backend APIs:**
- Use playwright MCP for API testing
- Validate endpoints
- Check response codes
- Test data validation

**n8n Workflows:**
- Use n8n-mcp for workflow validation
- Test trigger functionality
- Validate data transformations
- Check error handling

## Output Format

**If files were modified and tests run:**
```
🧪 Functional Validation
📝 Files Modified in Last Message: X
🎯 Platform: [Web/iOS/Backend/Workflow]
📊 Testing: [file1, file2, ...]

[Invoking 🧪 Validator agent...]

📋 Test Results:
✅ Passed: X
❌ Failed: Y
⏭️  Skipped: Z

[Test execution details...]

**Failed Tests:**
❌ [Test name]
   🐛 Issue: [Description]
   📍 Location: [File:line or URL]
   🔬 Root Cause: [Analysis]
   📸 Evidence: [Screenshot/log]

💡 Recommendations:
[Actionable fixes for failures...]

⏱️ Duration: Xms
```

**If no files modified in last message:**
```
🧪 Functional Validation
⚠️  No file modifications detected in the immediately prior message.

This command validates only file changes from the last assistant action.
Use after Edit/Write/NotebookEdit operations.
```

**If validation not applicable:**
```
🧪 Functional Validation
ℹ️  Recent changes don't require functional testing:
- Documentation updates
- Configuration changes
- Non-functional code

Use /code-review for quality checks on these changes.
```

## Example Usage

```bash
# After implementing a new feature, test it
/validate

# After fixing a bug, verify the fix works
/validate

# After UI changes, validate functionality
/validate
```

## When to Use

- Immediately after implementing new features
- After fixing bugs (verify the fix works)
- After UI/UX changes (test user flows)
- After API changes (validate endpoints)
- Before committing functional changes
- When unsure if your changes actually work

## Validation Strategy

**Quick Validation (Default):**
- Smoke tests on changed functionality
- Core user flows affected by changes
- Fast feedback (<30 seconds)

**Comprehensive Validation (When Needed):**
- Full test suite for affected modules
- Integration tests
- E2E user journeys
- Performance validation

Validator decides scope based on:
- Extent of changes
- Criticality of functionality
- Available test coverage
- Time constraints

## Relationship to Code Review

**Proper workflow order:**
1. `/code-review` - Check code quality first
2. Fix any code quality issues
3. `/validate` - Test functionality last
4. Fix any test failures
5. Commit when both pass

**Why this order:**
- No point testing buggy code
- Code quality affects testability
- Validation is the final gate
- Ensures working, quality code

## Notes

- **Laser-focused** - ONLY the immediate prior message's file changes
- **Manual trigger only** - on-demand validation when you want it
- **No blocking behavior** - informational feedback only
- **Platform-aware** - automatically uses correct testing approach
- **Uses testing skills** - frontend-testing, ios-testing when applicable
- **Context-aware** - validator has full session context
- **Evidence-based** - includes screenshots, logs, traces
- **Actionable** - provides clear recommendations for failures

Proceed with functional validation of most recent file modifications.
