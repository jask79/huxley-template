#!/usr/bin/env node
/**
 * Skill Loader CLI
 *
 * Command-line interface for the progressive disclosure skill loader.
 */

import { createSkillLoader } from "./loader.js";
import { generateSkillInstallCommands, skillNeedsInstall } from "./installer.js";
import { hasBinary } from "./eligibility.js";
import type { EligibilityContext, InstallSpec, ProficiencyLevel } from "./types.js";

function getSpecIdentifier(spec: InstallSpec): string {
  switch (spec.kind) {
    case "brew":
      return spec.formula;
    case "node":
      return spec.package;
    case "go":
      return spec.module;
    case "uv":
      return spec.package;
    case "download":
      return spec.url;
    default:
      return "unknown";
  }
}

const args = process.argv.slice(2);
const command = args[0];

function printUsage(): void {
  console.log(`
Huxley Skill Loader CLI

USAGE:
  skill-loader <command> [options]

COMMANDS:
  list [--dir <path>]                      List all skills
  show <skill-name> [--dir <path>]         Show skill details
  search <query> [--dir <path>]            Search skills
  eligible [--agent <name>] [--dir <path>] Show eligible skills for agent
  install <skill-name> [--dir <path>]      Show install commands for skill
  check <skill-name> [--dir <path>]        Check if skill dependencies are met

OPTIONS:
  --dir <path>          Skills directory (default: ./.claude/skills)
  --agent <name>        Agent name for filtering
  --proficiency <level> Proficiency level (beginner|intermediate|advanced)
  --tags <tags>         Comma-separated tags to filter by
  --json                Output as JSON
  --help                Show this help

EXAMPLES:
  skill-loader list
  skill-loader show frontend-testing
  skill-loader eligible --agent "Backend Developer"
  skill-loader search "authentication"
  skill-loader install ios-testing
  skill-loader check frontend-testing
`);
}

function parseArgs(): Record<string, string | boolean> {
  const result: Record<string, string | boolean> = {};
  let i = 1; // Skip command

  while (i < args.length) {
    const arg = args[i];
    if (arg?.startsWith("--")) {
      const key = arg.slice(2);
      const nextArg = args[i + 1];
      if (nextArg && !nextArg.startsWith("--")) {
        result[key] = nextArg;
        i += 2;
      } else {
        result[key] = true;
        i++;
      }
    } else {
      if (!result.positional) {
        result.positional = arg ?? "";
      }
      i++;
    }
  }

  return result;
}

async function main(): Promise<void> {
  if (!command || command === "--help" || command === "-h") {
    printUsage();
    process.exit(0);
  }

  const opts = parseArgs();
  const skillsDir = (opts.dir as string) || "./.claude/skills";
  const outputJson = opts.json === true;

  const loader = createSkillLoader({
    skillsDir,
    watch: false,
  });

  try {
    switch (command) {
      case "list": {
        const index = await loader.getIndex();
        const skills = Array.from(index.skills.values());

        if (outputJson) {
          console.log(JSON.stringify(skills.map(s => ({
            name: s.name,
            description: s.description,
            tags: s.frontmatter.tags,
            proficiency: s.frontmatter.proficiency_level,
            complexity: s.frontmatter.complexity_score,
          })), null, 2));
        } else {
          console.log(`Found ${skills.length} skills:\n`);
          for (const skill of skills.sort((a, b) => a.name.localeCompare(b.name))) {
            const tags = skill.frontmatter.tags?.join(", ") || "";
            const level = skill.frontmatter.proficiency_level || "";
            console.log(`  ${skill.name}`);
            if (skill.description) {
              console.log(`    ${skill.description.slice(0, 80)}${skill.description.length > 80 ? "..." : ""}`);
            }
            if (tags) console.log(`    Tags: ${tags}`);
            if (level) console.log(`    Level: ${level}`);
            console.log();
          }
        }
        break;
      }

      case "show": {
        const name = opts.positional as string;
        if (!name) {
          console.error("Error: skill name required");
          process.exit(1);
        }

        const entry = await loader.getSkillEntry(name);
        if (!entry) {
          console.error(`Error: skill "${name}" not found`);
          process.exit(1);
        }

        if (outputJson) {
          console.log(JSON.stringify({
            ...entry.metadata,
            body: entry.body,
          }, null, 2));
        } else {
          const { metadata } = entry;
          console.log(`\nSkill: ${metadata.name}`);
          console.log(`Description: ${metadata.description || "N/A"}`);
          console.log(`Path: ${metadata.filePath}`);
          console.log(`Source: ${metadata.source}`);

          const fm = metadata.frontmatter;
          if (fm.when) console.log(`When: ${fm.when}`);
          if (fm.proficiency_level) console.log(`Proficiency: ${fm.proficiency_level}`);
          if (fm.complexity_score !== undefined) console.log(`Complexity: ${fm.complexity_score}`);
          if (fm.tags?.length) console.log(`Tags: ${fm.tags.join(", ")}`);
          if (fm.audience?.length) console.log(`Audience: ${fm.audience.join(", ")}`);
          if (fm.prerequisites?.length) console.log(`Prerequisites: ${fm.prerequisites.join(", ")}`);
          if (fm.allowed_tools?.length) console.log(`Allowed Tools: ${fm.allowed_tools.join(", ")}`);

          if (fm.integration) {
            console.log("\nIntegration Requirements:");
            if (fm.integration.requires_mcp?.length) {
              console.log(`  MCP: ${fm.integration.requires_mcp.join(", ")}`);
            }
            if (fm.integration.requires_bins?.length) {
              console.log(`  Binaries: ${fm.integration.requires_bins.join(", ")}`);
            }
            if (fm.integration.requires_env?.length) {
              console.log(`  Env Vars: ${fm.integration.requires_env.join(", ")}`);
            }
          }

          if (fm.install?.length) {
            console.log("\nInstall Specs:");
            for (const spec of fm.install) {
              console.log(`  - ${spec.kind}: ${getSpecIdentifier(spec)}`);
            }
          }

          if (entry.body) {
            console.log("\n--- Body ---\n");
            console.log(entry.body.slice(0, 500));
            if (entry.body.length > 500) {
              console.log(`\n... (${entry.body.length - 500} more characters)`);
            }
          }
        }
        break;
      }

      case "search": {
        const query = opts.positional as string;
        if (!query) {
          console.error("Error: search query required");
          process.exit(1);
        }

        const results = await loader.searchSkills(query);

        if (outputJson) {
          console.log(JSON.stringify(results.map(s => ({
            name: s.name,
            description: s.description,
          })), null, 2));
        } else {
          console.log(`Found ${results.length} skills matching "${query}":\n`);
          for (const skill of results) {
            console.log(`  ${skill.name}`);
            if (skill.description) {
              console.log(`    ${skill.description.slice(0, 80)}${skill.description.length > 80 ? "..." : ""}`);
            }
            console.log();
          }
        }
        break;
      }

      case "eligible": {
        const context: EligibilityContext = {};

        if (opts.agent) {
          context.agentName = opts.agent as string;
        }
        if (opts.proficiency) {
          context.proficiencyLevel = opts.proficiency as ProficiencyLevel;
        }
        if (opts.tags) {
          context.requiredTags = (opts.tags as string).split(",").map(t => t.trim());
        }

        const eligible = await loader.getEligibleSkills(context);

        if (outputJson) {
          console.log(JSON.stringify(eligible.map(e => ({
            name: e.metadata.name,
            description: e.metadata.description,
          })), null, 2));
        } else {
          const agentStr = context.agentName ? ` for ${context.agentName}` : "";
          console.log(`Found ${eligible.length} eligible skills${agentStr}:\n`);
          for (const entry of eligible) {
            console.log(`  ${entry.metadata.name}`);
            if (entry.metadata.description) {
              console.log(`    ${entry.metadata.description.slice(0, 80)}${entry.metadata.description.length > 80 ? "..." : ""}`);
            }
            console.log();
          }
        }
        break;
      }

      case "install": {
        const name = opts.positional as string;
        if (!name) {
          console.error("Error: skill name required");
          process.exit(1);
        }

        const metadata = await loader.getSkillMetadata(name);
        if (!metadata) {
          console.error(`Error: skill "${name}" not found`);
          process.exit(1);
        }

        const commands = generateSkillInstallCommands(metadata);

        if (commands.length === 0) {
          console.log(`Skill "${name}" has no install specifications.`);
        } else {
          if (outputJson) {
            console.log(JSON.stringify(commands, null, 2));
          } else {
            console.log(`Install commands for "${name}":\n`);
            for (const cmd of commands) {
              console.log(`# ${cmd.description}`);
              console.log(cmd.command);
              console.log();
            }
          }
        }
        break;
      }

      case "check": {
        const name = opts.positional as string;
        if (!name) {
          console.error("Error: skill name required");
          process.exit(1);
        }

        const metadata = await loader.getSkillMetadata(name);
        if (!metadata) {
          console.error(`Error: skill "${name}" not found`);
          process.exit(1);
        }

        const needsInstall = skillNeedsInstall(metadata, hasBinary);
        const integration = metadata.frontmatter.integration;

        if (outputJson) {
          const status: Record<string, unknown> = {
            skill: name,
            installNeeded: needsInstall,
          };

          if (integration?.requires_bins) {
            status.binaries = integration.requires_bins.map(bin => ({
              name: bin,
              available: hasBinary(bin),
            }));
          }

          if (integration?.requires_env) {
            status.envVars = integration.requires_env.map(env => ({
              name: env,
              set: !!process.env[env],
            }));
          }

          console.log(JSON.stringify(status, null, 2));
        } else {
          console.log(`\nDependency check for "${name}":\n`);

          if (integration?.requires_bins?.length) {
            console.log("Binaries:");
            for (const bin of integration.requires_bins) {
              const available = hasBinary(bin);
              console.log(`  ${available ? "[OK]" : "[MISSING]"} ${bin}`);
            }
          }

          if (integration?.requires_env?.length) {
            console.log("\nEnvironment Variables:");
            for (const env of integration.requires_env) {
              const set = !!process.env[env];
              console.log(`  ${set ? "[OK]" : "[MISSING]"} ${env}`);
            }
          }

          if (metadata.frontmatter.install?.length) {
            console.log("\nInstall Specs:");
            for (const spec of metadata.frontmatter.install) {
              const bins = spec.bins || [];
              const allPresent = bins.every(hasBinary);
              const status = bins.length === 0 ? "[UNKNOWN]" : allPresent ? "[OK]" : "[NEEDS INSTALL]";
              console.log(`  ${status} ${spec.kind}: ${getSpecIdentifier(spec)}`);
            }
          }

          console.log();
          console.log(needsInstall
            ? "Status: INSTALLATION NEEDED"
            : "Status: ALL DEPENDENCIES MET");
        }
        break;
      }

      default:
        console.error(`Unknown command: ${command}`);
        printUsage();
        process.exit(1);
    }
  } finally {
    await loader.close();
  }
}

main().catch((err) => {
  console.error("Error:", err instanceof Error ? err.message : err);
  process.exit(1);
});
