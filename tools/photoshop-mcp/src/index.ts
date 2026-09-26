#!/usr/bin/env node
/**
 * Huxley Photoshop MCP Server
 *
 * Drives Adobe Photoshop programmatically via ExtendScript-over-AppleScript.
 * Designed for Huxley's brand asset / thumbnail / product photo workflows
 * (your visual-brand capsules).
 *
 * Transport: stdio (matches the catalyst-mcp convention).
 * MCP Spec:  2025-06-18.
 */
import { Server } from '@modelcontextprotocol/sdk/server/index.js';
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js';
import {
  CallToolRequestSchema,
  ListToolsRequestSchema,
  type CallToolResult,
} from '@modelcontextprotocol/sdk/types.js';
import { resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { PhotoshopBridge } from './bridge/extendscript.js';
import { TemplateRegistry } from './templates/registry.js';
import { ALL_TOOLS, getToolByName } from './tools/index.js';
import type { ToolContext } from './tools/types.js';

const SERVER_NAME = 'catalyst-photoshop-mcp';
const SERVER_VERSION = '1.0.0';

// `fileURLToPath` correctly decodes percent-escaped install paths (spaces,
// unicode). The previous `.pathname` access returned a percent-encoded string
// and broke when CATALYST_ROOT contained spaces.
const CATALYST_ROOT =
  process.env.CATALYST_ROOT ?? resolve(fileURLToPath(new URL('../../..', import.meta.url)));

function log(...args: unknown[]): void {
  // MCP servers MUST keep stdout for protocol — log to stderr only.
  console.error('[photoshop-mcp]', ...args);
}

const server = new Server(
  {
    name: SERVER_NAME,
    version: SERVER_VERSION,
  },
  {
    capabilities: {
      tools: {},
    },
  },
);

const bridge = new PhotoshopBridge();
const templates = new TemplateRegistry(CATALYST_ROOT);

const ctx: ToolContext = { bridge, templates };

server.setRequestHandler(ListToolsRequestSchema, async () => {
  log(`Listing ${ALL_TOOLS.length} tools`);
  return {
    tools: ALL_TOOLS.map((t) => ({
      name: t.name,
      description: t.description,
      inputSchema: t.inputSchema,
      ...(t.annotations ? { annotations: t.annotations } : {}),
    })),
  };
});

// Our handlers return CallToolResult directly (the immediate, non-task form).
// CallToolResult is the SDK's canonical response type so no double-cast needed.
server.setRequestHandler(CallToolRequestSchema, async (request): Promise<CallToolResult> => {
  const name = request.params.name;
  const args = request.params.arguments ?? {};
  log(`Tool call: ${name}`);

  const tool = getToolByName(name);
  if (!tool) {
    return {
      content: [
        {
          type: 'text',
          text: JSON.stringify(
            {
              error: `Unknown tool: ${name}`,
              available: ALL_TOOLS.map((t) => t.name),
            },
            null,
            2,
          ),
        },
      ],
      isError: true,
    };
  }

  try {
    // Validate input via the tool's Zod schema so handlers can trust their args.
    tool.zodSchema.parse(args);
  } catch (e) {
    return {
      content: [
        {
          type: 'text',
          text: JSON.stringify(
            {
              error: `Invalid arguments for ${name}: ${(e as Error).message}`,
            },
            null,
            2,
          ),
        },
      ],
      isError: true,
    };
  }

  // Preflight: every PS tool except ps_is_running needs PS to be running.
  if (name !== 'ps_is_running') {
    const running = await bridge.isRunning();
    if (!running) {
      return {
        content: [
          {
            type: 'text',
            text: JSON.stringify(
              {
                error: `Photoshop is not running. Open ${bridge.getAppName()} and try again.`,
                hint: "Use the 'ps_is_running' tool to confirm before calling other tools.",
              },
              null,
              2,
            ),
          },
        ],
        isError: true,
      };
    }
  }

  try {
    return await tool.handler(args, ctx);
  } catch (e) {
    log(`Tool ${name} failed:`, (e as Error).message);
    return {
      content: [
        {
          type: 'text',
          text: JSON.stringify(
            {
              error: (e as Error).message,
              tool: name,
            },
            null,
            2,
          ),
        },
      ],
      isError: true,
    };
  }
});

async function main(): Promise<void> {
  log(`Starting ${SERVER_NAME} v${SERVER_VERSION}`);
  log(`Huxley root: ${CATALYST_ROOT}`);
  log(`Photoshop app name: ${bridge.getAppName()}`);
  log(`Tools registered: ${ALL_TOOLS.map((t) => t.name).join(', ')}`);

  const transport = new StdioServerTransport();
  await server.connect(transport);
  log('Server connected on stdio');

  process.on('SIGINT', () => {
    log('SIGINT — shutting down');
    process.exit(0);
  });
  process.on('SIGTERM', () => {
    log('SIGTERM — shutting down');
    process.exit(0);
  });
}

main().catch((err) => {
  log('Fatal error during startup:', err);
  process.exit(1);
});
