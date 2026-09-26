# Integration Tools (Lazy-Loaded Section)
<!-- Template version: 2026-09-24 -->

## Memory & Privacy Controls
**MCP Memory Location:** `~/.claude/mcp-data/builder-memory.json`
**Key Commands:**
- Status: `tools/memory/memory_status.sh`
- Backup: `tools/memory/backup_memory.sh`
- Clear: `tools/memory/clear_memory.sh`
- Setup: `tools/memory/setup_memory.sh`

**Privacy Rule:** Use `[PRIVATE]` prefix for sensitive information that should NOT be stored in MCP memory.

---

## TaskMaster: Work Item Management

**Summary:** TaskMaster is Huxley's work item tracking system. Each capsule has `tasks.json` for managing work items with full lifecycle tracking. Native support for mobile app (Swift) and web dashboard (JavaScript).

**Note:** TaskMaster is separate from Claude Code's "Task tool" (which invokes specialist agents). TaskMaster manages persistent work items in capsules.

**Quick Reference:**
```bash
# Add task
python3 tools/task_manager.py add [capsule] "Task description" --priority high --tags feature

# List tasks
python3 tools/task_manager.py list --capsule [capsule] --status pending

# Update task
python3 tools/task_manager.py update [capsule] [task-id] --status in_progress

# Complete task
python3 tools/task_manager.py complete [capsule] [task-id]

# Statistics
python3 tools/task_manager.py stats
```

**Complete guide:** `global/docs/TaskMaster_Guide.md`

**Huxley System Tasks:** Use root-level TaskMaster or Claude Code task tools for framework and infrastructure work.

---

## API Key Storage & Retrieval

**Summary:** All API keys stored in macOS Keychain. Per-capsule `.env` files (gitignored) hold capsule-specific config and references to Keychain entries.

**Standard pattern:**
```bash
# Store
security add-generic-password -s "openai-api" -a "huxley" -w "sk-xxx" -U

# Retrieve
security find-generic-password -s "openai-api" -a "huxley" -w
```

**Python pattern:**
```python
from global.lib.secret_provider import get_secret
api_key = get_secret("openai-api")
```

**TypeScript pattern:**
```typescript
import { getSecret } from "../../global/lib/secret-provider";
const apiKey = await getSecret("openai-api");
```

**Conventions:**
- **Service name:** `<service>-<purpose>` (e.g., `gemini-api`, `telegram-bot-token`)
- **Account name:** `huxley` (fixed) — every shipped tool reads and writes Keychain items under this literal account name, so always create entries with `-a huxley`
- `.env` files are gitignored and capsule-scoped — never store actual secret values here, only references/non-sensitive config

---

## Codex Consultation

**CRITICAL:** When {{USER_NAME}} says "discuss with Codex" or "consult Codex", use `tools/codex-consult.sh` (a thin wrapper around `codex exec`).

**Quick reference:**
```bash
# Free-form question
{{CATALYST_ROOT}}/tools/codex-consult.sh --topic <slug> "your question"

# Peer review of a file
{{CATALYST_ROOT}}/tools/codex-consult.sh --mode review --file <path> "extra context"

# Review the staged git diff
{{CATALYST_ROOT}}/tools/codex-consult.sh --mode diff
```

Logs land at `~/.cache/huxley/codex-consult/YYYY-MM-DD/`.

**Complete guide:** See `global/docs/Codex_Consultation.md`

---

## Apple Provisioning (App Store Connect API)

**Summary:** Automates Apple Developer portal operations via REST API. Account-level — one API key covers all apps.

**Credentials (set these up once; never commit them):**
- **Key file:** `~/.apple-provision/keys/AuthKey_<YOUR_KEY_ID>.p8` (permissions: 600)
- **Env vars:** `ASC_KEY_ID`, `ASC_ISSUER_ID`, `ASC_KEY_PATH` (set in your shell profile, e.g. `~/.zshrc`)
- **Key ID / Issuer ID:** from App Store Connect → Users and Access → Integrations → App Store Connect API
- **Team ID:** export `APPLE_DEVELOPER_TEAM_ID` in your shell profile -- `global/config/config.json` already reads it as `${APPLE_DEVELOPER_TEAM_ID}`; never write the literal value into a tracked file.

**Quick Reference:**
```bash
# Full provisioning for a new app (idempotent, safe to re-run)
python3 tools/apple_provision.py provision \
  --app-name "My App" --bundle-id "com.example.myapp" \
  --capabilities push,siwa,app-groups --platform ios

# Validate credentials
python3 tools/apple_provision.py preflight

# List existing resources
python3 tools/apple_provision.py list-certs
python3 tools/apple_provision.py list-bundle-ids
python3 tools/apple_provision.py list-profiles
python3 tools/apple_provision.py list-devices

# Register a device
python3 tools/apple_provision.py register-device --name "My iPhone" --udid "xxx"
```

**Capability shorthand:** push, siwa, app-groups, icloud, healthkit, homekit, wallet, siri, maps, game-center, in-app-purchase, associated-domains, nfc, data-protection, network-extensions, access-wifi

**Agents with access:** Mobile Dev, macOS Dev (skill sections in agent files), {{ORCHESTRATOR_NAME}} (authority)

**What requires the portal (rare):** APNs/SIWA/MusicKit keys, initial API key creation, agreement acceptance, tax/banking info

**Tool:** `tools/apple_provision.py` | **Skill:** `.claude/skills/apple-provision/SKILL.md`

---

## Browser Automation Strategy

**PRIMARY: Direct Playwright Library**

🐲 **Bowser uses direct Playwright Python library** for all complex automation:
- ✅ Full playwright-stealth integration (anti-detection)
- ✅ playwright-recaptcha for CAPTCHA solving (~85-90% success)
- ✅ Human behavior simulation (mouse, typing, pauses, typos)
- ✅ Dynamic field detection (site-agnostic)
- ✅ Complete control over timing and fingerprints

**Tool:**  `tools/registration_automation.py`

**When MCP Tools Used:**
- Quick tasks by {{ORCHESTRATOR_NAME}}/other agents (screenshots, page checks)
- **NOT for Bowser** - agent uses direct library

**Fallback: SeleniumBase UC mode** (extreme detection cases only)

**Safety rule:** Playwright must never launch your real daily-driver browser profile (it can wipe extensions and sessions). Use a dedicated user-data-dir, or the Claude in Chrome extension when a logged-in session is required.

---

## Workflow Automation

**Code-first approach.** All new automations are raw code (Python, TypeScript, shell scripts), version-controlled in git, triggered by LaunchAgents/cron/file watchers/webhooks.

### Default Stack
- **Scripts:** Python (primary) or TypeScript
- **Scheduling:** LaunchAgents (macOS launchd)
- **File watching:** `fswatch` or Python `watchdog`
- **Webhooks:** FastAPI micro-server when external push events are needed
- **Credentials:** Keychain via `global/lib/secret_provider.py`
- **Logging:** `quality.db` or structured log files
- **Visualization:** Pretty Mermaid (workflow logic) / FossFLOW (infrastructure)

### N8N (LEGACY — Optional, Not Default)

n8n is **not the default for new automations.** Only use it if explicitly requested. Huxley does not ship an n8n instance; if you run one, record its details here so {{ORCHESTRATOR_NAME}} can find it:

- **URL:** _FILL IN (e.g. https://n8n.localhost)_
- **Container / service:** _FILL IN_
- **Credentials:** Keychain service `n8n-huxley` (or your own name — never in this file)
- **Workflow exports:** _FILL IN (a git-tracked directory, e.g. `tools/n8n-local/workflows/`)_

New automations should be code-first unless there's a specific reason to use n8n.
