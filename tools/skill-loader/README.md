# Huxley Skill Loader

Progressive disclosure skill loader for Huxley agents with context-aware filtering and installer specs support.

## Features

- **Two-Phase Loading**: Metadata loaded first (fast), body loaded on-demand (lazy)
- **Context-Aware Filtering**: Filter skills by agent, proficiency, prerequisites, and integrations
- **Integration Requirements**: Check for MCP servers, binaries, environment variables
- **Installer Specs**: Generate install commands for missing dependencies
- **File Watching**: Automatic cache invalidation on skill file changes
- **Indexed Access**: Fast lookups by tag, audience, and proficiency level

## Installation

```bash
cd tools/skill-loader
npm install
npm run build
```

## Usage

### Basic Usage

```typescript
import { createCatalystSkillLoader } from '@catalyst/skill-loader';

// Create loader for Huxley skills directory
const loader = createCatalystSkillLoader('{{CATALYST_ROOT}}', true);

// Get eligible skills for an agent
const skills = await loader.getEligibleSkills({
  agentName: 'Backend Developer',
  proficiencyLevel: 'advanced',
  availableMcpServers: ['supabase-toolkit'],
});

// Build prompt snapshot
const snapshot = await loader.buildSnapshot({
  agentName: 'Frontend Developer',
});

console.log(snapshot.prompt);

// Clean up when done
await loader.close();
```

### Advanced Options

```typescript
import { createSkillLoader } from '@catalyst/skill-loader';

const loader = createSkillLoader({
  skillsDir: '/path/to/.claude/skills',
  extraDirs: ['/path/to/additional/skills'],
  watch: true,           // Enable file watching
  cacheTtl: 60000,       // Cache TTL in ms
  alwaysInclude: ['core-skill'],
  alwaysExclude: ['deprecated-skill'],
});
```

### Eligibility Context

```typescript
const context: EligibilityContext = {
  // Filter by agent
  agentName: 'Backend Developer',

  // Filter by proficiency
  proficiencyLevel: 'intermediate',

  // Available MCP servers
  availableMcpServers: ['supabase-toolkit', 'playwright'],

  // Binary availability
  hasBinary: (bin) => checkIfBinaryExists(bin),

  // Environment variables
  hasEnvVar: (name) => !!process.env[name],

  // Config values
  hasConfig: (path) => getConfigValue(path) !== undefined,

  // Operating system
  platform: 'darwin',

  // Tag filtering
  requiredTags: ['backend', 'api'],

  // Complexity threshold
  maxComplexity: 7,
};
```

### Enhanced Frontmatter Schema

Skills can use the enhanced frontmatter schema:

```yaml
---
name: my-skill
description: A skill that does things
when: When to use this skill

# Proficiency and complexity
proficiency_level: intermediate  # beginner | intermediate | advanced
complexity_score: 6              # 0-10

# Prerequisites
prerequisites:
  - base-skill
  - another-skill

# Target audience
audience:
  - Backend Developer
  - {{ORCHESTRATOR_NAME}}

# Categorization
tags:
  - authentication
  - security
  - backend

# Integration requirements
integration:
  requires_mcp:
    - supabase-toolkit
  requires_context7:
    - fastapi
  requires_bins:
    - node
    - npm
  requires_env:
    - DATABASE_URL

# Install specifications
install:
  - kind: brew
    formula: ffmpeg
    bins:
      - ffmpeg
      - ffprobe
  - kind: node
    package: playwright
    global: true
    bins:
      - playwright
  - kind: go
    module: github.com/cli/cli/v2/cmd/gh
    bins:
      - gh
  - kind: uv
    package: ruff
    bins:
      - ruff
  - kind: download
    url: https://example.com/tool.tar.gz
    archive: tar.gz
    extract: true
    stripComponents: 1
    targetDir: /usr/local/bin
---

# Skill Body

Full skill documentation here...
```

### Install Command Generation

```typescript
import {
  generateSkillInstallCommands,
  skillNeedsInstall,
  getMissingDependencies,
  generateBatchInstallScript,
} from '@catalyst/skill-loader';

// Check if skill needs installation
if (skillNeedsInstall(skill, hasBinary)) {
  // Get missing dependencies
  const missing = getMissingDependencies(skill, hasBinary);

  // Generate install commands
  const commands = generateSkillInstallCommands(skill, {
    nodePackageManager: 'pnpm',
    preferBrew: true,
  });

  for (const cmd of commands) {
    console.log(cmd.description);
    console.log(cmd.command);
  }
}

// Or generate a batch script for multiple skills
const script = generateBatchInstallScript(skills, {
  nodePackageManager: 'pnpm',
});
fs.writeFileSync('install-deps.sh', script);
```

## API Reference

### SkillLoader

| Method | Description |
|--------|-------------|
| `getIndex()` | Get or build the skill index |
| `rebuildIndex()` | Force rebuild the index from disk |
| `getSkillMetadata(name)` | Get metadata for a skill by name |
| `loadBody(name)` | Load the body content on demand |
| `getSkillEntry(name)` | Get full skill entry with body |
| `getAllSkillEntries()` | Get all entries (metadata only) |
| `getEligibleSkills(context)` | Get filtered skills for context |
| `getEligibleSkillsWithBodies(context)` | Get filtered skills with bodies loaded |
| `buildSnapshot(context)` | Build prompt snapshot |
| `getSkillsByTag(tag)` | Get skills by tag |
| `getSkillsByAudience(agent)` | Get skills by audience |
| `searchSkills(query)` | Search by name/description |
| `close()` | Stop watching and clean up |

### Eligibility Helpers

| Function | Description |
|----------|-------------|
| `isSkillEligible(skill, context)` | Check single skill eligibility |
| `filterEligibleSkills(entries, context)` | Filter entries by eligibility |
| `hasBinary(bin)` | Check if binary exists in PATH |

### Install Helpers

| Function | Description |
|----------|-------------|
| `generateInstallCommand(spec, prefs)` | Generate single install command |
| `generateSkillInstallCommands(skill, prefs)` | Generate all commands for skill |
| `skillNeedsInstall(skill, hasBinary)` | Check if skill needs installation |
| `getMissingDependencies(skill, hasBinary)` | Get missing install specs |
| `generateBatchInstallScript(skills, prefs)` | Generate combined install script |

## Testing

```bash
npm test
npm run test:run  # Run once without watch
```

## License

MIT
