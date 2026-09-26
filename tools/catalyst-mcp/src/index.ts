#!/usr/bin/env node

/**
 * Huxley MCP Server
 * Exposes Huxley task management system to Claude and other MCP clients
 *
 * Version: 1.0.0
 * MCP Spec: 2025-06-18
 */

import { Server } from '@modelcontextprotocol/sdk/server/index.js';
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js';
import {
  CallToolRequestSchema,
  ListResourcesRequestSchema,
  ListToolsRequestSchema,
  ReadResourceRequestSchema,
} from '@modelcontextprotocol/sdk/types.js';
import { tools } from './tools.js';
import { resources } from './resources.js';
import { getDatabase } from './database.js';

/**
 * Initialize MCP server
 */
const server = new Server(
  {
    name: 'catalyst-mcp',
    version: '1.0.0',
  },
  {
    capabilities: {
      tools: {},
      resources: {},
    },
  }
);

/**
 * Error handler utility
 */
function handleError(error: unknown): { error: string; details?: string } {
  if (error instanceof Error) {
    console.error('[Huxley MCP] Error:', error.message);
    console.error('[Huxley MCP] Stack:', error.stack);
    return {
      error: error.message,
      details: error.stack,
    };
  }
  console.error('[Huxley MCP] Unknown error:', error);
  return {
    error: 'An unknown error occurred',
    details: String(error),
  };
}

/**
 * List available tools
 */
server.setRequestHandler(ListToolsRequestSchema, async () => {
  console.error('[Huxley MCP] Listing tools');

  return {
    tools: [
      {
        name: 'create_task',
        description: tools.create_task.description,
        inputSchema: tools.create_task.inputSchema,
      },
      {
        name: 'update_task_status',
        description: tools.update_task_status.description,
        inputSchema: tools.update_task_status.inputSchema,
      },
      {
        name: 'get_task_tree',
        description: tools.get_task_tree.description,
        inputSchema: tools.get_task_tree.inputSchema,
      },
      {
        name: 'search_tasks',
        description: tools.search_tasks.description,
        inputSchema: tools.search_tasks.inputSchema,
      },
      {
        name: 'link_document',
        description: tools.link_document.description,
        inputSchema: tools.link_document.inputSchema,
      },
    ],
  };
});

/**
 * Handle tool calls
 */
server.setRequestHandler(CallToolRequestSchema, async (request) => {
  console.error(`[Huxley MCP] Tool called: ${request.params.name}`);
  console.error(`[Huxley MCP] Arguments:`, JSON.stringify(request.params.arguments, null, 2));

  try {
    switch (request.params.name) {
      case 'create_task':
        return await tools.create_task.handler(request.params.arguments);

      case 'update_task_status':
        return await tools.update_task_status.handler(request.params.arguments);

      case 'get_task_tree':
        return await tools.get_task_tree.handler(request.params.arguments);

      case 'search_tasks':
        return await tools.search_tasks.handler(request.params.arguments);

      case 'link_document':
        return await tools.link_document.handler(request.params.arguments);

      default:
        throw new Error(`Unknown tool: ${request.params.name}`);
    }
  } catch (error) {
    const errorInfo = handleError(error);
    return {
      content: [
        {
          type: 'text',
          text: JSON.stringify({
            success: false,
            ...errorInfo,
          }, null, 2),
        },
      ],
      isError: true,
    };
  }
});

/**
 * List available resources
 */
server.setRequestHandler(ListResourcesRequestSchema, async () => {
  console.error('[Huxley MCP] Listing resources');
  return resources.list();
});

/**
 * Read a specific resource
 */
server.setRequestHandler(ReadResourceRequestSchema, async (request) => {
  const uri = request.params.uri;
  console.error(`[Huxley MCP] Reading resource: ${uri}`);

  try {
    return resources.read(uri);
  } catch (error) {
    const errorInfo = handleError(error);
    return {
      contents: [
        {
          uri,
          mimeType: 'application/json',
          text: JSON.stringify({
            success: false,
            ...errorInfo,
          }, null, 2),
        },
      ],
    };
  }
});

/**
 * Start server
 */
async function main() {
  console.error('[Huxley MCP] Starting Huxley MCP Server v1.0.0');
  console.error(`[Huxley MCP] Database: ${process.env.CATALYST_DB || '{{CATALYST_ROOT}}/tasks.db'}`);

  // Initialize database
  try {
    getDatabase();
    console.error('[Huxley MCP] Database initialized successfully');
  } catch (error) {
    console.error('[Huxley MCP] Failed to initialize database:', error);
    process.exit(1);
  }

  // Create transport and connect
  const transport = new StdioServerTransport();
  await server.connect(transport);

  console.error('[Huxley MCP] Server started and ready for requests');

  // Handle shutdown gracefully
  process.on('SIGINT', () => {
    console.error('[Huxley MCP] Received SIGINT, shutting down...');
    const db = getDatabase();
    db.close();
    process.exit(0);
  });

  process.on('SIGTERM', () => {
    console.error('[Huxley MCP] Received SIGTERM, shutting down...');
    const db = getDatabase();
    db.close();
    process.exit(0);
  });
}

main().catch((error) => {
  console.error('[Huxley MCP] Fatal error:', error);
  process.exit(1);
});
