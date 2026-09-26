/**
 * Frontmatter Parser Tests
 */

import { describe, expect, it } from "vitest";
import {
  extractBody,
  parseFrontmatter,
  parseSkillFrontmatter,
  transformFrontmatter,
} from "./frontmatter.js";

describe("parseFrontmatter", () => {
  it("parses basic YAML frontmatter", () => {
    const content = `---
name: test-skill
description: A test skill
---
# Body content`;

    const result = parseFrontmatter(content);
    expect(result.name).toBe("test-skill");
    expect(result.description).toBe("A test skill");
  });

  it("handles quoted values", () => {
    const content = `---
name: "quoted-skill"
description: 'single quoted'
---`;

    const result = parseFrontmatter(content);
    expect(result.name).toBe("quoted-skill");
    expect(result.description).toBe("single quoted");
  });

  it("returns empty object for content without frontmatter", () => {
    const content = "# Just markdown";
    const result = parseFrontmatter(content);
    expect(result).toEqual({});
  });

  it("parses arrays", () => {
    const content = `---
name: test
tags:
  - authentication
  - security
  - backend
---`;

    const result = parseFrontmatter(content);
    expect(result.tags).toEqual(["authentication", "security", "backend"]);
  });

  it("parses nested objects", () => {
    const content = `---
name: test
integration:
  requires_mcp:
    - supabase-toolkit
  requires_bins:
    - node
---`;

    const result = parseFrontmatter(content);
    expect(result.integration).toEqual({
      requires_mcp: ["supabase-toolkit"],
      requires_bins: ["node"],
    });
  });
});

describe("extractBody", () => {
  it("extracts content after frontmatter", () => {
    const content = `---
name: test
---
# Body Content

This is the body.`;

    const body = extractBody(content);
    expect(body).toBe("# Body Content\n\nThis is the body.");
  });

  it("returns full content if no frontmatter", () => {
    const content = "# Just markdown\n\nBody here.";
    const body = extractBody(content);
    expect(body).toBe(content);
  });

  it("handles empty body", () => {
    const content = `---
name: test
---
`;

    const body = extractBody(content);
    expect(body).toBe("");
  });
});

describe("transformFrontmatter", () => {
  it("transforms basic frontmatter", () => {
    const raw = {
      name: "my-skill",
      description: "A skill",
    };

    const result = transformFrontmatter(raw);
    expect(result.name).toBe("my-skill");
    expect(result.description).toBe("A skill");
  });

  it("throws if name is missing", () => {
    expect(() => transformFrontmatter({})).toThrow(
      "Skill frontmatter must have a name"
    );
  });

  it("parses proficiency levels", () => {
    expect(
      transformFrontmatter({ name: "t", proficiency_level: "beginner" })
        .proficiency_level
    ).toBe("beginner");

    expect(
      transformFrontmatter({ name: "t", proficiency_level: "ADVANCED" })
        .proficiency_level
    ).toBe("advanced");

    expect(
      transformFrontmatter({ name: "t", proficiency_level: "invalid" })
        .proficiency_level
    ).toBeUndefined();
  });

  it("parses complexity scores", () => {
    expect(
      transformFrontmatter({ name: "t", complexity_score: 5 }).complexity_score
    ).toBe(5);

    expect(
      transformFrontmatter({ name: "t", complexity_score: "7.5" })
        .complexity_score
    ).toBe(7.5);

    // Clamps to 0-10 range
    expect(
      transformFrontmatter({ name: "t", complexity_score: 15 }).complexity_score
    ).toBe(10);

    expect(
      transformFrontmatter({ name: "t", complexity_score: -5 }).complexity_score
    ).toBe(0);
  });

  it("parses string lists", () => {
    // From array
    expect(
      transformFrontmatter({ name: "t", tags: ["a", "b"] }).tags
    ).toEqual(["a", "b"]);

    // From comma-separated string
    expect(
      transformFrontmatter({ name: "t", tags: "a, b, c" }).tags
    ).toEqual(["a", "b", "c"]);
  });

  it("parses install specs", () => {
    const result = transformFrontmatter({
      name: "t",
      install: [
        { kind: "brew", formula: "ffmpeg" },
        { kind: "node", package: "typescript" },
      ],
    });

    expect(result.install).toHaveLength(2);
    expect(result.install?.[0]).toEqual({
      kind: "brew",
      formula: "ffmpeg",
    });
    expect(result.install?.[1]).toEqual({
      kind: "node",
      package: "typescript",
    });
  });

  it("parses integration requirements", () => {
    const result = transformFrontmatter({
      name: "t",
      integration: {
        requires_mcp: ["supabase"],
        requires_bins: ["node", "npm"],
        requires_env: ["API_KEY"],
      },
    });

    expect(result.integration).toEqual({
      requires_mcp: ["supabase"],
      requires_bins: ["node", "npm"],
      requires_env: ["API_KEY"],
    });
  });

  it("handles hyphenated keys", () => {
    const result = transformFrontmatter({
      name: "t",
      "allowed-tools": ["Read", "Write"],
      "proficiency-level": "intermediate",
      "requires-mcp": ["test"], // This is in integration object normally
    });

    expect(result.allowed_tools).toEqual(["Read", "Write"]);
    expect(result.proficiency_level).toBe("intermediate");
  });
});

describe("parseSkillFrontmatter", () => {
  it("parses a complete skill file", () => {
    const content = `---
name: frontend-testing
description: Comprehensive frontend testing using Playwright MCP
when: Generating or modifying frontend UI code
allowed-tools:
  - Bash
  - Read
  - mcp__playwright__browser_navigate
proficiency_level: intermediate
complexity_score: 6
tags:
  - testing
  - frontend
  - playwright
audience:
  - Frontend Developer
  - {{ORCHESTRATOR_NAME}}
integration:
  requires_mcp:
    - playwright
install:
  - kind: node
    package: playwright
    bins:
      - playwright
metadata:
  version: "2.0.0"
---
# Frontend Testing Skill

This is the body content.`;

    const result = parseSkillFrontmatter(content);

    expect(result.name).toBe("frontend-testing");
    expect(result.description).toBe(
      "Comprehensive frontend testing using Playwright MCP"
    );
    expect(result.when).toBe("Generating or modifying frontend UI code");
    expect(result.allowed_tools).toEqual([
      "Bash",
      "Read",
      "mcp__playwright__browser_navigate",
    ]);
    expect(result.proficiency_level).toBe("intermediate");
    expect(result.complexity_score).toBe(6);
    expect(result.tags).toEqual(["testing", "frontend", "playwright"]);
    expect(result.audience).toEqual(["Frontend Developer", "{{ORCHESTRATOR_NAME}}"]);
    expect(result.integration?.requires_mcp).toEqual(["playwright"]);
    expect(result.install).toHaveLength(1);
    expect(result.install?.[0]).toEqual({
      kind: "node",
      package: "playwright",
      bins: ["playwright"],
    });
    expect(result.metadata).toEqual({ version: "2.0.0" });
  });
});
