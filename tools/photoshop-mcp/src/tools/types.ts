/**
 * Shared types for Huxley Photoshop MCP tool definitions.
 */
import type { z } from 'zod';
import type { CallToolResult } from '@modelcontextprotocol/sdk/types.js';
import type { PhotoshopBridge } from '../bridge/extendscript.js';
import type { TemplateRegistry } from '../templates/registry.js';

export interface ToolContext {
  bridge: PhotoshopBridge;
  templates: TemplateRegistry;
}

/**
 * Tool handlers return the MCP SDK's `CallToolResult` directly so the server
 * dispatch can pass results through with a single, unambiguous cast (or none
 * at all). Re-exported for downstream callers that prefer the local name.
 */
export type ToolResult = CallToolResult;

export interface ToolDefinition {
  name: string;
  description: string;
  inputSchema: Record<string, unknown>;
  zodSchema: z.ZodTypeAny;
  /** Optional MCP tool annotations (read-only, destructive, etc). */
  annotations?: {
    readOnlyHint?: boolean;
    destructiveHint?: boolean;
    idempotentHint?: boolean;
    openWorldHint?: boolean;
  };
  handler: (args: unknown, ctx: ToolContext) => Promise<ToolResult>;
}
