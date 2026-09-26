/**
 * Eligibility Filter Tests
 */

import { describe, expect, it } from "vitest";
import {
  filterEligibleSkills,
  isSkillEligible,
} from "./eligibility.js";
import type { EligibilityContext, SkillEntry, SkillMetadata } from "./types.js";

function createSkillMetadata(
  overrides: Partial<SkillMetadata["frontmatter"]> & { name?: string }
): SkillMetadata {
  return {
    name: overrides.name ?? "test-skill",
    description: "Test skill",
    filePath: "/path/to/skill.md",
    baseDir: "/path/to",
    source: "test",
    frontmatter: {
      name: overrides.name ?? "test-skill",
      ...overrides,
    },
    mtime: Date.now(),
  };
}

function createSkillEntry(
  overrides: Partial<SkillMetadata["frontmatter"]> & { name?: string }
): SkillEntry {
  return {
    metadata: createSkillMetadata(overrides),
    body: undefined,
    bodyLoaded: false,
  };
}

describe("isSkillEligible", () => {
  describe("always flag", () => {
    it("includes skills marked as always", () => {
      const skill = createSkillMetadata({ always: true });
      expect(isSkillEligible(skill, {})).toBe(true);
    });
  });

  describe("platform filtering", () => {
    it("includes skills with matching platform", () => {
      const skill = createSkillMetadata({ os: ["darwin"] });
      expect(isSkillEligible(skill, { platform: "darwin" })).toBe(true);
    });

    it("excludes skills with non-matching platform", () => {
      const skill = createSkillMetadata({ os: ["linux"] });
      expect(isSkillEligible(skill, { platform: "darwin" })).toBe(false);
    });

    it("includes skills without platform restriction", () => {
      const skill = createSkillMetadata({});
      expect(isSkillEligible(skill, { platform: "darwin" })).toBe(true);
    });
  });

  describe("audience filtering", () => {
    it("includes skills targeting specific agent", () => {
      const skill = createSkillMetadata({ audience: ["Backend Developer"] });
      expect(
        isSkillEligible(skill, { agentName: "Backend Developer" })
      ).toBe(true);
    });

    it("matches partial agent names", () => {
      const skill = createSkillMetadata({ audience: ["Backend"] });
      expect(
        isSkillEligible(skill, { agentName: "Backend Developer" })
      ).toBe(true);
    });

    it("excludes skills not targeting agent", () => {
      const skill = createSkillMetadata({ audience: ["Frontend Developer"] });
      expect(
        isSkillEligible(skill, { agentName: "Backend Developer" })
      ).toBe(false);
    });

    it("includes skills with no audience restriction", () => {
      const skill = createSkillMetadata({});
      expect(
        isSkillEligible(skill, { agentName: "Backend Developer" })
      ).toBe(true);
    });

    it('handles "all" audience', () => {
      const skill = createSkillMetadata({ audience: ["all"] });
      expect(
        isSkillEligible(skill, { agentName: "Backend Developer" })
      ).toBe(true);
    });
  });

  describe("proficiency filtering", () => {
    it("includes beginner skills for beginner agents", () => {
      const skill = createSkillMetadata({ proficiency_level: "beginner" });
      expect(
        isSkillEligible(skill, { proficiencyLevel: "beginner" })
      ).toBe(true);
    });

    it("includes beginner skills for advanced agents", () => {
      const skill = createSkillMetadata({ proficiency_level: "beginner" });
      expect(
        isSkillEligible(skill, { proficiencyLevel: "advanced" })
      ).toBe(true);
    });

    it("excludes advanced skills for beginner agents", () => {
      const skill = createSkillMetadata({ proficiency_level: "advanced" });
      expect(
        isSkillEligible(skill, { proficiencyLevel: "beginner" })
      ).toBe(false);
    });

    it("includes intermediate skills for intermediate agents", () => {
      const skill = createSkillMetadata({ proficiency_level: "intermediate" });
      expect(
        isSkillEligible(skill, { proficiencyLevel: "intermediate" })
      ).toBe(true);
    });
  });

  describe("integration requirements", () => {
    it("checks required MCP servers", () => {
      const skill = createSkillMetadata({
        integration: { requires_mcp: ["supabase-toolkit"] },
      });

      expect(
        isSkillEligible(skill, {
          availableMcpServers: ["supabase-toolkit"],
        })
      ).toBe(true);

      expect(
        isSkillEligible(skill, {
          availableMcpServers: [],
        })
      ).toBe(false);
    });

    it("checks required binaries", () => {
      const skill = createSkillMetadata({
        integration: { requires_bins: ["node"] },
      });

      expect(
        isSkillEligible(skill, {
          hasBinary: (bin) => bin === "node",
        })
      ).toBe(true);

      expect(
        isSkillEligible(skill, {
          hasBinary: () => false,
        })
      ).toBe(false);
    });

    it("checks any-of binaries", () => {
      const skill = createSkillMetadata({
        integration: { requires_any_bins: ["npm", "yarn", "pnpm"] },
      });

      expect(
        isSkillEligible(skill, {
          hasBinary: (bin) => bin === "pnpm",
        })
      ).toBe(true);

      expect(
        isSkillEligible(skill, {
          hasBinary: () => false,
        })
      ).toBe(false);
    });

    it("checks required environment variables", () => {
      const skill = createSkillMetadata({
        integration: { requires_env: ["API_KEY"] },
      });

      expect(
        isSkillEligible(skill, {
          hasEnvVar: (name) => name === "API_KEY",
        })
      ).toBe(true);

      expect(
        isSkillEligible(skill, {
          hasEnvVar: () => false,
        })
      ).toBe(false);
    });
  });

  describe("tag filtering", () => {
    it("includes skills with matching tags", () => {
      const skill = createSkillMetadata({ tags: ["backend", "api"] });

      expect(
        isSkillEligible(skill, { requiredTags: ["backend"] })
      ).toBe(true);
    });

    it("excludes skills without matching tags", () => {
      const skill = createSkillMetadata({ tags: ["frontend"] });

      expect(
        isSkillEligible(skill, { requiredTags: ["backend"] })
      ).toBe(false);
    });

    it("includes skills when no tags required", () => {
      const skill = createSkillMetadata({ tags: ["frontend"] });

      expect(isSkillEligible(skill, {})).toBe(true);
    });
  });

  describe("complexity filtering", () => {
    it("includes skills within complexity threshold", () => {
      const skill = createSkillMetadata({ complexity_score: 5 });

      expect(
        isSkillEligible(skill, { maxComplexity: 7 })
      ).toBe(true);
    });

    it("excludes skills above complexity threshold", () => {
      const skill = createSkillMetadata({ complexity_score: 8 });

      expect(
        isSkillEligible(skill, { maxComplexity: 5 })
      ).toBe(false);
    });

    it("includes skills when no complexity threshold", () => {
      const skill = createSkillMetadata({ complexity_score: 10 });

      expect(isSkillEligible(skill, {})).toBe(true);
    });
  });
});

describe("filterEligibleSkills", () => {
  it("filters out ineligible skills", () => {
    const entries: SkillEntry[] = [
      createSkillEntry({ name: "skill-a", audience: ["Backend"] }),
      createSkillEntry({ name: "skill-b", audience: ["Frontend"] }),
      createSkillEntry({ name: "skill-c", audience: ["Backend"] }),
    ];

    const result = filterEligibleSkills(entries, {
      agentName: "Backend Developer",
    });

    expect(result.map((e) => e.metadata.name)).toEqual([
      "skill-a",
      "skill-c",
    ]);
  });

  it("handles prerequisites correctly", () => {
    const entries: SkillEntry[] = [
      createSkillEntry({ name: "base-skill" }),
      createSkillEntry({
        name: "advanced-skill",
        prerequisites: ["base-skill"],
      }),
      createSkillEntry({
        name: "broken-skill",
        prerequisites: ["missing-skill"],
      }),
    ];

    const result = filterEligibleSkills(entries, {});

    expect(result.map((e) => e.metadata.name)).toEqual([
      "base-skill",
      "advanced-skill",
    ]);
  });

  it("re-checks prerequisites after filtering", () => {
    const entries: SkillEntry[] = [
      createSkillEntry({
        name: "frontend-base",
        audience: ["Frontend"],
      }),
      createSkillEntry({
        name: "frontend-advanced",
        audience: ["Frontend"],
        prerequisites: ["frontend-base"],
      }),
      createSkillEntry({
        name: "backend-advanced",
        audience: ["Backend"],
        prerequisites: ["frontend-base"], // Depends on frontend skill
      }),
    ];

    // Backend agent shouldn't get frontend skills
    const result = filterEligibleSkills(entries, {
      agentName: "Backend Developer",
    });

    // backend-advanced depends on frontend-base which is filtered out
    expect(result.map((e) => e.metadata.name)).toEqual([]);
  });
});
