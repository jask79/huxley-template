# React-Spring MCP Server

**Physics-informed animation documentation** for Claude Code's Frontend Specialist agent.


## Features

- **list_documentation**: ⭐ NEW: Browse all available hooks and concepts with descriptions
- **get_hook_api**: Comprehensive hook documentation with physics explanations
- **get_concept**: Deep conceptual documentation (spring physics, tuning strategies)
- **Auto-Discovery**: ⭐ NEW: Automatically discovers hooks/concepts from filesystem (no code changes needed)
- **Zod Validation**: ⭐ NEW: Runtime schema validation catches malformed JSON at load time
- **Type Safety**: Full TypeScript types inferred from Zod schemas
- **13 Config Properties**: Complete physics parameters with explanations
- **Path Sanitization**: Security hardening with input validation
- Fast JSON-based documentation storage
- In-memory caching for performance
- Formatted markdown output optimized for Claude

## Available Hooks

- `useSpring` - Single spring animations (fade, slide, toggle)
- `useTrail` - Stagger animations (lists, sequences, menus)
- `useTransition` - Mount/unmount animations (modals, lists, routes)
- `useSpringValue` - Imperative spring control (scroll, gestures)
- **`useSpringRef`** - ⭐ NEW: Imperative API without re-renders (mouse tracking, gestures)
- **`config`** - ⭐ EXPANDED: 13 physics properties with detailed explanations

## Available Concepts

- **`spring-physics`** - ⭐ NEW: Complete physics understanding, tuning strategies, damping ratios, when to use springs vs duration

## Usage in Claude Code

Once registered, the Frontend Specialist can query:

**Discovery:**
```
"What react-spring documentation is available?"
"List all available hooks"
"Show me all concepts"
```

**Hook Documentation:**
```
"Show me the useSpring API"
"How do I use useTrail for stagger animations?"
"What config properties are available?"  // Returns all 13 physics properties!
"Show me useSpringRef for imperative control"
```

**Physics Understanding:**
```
"Explain spring physics and how to tune animations"
"What's the difference between tension and frequency?"
"How do I prevent overshoot?"
"When should I use springs vs duration-based animations?"
```

## Integration

Already registered in Huxley:
- ✅ `global/mcp/server-registry.json` - Server configuration
- ✅ `global/mcp/profile-configs.json` - Frontend Specialist profile
- ✅ `.claude/agents/frontend-specialist.md` - Agent documentation

## Test Locally

```bash
# List tools
echo '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}' | node dist/index.js

# Browse available documentation
echo '{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"list_documentation","arguments":{"category":"all"}}}' | node dist/index.js

# Get hook documentation
echo '{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"get_hook_api","arguments":{"hook":"useSpring"}}}' | node dist/index.js

# Get concept documentation
echo '{"jsonrpc":"2.0","id":4,"method":"tools/call","params":{"name":"get_concept","arguments":{"concept":"spring-physics"}}}' | node dist/index.js
```

## Performance

- **Startup**: <100ms
- **Cached lookup**: <1ms
- **First lookup**: <10ms
- **Memory**: ~5MB

## Architecture

```
data/
├── hooks/*.json             → Hook documentation (auto-discovered)
└── concepts/*.json          → Concept documentation (auto-discovered)
src/
├── types.ts                 → Zod schemas + TypeScript types
├── data-loader.ts           → JSON loading + validation + caching
├── tools/
│   ├── list-documentation.ts → Discovery tool
│   ├── hook-api.ts          → Hook documentation formatter
│   └── concept.ts           → Concept documentation formatter
├── index.ts                 → MCP server + tool registration
└── dist/index.js            → Compiled server (entry point)
```

## Adding New Hooks

**Now zero-maintenance with auto-discovery!**

1. Create JSON file: `data/hooks/newHook.json`
2. Follow existing schema (validated by Zod at runtime)
3. Rebuild: `npm run build`

That's it! No code changes needed - the server auto-discovers new files.

## Adding New Concepts

1. Create JSON file: `data/concepts/newConcept.json`
2. Follow existing schema (validated by Zod at runtime)
3. Rebuild: `npm run build`

## Maintenance

- **Update docs**: Edit JSON files → `npm run build`
- **Add hooks/concepts**: Just drop JSON files in `data/hooks/` or `data/concepts/`
- **Schema validation**: Zod catches errors at load time
- **React-spring updates**: ~30 min every 6-12 months

Built with ❤️ by The Big 3 (Boss + System Architect + {{ORCHESTRATOR_NAME}})
