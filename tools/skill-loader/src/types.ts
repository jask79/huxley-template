/**
 * Skill Loader Type Definitions
 *
 * Progressive disclosure skill loading with enhanced frontmatter schema.
 */

// ============================================================================
// Proficiency & Complexity
// ============================================================================

export type ProficiencyLevel = "beginner" | "intermediate" | "advanced";

// ============================================================================
// Install Specifications
// ============================================================================

export type InstallKind = "brew" | "node" | "go" | "uv" | "download";

export interface BrewInstallSpec {
  kind: "brew";
  id?: string;
  label?: string;
  formula: string;
  cask?: boolean;
  bins?: string[];
  os?: string[];
}

export interface NodeInstallSpec {
  kind: "node";
  id?: string;
  label?: string;
  package: string;
  global?: boolean;
  bins?: string[];
  os?: string[];
}

export interface GoInstallSpec {
  kind: "go";
  id?: string;
  label?: string;
  module: string;
  bins?: string[];
  os?: string[];
}

export interface UvInstallSpec {
  kind: "uv";
  id?: string;
  label?: string;
  package: string;
  bins?: string[];
  os?: string[];
}

export interface DownloadInstallSpec {
  kind: "download";
  id?: string;
  label?: string;
  url: string;
  archive?: string;
  extract?: boolean;
  stripComponents?: number;
  targetDir?: string;
  bins?: string[];
  os?: string[];
}

export type InstallSpec =
  | BrewInstallSpec
  | NodeInstallSpec
  | GoInstallSpec
  | UvInstallSpec
  | DownloadInstallSpec;

// ============================================================================
// Integration Requirements
// ============================================================================

export interface IntegrationRequirements {
  /** MCP servers required for this skill */
  requires_mcp?: string[];
  /** Context7 libraries to query for documentation */
  requires_context7?: string[];
  /** Required environment variables */
  requires_env?: string[];
  /** Required binaries in PATH */
  requires_bins?: string[];
  /** At least one of these binaries must be present */
  requires_any_bins?: string[];
  /** Required config paths (dot notation) */
  requires_config?: string[];
}

// ============================================================================
// Skill Frontmatter (Enhanced Schema)
// ============================================================================

export interface SkillFrontmatter {
  /** Skill name (required) */
  name: string;

  /** Human-readable description */
  description?: string;

  /** When to use this skill */
  when?: string;

  /** Allowed tools for this skill */
  allowed_tools?: string[];

  /** Skill proficiency level */
  proficiency_level?: ProficiencyLevel;

  /** Other skills that must be available first */
  prerequisites?: string[];

  /** Which agents can use this skill */
  audience?: string[];

  /** Complexity score (0-10) for filtering */
  complexity_score?: number;

  /** Tags for categorization and filtering */
  tags?: string[];

  /** Integration requirements */
  integration?: IntegrationRequirements;

  /** Installation specifications */
  install?: InstallSpec[];

  /** Arbitrary metadata object (JSON5 stringified in source) */
  metadata?: Record<string, unknown>;

  /** Disable model invocation (skill is user-only) */
  disable_model_invocation?: boolean;

  /** User can invoke this skill via /command */
  user_invocable?: boolean;

  /** Always include regardless of eligibility */
  always?: boolean;

  /** OS restrictions */
  os?: string[];
}

// ============================================================================
// Skill Entry (Runtime Representation)
// ============================================================================

export interface SkillMetadata {
  /** Unique skill name */
  name: string;

  /** Skill description */
  description: string;

  /** File path to SKILL.md */
  filePath: string;

  /** Base directory containing the skill */
  baseDir: string;

  /** Source of the skill (workspace, managed, bundled, etc.) */
  source: string;

  /** Parsed frontmatter */
  frontmatter: SkillFrontmatter;

  /** File modification time for cache invalidation */
  mtime: number;
}

export interface SkillEntry {
  /** Lightweight metadata (always loaded) */
  metadata: SkillMetadata;

  /** Full body content (lazy loaded) */
  body?: string;

  /** Whether body has been loaded */
  bodyLoaded: boolean;
}

// ============================================================================
// Eligibility Context
// ============================================================================

export interface EligibilityContext {
  /** Current agent name (e.g., "Backend Developer") */
  agentName?: string;

  /** Agent's proficiency level */
  proficiencyLevel?: ProficiencyLevel;

  /** Available MCP servers */
  availableMcpServers?: string[];

  /** Check if a binary is available */
  hasBinary?: (bin: string) => boolean;

  /** Check if environment variable is set */
  hasEnvVar?: (name: string) => boolean;

  /** Check config value */
  hasConfig?: (path: string) => boolean;

  /** Current operating system */
  platform?: NodeJS.Platform;

  /** Tags to filter by */
  requiredTags?: string[];

  /** Maximum complexity score */
  maxComplexity?: number;

  /** Remote environment context (for sandboxed execution) */
  remote?: {
    platforms: string[];
    hasBin: (bin: string) => boolean;
    hasAnyBin: (bins: string[]) => boolean;
    note?: string;
  };
}

// ============================================================================
// Skill Index (Cached Metadata)
// ============================================================================

export interface SkillIndex {
  /** All skill metadata indexed by name */
  skills: Map<string, SkillMetadata>;

  /** Skills indexed by tag */
  byTag: Map<string, Set<string>>;

  /** Skills indexed by audience */
  byAudience: Map<string, Set<string>>;

  /** Skills indexed by proficiency */
  byProficiency: Map<ProficiencyLevel, Set<string>>;

  /** Last index build time */
  builtAt: number;

  /** Index version for cache invalidation */
  version: number;
}

// ============================================================================
// Skill Snapshot (For Prompt Generation)
// ============================================================================

export interface SkillSnapshot {
  /** Formatted prompt for model consumption */
  prompt: string;

  /** List of included skills with minimal info */
  skills: Array<{
    name: string;
    description: string;
    proficiencyLevel?: ProficiencyLevel;
  }>;

  /** Full skill entries if needed */
  entries?: SkillEntry[];

  /** Snapshot version */
  version?: number;
}

// ============================================================================
// Loader Options
// ============================================================================

export interface SkillLoaderOptions {
  /** Root directory to scan for skills */
  skillsDir: string;

  /** Additional directories to scan */
  extraDirs?: string[];

  /** Enable file watching for cache invalidation */
  watch?: boolean;

  /** Cache TTL in milliseconds (default: 60000) */
  cacheTtl?: number;

  /** Skills to always include regardless of eligibility */
  alwaysInclude?: string[];

  /** Skills to always exclude */
  alwaysExclude?: string[];
}

// ============================================================================
// Install Command Generation
// ============================================================================

export interface InstallCommand {
  /** The command to run */
  command: string;

  /** Human-readable description */
  description: string;

  /** Expected binaries after installation */
  expectedBins?: string[];

  /** Whether this needs sudo */
  requiresSudo?: boolean;
}

export interface InstallPreferences {
  /** Package manager for Node packages */
  nodePackageManager: "npm" | "pnpm" | "yarn" | "bun";

  /** Prefer Homebrew when available */
  preferBrew: boolean;

  /** Target directory for downloads */
  downloadDir?: string;
}
