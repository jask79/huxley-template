/**
 * Frontmatter Parser
 *
 * Parses YAML frontmatter from SKILL.md files with enhanced schema support.
 */

import YAML from "yaml";
import type {
  InstallSpec,
  IntegrationRequirements,
  ProficiencyLevel,
  SkillFrontmatter,
} from "./types.js";

// ============================================================================
// Raw Frontmatter Parsing
// ============================================================================

interface RawFrontmatter {
  [key: string]: unknown;
}

/**
 * Extract and parse YAML frontmatter from content.
 */
export function parseFrontmatter(content: string): RawFrontmatter {
  const normalized = content.replace(/\r\n/g, "\n").replace(/\r/g, "\n");

  if (!normalized.startsWith("---")) {
    return {};
  }

  const endIndex = normalized.indexOf("\n---", 3);
  if (endIndex === -1) {
    return {};
  }

  const block = normalized.slice(4, endIndex);

  try {
    const parsed = YAML.parse(block) as unknown;
    if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
      return {};
    }
    return parsed as RawFrontmatter;
  } catch {
    // Fallback to line-based parsing for malformed YAML
    return parseLineFrontmatter(block);
  }
}

/**
 * Fallback line-based frontmatter parser.
 */
function parseLineFrontmatter(block: string): RawFrontmatter {
  const result: RawFrontmatter = {};
  const lines = block.split("\n");

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    const match = line?.match(/^([\w-]+):\s*(.*)$/);
    if (!match) continue;

    const key = match[1];
    const value = match[2]?.trim();

    if (key && value) {
      result[key] = stripQuotes(value);
    }
  }

  return result;
}

function stripQuotes(value: string): string {
  if (
    (value.startsWith('"') && value.endsWith('"')) ||
    (value.startsWith("'") && value.endsWith("'"))
  ) {
    return value.slice(1, -1);
  }
  return value;
}

/**
 * Extract the body content (after frontmatter).
 */
export function extractBody(content: string): string {
  const normalized = content.replace(/\r\n/g, "\n").replace(/\r/g, "\n");

  if (!normalized.startsWith("---")) {
    return normalized;
  }

  const endIndex = normalized.indexOf("\n---", 3);
  if (endIndex === -1) {
    return normalized;
  }

  // Skip the closing --- and any following newlines
  const bodyStart = endIndex + 4;
  return normalized.slice(bodyStart).trim();
}

// ============================================================================
// Schema Transformation
// ============================================================================

/**
 * Normalize string list from various input formats.
 */
function normalizeStringList(input: unknown): string[] {
  if (!input) return [];

  if (Array.isArray(input)) {
    return input.map((v) => String(v).trim()).filter(Boolean);
  }

  if (typeof input === "string") {
    // Handle comma-separated strings
    return input
      .split(",")
      .map((v) => v.trim())
      .filter(Boolean);
  }

  return [];
}

/**
 * Parse proficiency level from input.
 */
function parseProficiencyLevel(input: unknown): ProficiencyLevel | undefined {
  if (typeof input !== "string") return undefined;

  const normalized = input.toLowerCase().trim();
  if (
    normalized === "beginner" ||
    normalized === "intermediate" ||
    normalized === "advanced"
  ) {
    return normalized;
  }

  return undefined;
}

/**
 * Parse complexity score (0-10).
 */
function parseComplexityScore(input: unknown): number | undefined {
  if (typeof input === "number") {
    return Math.max(0, Math.min(10, input));
  }

  if (typeof input === "string") {
    const num = parseFloat(input);
    if (!isNaN(num)) {
      return Math.max(0, Math.min(10, num));
    }
  }

  return undefined;
}

/**
 * Parse boolean value from various input formats.
 */
function parseBoolean(input: unknown): boolean | undefined {
  if (typeof input === "boolean") return input;

  if (typeof input === "string") {
    const normalized = input.toLowerCase().trim();
    if (normalized === "true" || normalized === "yes" || normalized === "1") {
      return true;
    }
    if (normalized === "false" || normalized === "no" || normalized === "0") {
      return false;
    }
  }

  if (typeof input === "number") {
    return input !== 0;
  }

  return undefined;
}

/**
 * Parse integration requirements.
 */
function parseIntegration(input: unknown): IntegrationRequirements | undefined {
  if (!input || typeof input !== "object") return undefined;

  const raw = input as Record<string, unknown>;
  const result: IntegrationRequirements = {};

  const mcpList = normalizeStringList(raw.requires_mcp ?? raw["requires-mcp"]);
  if (mcpList.length > 0) result.requires_mcp = mcpList;

  const c7List = normalizeStringList(
    raw.requires_context7 ?? raw["requires-context7"]
  );
  if (c7List.length > 0) result.requires_context7 = c7List;

  const envList = normalizeStringList(raw.requires_env ?? raw["requires-env"]);
  if (envList.length > 0) result.requires_env = envList;

  const binsList = normalizeStringList(
    raw.requires_bins ?? raw["requires-bins"]
  );
  if (binsList.length > 0) result.requires_bins = binsList;

  const anyBinsList = normalizeStringList(
    raw.requires_any_bins ?? raw["requires-any-bins"]
  );
  if (anyBinsList.length > 0) result.requires_any_bins = anyBinsList;

  const configList = normalizeStringList(
    raw.requires_config ?? raw["requires-config"]
  );
  if (configList.length > 0) result.requires_config = configList;

  return Object.keys(result).length > 0 ? result : undefined;
}

/**
 * Parse install specification.
 */
function parseInstallSpec(input: unknown): InstallSpec | undefined {
  if (!input || typeof input !== "object") return undefined;

  const raw = input as Record<string, unknown>;
  const kindRaw =
    typeof raw.kind === "string"
      ? raw.kind
      : typeof raw.type === "string"
        ? raw.type
        : "";
  const kind = kindRaw.trim().toLowerCase();

  if (!["brew", "node", "go", "uv", "download"].includes(kind)) {
    return undefined;
  }

  const base = {
    id: typeof raw.id === "string" ? raw.id : undefined,
    label: typeof raw.label === "string" ? raw.label : undefined,
    bins: normalizeStringList(raw.bins),
    os: normalizeStringList(raw.os),
  };

  // Clean up empty arrays
  if (base.bins?.length === 0) delete (base as Record<string, unknown>).bins;
  if (base.os?.length === 0) delete (base as Record<string, unknown>).os;

  switch (kind) {
    case "brew": {
      const formula = typeof raw.formula === "string" ? raw.formula : undefined;
      if (!formula) return undefined;
      return {
        kind: "brew",
        ...base,
        formula,
        cask: parseBoolean(raw.cask),
      } as InstallSpec;
    }

    case "node": {
      const pkg = typeof raw.package === "string" ? raw.package : undefined;
      if (!pkg) return undefined;
      return {
        kind: "node",
        ...base,
        package: pkg,
        global: parseBoolean(raw.global),
      } as InstallSpec;
    }

    case "go": {
      const module = typeof raw.module === "string" ? raw.module : undefined;
      if (!module) return undefined;
      return {
        kind: "go",
        ...base,
        module,
      } as InstallSpec;
    }

    case "uv": {
      const pkg = typeof raw.package === "string" ? raw.package : undefined;
      if (!pkg) return undefined;
      return {
        kind: "uv",
        ...base,
        package: pkg,
      } as InstallSpec;
    }

    case "download": {
      const url = typeof raw.url === "string" ? raw.url : undefined;
      if (!url) return undefined;
      return {
        kind: "download",
        ...base,
        url,
        archive: typeof raw.archive === "string" ? raw.archive : undefined,
        extract: parseBoolean(raw.extract),
        stripComponents:
          typeof raw.stripComponents === "number"
            ? raw.stripComponents
            : undefined,
        targetDir:
          typeof raw.targetDir === "string" ? raw.targetDir : undefined,
      } as InstallSpec;
    }

    default:
      return undefined;
  }
}

/**
 * Parse install specifications array.
 */
function parseInstallSpecs(input: unknown): InstallSpec[] | undefined {
  if (!Array.isArray(input)) {
    // Try single spec
    const single = parseInstallSpec(input);
    return single ? [single] : undefined;
  }

  const specs = input
    .map((item) => parseInstallSpec(item))
    .filter((s): s is InstallSpec => s !== undefined);

  return specs.length > 0 ? specs : undefined;
}

/**
 * Parse metadata object (can be JSON5 string or object).
 */
function parseMetadata(input: unknown): Record<string, unknown> | undefined {
  if (!input) return undefined;

  if (typeof input === "object" && !Array.isArray(input)) {
    return input as Record<string, unknown>;
  }

  if (typeof input === "string") {
    try {
      // Try JSON parse first
      const parsed = JSON.parse(input);
      if (typeof parsed === "object" && !Array.isArray(parsed)) {
        return parsed as Record<string, unknown>;
      }
    } catch {
      // Not valid JSON, ignore
    }
  }

  return undefined;
}

// ============================================================================
// Main Transformer
// ============================================================================

/**
 * Transform raw frontmatter into typed SkillFrontmatter.
 */
export function transformFrontmatter(raw: RawFrontmatter): SkillFrontmatter {
  const name = typeof raw.name === "string" ? raw.name.trim() : "";
  if (!name) {
    throw new Error("Skill frontmatter must have a name");
  }

  const result: SkillFrontmatter = { name };

  // Basic fields
  if (typeof raw.description === "string") {
    result.description = raw.description.trim();
  }

  if (typeof raw.when === "string") {
    result.when = raw.when.trim();
  }

  // Lists
  const allowedTools = normalizeStringList(
    raw.allowed_tools ?? raw["allowed-tools"]
  );
  if (allowedTools.length > 0) result.allowed_tools = allowedTools;

  const prerequisites = normalizeStringList(raw.prerequisites);
  if (prerequisites.length > 0) result.prerequisites = prerequisites;

  const audience = normalizeStringList(raw.audience);
  if (audience.length > 0) result.audience = audience;

  const tags = normalizeStringList(raw.tags);
  if (tags.length > 0) result.tags = tags;

  const os = normalizeStringList(raw.os);
  if (os.length > 0) result.os = os;

  // Proficiency and complexity
  const proficiency = parseProficiencyLevel(
    raw.proficiency_level ?? raw["proficiency-level"]
  );
  if (proficiency) result.proficiency_level = proficiency;

  const complexity = parseComplexityScore(
    raw.complexity_score ?? raw["complexity-score"]
  );
  if (complexity !== undefined) result.complexity_score = complexity;

  // Integration requirements
  const integration = parseIntegration(raw.integration);
  if (integration) result.integration = integration;

  // Install specifications
  const install = parseInstallSpecs(raw.install);
  if (install) result.install = install;

  // Metadata
  const metadata = parseMetadata(raw.metadata);
  if (metadata) result.metadata = metadata;

  // Boolean flags
  const disableModel = parseBoolean(
    raw.disable_model_invocation ?? raw["disable-model-invocation"]
  );
  if (disableModel !== undefined) result.disable_model_invocation = disableModel;

  const userInvocable = parseBoolean(
    raw.user_invocable ?? raw["user-invocable"]
  );
  if (userInvocable !== undefined) result.user_invocable = userInvocable;

  const always = parseBoolean(raw.always);
  if (always !== undefined) result.always = always;

  return result;
}

/**
 * Parse frontmatter from content and transform to typed schema.
 */
export function parseSkillFrontmatter(content: string): SkillFrontmatter {
  const raw = parseFrontmatter(content);
  return transformFrontmatter(raw);
}
