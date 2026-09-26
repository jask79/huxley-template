# Huxley Claude Code Router

This directory vendors [musistudio/claude-code-router](https://github.com/musistudio/claude-code-router) for the Infinity gateway profile. The router forwards Anthropic-style `/v1/messages` calls to a configurable downstream gateway (the shipped Infinity profile targets Bifrost on `127.0.0.1:8083`), so you can route to GPT‑5 Codex, Groq, Fireworks, etc., while preserving tool events.

## Structure

- `start_router.sh` – idempotent bootstrap script executed by `tools/run-gateway.sh`. Installs dependencies (via `pnpm`), builds the router CLI, copies `config/catalyst.json` to `~/.claude-code-router/config.json` if missing, and starts the background service.
- `config/catalyst.json` – default routing template. Its LiteLLM entries (`http://127.0.0.1:4000`, `$LITELLM_MASTER_KEY`) describe an optional lane — no LiteLLM proxy ships in this template; point routes at Bifrost (`:8083`) or your own proxy.
- `dist/` – generated at build time by the upstream router build script.

## Usage

1. Ensure LiteLLM proxy API keys are present in `{{CATALYST_ROOT}}/.env` (`GROQ_API_KEY`, `FIREWORKS_API_KEY`, `OPENAI_API_KEY`).  
2. Launch Infinity gateway session:
   ```bash
   {{CATALYST_ROOT}}/tools/run-gateway.sh
   ```
   The script:
   - Starts Bifrost if necessary.
   - Builds/starts the router (via `start_router.sh`).
   - Exports `ANTHROPIC_BASE_URL=http://127.0.0.1:3456` so Claude Code talks to the router instead of the raw proxy.
3. For subscription mode, continue using `{{CATALYST_ROOT}}/tools/run-subscription.sh` (unchanged).

### Managing the Router

The upstream CLI is available under `pnpm exec node dist/cli.js`:

```bash
cd {{CATALYST_ROOT}}/tools/gateways/claude-router
pnpm exec node dist/cli.js status   # show service status
pnpm exec node dist/cli.js stop     # stop the daemon
pnpm exec node dist/cli.js ui       # open configuration UI
```

## Customising Routes

Edit `~/.claude-code-router/config.json` (or use `pnpm exec node dist/cli.js ui`) to adjust providers, models, or routing rules. Example tweaks:

- Change the default Infinity model:
  ```json
  "Router": {
    "default": "litellm,groq-simple",
    ...
  }
  ```
- Add a dedicated model for long context:
  ```json
  "longContext": "litellm,fireworks-glm-4.6",
  "longContextThreshold": 160000
  ```

Restart the service after editing:
```bash
cd {{CATALYST_ROOT}}/tools/gateways/claude-router
pnpm exec node dist/cli.js restart
```

## Requirements

- Node.js with `pnpm` (install via `corepack enable pnpm` or `npm install -g pnpm`).
- Optional: a LiteLLM proxy on port 4000, only if you configure LiteLLM routes (not included — the shipped lane is Router (:3456) → Bifrost (:8083)).

The legacy subscription profile remains untouched, so you can toggle between native Anthropic usage and the router-powered Infinity flow without conflicts.
