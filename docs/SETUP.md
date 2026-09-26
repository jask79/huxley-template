# Huxley Setup Guide

The short version is in [GETTING-STARTED.md](../GETTING-STARTED.md). This page goes deeper on each step, on keeping your copy current with the template, and on customising the system.

## Prerequisites

- **Claude Code**: Anthropic's CLI (`npm install -g @anthropic-ai/claude-code`)
- **Python 3.10+**: tools and hooks
- **Node.js 18+**: MCP servers and skill tooling
- **git**: version control and community skills
- **Docker** (optional): only for the ChromaDB-backed agent-memory layer
- **OpenAI Codex CLI** (optional): `npm install -g @openai/codex`, then `codex login` once. Backs `tools/codex-consult.sh` and the automatic post-turn review; without it the review hook stands down and does nothing (`HOOKS.md`)
- **macOS** is assumed by most shell tooling

## First-Time Setup

### 1. Run the setup script

```bash
./setup.sh
```

This will:

- Ask for your name, the orchestrator's name, an assistant persona name, your email and GitHub user, and optionally a Telegram bot username, chat ID and a machine label
- Replace every double-curly placeholder in the tree with your values
- Create `.env` from `.env.example` if none exists, and create `memory/` and `capsules/`
- Save your answers to `.catalyst-config` for future re-application

`./setup.sh --apply` reads `.catalyst-config` and re-runs the replacement without prompting.

### 2. Configure API keys

Edit `.env`:

```bash
ANTHROPIC_API_KEY=sk-ant-...     # first: tools and hooks that call the API
GEMINI_API_KEY=...               # optional: image generation (nano-banana, media engine)
OPENROUTER_API_KEY=sk-or-...     # optional: multi-model routing, media-engine fallbacks
FAL_API_KEY=...                  # optional: video generation
```

All four have placeholder lines in `.env.example`. The rest of the file belongs to specific tools; fill a key in when the tool asks for it. Keep the file at `chmod 600` and never commit it.

### 3. Install community skills (optional)

```bash
./setup-skills.sh
```

Clones 13 community skill repositories into `.claude/skills/community/` and creates symlinks for the ones the agents reference. The 48 skills that ship with the template do not depend on this step, but several agents' skill tables point at the community symlinks — run it once after setup.

### 4. Set up MCP servers (optional)

`.mcp.json` ships with:

- **filesystem**: scoped file access, works out of the box
- **builder-memory**: persistent knowledge graph across sessions, works out of the box
- **context7**: current library documentation; agents query it before technical answers
- **iterm-mcp**: interact with an already-running terminal process
- **google-workspace**: Google mail, calendar and drive; needs your own OAuth client via environment variables. Remove the entry if you don't use it.

Add an `agent-memory` entry here if you stand up the ChromaDB memory layer, which is not bundled in v0.1 (see Memory below and `AGENT_MEMORY.md`).

### 5. Start Claude Code

```bash
cd /path/to/your/repo
claude
```

The orchestrator activates with the full agent system. Run `./catalyst-doctor.sh` at any time to check the installation; `--fix` attempts repairs.

---

## Understanding the System

### Agent system

35 specialist agents live in `.claude/agents/`. Each has:

- A defined role and expertise domain
- A model tier (heavier models for coding agents, lighter ones for research and analysis)
- Skills and reference documentation it loads
- Routing rules for when to invoke it

Your orchestrator (the main Claude instance) routes tasks to the right specialist automatically. Friendly names ("Backend Dev", "the reviewer") resolve through `.claude-context/agent-name-routing.json`.

### Capsules

Capsules are self-contained project environments under `capsules/`:

```
capsules/my-project/
  CLAUDE.md          # Project-specific instructions
  .env               # Project credentials (gitignored)
  specs/             # Data models and schemas
  docs/              # Project documentation
  src/               # Source code
```

Create one:

```bash
python3 tools/capsule_creator.py --name my-project --purpose "One line on what it is for"
```

That writes `CLAUDE.md`, `README.md`, `specs/current.yaml` and `docs/`, registers a `/<short-name>` navigation skill and adds an entry to `capsules/CAPSULES_INDEX.md`. Or copy the template by hand: `cp -r templates/capsule-base capsules/my-project` and write its `CLAUDE.md` from `templates/capsule-claude-md.template.md`.

Open Claude Code inside the capsule directory and its `CLAUDE.md` loads on top of the root one.

### Skills

Skills are markdown bundles that give agents specialised knowledge. They live in `.claude/skills/`:

- **Shipped skills** (73): framework best practice, testing, design, marketing, media, security and workflow skills wired to specific agents
- **Community skills** (optional): third-party repos installed by `./setup-skills.sh`, covering SwiftUI, React, Expo, SEO and more

Find more with `npx skills find <topic>`.

### Commands

Slash commands in `.claude/commands/` provide shortcuts for common workflows:

- `/build-feature`: autonomous feature development loop
- `/code-review`: manual code review
- `/debug`: systematic debugging
- `/validate`: comprehensive testing
- `/audit`: security-weighted capsule audit
- `/capsules`, `/tools`: list what's installed
- `/auto-review`: toggle the automatic post-turn review, and report whether the Codex CLI it runs on is installed

### Hooks

Hooks live in `tools/hooks/` and `tools/system-utils/hooks/` and are wired in `.claude/settings.json`. They provide:

- Orchestration routing reminders after tool use
- Automatic post-turn code review through the Codex CLI — enabled, and dormant until that CLI is installed
- A git checkpoint at the end of each turn
- Capsule context updates and transcript export at session end

`docs/HOOKS.md` documents each hook and how to add your own.

### Memory

`builder-memory` needs no setup. The optional ChromaDB-backed layer stores reusable patterns, anti-patterns and task outcomes; the orchestrator searches it before delegating and writes to it after novel wins. The template does not bundle that server. To enable it, run a ChromaDB container with Docker, write or adopt an MCP server that exposes the tools `CLAUDE.md` lists, and register it as `agent-memory` in `.mcp.json`; `AGENT_MEMORY.md` walks through it. When it is absent every memory operation is skipped gracefully.

### Voice (not included in v0.1)

The template ships no TTS server and no voice hook. One piece of the slot remains so you can add your own: the TTS Notification Protocol section of `CLAUDE.md`, which is off by default and tells the orchestrator to end every response with a one-line `<tts-summary>` tag only once a TTS Stop hook exists. To wire voice, write a Stop hook script (Claude Code passes the session JSON on stdin, including the transcript path), pull the latest `<tts-summary>` text out of the transcript, and speak it through any engine you like; a free local model such as Kokoro works well. Register it under `hooks.Stop` in `.claude/settings.json` via `tools/hooks/run-hook.sh`, the same way the other hooks are wired, then reread the `CLAUDE.md` section: it activates itself once the hook is present. If you never want voice, delete that section from `CLAUDE.md`.

### GitNexus code intelligence (optional)

`CLAUDE.md`, the Debugger and Code Reviewer agents and the four skills under `.claude/skills/gitnexus/` reference [GitNexus](https://github.com/abhigyanpatwari/gitnexus), an external tool that indexes a repository into a code graph and serves it over MCP (`query`, `context`, `impact`, `detect_changes`, `rename`, `cypher`). The template bundles neither the CLI nor an MCP entry for it, and `global/config/tool-registry.yaml` lists it as dormant. Until you add it, the agents skip their GitNexus steps and fall back to grep and file reads.

To enable it (commands taken from the GitNexus README at the time of writing; if one fails, check the project README for the current form):

1. **Install the CLI globally.** A global install also avoids the `npx` cold start that can exceed Claude Code's MCP startup timeout:

   ```bash
   npm install -g gitnexus@latest
   ```

2. **Build the first index** from the repo root through the shipped wrapper, never with `gitnexus analyze` directly:

   ```bash
   tools/gitnexus-reindex.sh          # add --force to rebuild from scratch
   ```

   `gitnexus analyze` expands the block between `<!-- gitnexus:start -->` and `<!-- gitnexus:end -->` in `CLAUDE.md` to about sixty lines and writes its own `AGENTS.md`; the wrapper restores the compact block afterwards, and backs up your `AGENTS.md` (the orchestrator's identity for Codex and other CLIs — a personalized file, not a GitNexus artifact) before the index and puts it back after. One thing to know: `analyze` also installs its own skills and registers its own Claude Code hooks, so review the diff to `.claude/` before you commit. The index itself lands in `.gitnexus/`; add that directory to `.gitignore` if you do not want it tracked.

3. **Register the MCP server.** Either let Claude Code write it:

   ```bash
   claude mcp add gitnexus -- npx -y gitnexus@latest mcp
   ```

   or add this entry to `mcpServers` in `.mcp.json` (the file ships without it):

   ```json
   "gitnexus": {
     "command": "npx",
     "args": ["-y", "gitnexus@latest", "mcp"],
     "description": "GitNexus code intelligence (optional). Index first with tools/gitnexus-reindex.sh"
   }
   ```

   With the global install from step 1 you can use `"command": "gitnexus", "args": ["mcp"]` instead and skip `npx` entirely. `gitnexus setup` can also write the editor config for you; it auto-detects Claude Code.

4. **Restart Claude Code.** `/mcp` should list `gitnexus`. Re-run `tools/gitnexus-reindex.sh` whenever `gitnexus status` reports the index stale.

### Not included in v0.1

- **Telegram bot stack** (drive Claude Code from your phone): not shipped. Write your own bot against `claude -p`; `setup.sh` already collected `TELEGRAM_BOT` and `TELEGRAM_CHAT_ID` for it. Tools that only post a status line still work if you put a bot token in the Keychain under the name each tool's source expects.
- **TTS voice hook**: not shipped; see Voice above.
- **`agent-memory` server**: not shipped; see Memory above and `AGENT_MEMORY.md`.
- **Music bridge** (control a local music player from a session): not shipped. Recreate it as a CLI under `tools/` plus a skill; nothing in the framework depends on it.
- **The previous operator's personal tools** (personal trackers and private dashboards): not shipped. Build your own as capsules or `tools/` scripts following the same CLI-first pattern.
- **GitNexus code intelligence**: not shipped; see GitNexus above for the install, first index and `.mcp.json` entry.

---

## Updating from the template

The template is rebuilt periodically. Your repo has its own history, so updates arrive by merging the template repo as a second remote:

```bash
# Once: add the template as a remote
git remote add template https://github.com/<template-owner>/<template-repo>.git

# Each time you want updates
git fetch template
git merge template/main --allow-unrelated-histories   # the flag is needed on the first merge only

# Resolve any conflicts, then COMMIT the merge before continuing
git status                                            # see what conflicted
# ...edit the conflicted files...
git add -A && git commit                              # finish the merge

./setup.sh --apply                                    # re-apply your saved names and paths
```

Merged files arrive with placeholders in them; `--apply` fills them back in from `.catalyst-config`. Run it only once the merge is committed — `--apply` is not read-only (it also creates `.env`, the runtime directories and `.venv`), so it should never run on a tree that still has conflict markers or a half-finished merge. Conflicts usually land in the files you customised most, typically `CLAUDE.md` and `.claude/settings.json`.

To preview what a template merge would bring before running it:

```bash
git fetch template
git log --oneline HEAD..template/main      # commits you don't have yet
git diff --stat HEAD...template/main       # files that would change
```

`./upgrade.sh` is intentionally disabled in this template version: its automatic de-personalize/re-personalize round-trip could corrupt files that legitimately contain your name. Running it prints this same guidance and exits. Use the `git fetch template` flow above, then `./setup.sh --apply` to personalize any newly merged files.

---

## Customization

### Adding a new agent

1. Create `.claude/agents/my-specialist.md` with YAML frontmatter (`name`, `description`, `model`)
2. Add routing rules to `CLAUDE.md` under the specialist routing map
3. Add name aliases to `.claude-context/agent-name-routing.json`
4. Test with "have My Specialist do [a task in its domain]"

`CONTRIBUTING.md` has the full agent template and the model-tier guidance.

### Adding a new command

1. Create `.claude/commands/my-command.md`
2. The command becomes available as `/my-command` in Claude Code

### Adding a new skill

1. Create `.claude/skills/my-skill/SKILL.md` with `name`, `description` and `when` in the frontmatter
2. Reference it in the agent files that should load it

### Creating capsule-specific commands

`capsule_creator.py` generates a navigation skill for every capsule. To write one by hand:

```markdown
# .claude/skills/my-project/SKILL.md
---
name: my-project
description: Navigate to My Project capsule
when: User types /my-project or mentions my-project
---
Navigate to capsule: capsules/my-project
Load capsule CLAUDE.md and begin work.
```

### Changing the orchestrator's name or your details

Edit `.catalyst-config`, then run `./setup.sh --apply`.

### Changing defaults you may not want

- **Emojis**: `CLAUDE.md` asks agents to use emojis liberally. Edit the Communication Style section for plain text.
- **Model routing**: `global/claude-config/agent_model_map.json` maps agents to models when you run through a gateway; otherwise each agent's `model:` field applies.
- **Ports**: `global/config/port-registry.yaml` is the source of truth for every local service. Add yours there before starting it.
