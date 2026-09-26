/**
 * Install Command Generator
 *
 * Generates install commands from skill install specifications.
 */

import type {
  BrewInstallSpec,
  DownloadInstallSpec,
  GoInstallSpec,
  InstallCommand,
  InstallPreferences,
  InstallSpec,
  NodeInstallSpec,
  SkillMetadata,
  UvInstallSpec,
} from "./types.js";

// ============================================================================
// Default Preferences
// ============================================================================

const DEFAULT_PREFERENCES: InstallPreferences = {
  nodePackageManager: "npm",
  preferBrew: true,
  downloadDir: "/tmp/skill-downloads",
};

// ============================================================================
// Brew Commands
// ============================================================================

function generateBrewCommand(
  spec: BrewInstallSpec,
  _prefs: InstallPreferences
): InstallCommand {
  const command = spec.cask
    ? `brew install --cask ${spec.formula}`
    : `brew install ${spec.formula}`;

  return {
    command,
    description: spec.label ?? `Install ${spec.formula} via Homebrew`,
    expectedBins: spec.bins,
    requiresSudo: false,
  };
}

// ============================================================================
// Node Commands
// ============================================================================

function generateNodeCommand(
  spec: NodeInstallSpec,
  prefs: InstallPreferences
): InstallCommand {
  const pm = prefs.nodePackageManager;
  const global = spec.global ?? true;

  let command: string;

  switch (pm) {
    case "npm":
      command = global
        ? `npm install -g ${spec.package}`
        : `npm install ${spec.package}`;
      break;

    case "pnpm":
      command = global
        ? `pnpm add -g ${spec.package}`
        : `pnpm add ${spec.package}`;
      break;

    case "yarn":
      command = global
        ? `yarn global add ${spec.package}`
        : `yarn add ${spec.package}`;
      break;

    case "bun":
      command = global
        ? `bun add -g ${spec.package}`
        : `bun add ${spec.package}`;
      break;

    default:
      command = `npm install -g ${spec.package}`;
  }

  return {
    command,
    description: spec.label ?? `Install ${spec.package} via ${pm}`,
    expectedBins: spec.bins,
    requiresSudo: false,
  };
}

// ============================================================================
// Go Commands
// ============================================================================

function generateGoCommand(
  spec: GoInstallSpec,
  _prefs: InstallPreferences
): InstallCommand {
  return {
    command: `go install ${spec.module}@latest`,
    description: spec.label ?? `Install ${spec.module} via go install`,
    expectedBins: spec.bins,
    requiresSudo: false,
  };
}

// ============================================================================
// UV (Python) Commands
// ============================================================================

function generateUvCommand(
  spec: UvInstallSpec,
  _prefs: InstallPreferences
): InstallCommand {
  return {
    command: `uv tool install ${spec.package}`,
    description: spec.label ?? `Install ${spec.package} via uv`,
    expectedBins: spec.bins,
    requiresSudo: false,
  };
}

// ============================================================================
// Download Commands
// ============================================================================

function generateDownloadCommand(
  spec: DownloadInstallSpec,
  prefs: InstallPreferences
): InstallCommand {
  const targetDir = spec.targetDir ?? prefs.downloadDir ?? "/tmp/downloads";
  const commands: string[] = [];

  // Create target directory
  commands.push(`mkdir -p "${targetDir}"`);

  // Download file
  const filename = spec.url.split("/").pop() ?? "download";
  const downloadPath = `${targetDir}/${filename}`;
  commands.push(`curl -fsSL "${spec.url}" -o "${downloadPath}"`);

  // Extract if needed
  if (spec.extract !== false && spec.archive) {
    const stripFlag =
      spec.stripComponents !== undefined
        ? `--strip-components=${spec.stripComponents}`
        : "";

    switch (spec.archive) {
      case "tar.gz":
      case "tgz":
        commands.push(`tar xzf "${downloadPath}" -C "${targetDir}" ${stripFlag}`);
        break;

      case "tar.bz2":
        commands.push(`tar xjf "${downloadPath}" -C "${targetDir}" ${stripFlag}`);
        break;

      case "tar.xz":
        commands.push(`tar xJf "${downloadPath}" -C "${targetDir}" ${stripFlag}`);
        break;

      case "zip":
        commands.push(`unzip -o "${downloadPath}" -d "${targetDir}"`);
        break;

      default:
        // Unknown archive type, try to detect
        if (spec.archive.endsWith(".tar.gz") || spec.archive.endsWith(".tgz")) {
          commands.push(`tar xzf "${downloadPath}" -C "${targetDir}" ${stripFlag}`);
        } else if (spec.archive.endsWith(".zip")) {
          commands.push(`unzip -o "${downloadPath}" -d "${targetDir}"`);
        }
    }
  }

  return {
    command: commands.join(" && "),
    description:
      spec.label ?? `Download and install from ${new URL(spec.url).hostname}`,
    expectedBins: spec.bins,
    requiresSudo: false,
  };
}

// ============================================================================
// Main Generator
// ============================================================================

/**
 * Generate install command for a single spec.
 */
export function generateInstallCommand(
  spec: InstallSpec,
  prefs: Partial<InstallPreferences> = {}
): InstallCommand {
  const fullPrefs: InstallPreferences = { ...DEFAULT_PREFERENCES, ...prefs };

  switch (spec.kind) {
    case "brew":
      return generateBrewCommand(spec, fullPrefs);

    case "node":
      return generateNodeCommand(spec, fullPrefs);

    case "go":
      return generateGoCommand(spec, fullPrefs);

    case "uv":
      return generateUvCommand(spec, fullPrefs);

    case "download":
      return generateDownloadCommand(spec, fullPrefs);

    default:
      // Should never happen with proper typing
      throw new Error(`Unknown install kind: ${(spec as InstallSpec).kind}`);
  }
}

/**
 * Generate install commands for all specs in a skill.
 */
export function generateSkillInstallCommands(
  skill: SkillMetadata,
  prefs: Partial<InstallPreferences> = {}
): InstallCommand[] {
  const specs = skill.frontmatter.install;
  if (!specs || specs.length === 0) return [];

  const platform = process.platform;

  return specs
    .filter((spec) => {
      // Filter by OS if specified
      if (spec.os && spec.os.length > 0) {
        return spec.os.includes(platform);
      }
      return true;
    })
    .map((spec) => generateInstallCommand(spec, prefs));
}

/**
 * Check if a skill needs installation.
 */
export function skillNeedsInstall(
  skill: SkillMetadata,
  hasBinary: (bin: string) => boolean
): boolean {
  const specs = skill.frontmatter.install;
  if (!specs || specs.length === 0) return false;

  // Check if any expected binaries are missing
  for (const spec of specs) {
    if (spec.bins && spec.bins.length > 0) {
      if (spec.bins.some((bin) => !hasBinary(bin))) {
        return true;
      }
    }
  }

  return false;
}

/**
 * Get missing dependencies for a skill.
 */
export function getMissingDependencies(
  skill: SkillMetadata,
  hasBinary: (bin: string) => boolean
): InstallSpec[] {
  const specs = skill.frontmatter.install;
  if (!specs || specs.length === 0) return [];

  return specs.filter((spec) => {
    if (!spec.bins || spec.bins.length === 0) return false;
    return spec.bins.some((bin) => !hasBinary(bin));
  });
}

/**
 * Generate a combined install script for multiple skills.
 */
export function generateBatchInstallScript(
  skills: SkillMetadata[],
  prefs: Partial<InstallPreferences> = {}
): string {
  const lines: string[] = [
    "#!/bin/bash",
    "set -e",
    "",
    "# Auto-generated skill dependency installation script",
    `# Generated at: ${new Date().toISOString()}`,
    "",
  ];

  // Group by install kind for efficiency
  const brewSpecs: BrewInstallSpec[] = [];
  const nodeSpecs: NodeInstallSpec[] = [];
  const goSpecs: GoInstallSpec[] = [];
  const uvSpecs: UvInstallSpec[] = [];
  const downloadSpecs: DownloadInstallSpec[] = [];

  for (const skill of skills) {
    const specs = skill.frontmatter.install ?? [];
    for (const spec of specs) {
      switch (spec.kind) {
        case "brew":
          brewSpecs.push(spec);
          break;
        case "node":
          nodeSpecs.push(spec);
          break;
        case "go":
          goSpecs.push(spec);
          break;
        case "uv":
          uvSpecs.push(spec);
          break;
        case "download":
          downloadSpecs.push(spec);
          break;
      }
    }
  }

  // Brew installs
  if (brewSpecs.length > 0) {
    lines.push("# Homebrew packages");
    const formulas = brewSpecs
      .filter((s) => !s.cask)
      .map((s) => s.formula)
      .join(" ");
    const casks = brewSpecs
      .filter((s) => s.cask)
      .map((s) => s.formula)
      .join(" ");

    if (formulas) {
      lines.push(`brew install ${formulas}`);
    }
    if (casks) {
      lines.push(`brew install --cask ${casks}`);
    }
    lines.push("");
  }

  // Node installs
  if (nodeSpecs.length > 0) {
    lines.push("# Node packages");
    const pm = prefs.nodePackageManager ?? "npm";
    const packages = nodeSpecs.map((s) => s.package).join(" ");

    switch (pm) {
      case "npm":
        lines.push(`npm install -g ${packages}`);
        break;
      case "pnpm":
        lines.push(`pnpm add -g ${packages}`);
        break;
      case "yarn":
        lines.push(`yarn global add ${packages}`);
        break;
      case "bun":
        lines.push(`bun add -g ${packages}`);
        break;
    }
    lines.push("");
  }

  // Go installs
  if (goSpecs.length > 0) {
    lines.push("# Go modules");
    for (const spec of goSpecs) {
      lines.push(`go install ${spec.module}@latest`);
    }
    lines.push("");
  }

  // UV installs
  if (uvSpecs.length > 0) {
    lines.push("# Python tools (via uv)");
    for (const spec of uvSpecs) {
      lines.push(`uv tool install ${spec.package}`);
    }
    lines.push("");
  }

  // Download installs
  if (downloadSpecs.length > 0) {
    lines.push("# Downloads");
    for (const spec of downloadSpecs) {
      const cmd = generateDownloadCommand(spec, { ...DEFAULT_PREFERENCES, ...prefs });
      lines.push(cmd.command);
    }
    lines.push("");
  }

  lines.push('echo "Installation complete!"');

  return lines.join("\n");
}
