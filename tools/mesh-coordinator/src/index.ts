#!/usr/bin/env node

/**
 * Mesh Coordinator MCP Server
 * Enables supervised mesh agent communication in Huxley
 *
 * Version: 1.0.0
 * MCP Spec: 2025-06-18
 */

import { Server } from '@modelcontextprotocol/sdk/server/index.js';
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js';
import {
  CallToolRequestSchema,
  ListToolsRequestSchema,
} from '@modelcontextprotocol/sdk/types.js';
import {
  handleRequestPeerHelp,
  handleDiscoverCapabilities,
  handleBroadcastStatus,
  handleGetMeshActivity,
  RequestPeerHelpSchema,
  DiscoverCapabilitiesSchema,
  BroadcastStatusSchema,
  GetMeshActivitySchema
} from './router.js';
import { getDatabase, closeDatabase } from './audit.js';
import { z } from 'zod';

/**
 * Initialize MCP server
 */
const server = new Server(
  {
    name: 'mesh-coordinator',
    version: '1.0.0',
  },
  {
    capabilities: {
      tools: {},
    },
  }
);

/**
 * Error handler utility
 */
function handleError(error: unknown): { error: string; details?: string } {
  if (error instanceof Error) {
    console.error('[Mesh Coordinator] Error:', error.message);
    console.error('[Mesh Coordinator] Stack:', error.stack);
    return {
      error: error.message,
      details: error.stack,
    };
  }
  console.error('[Mesh Coordinator] Unknown error:', error);
  return {
    error: 'An unknown error occurred',
    details: String(error),
  };
}

/**
 * List available tools
 */
server.setRequestHandler(ListToolsRequestSchema, async () => {
  console.error('[Mesh Coordinator] Listing tools');

  return {
    tools: [
      {
        name: 'request_peer_help',
        description: 'Request assistance from a peer agent. All communications are logged to quality.db for {{ORCHESTRATOR_NAME}} oversight.',
        inputSchema: {
          type: 'object',
          properties: {
            from_agent: {
              type: 'string',
              description: 'Name of the agent making the request (with emoji, e.g., "🎨 Frontend Developer")'
            },
            to_agent: {
              type: 'string',
              description: 'Name of the target agent (with emoji, e.g., "🏛️ Backend Developer")'
            },
            request_type: {
              type: 'string',
              description: 'Type of help needed (e.g., "api-design", "accessibility-audit")'
            },
            context: {
              type: 'string',
              description: 'Detailed context about what help is needed'
            },
            urgency: {
              type: 'string',
              enum: ['blocking', 'nice_to_have', 'fyi'],
              description: 'Urgency level: blocking (task cannot proceed), nice_to_have (would help but optional), fyi (informational)',
              default: 'nice_to_have'
            }
          },
          required: ['from_agent', 'to_agent', 'request_type', 'context']
        }
      },
      {
        name: 'discover_capabilities',
        description: 'Find which agent can help with a specific capability.',
        inputSchema: {
          type: 'object',
          properties: {
            capability: {
              type: 'string',
              description: 'Capability to search for (e.g., "authentication", "css-styling", "mobile-testing")'
            }
          },
          required: ['capability']
        }
      },
      {
        name: 'broadcast_status',
        description: 'Announce completion, blockers, or status updates to interested parties.',
        inputSchema: {
          type: 'object',
          properties: {
            from_agent: {
              type: 'string',
              description: 'Name of the agent broadcasting (with emoji)'
            },
            status: {
              type: 'string',
              description: 'Status type (e.g., "completed", "blocked", "in_progress")'
            },
            message: {
              type: 'string',
              description: 'Status message details'
            },
            session_id: {
              type: 'string',
              description: 'Optional session ID if this relates to a previous request'
            }
          },
          required: ['from_agent', 'status', 'message']
        }
      },
      {
        name: 'get_mesh_activity',
        description: 'Get recent mesh communications ({{ORCHESTRATOR_NAME}}-only). Shows all agent-to-agent communication activity.',
        inputSchema: {
          type: 'object',
          properties: {
            limit: {
              type: 'number',
              description: 'Maximum number of records to return',
              default: 50
            },
            since: {
              type: 'string',
              description: 'Optional ISO timestamp - only return communications since this time'
            }
          }
        }
      }
    ],
  };
});

/**
 * Handle tool calls
 */
server.setRequestHandler(CallToolRequestSchema, async (request) => {
  console.error(`[Mesh Coordinator] Tool called: ${request.params.name}`);
  console.error(`[Mesh Coordinator] Arguments:`, JSON.stringify(request.params.arguments, null, 2));

  try {
    switch (request.params.name) {
      case 'request_peer_help': {
        const params = RequestPeerHelpSchema.parse(request.params.arguments);
        const result = handleRequestPeerHelp(params);

        return {
          content: [
            {
              type: 'text',
              text: JSON.stringify(result, null, 2),
            },
          ],
        };
      }

      case 'discover_capabilities': {
        const params = DiscoverCapabilitiesSchema.parse(request.params.arguments);
        const result = handleDiscoverCapabilities(params);

        return {
          content: [
            {
              type: 'text',
              text: JSON.stringify(result, null, 2),
            },
          ],
        };
      }

      case 'broadcast_status': {
        const params = BroadcastStatusSchema.parse(request.params.arguments);
        const result = handleBroadcastStatus(params);

        return {
          content: [
            {
              type: 'text',
              text: JSON.stringify(result, null, 2),
            },
          ],
        };
      }

      case 'get_mesh_activity': {
        const params = GetMeshActivitySchema.parse(request.params.arguments);
        const result = handleGetMeshActivity(params);

        return {
          content: [
            {
              type: 'text',
              text: JSON.stringify(result, null, 2),
            },
          ],
        };
      }

      default:
        throw new Error(`Unknown tool: ${request.params.name}`);
    }
  } catch (error) {
    if (error instanceof z.ZodError) {
      console.error('[Mesh Coordinator] Validation error:', error.errors);
      return {
        content: [
          {
            type: 'text',
            text: JSON.stringify({
              success: false,
              error: 'Validation error',
              details: error.errors,
            }, null, 2),
          },
        ],
        isError: true,
      };
    }

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
 * Start server
 */
async function main() {
  console.error('[Mesh Coordinator] Starting Mesh Coordinator MCP Server v1.0.0');
  console.error(`[Mesh Coordinator] Database: ${process.env.CATALYST_QUALITY_DB || '{{CATALYST_ROOT}}/monitoring/quality.db'}`);

  // Initialize database
  try {
    getDatabase();
    console.error('[Mesh Coordinator] Database initialized successfully');
  } catch (error) {
    console.error('[Mesh Coordinator] Failed to initialize database:', error);
    process.exit(1);
  }

  // Create transport and connect
  const transport = new StdioServerTransport();
  await server.connect(transport);

  console.error('[Mesh Coordinator] Server started and ready for requests');

  // Handle shutdown gracefully
  process.on('SIGINT', () => {
    console.error('[Mesh Coordinator] Received SIGINT, shutting down...');
    closeDatabase();
    process.exit(0);
  });

  process.on('SIGTERM', () => {
    console.error('[Mesh Coordinator] Received SIGTERM, shutting down...');
    closeDatabase();
    process.exit(0);
  });
}

main().catch((error) => {
  console.error('[Mesh Coordinator] Fatal error:', error);
  process.exit(1);
});
