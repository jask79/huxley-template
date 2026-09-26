# Getting Started with Huxley

Huxley is a multi-agent operating layer for Claude Code. One orchestrator agent, named by you during setup, sits between you and 35 specialist agents, each a markdown file with its own domain, tools and routing rules. Work happens inside isolated project workspaces called capsules. Skills give agents reusable knowledge, hooks wire behaviour around every turn, and CLI tools give them hands. You describe what to build; the orchestrator decides who builds it, runs it in parallel where it can, and verifies the result.

This page is the one to read first. Everything else is linked at the bottom.

## Prerequisites

- **Claude Code** (`npm install -g @anthropic-ai/claude-code`), logged in or with `ANTHROPIC_API_KEY` set
- **Python 3.10+** for tools and hooks
- **Node.js 18+** for the MCP servers (they run via `npx`) and skill tooling
- **git**
- **uv** (`brew install uv`), optional — only for the `google-workspace` MCP server in `.mcp.json`; delete that server's entry if you do not use Google Workspace
- **Docker** (optional), only for the ChromaDB-backed agent-memory layer
- **OpenAI Codex CLI** (optional), `npm install -g @openai/codex` — powers `tools/codex-consult.sh` and the automatic post-turn code review; without it that review hook detects the absence and does nothing (step 4)
- **GitNexus** (optional), an external code-graph tool that `CLAUDE.md` and two agents reference; not bundled (`docs/SETUP.md` → GitNexus)
- Most shell tooling assumes **macOS**

## 1. Create your repo

On GitHub, open the template repo and click **Use this template → Create a new repository**. Name it whatever you like. Then:

```bash
git clone https://github.com/<your-user>/<your-repo>.git
cd <your-repo>
```

A plain clone of the template works too, but "Use this template" gives you a repo you own, with a history that starts at your first commit. The template ships with no history from anyone else's machine.

## 2. Run setup

```bash
./setup.sh
```

The tree is full of double-curly placeholders. `setup.sh` asks for the values and rewrites every file that contains one:

| Prompt | Placeholder | Used for |
|---|---|---|
| Your name | `USER_NAME` | how the agents address you |
| Orchestrator name | `ORCHESTRATOR_NAME` | the main agent's identity in `CLAUDE.md` and `AGENTS.md` |
| Assistant name | `ASSISTANT_NAME` | the persona in `SOUL.md`; defaults to the orchestrator name |
| Email | `USER_EMAIL` | tool configs that need a contact address |
| GitHub user | `GITHUB_USER` | repo URLs and attribution |
| Telegram bot username, chat ID (optional) | `TELEGRAM_BOT`, `TELEGRAM_CHAT_ID` | only for tools that post a notification to a Telegram chat; leave both blank if you have none |
| Machine label (optional) | `MACHINE_HOST` | a nickname for this machine in docs and logs |

The script also derives your login, home directory and the repo's absolute path, copies `.env.example` to `.env` if none exists, materializes the `global/config/*.example.*` registries, creates a `.venv` virtualenv with `tools/requirements.txt` installed (the shipped tools and LaunchAgents run `.venv/bin/python3`), creates `memory/` and `capsules/`, and saves your answers to `.catalyst-config`. `./setup.sh --apply` re-applies the saved answers without prompting; you will use it after pulling template updates.

One default worth knowing about: the Communication Style section of `CLAUDE.md` asks agents to use emojis liberally. That is a preference, not a requirement. Edit the section if you want plain text.

## 3. Add API keys

Open `.env` and set, in this order of importance:

- `ANTHROPIC_API_KEY` first. Claude Code itself can run on your `claude login` session, but the tools and hooks that call the API read this key from `.env`.
- Then, only when you reach for the feature: `GEMINI_API_KEY` for image generation (the `nano-banana` skill and the media engine), `OPENROUTER_API_KEY` for multi-model routing and media-engine fallbacks, `FAL_API_KEY` for video generation. All three have placeholder lines in `.env.example`.

Everything else in the file belongs to one specific tool. Leave it blank until that tool complains. Run `chmod 600 .env` and never commit it.

## 4. Optional layers

Each of these is independent. Skip any of them and the rest still works.

**Community skills.** `./setup-skills.sh` clones 13 third-party skill repos into `.claude/skills/community/` and symlinks 25 of their skills into place (Vercel's React guidelines, Expo, SwiftUI, Better Auth, Cloudflare performance, SEO and more). Several agents' skill tables point at those symlinks, so run it once after setup; the 48 skills that ship in the template need none of this.

**MCP servers.** `.mcp.json` registers `filesystem`, `builder-memory` (a persistent knowledge graph across sessions), `context7` (live library documentation; agents query it before answering framework questions), `iterm-mcp` (for driving an already-running terminal process) and `google-workspace`. The first four run through `npx` and need nothing further. `google-workspace` needs your own OAuth client passed through environment variables; delete the entry if you don't use Google Workspace.

**Voice (TTS).** Not included in v0.1. `CLAUDE.md` carries a TTS Notification Protocol section that is off by default: the orchestrator only adds a `<tts-summary>` tag to its responses once you wire a Stop hook that speaks the text. Wire your own later (see the Voice section of `docs/SETUP.md`) or delete the section if you never want it.

**Telegram notifications.** The Telegram bot framework for driving Claude Code from your phone is not part of v0.1. What remains are a few tools that can post a status line to a Telegram chat, such as `tools/skill-curator/`. They read the chat ID from `TELEGRAM_CHAT_ID` in your environment — export it in your shell profile; the `setup.sh` answer is only recorded in `.catalyst-config`, which nothing exports — and expect the bot token in the macOS Keychain under service `telegram-bot-token`, account `huxley`. Never put a bot token in a tracked file, and never paste one into a chat with an agent. Skip the prompts and these tools simply stay inert (`--skip-telegram` where offered).

**Agent memory.** Out of the box, `builder-memory` gives Claude Code persistent memory between sessions. The deeper layer is a ChromaDB-backed memory server that stores patterns, anti-patterns and task outcomes, which the orchestrator searches before every delegation and writes to after novel wins. That server is not bundled in v0.1; when it is absent, every delegation step skips memory without error. `docs/AGENT_MEMORY.md` covers what ships, what doesn't, and how to add it.

**Codex peer consultation and the auto-review hook.** `tools/codex-consult.sh` wraps the OpenAI Codex CLI so the orchestrator can ask a second model for a free-form opinion, a file review, a diff review or a spec check. The Stop hook `tools/system-utils/hooks/review_stop_hook.py` runs that same wrapper automatically at the end of every turn that edited a source file (the extension list is at the top of `tools/system-utils/hooks/review_accumulator.py`; markdown and data files do not count).

The hook ships wired and enabled, and the Codex CLI is the one thing it needs. Until that CLI is on your `PATH` the hook sees it is missing and does nothing — no turn is blocked, no review is requested, and after one short first-time hint it stays quiet. To activate the review, install Codex with `npm install -g @openai/codex` (the Codex README also lists Homebrew and a standalone installer) and run `codex login` once; the next turn that touches code is reviewed, with nothing else to switch on. `/auto-review` turns the flow off and back on at any time and tells you whether Codex is present. `docs/HOOKS.md` has the details.

### Not included in v0.1

One line each on what was left out and how to add it back:

- **Telegram bot stack**: write your own bot against `claude -p` using the `TELEGRAM_BOT` / `TELEGRAM_CHAT_ID` values `setup.sh` already collected.
- **TTS voice hook**: add a Stop hook that speaks the `<tts-summary>` tag (`docs/SETUP.md` → Voice); the `CLAUDE.md` protocol switches on once the hook exists.
- **`agent-memory` server**: stand up ChromaDB plus an MCP server registered as `agent-memory` (`docs/AGENT_MEMORY.md`).
- **Music bridge**: recreate as a small CLI under `tools/` plus a skill; nothing depends on it.
- **The previous operator's personal tools** (personal trackers and private dashboards): build your own as capsules or `tools/` scripts.
- **GitNexus code intelligence**: external CLI, not bundled and not in `.mcp.json`; `npm install -g gitnexus@latest`, index with `tools/gitnexus-reindex.sh`, then add the MCP entry shown in `docs/SETUP.md` → GitNexus. Until then the agents skip their GitNexus steps.

## 5. First run

```bash
claude
```

Say hello. `CLAUDE.md` loads, and the orchestrator introduces itself by the name you gave it. Then try:

> have Backend Dev scaffold a FastAPI hello world in a new capsule

What happens, step by step:

1. The orchestrator recognises an explicit delegation ("have X do Y"). Its rules forbid doing specialist work itself, so it will not write the code.
2. "Backend Dev" is resolved through `.claude-context/agent-name-routing.json` to the registered agent name `🏛️ Backend Developer`. Every agent has a set of shorthand aliases there.
3. It creates the capsule (or asks you what to call it) and dispatches a Task to the Backend Developer with the capsule path and the request. Two independent asks would go out in parallel; dependent ones run as a pipeline.
4. The specialist loads its own agent file (`.claude/agents/backend-specialist.md`), pulls current FastAPI docs through Context7, writes the code inside `capsules/<name>/` and reports back.
5. The orchestrator summarises the result. Ask for `/code-review`, `/debug` or `/validate` to run the quality pipeline (Code Reviewer, then Debugger, then Validator) over what was built.

Hooks from `.claude/settings.json` fire around each step: routing reminders so the orchestrator delegates rather than implements, a git checkpoint at the end of the turn, and session-context updates in the capsule when you leave.

## 6. Create a capsule

A capsule is one project under `capsules/` with its own `CLAUDE.md`, `.env`, specs and code. When you open Claude Code inside it, the capsule's `CLAUDE.md` loads on top of the root one, so agents get project context without seeing your other projects.

The generic creator:

```bash
python3 tools/capsule_creator.py --name my-project --purpose "One line on what it is for"
```

It builds `capsules/my-project/` with `CLAUDE.md`, `README.md`, `specs/current.yaml` and `docs/`, registers a `/<short-name>` navigation skill, and adds a line to `capsules/CAPSULES_INDEX.md`. The `/new-capsule` skill is the same script driven by the orchestrator: say "create a capsule called my-project" and it runs it for you.

Manual alternative: `cp -r templates/capsule-base capsules/my-project`, then write its `CLAUDE.md` from `templates/capsule-claude-md.template.md`.

Then:

```bash
cd capsules/my-project && claude
```

## 7. Renaming the orchestrator later

Edit `.catalyst-config` (the `ORCHESTRATOR_NAME` and `ASSISTANT_NAME` lines, or any other value), then run `./setup.sh --apply`.

## 8. Never commit these

- `.env` and any `.env.*` at the root or inside a capsule
- `memory/` (session notes, conversations, checkpoints)
- `.catalyst-config` (your setup answers, including email and chat ID)

All three are in `.gitignore`. Before pushing anything public, run `gitleaks detect --no-git --redact` (the repo ships a tuned `.gitleaks.toml`); `tools/scan_secrets.sh` is a lighter grep-based fallback if you don't have gitleaks installed. `tools/secretctl.py` checks which secrets are present in the **environment** (`has`, `get` — output is always redacted — and `preflight`); it never reads the Keychain. For Keychain-backed secrets, `tools/check-secrets.py` reads each capsule's `keychain.required.toml` and verifies every declared secret really is in the macOS Keychain.

## 9. Where to go next

- `CLAUDE.md`: the orchestrator's operating rules; this is what Claude Code reads every session
- `ARCHITECTURE.md`: how the pieces fit together
- `docs/SETUP.md`: the longer setup and customisation guide, including how to pull template updates
- `docs/AGENT_MEMORY.md`: the two memory layers and how to add the optional one
- `.claude/agents/`: the 35 specialists; open one to see how a domain is defined
- `.claude/skills/`: the skills; `.claude/commands/` holds the slash commands
- `.claude-context/`: deeper context that loads on demand (architecture, orchestration, integrations, navigation, operating), plus `CLAUDE-strategy.md`, a fill-in template for your own north star and priorities
- `CONTRIBUTING.md`: conventions for adding agents, skills and capsules
- `./catalyst-doctor.sh`: checks the installation and can auto-fix common problems
