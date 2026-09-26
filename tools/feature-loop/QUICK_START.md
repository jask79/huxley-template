# Feature Loop - Quick Start Guide

Get started with autonomous feature development in 5 minutes.

## Step 1: Create a PRD

Create a JSON file describing your feature:

```bash
cat > tasks/my-feature.json <<'JSON'
{
  "feature": "My First Feature",
  "branch": "feature/my-first",
  "maxIterations": 5,
  "governance": {
    "requireValidation": true,
    "notifyOnComplete": true,
    "costAlertThreshold": 3
  },
  "tasks": [
    {
      "id": "FEAT-001",
      "title": "Create API endpoint",
      "description": "Build a simple GET /hello endpoint that returns JSON",
      "specialist": "Backend Dev",
      "priority": 1,
      "acceptanceCriteria": [
        "Returns 200 status code",
        "Returns JSON with 'message' field"
      ],
      "passes": false,
      "completedAt": null,
      "learnings": []
    }
  ]
}
JSON
```

**Tip:** Copy `tools/feature-loop/prd-example.json` as a starting template.

## Step 2: Run the Loop

```bash
# Via Claude Code skill (recommended)
/feature-loop tasks/my-feature.json

# Or directly via script
./tools/feature-loop/loop.sh tasks/my-feature.json
```

## Step 3: Monitor Progress

```bash
# Watch the progress log in real-time
tail -f tools/feature-loop/runs/feature-my-first/progress.log

# Check task completion status
cat tasks/my-feature.json | jq '.tasks[] | {id, title, passes}'
```

## Step 4: Review Results

When complete, you'll see:
- ✅ macOS notification (if enabled)
- All tasks marked `passes: true` in PRD
- Learnings captured in each task
- Complete audit trail in progress log

## Next Steps

- **Iterate**: Review learnings, adjust PRD, run again
- **Scale**: Add more tasks to the same PRD
- **Learn**: Check Agent Memory for stored patterns
- **Validate**: Review code changes with Code Reviewer

## Troubleshooting

**Loop won't start?**
```bash
# Check PRD syntax
jq empty tasks/my-feature.json
```

**Task stuck?**
```bash
# Check iteration output
cat tools/feature-loop/runs/feature-my-first/iteration-N-output.txt
```

**Need help?**
```bash
# Read full documentation
cat tools/feature-loop/README.md
```

## Example PRDs

See `tools/feature-loop/` for examples:
- `prd-example.json` - Full authentication system (7 tasks)
- `test-prd-simple.json` - Simple 1-task test

## Tips

1. **Start small**: 1-3 tasks for your first loop
2. **Be specific**: Clear acceptance criteria = better results
3. **Use specialists**: Match task to expert (Backend Dev, Frontend Dev, etc.)
4. **Validate early**: Turn on `requireValidation` for critical features
5. **Monitor costs**: Set `costAlertThreshold` conservatively

---

**Ready to build?** Create your PRD and run `/feature-loop`!
