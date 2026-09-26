/**
 * Progressive Disclosure Skill Loader
 *
 * Context-aware skill loading for Huxley agents with:
 * - Two-phase loading (metadata first, body on-demand)
 * - Context-aware filtering (agent, proficiency, prerequisites)
 * - Integration requirements checking
 * - Installer specs support
 * - File watching for cache invalidation
 *
 * @example
 * ```typescript
 * import { createCatalystSkillLoader } from '@catalyst/skill-loader';
 *
 * const loader = createCatalystSkillLoader('{{CATALYST_ROOT}}', true);
 *
 * // Get eligible skills for an agent
 * const skills = await loader.getEligibleSkills({
 *   agentName: 'Backend Developer',
 *   proficiencyLevel: 'advanced',
 *   availableMcpServers: ['supabase-toolkit'],
 * });
 *
 * // Build prompt snapshot
 * const snapshot = await loader.buildSnapshot({
 *   agentName: 'Frontend Developer',
 * });
 *
 * console.log(snapshot.prompt);
 * ```
 */

// Core types
export type {
  // Proficiency
  ProficiencyLevel,

  // Install specs
  InstallKind,
  InstallSpec,
  BrewInstallSpec,
  NodeInstallSpec,
  GoInstallSpec,
  UvInstallSpec,
  DownloadInstallSpec,

  // Integration
  IntegrationRequirements,

  // Skill data
  SkillFrontmatter,
  SkillMetadata,
  SkillEntry,
  SkillIndex,
  SkillSnapshot,

  // Context
  EligibilityContext,

  // Options
  SkillLoaderOptions,
  InstallCommand,
  InstallPreferences,
} from "./types.js";

// Frontmatter parsing
export {
  parseFrontmatter,
  extractBody,
  transformFrontmatter,
  parseSkillFrontmatter,
} from "./frontmatter.js";

// Eligibility filtering
export {
  isSkillEligible,
  filterEligibleSkills,
  getEligibleSkillsFromIndex,
  hasBinary,
} from "./eligibility.js";

// Install command generation
export {
  generateInstallCommand,
  generateSkillInstallCommands,
  skillNeedsInstall,
  getMissingDependencies,
  generateBatchInstallScript,
} from "./installer.js";

// Main loader
export {
  SkillLoader,
  createSkillLoader,
  createCatalystSkillLoader,
} from "./loader.js";
