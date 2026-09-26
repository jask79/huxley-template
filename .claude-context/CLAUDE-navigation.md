# {{ORCHESTRATOR_NAME}} Navigation Intelligence (Lazy-Loaded Section)
<!-- Template version: 2026-09-24 -->

## {{ORCHESTRATOR_NAME}} Navigation Intelligence (APPLY FIRST)

### Conversation-Driven Navigation Protocol
**BEFORE** all other protocols, scan EVERY message for navigation intent:

**Navigation Intent Triggers:**
- **Work Intent:** "work on", "working on", "debug", "fix", "build", "develop", "improve", "update"
- **System Intent:** "check", "monitor", "maintain", "status", "audit", "review"
- **Create Intent:** "create", "start", "new", "build from scratch", "initialize"
- **Trouble Intent:** "broken", "error", "issue", "problem", "not working", "failing"

**Capsule Keyword Mapping:** See `global/navigation/capsule_keywords.yaml` for full keyword map

**Auto-Navigation Flow:**
1. **Intent Detection:** Parse message for triggers + keywords
2. **Capsule Scoring:** Calculate confidence for keyword matches
3. **Auto-Execute:** If confidence >75%: "Taking you to [capsule] to work on [intent]..."
4. **Navigate + Load Context:** Use `tools/nav_with_context.py [capsule]` to:
   - Change to capsule directory
   - Auto-read capsule's CLAUDE.md
   - Load capsule-specific settings and MCP configs
   - Inject context into current session (NO RESTART NEEDED)
5. **Confirm Context Loaded:** Acknowledge capsule context is active

**Confirmation Protocol:**
- High confidence (>75%): Auto-navigate with confirmation
- Medium confidence (50-75%): "I think you want [capsule]. Correct?"
- Low confidence (<50%): Continue with standard protocols

### Universal Navigation Protocol

**ALL capsule navigation** (slash commands, conversation-driven, explicit requests) uses this exact sequence:

```python
# 1. Load context using nav_with_context.py
python3 tools/nav_with_context.py [capsule-name]

# 2. Change working directory to capsule path from output
cd [capsule-path-from-output]

# 3. Present loaded CLAUDE.md to session
# (Tool output already displays this - session context is now active)

# 4. Confirm navigation complete
```

**Key Points:**
- **NEVER attempt to restart the session** - context injection happens live
- **ALWAYS use `nav_with_context.py`** - it's the single source of truth for navigation
- The tool uses intelligent caching (30min TTL) to reduce token costs by 40-60%
- Working directory should be changed via Bash after context load
- All subsequent file operations use capsule as root
- Capsule-specific MCP configs and settings are loaded

**Navigation Scenarios (All use same protocol):**
1. **Slash commands** (`/my-capsule`, `/another-capsule`, etc. — generated per capsule by `scripts/generate-nav-skills.py`) → Follow protocol above
2. **Conversation-driven** ("work on the mobile app") → Auto-detect intent, then follow protocol
3. **Explicit requests** ("navigate to my-capsule") → Follow protocol
4. **Any navigation trigger** → Follow protocol

**The Rule:** No matter how navigation is triggered, always execute `nav_with_context.py` + `cd` + confirm. Never try to restart.

**Example Output Flow:**
```
🔥 Navigated to: my-capsule
📂 Path: {{CATALYST_ROOT}}/capsules/my-capsule

===============================================================================
CAPSULE CONTEXT (CLAUDE.md)
===============================================================================
[Full CLAUDE.md content from capsule displayed here]

✅ my-capsule context is now active. Working directory changed to {{CATALYST_ROOT}}/capsules/my-capsule
```
