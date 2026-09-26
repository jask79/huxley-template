/**
 * Progressive Disclosure Skill Loader
 *
 * Two-phase loading: metadata first (always), body on-demand (lazy).
 * Includes file watching for cache invalidation.
 */

import fs from "node:fs";
import path from "node:path";
import type { FSWatcher } from "chokidar";
import {
  extractBody,
  parseFrontmatter,
  transformFrontmatter,
} from "./frontmatter.js";
import { filterEligibleSkills } from "./eligibility.js";
import type {
  EligibilityContext,
  ProficiencyLevel,
  SkillEntry,
  SkillFrontmatter,
  SkillIndex,
  SkillLoaderOptions,
  SkillMetadata,
  SkillSnapshot,
} from "./types.js";

const fsp = fs.promises;

// ============================================================================
// Skill Discovery
// ============================================================================

interface SkillFile {
  filePath: string;
  baseDir: string;
  name: string;
}

/**
 * Find all SKILL.md files in a directory recursively.
 */
async function discoverSkillFiles(dir: string): Promise<SkillFile[]> {
  const skills: SkillFile[] = [];

  async function scanDir(currentDir: string): Promise<void> {
    let entries: fs.Dirent[];

    try {
      entries = await fsp.readdir(currentDir, { withFileTypes: true });
    } catch {
      return; // Directory doesn't exist or not readable
    }

    for (const entry of entries) {
      const fullPath = path.join(currentDir, entry.name);

      if (entry.isDirectory()) {
        // Recurse into subdirectories
        await scanDir(fullPath);
      } else if (entry.isFile()) {
        // Check for SKILL.md or skill.md
        const lowerName = entry.name.toLowerCase();
        if (lowerName === "skill.md") {
          skills.push({
            filePath: fullPath,
            baseDir: currentDir,
            name: path.basename(currentDir),
          });
        }
      }
    }
  }

  await scanDir(dir);
  return skills;
}

// ============================================================================
// Metadata Loading (Phase 1 - Always)
// ============================================================================

/**
 * Load skill metadata from a file (fast, no body loading).
 */
async function loadSkillMetadata(
  skillFile: SkillFile,
  source: string
): Promise<SkillMetadata | null> {
  try {
    const content = await fsp.readFile(skillFile.filePath, "utf-8");
    const stat = await fsp.stat(skillFile.filePath);

    const rawFrontmatter = parseFrontmatter(content);

    // Handle files without proper frontmatter
    if (!rawFrontmatter.name) {
      // Use directory name as skill name
      (rawFrontmatter as Record<string, unknown>).name = skillFile.name;
    }

    const frontmatter = transformFrontmatter(rawFrontmatter);

    return {
      name: frontmatter.name,
      description: frontmatter.description ?? "",
      filePath: skillFile.filePath,
      baseDir: skillFile.baseDir,
      source,
      frontmatter,
      mtime: stat.mtimeMs,
    };
  } catch (error) {
    console.warn(
      `[skill-loader] Failed to load ${skillFile.filePath}:`,
      error instanceof Error ? error.message : error
    );
    return null;
  }
}

// ============================================================================
// Body Loading (Phase 2 - On Demand)
// ============================================================================

/**
 * Load skill body content on demand.
 */
async function loadSkillBody(metadata: SkillMetadata): Promise<string> {
  const content = await fsp.readFile(metadata.filePath, "utf-8");
  return extractBody(content);
}

// ============================================================================
// Index Building
// ============================================================================

/**
 * Build skill index from metadata.
 */
function buildIndex(skills: SkillMetadata[]): SkillIndex {
  const index: SkillIndex = {
    skills: new Map(),
    byTag: new Map(),
    byAudience: new Map(),
    byProficiency: new Map(),
    builtAt: Date.now(),
    version: 1,
  };

  // Initialize proficiency maps
  const proficiencies: ProficiencyLevel[] = [
    "beginner",
    "intermediate",
    "advanced",
  ];
  for (const level of proficiencies) {
    index.byProficiency.set(level, new Set());
  }

  for (const skill of skills) {
    // Main index
    index.skills.set(skill.name, skill);

    // Tag index
    const tags = skill.frontmatter.tags ?? [];
    for (const tag of tags) {
      if (!index.byTag.has(tag)) {
        index.byTag.set(tag, new Set());
      }
      index.byTag.get(tag)?.add(skill.name);
    }

    // Audience index
    const audience = skill.frontmatter.audience ?? [];
    for (const agent of audience) {
      if (!index.byAudience.has(agent)) {
        index.byAudience.set(agent, new Set());
      }
      index.byAudience.get(agent)?.add(skill.name);
    }

    // Proficiency index
    const level = skill.frontmatter.proficiency_level ?? "beginner";
    index.byProficiency.get(level)?.add(skill.name);
  }

  return index;
}

// ============================================================================
// Prompt Generation
// ============================================================================

/**
 * Format skills for prompt injection.
 */
function formatSkillsForPrompt(entries: SkillEntry[]): string {
  const lines: string[] = [];

  for (const entry of entries) {
    const { metadata, body } = entry;
    const fm = metadata.frontmatter;

    // Skill header
    lines.push(`## ${metadata.name}`);

    // Description
    if (fm.description) {
      lines.push(fm.description);
    }

    // When clause
    if (fm.when) {
      lines.push(`\n**When:** ${fm.when}`);
    }

    // Prerequisites
    if (fm.prerequisites && fm.prerequisites.length > 0) {
      lines.push(`\n**Prerequisites:** ${fm.prerequisites.join(", ")}`);
    }

    // Allowed tools
    if (fm.allowed_tools && fm.allowed_tools.length > 0) {
      lines.push(`\n**Allowed Tools:** ${fm.allowed_tools.join(", ")}`);
    }

    // Body content (if loaded)
    if (body) {
      lines.push("\n" + body);
    }

    lines.push(""); // Empty line between skills
  }

  return lines.join("\n");
}

// ============================================================================
// Main Loader Class
// ============================================================================

export class SkillLoader {
  private options: Required<SkillLoaderOptions>;
  private index: SkillIndex | null = null;
  private bodyCache: Map<string, { body: string; mtime: number }> = new Map();
  private watcher: FSWatcher | null = null;
  private indexDirty = true;

  constructor(options: SkillLoaderOptions) {
    this.options = {
      skillsDir: options.skillsDir,
      extraDirs: options.extraDirs ?? [],
      watch: options.watch ?? false,
      cacheTtl: options.cacheTtl ?? 60000,
      alwaysInclude: options.alwaysInclude ?? [],
      alwaysExclude: options.alwaysExclude ?? [],
    };

    if (this.options.watch) {
      this.startWatching();
    }
  }

  /**
   * Get or build the skill index.
   */
  async getIndex(): Promise<SkillIndex> {
    if (this.index && !this.indexDirty) {
      return this.index;
    }

    await this.rebuildIndex();
    return this.index!;
  }

  /**
   * Rebuild the skill index from disk.
   */
  async rebuildIndex(): Promise<void> {
    const allDirs = [this.options.skillsDir, ...this.options.extraDirs];
    const allSkills: SkillMetadata[] = [];

    for (const dir of allDirs) {
      const source = dir === this.options.skillsDir ? "workspace" : "extra";
      const files = await discoverSkillFiles(dir);

      for (const file of files) {
        const metadata = await loadSkillMetadata(file, source);
        if (metadata) {
          // Check exclusions
          if (this.options.alwaysExclude.includes(metadata.name)) {
            continue;
          }
          allSkills.push(metadata);
        }
      }
    }

    // Merge skills (later sources override earlier)
    const merged = new Map<string, SkillMetadata>();
    for (const skill of allSkills) {
      merged.set(skill.name, skill);
    }

    this.index = buildIndex(Array.from(merged.values()));
    this.indexDirty = false;
  }

  /**
   * Get skill metadata by name.
   */
  async getSkillMetadata(name: string): Promise<SkillMetadata | null> {
    const index = await this.getIndex();
    return index.skills.get(name) ?? null;
  }

  /**
   * Load skill body on demand.
   */
  async loadBody(name: string): Promise<string | null> {
    const metadata = await this.getSkillMetadata(name);
    if (!metadata) return null;

    // Check cache
    const cached = this.bodyCache.get(name);
    if (cached && cached.mtime === metadata.mtime) {
      return cached.body;
    }

    // Load from disk
    const body = await loadSkillBody(metadata);
    this.bodyCache.set(name, { body, mtime: metadata.mtime });
    return body;
  }

  /**
   * Get a full skill entry with body loaded.
   */
  async getSkillEntry(name: string): Promise<SkillEntry | null> {
    const metadata = await this.getSkillMetadata(name);
    if (!metadata) return null;

    const body = await this.loadBody(name);
    return {
      metadata,
      body: body ?? undefined,
      bodyLoaded: body !== null,
    };
  }

  /**
   * Get all skill entries (metadata only, bodies not loaded).
   */
  async getAllSkillEntries(): Promise<SkillEntry[]> {
    const index = await this.getIndex();
    return Array.from(index.skills.values()).map((metadata) => ({
      metadata,
      body: undefined,
      bodyLoaded: false,
    }));
  }

  /**
   * Get eligible skills for a given context.
   */
  async getEligibleSkills(context: EligibilityContext): Promise<SkillEntry[]> {
    const allEntries = await this.getAllSkillEntries();

    // Apply always-include
    const alwaysIncludeSet = new Set(this.options.alwaysInclude);
    for (const entry of allEntries) {
      if (alwaysIncludeSet.has(entry.metadata.name)) {
        entry.metadata.frontmatter.always = true;
      }
    }

    return filterEligibleSkills(allEntries, context);
  }

  /**
   * Get eligible skills with bodies loaded.
   */
  async getEligibleSkillsWithBodies(
    context: EligibilityContext
  ): Promise<SkillEntry[]> {
    const eligible = await this.getEligibleSkills(context);

    // Load bodies in parallel
    await Promise.all(
      eligible.map(async (entry) => {
        if (!entry.bodyLoaded) {
          const body = await this.loadBody(entry.metadata.name);
          entry.body = body ?? undefined;
          entry.bodyLoaded = true;
        }
      })
    );

    return eligible;
  }

  /**
   * Build a skill snapshot for prompt generation.
   */
  async buildSnapshot(context: EligibilityContext): Promise<SkillSnapshot> {
    const entries = await this.getEligibleSkillsWithBodies(context);

    // Filter out skills with disable_model_invocation
    const promptEntries = entries.filter(
      (e) => e.metadata.frontmatter.disable_model_invocation !== true
    );

    const prompt = formatSkillsForPrompt(promptEntries);

    return {
      prompt,
      skills: entries.map((e) => ({
        name: e.metadata.name,
        description: e.metadata.description,
        proficiencyLevel: e.metadata.frontmatter.proficiency_level,
      })),
      entries,
      version: this.index?.version,
    };
  }

  /**
   * Get skills by tag.
   */
  async getSkillsByTag(tag: string): Promise<SkillMetadata[]> {
    const index = await this.getIndex();
    const names = index.byTag.get(tag);
    if (!names) return [];

    return Array.from(names)
      .map((name) => index.skills.get(name))
      .filter((s): s is SkillMetadata => s !== undefined);
  }

  /**
   * Get skills by audience (agent name).
   */
  async getSkillsByAudience(agent: string): Promise<SkillMetadata[]> {
    const index = await this.getIndex();
    const names = index.byAudience.get(agent);
    if (!names) return [];

    return Array.from(names)
      .map((name) => index.skills.get(name))
      .filter((s): s is SkillMetadata => s !== undefined);
  }

  /**
   * Search skills by name or description.
   */
  async searchSkills(query: string): Promise<SkillMetadata[]> {
    const index = await this.getIndex();
    const lowerQuery = query.toLowerCase();

    return Array.from(index.skills.values()).filter((skill) => {
      const nameMatch = skill.name.toLowerCase().includes(lowerQuery);
      const descMatch = skill.description.toLowerCase().includes(lowerQuery);
      const tagMatch = skill.frontmatter.tags?.some((t) =>
        t.toLowerCase().includes(lowerQuery)
      );

      return nameMatch || descMatch || tagMatch;
    });
  }

  /**
   * Start watching for file changes.
   */
  private startWatching(): void {
    // Dynamic import to keep chokidar optional
    import("chokidar")
      .then(({ watch }) => {
        const dirs = [this.options.skillsDir, ...this.options.extraDirs];

        this.watcher = watch(dirs, {
          ignored: /(^|[/\\])\../, // Ignore dotfiles
          persistent: true,
          ignoreInitial: true,
          depth: 10,
        });

        this.watcher.on("add", (filePath) => {
          if (this.isSkillFile(filePath)) {
            this.invalidateCache(filePath);
          }
        });

        this.watcher.on("change", (filePath) => {
          if (this.isSkillFile(filePath)) {
            this.invalidateCache(filePath);
          }
        });

        this.watcher.on("unlink", (filePath) => {
          if (this.isSkillFile(filePath)) {
            this.invalidateCache(filePath);
          }
        });
      })
      .catch((err) => {
        console.warn(
          "[skill-loader] Failed to start file watcher:",
          err instanceof Error ? err.message : err
        );
      });
  }

  /**
   * Check if a path is a skill file.
   */
  private isSkillFile(filePath: string): boolean {
    const basename = path.basename(filePath).toLowerCase();
    return basename === "skill.md";
  }

  /**
   * Invalidate cache for a file change.
   */
  private invalidateCache(filePath: string): void {
    // Mark index as dirty
    this.indexDirty = true;

    // Remove body cache for affected skill
    const dir = path.dirname(filePath);
    const skillName = path.basename(dir);
    this.bodyCache.delete(skillName);

    // Also try to find by full path
    if (this.index) {
      for (const [name, metadata] of this.index.skills) {
        if (metadata.filePath === filePath) {
          this.bodyCache.delete(name);
          break;
        }
      }
    }
  }

  /**
   * Stop watching and clean up.
   */
  async close(): Promise<void> {
    if (this.watcher) {
      await this.watcher.close();
      this.watcher = null;
    }
  }
}

// ============================================================================
// Factory Function
// ============================================================================

/**
 * Create a new skill loader instance.
 */
export function createSkillLoader(options: SkillLoaderOptions): SkillLoader {
  return new SkillLoader(options);
}

/**
 * Create a skill loader for Huxley's default skills directory.
 */
export function createCatalystSkillLoader(
  catalystRoot: string,
  watch = false
): SkillLoader {
  return new SkillLoader({
    skillsDir: path.join(catalystRoot, ".claude", "skills"),
    watch,
  });
}
