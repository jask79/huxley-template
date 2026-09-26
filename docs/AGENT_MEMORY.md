# Agent Memory

Huxley has two memory layers. One ships with the template; the other does not.

## What ships: `builder-memory`

`.mcp.json` registers `builder-memory` (`@modelcontextprotocol/server-memory`, run through `npx`), a persistent knowledge graph that survives between Claude Code sessions. It needs no setup. `tools/memory/setup_memory.sh` seeds it and `tools/memory/memory_status.sh` reports on it; both work on the JSON file under `~/.claude/mcp-data/`. The orchestrator's long-lived notes (project state, standing preferences) live beside it in `~/.claude/projects/<repo-slug>/memory/`, which is plain markdown.

## What does not ship in v0.1: the `agent-memory` server

`CLAUDE.md` describes a second, deeper layer: an MCP server registered as `agent-memory` that keeps reusable patterns, anti-patterns and task outcomes in a ChromaDB vector store and exposes `create_memory`, `create_pattern`, `create_adr`, `search_memories`, `get_agent_memories`, `find_similar_memories`, `get_agent_summary` and `get_system_insights`.

The template contains **no implementation of that server, no ChromaDB container definition and no `.mcp.json` entry for it**. The orchestrator rules mention it so that, when you add one, the workflow (search before delegating, store after novel wins, warn specialists about known pitfalls) is already in place. Some scripts in `tools/memory/` were written against that layer (`memory_intelligence_bridge.py`, `simple_memory_bridge.py`, `temporal-memory-server.py`); they are inert until it exists.

## How the orchestrator behaves without it

- Every memory step in `CLAUDE.md` is conditional on the `agent-memory` tools being present in the session. When they are not, the orchestrator skips the step silently: no error, no prompt to install it, no retry.
- Delegation, parallel dispatch, the quality pipeline and the shipped hooks are unaffected. None of the hooks in `.claude/settings.json` call `agent-memory`.
- `builder-memory` and the markdown memory directory keep providing cross-session context.

## Adding it later

1. Run ChromaDB (for example `docker run -d -p <port>:8000 chromadb/chroma`) and register the port in `global/config/port-registry.yaml` before starting it.
2. Write or adopt an MCP server that exposes the eight tools above on top of ChromaDB. The `mcp-builder` skill and 🏄🏼‍♂️ MCP Server Dude are the in-house route (Python FastMCP is the quickest); any third-party memory server works if you map its tool names to the ones `CLAUDE.md` expects.
3. Register it in `.mcp.json` as `agent-memory`, as a stdio `command` entry or an SSE `url`, whichever transport the server speaks.
4. Restart Claude Code and confirm the tools appear (`/mcp`). The orchestrator starts using them on the next delegation; nothing else needs to change.
