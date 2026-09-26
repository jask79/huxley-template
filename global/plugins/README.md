# Huxley Plugin Marketplace

Official Huxley plugin marketplace containing forked, customized, and original plugins maintained by the Huxley system.

## Philosophy

**Plugins = Owned, Not Borrowed**

Huxley maintains its own plugin marketplace to ensure:
- ✅ **Full control** - No dependency on external maintenance
- ✅ **Customization** - Modify plugins to fit Huxley patterns
- ✅ **Security** - All plugin code audited and version controlled
- ✅ **Governance** - Plugins align with Huxley security and quality standards
- ✅ **Longevity** - Plugins work indefinitely, regardless of upstream status

## Plugin Strategy

### Fork External Plugins
1. **Evaluate** - Test plugin from external marketplace
2. **Fork** - Copy to Huxley marketplace if valuable
3. **Customize** - Adapt to Huxley patterns and governance
4. **Maintain** - Huxley owns it from that point forward

### Create Custom Plugins
Package Huxley-specific capabilities:
- Huxley utilities
- Capsule templates
- Workflow automation
- Security and governance tools

## Installation

### Add Huxley Marketplace
```bash
/plugin marketplace add {{CATALYST_ROOT}}/global/plugins
```

### Install Plugin
```bash
/plugin install <plugin-name>@Huxley
```

### List Available Plugins
```bash
/plugin list
```

## Plugin Structure

Each plugin follows this structure:

```
plugin-name/
├── .claude-plugin/
│   └── plugin.json           # Plugin manifest
├── agents/                   # Specialist agent definitions (optional)
├── commands/                 # Slash commands (optional)
├── skills/                   # Autonomous capabilities (optional)
├── hooks/                    # Event handlers (optional)
└── README.md                 # Plugin documentation
```

## Available Plugins

### supabase-toolkit (Coming Soon)
Supabase integration for Backend Specialist
- Supabase-optimized backend agent
- Database schema management commands
- Type generation and migration tools

## Contributing

When adding a new plugin to this marketplace:

1. **Create plugin directory** with proper structure
2. **Add plugin manifest** (`.claude-plugin/plugin.json`)
3. **Document the plugin** (`README.md`)
4. **Update marketplace.json** to include new plugin
5. **Test installation** before committing
6. **Security review** if plugin includes MCPs or hooks

---

*Part of the Huxley - The one thing that builds all other things.*
