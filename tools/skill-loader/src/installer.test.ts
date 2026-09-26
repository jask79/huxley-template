/**
 * Installer Tests
 */

import { describe, expect, it } from "vitest";
import {
  generateBatchInstallScript,
  generateInstallCommand,
  getMissingDependencies,
  skillNeedsInstall,
} from "./installer.js";
import type { InstallSpec, SkillMetadata } from "./types.js";

function createSkillWithInstall(install: InstallSpec[]): SkillMetadata {
  return {
    name: "test-skill",
    description: "Test",
    filePath: "/path/to/skill.md",
    baseDir: "/path/to",
    source: "test",
    frontmatter: {
      name: "test-skill",
      install,
    },
    mtime: Date.now(),
  };
}

describe("generateInstallCommand", () => {
  describe("brew", () => {
    it("generates brew install command", () => {
      const cmd = generateInstallCommand({
        kind: "brew",
        formula: "ffmpeg",
      });

      expect(cmd.command).toBe("brew install ffmpeg");
      expect(cmd.requiresSudo).toBe(false);
    });

    it("generates brew cask command", () => {
      const cmd = generateInstallCommand({
        kind: "brew",
        formula: "visual-studio-code",
        cask: true,
      });

      expect(cmd.command).toBe("brew install --cask visual-studio-code");
    });
  });

  describe("node", () => {
    it("generates npm install command", () => {
      const cmd = generateInstallCommand(
        { kind: "node", package: "typescript" },
        { nodePackageManager: "npm" }
      );

      expect(cmd.command).toBe("npm install -g typescript");
    });

    it("generates pnpm install command", () => {
      const cmd = generateInstallCommand(
        { kind: "node", package: "typescript" },
        { nodePackageManager: "pnpm" }
      );

      expect(cmd.command).toBe("pnpm add -g typescript");
    });

    it("generates yarn install command", () => {
      const cmd = generateInstallCommand(
        { kind: "node", package: "typescript" },
        { nodePackageManager: "yarn" }
      );

      expect(cmd.command).toBe("yarn global add typescript");
    });

    it("generates bun install command", () => {
      const cmd = generateInstallCommand(
        { kind: "node", package: "typescript" },
        { nodePackageManager: "bun" }
      );

      expect(cmd.command).toBe("bun add -g typescript");
    });

    it("handles local install", () => {
      const cmd = generateInstallCommand(
        { kind: "node", package: "lodash", global: false },
        { nodePackageManager: "npm" }
      );

      expect(cmd.command).toBe("npm install lodash");
    });
  });

  describe("go", () => {
    it("generates go install command", () => {
      const cmd = generateInstallCommand({
        kind: "go",
        module: "github.com/golangci/golangci-lint/cmd/golangci-lint",
      });

      expect(cmd.command).toBe(
        "go install github.com/golangci/golangci-lint/cmd/golangci-lint@latest"
      );
    });
  });

  describe("uv", () => {
    it("generates uv tool install command", () => {
      const cmd = generateInstallCommand({
        kind: "uv",
        package: "ruff",
      });

      expect(cmd.command).toBe("uv tool install ruff");
    });
  });

  describe("download", () => {
    it("generates download command", () => {
      const cmd = generateInstallCommand({
        kind: "download",
        url: "https://example.com/tool.tar.gz",
        archive: "tar.gz",
        extract: true,
      });

      expect(cmd.command).toContain("curl -fsSL");
      expect(cmd.command).toContain("tar xzf");
    });

    it("handles zip archives", () => {
      const cmd = generateInstallCommand({
        kind: "download",
        url: "https://example.com/tool.zip",
        archive: "zip",
        extract: true,
      });

      expect(cmd.command).toContain("unzip -o");
    });

    it("includes strip-components", () => {
      const cmd = generateInstallCommand({
        kind: "download",
        url: "https://example.com/tool.tar.gz",
        archive: "tar.gz",
        stripComponents: 1,
      });

      expect(cmd.command).toContain("--strip-components=1");
    });
  });
});

describe("skillNeedsInstall", () => {
  it("returns false for skills without install specs", () => {
    const skill = createSkillWithInstall([]);
    expect(skillNeedsInstall(skill, () => true)).toBe(false);
  });

  it("returns false when all binaries present", () => {
    const skill = createSkillWithInstall([
      { kind: "brew", formula: "ffmpeg", bins: ["ffmpeg", "ffprobe"] },
    ]);

    expect(skillNeedsInstall(skill, () => true)).toBe(false);
  });

  it("returns true when binaries missing", () => {
    const skill = createSkillWithInstall([
      { kind: "brew", formula: "ffmpeg", bins: ["ffmpeg", "ffprobe"] },
    ]);

    expect(skillNeedsInstall(skill, (bin) => bin === "ffmpeg")).toBe(true);
  });
});

describe("getMissingDependencies", () => {
  it("returns empty for fully satisfied dependencies", () => {
    const skill = createSkillWithInstall([
      { kind: "brew", formula: "ffmpeg", bins: ["ffmpeg"] },
    ]);

    const missing = getMissingDependencies(skill, () => true);
    expect(missing).toEqual([]);
  });

  it("returns missing specs", () => {
    const skill = createSkillWithInstall([
      { kind: "brew", formula: "ffmpeg", bins: ["ffmpeg"] },
      { kind: "brew", formula: "imagemagick", bins: ["convert"] },
    ]);

    const missing = getMissingDependencies(skill, (bin) => bin === "ffmpeg");
    expect(missing).toHaveLength(1);
    expect(missing[0]?.formula).toBe("imagemagick");
  });
});

describe("generateBatchInstallScript", () => {
  it("generates combined script", () => {
    const skills: SkillMetadata[] = [
      createSkillWithInstall([
        { kind: "brew", formula: "ffmpeg" },
        { kind: "node", package: "typescript" },
      ]),
      createSkillWithInstall([
        { kind: "brew", formula: "jq" },
        { kind: "go", module: "github.com/cli/cli/v2/cmd/gh" },
      ]),
    ];

    const script = generateBatchInstallScript(skills);

    expect(script).toContain("#!/bin/bash");
    expect(script).toContain("brew install ffmpeg jq");
    expect(script).toContain("npm install -g typescript");
    expect(script).toContain("go install github.com/cli/cli/v2/cmd/gh@latest");
  });

  it("respects package manager preference", () => {
    const skills: SkillMetadata[] = [
      createSkillWithInstall([{ kind: "node", package: "typescript" }]),
    ];

    const script = generateBatchInstallScript(skills, {
      nodePackageManager: "pnpm",
    });

    expect(script).toContain("pnpm add -g typescript");
  });
});
