/**
 * Skill Eligibility Filtering
 *
 * Context-aware filtering based on agent, proficiency, prerequisites,
 * and integration requirements.
 */

import fs from "node:fs";
import path from "node:path";
import type {
  EligibilityContext,
  ProficiencyLevel,
  SkillEntry,
  SkillIndex,
  SkillMetadata,
} from "./types.js";

// ============================================================================
// Proficiency Level Ordering
// ============================================================================

const PROFICIENCY_ORDER: Record<ProficiencyLevel, number> = {
  beginner: 1,
  intermediate: 2,
  advanced: 3,
};

/**
 * Check if agent proficiency meets skill requirement.
 */
function meetsProficiencyRequirement(
  skillLevel: ProficiencyLevel | undefined,
  agentLevel: ProficiencyLevel | undefined
): boolean {
  // No skill level means open to all
  if (!skillLevel) return true;

  // No agent level means assume beginner
  if (!agentLevel) {
    return skillLevel === "beginner";
  }

  return PROFICIENCY_ORDER[agentLevel] >= PROFICIENCY_ORDER[skillLevel];
}

// ============================================================================
// Binary Check
// ============================================================================

/**
 * Check if a binary exists in PATH.
 */
export function hasBinary(bin: string): boolean {
  const pathEnv = process.env.PATH ?? "";
  const parts = pathEnv.split(path.delimiter).filter(Boolean);

  for (const part of parts) {
    const candidate = path.join(part, bin);
    try {
      fs.accessSync(candidate, fs.constants.X_OK);
      return true;
    } catch {
      // Continue searching
    }
  }

  return false;
}

// ============================================================================
// Platform Check
// ============================================================================

/**
 * Check if skill is compatible with current platform.
 */
function isPlatformCompatible(
  skillOs: string[] | undefined,
  platform: NodeJS.Platform | undefined,
  remotePlatforms?: string[]
): boolean {
  // No OS restriction means compatible with all
  if (!skillOs || skillOs.length === 0) return true;

  const currentPlatform = platform ?? process.platform;

  // Check current platform
  if (skillOs.includes(currentPlatform)) return true;

  // Check remote platforms
  if (remotePlatforms && remotePlatforms.some((p) => skillOs.includes(p))) {
    return true;
  }

  return false;
}

// ============================================================================
// Audience Check
// ============================================================================

/**
 * Normalize agent name for comparison.
 */
function normalizeAgentName(name: string): string {
  return name
    .toLowerCase()
    .replace(/[^\w\s]/g, "") // Remove emojis and special chars
    .replace(/\s+/g, " ")
    .trim();
}

/**
 * Check if agent is in skill's audience.
 */
function isInAudience(
  skillAudience: string[] | undefined,
  agentName: string | undefined
): boolean {
  // No audience restriction means open to all
  if (!skillAudience || skillAudience.length === 0) return true;

  // No agent name means check fails (unless "all" is specified)
  if (!agentName) {
    return skillAudience.some(
      (a) => a.toLowerCase() === "all" || a.toLowerCase() === "*"
    );
  }

  const normalizedAgent = normalizeAgentName(agentName);

  // Check for "all" or wildcard
  if (
    skillAudience.some(
      (a) => a.toLowerCase() === "all" || a.toLowerCase() === "*"
    )
  ) {
    return true;
  }

  // Check if agent matches any audience member
  return skillAudience.some((audience) => {
    const normalizedAudience = normalizeAgentName(audience);
    return (
      normalizedAgent.includes(normalizedAudience) ||
      normalizedAudience.includes(normalizedAgent)
    );
  });
}

// ============================================================================
// Prerequisites Check
// ============================================================================

/**
 * Check if all prerequisites are available.
 */
function meetsPrerequisites(
  skillPrereqs: string[] | undefined,
  availableSkills: Set<string>
): boolean {
  // No prerequisites means always eligible
  if (!skillPrereqs || skillPrereqs.length === 0) return true;

  // Check each prerequisite
  return skillPrereqs.every((prereq) => availableSkills.has(prereq));
}

// ============================================================================
// Integration Requirements Check
// ============================================================================

/**
 * Check if integration requirements are met.
 */
function meetsIntegrationRequirements(
  skill: SkillMetadata,
  context: EligibilityContext
): boolean {
  const integration = skill.frontmatter.integration;
  if (!integration) return true;

  // Check required MCP servers
  if (integration.requires_mcp && integration.requires_mcp.length > 0) {
    const availableMcp = context.availableMcpServers ?? [];
    if (!integration.requires_mcp.every((mcp) => availableMcp.includes(mcp))) {
      return false;
    }
  }

  // Check required binaries
  if (integration.requires_bins && integration.requires_bins.length > 0) {
    const hasBin = context.hasBinary ?? hasBinary;
    const remoteBin = context.remote?.hasBin ?? (() => false);

    for (const bin of integration.requires_bins) {
      if (!hasBin(bin) && !remoteBin(bin)) {
        return false;
      }
    }
  }

  // Check "any of" binaries
  if (
    integration.requires_any_bins &&
    integration.requires_any_bins.length > 0
  ) {
    const hasBin = context.hasBinary ?? hasBinary;
    const remoteAnyBin =
      context.remote?.hasAnyBin ?? (() => false);

    const anyFound =
      integration.requires_any_bins.some((bin) => hasBin(bin)) ||
      remoteAnyBin(integration.requires_any_bins);

    if (!anyFound) return false;
  }

  // Check required environment variables
  if (integration.requires_env && integration.requires_env.length > 0) {
    const hasEnv = context.hasEnvVar ?? ((name) => !!process.env[name]);

    for (const env of integration.requires_env) {
      if (!hasEnv(env)) {
        return false;
      }
    }
  }

  // Check required config paths
  if (integration.requires_config && integration.requires_config.length > 0) {
    const hasConfig = context.hasConfig ?? (() => true); // Default to true if no config checker

    for (const configPath of integration.requires_config) {
      if (!hasConfig(configPath)) {
        return false;
      }
    }
  }

  return true;
}

// ============================================================================
// Tag and Complexity Check
// ============================================================================

/**
 * Check if skill matches required tags.
 */
function matchesTags(
  skillTags: string[] | undefined,
  requiredTags: string[] | undefined
): boolean {
  // No required tags means no filtering
  if (!requiredTags || requiredTags.length === 0) return true;

  // No skill tags means doesn't match
  if (!skillTags || skillTags.length === 0) return false;

  // Check if any required tag is present
  const normalizedSkillTags = skillTags.map((t) => t.toLowerCase());
  return requiredTags.some((tag) =>
    normalizedSkillTags.includes(tag.toLowerCase())
  );
}

/**
 * Check if skill complexity is within threshold.
 */
function meetsComplexityThreshold(
  skillComplexity: number | undefined,
  maxComplexity: number | undefined
): boolean {
  // No max means no filtering
  if (maxComplexity === undefined) return true;

  // No skill complexity means assume 0
  const complexity = skillComplexity ?? 0;

  return complexity <= maxComplexity;
}

// ============================================================================
// Main Eligibility Check
// ============================================================================

/**
 * Check if a skill is eligible given the context.
 */
export function isSkillEligible(
  skill: SkillMetadata,
  context: EligibilityContext,
  availableSkills?: Set<string>
): boolean {
  const fm = skill.frontmatter;

  // Always include skills marked as "always"
  if (fm.always === true) return true;

  // Platform check
  if (!isPlatformCompatible(fm.os, context.platform, context.remote?.platforms)) {
    return false;
  }

  // Audience check
  if (!isInAudience(fm.audience, context.agentName)) {
    return false;
  }

  // Proficiency check
  if (!meetsProficiencyRequirement(fm.proficiency_level, context.proficiencyLevel)) {
    return false;
  }

  // Prerequisites check
  if (availableSkills && !meetsPrerequisites(fm.prerequisites, availableSkills)) {
    return false;
  }

  // Integration requirements check
  if (!meetsIntegrationRequirements(skill, context)) {
    return false;
  }

  // Tags check
  if (!matchesTags(fm.tags, context.requiredTags)) {
    return false;
  }

  // Complexity check
  if (!meetsComplexityThreshold(fm.complexity_score, context.maxComplexity)) {
    return false;
  }

  return true;
}

/**
 * Filter skill entries based on eligibility context.
 */
export function filterEligibleSkills(
  entries: SkillEntry[],
  context: EligibilityContext
): SkillEntry[] {
  // Build set of available skill names for prerequisite checking
  const availableNames = new Set(entries.map((e) => e.metadata.name));

  // First pass: filter out ineligible skills
  let eligible = entries.filter((entry) =>
    isSkillEligible(entry.metadata, context, availableNames)
  );

  // Second pass: verify prerequisites are satisfied after filtering
  // (in case a prerequisite was filtered out)
  const eligibleNames = new Set(eligible.map((e) => e.metadata.name));
  eligible = eligible.filter((entry) =>
    meetsPrerequisites(entry.metadata.frontmatter.prerequisites, eligibleNames)
  );

  return eligible;
}

/**
 * Get skills from index that match eligibility.
 */
export function getEligibleSkillsFromIndex(
  index: SkillIndex,
  context: EligibilityContext
): SkillMetadata[] {
  const entries: SkillEntry[] = Array.from(index.skills.values()).map((m) => ({
    metadata: m,
    body: undefined,
    bodyLoaded: false,
  }));

  return filterEligibleSkills(entries, context).map((e) => e.metadata);
}
