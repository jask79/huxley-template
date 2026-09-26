/**
 * Request Routing Logic
 * Validates and routes mesh communication requests between agents
 */

import { z } from 'zod';
import {
  canRequestHelp,
  isBlockedTarget,
  findAgentsByCapability
} from './registry.js';
import {
  logMeshCommunication,
  logStatusBroadcast,
  getMeshActivity,
  type MeshCommunicationLog,
  type StatusBroadcastLog,
  type GetMeshActivityParams
} from './audit.js';

/**
 * Schema for request_peer_help
 */
export const RequestPeerHelpSchema = z.object({
  from_agent: z.string().min(1, "from_agent is required"),
  to_agent: z.string().min(1, "to_agent is required"),
  request_type: z.string().min(1, "request_type is required"),
  context: z.string().min(1, "context is required"),
  urgency: z.enum(['blocking', 'nice_to_have', 'fyi']).default('nice_to_have')
});

export type RequestPeerHelpParams = z.infer<typeof RequestPeerHelpSchema>;

/**
 * Handle request_peer_help tool
 */
export function handleRequestPeerHelp(params: RequestPeerHelpParams): {
  session_id: string;
  status: 'allowed' | 'blocked';
  message: string;
  block_reason?: string;
} {
  // Generate session ID
  const session_id = `mesh-${Date.now()}-${Math.random().toString(36).substring(2, 9)}`;

  // Check if target agent is blocked
  if (isBlockedTarget(params.to_agent)) {
    const block_reason = `Agent ${params.to_agent} cannot be requested directly. All requests must go through {{ORCHESTRATOR_NAME}}.`;

    const log: MeshCommunicationLog = {
      ...params,
      session_id,
      status: 'blocked',
      block_reason
    };

    logMeshCommunication(log);

    return {
      session_id,
      status: 'blocked',
      message: `Request blocked: ${params.to_agent} requires {{ORCHESTRATOR_NAME}} oversight`,
      block_reason
    };
  }

  // Check if request is within allowed capability mapping
  if (!canRequestHelp(params.from_agent, params.to_agent)) {
    const block_reason = `Agent ${params.from_agent} is not authorized to request help from ${params.to_agent}. Check capability registry.`;

    const log: MeshCommunicationLog = {
      ...params,
      session_id,
      status: 'blocked',
      block_reason
    };

    logMeshCommunication(log);

    return {
      session_id,
      status: 'blocked',
      message: `Request blocked: Not in capability mapping`,
      block_reason
    };
  }

  // Request is allowed - log it
  const log: MeshCommunicationLog = {
    ...params,
    session_id,
    status: 'allowed'
  };

  logMeshCommunication(log);

  return {
    session_id,
    status: 'allowed',
    message: `Request approved. Session ID: ${session_id}. ${params.to_agent} has been notified via {{ORCHESTRATOR_NAME}}.`
  };
}

/**
 * Schema for discover_capabilities
 */
export const DiscoverCapabilitiesSchema = z.object({
  capability: z.string().min(1, "capability is required")
});

export type DiscoverCapabilitiesParams = z.infer<typeof DiscoverCapabilitiesSchema>;

/**
 * Handle discover_capabilities tool
 */
export function handleDiscoverCapabilities(params: DiscoverCapabilitiesParams): {
  capability: string;
  agents: Array<{ agent_name: string; provides: string[] }>;
} {
  const agents = findAgentsByCapability(params.capability);

  return {
    capability: params.capability,
    agents
  };
}

/**
 * Schema for broadcast_status
 */
export const BroadcastStatusSchema = z.object({
  from_agent: z.string().min(1, "from_agent is required"),
  status: z.string().min(1, "status is required"),
  message: z.string().min(1, "message is required"),
  session_id: z.string().optional()
});

export type BroadcastStatusParams = z.infer<typeof BroadcastStatusSchema>;

/**
 * Handle broadcast_status tool
 */
export function handleBroadcastStatus(params: BroadcastStatusParams): {
  acknowledged: boolean;
  message: string;
} {
  const log: StatusBroadcastLog = {
    from_agent: params.from_agent,
    status: params.status,
    message: params.message,
    session_id: params.session_id
  };

  logStatusBroadcast(log);

  return {
    acknowledged: true,
    message: `Status broadcast from ${params.from_agent} logged. {{ORCHESTRATOR_NAME}} will be notified.`
  };
}

/**
 * Schema for get_mesh_activity
 */
export const GetMeshActivitySchema = z.object({
  limit: z.number().int().positive().default(50),
  since: z.string().optional()
});

export type GetMeshActivityParamsInput = z.infer<typeof GetMeshActivitySchema>;

/**
 * Handle get_mesh_activity tool
 */
export function handleGetMeshActivity(params: GetMeshActivityParamsInput): {
  total: number;
  communications: Array<Record<string, unknown>>;
} {
  const communications = getMeshActivity(params as GetMeshActivityParams);

  return {
    total: communications.length,
    communications
  };
}
