/**
 * Agent Capability Registry
 * Defines which agents can provide what capabilities and who they can request help from
 */

export interface AgentCapabilities {
  provides: string[];
  can_request: string[];
}

export const AGENT_CAPABILITIES: Record<string, AgentCapabilities> = {
  "🎨 Frontend Developer": {
    provides: ["react-components", "accessibility-audit", "animation-implementation", "css-styling"],
    can_request: ["🏛️ Backend Developer", "📐 UI Designer", "📱 Mobile Developer"]
  },
  "🏛️ Backend Developer": {
    provides: ["api-design", "database-schema", "authentication", "cloudflare-config"],
    can_request: ["🎨 Frontend Developer", "🛡️ Security Analyst", "📱 Mobile Developer"]
  },
  "📱 Mobile Developer": {
    provides: ["ios-implementation", "react-native", "mobile-testing"],
    can_request: ["🏛️ Backend Developer", "📐 UI Designer", "🎨 Frontend Developer"]
  },
  "📐 UI Designer": {
    provides: ["wireframes", "design-system", "user-flows", "prototypes"],
    can_request: ["🎨 Frontend Developer", "📱 Mobile Developer"]
  },
  "🧐 Code Reviewer": {
    provides: ["code-quality-review", "security-review", "performance-review"],
    can_request: ["👾 Debugger", "🧪 Validator"]
  },
  "👾 Debugger": {
    provides: ["root-cause-analysis", "bug-investigation", "log-analysis"],
    can_request: ["🧐 Code Reviewer", "🧪 Validator"]
  },
  "🧪 Validator": {
    provides: ["functional-testing", "e2e-testing", "performance-testing"],
    can_request: ["🧐 Code Reviewer", "👾 Debugger"]
  }
};

/**
 * Find which agents can provide a specific capability
 */
export function findAgentsByCapability(capability: string): Array<{
  agent_name: string;
  provides: string[];
}> {
  const results: Array<{ agent_name: string; provides: string[] }> = [];

  for (const [agent_name, capabilities] of Object.entries(AGENT_CAPABILITIES)) {
    // Fuzzy match: check if capability is substring of any provided capability
    const hasCapability = capabilities.provides.some(
      provided => provided.includes(capability) || capability.includes(provided)
    );

    if (hasCapability) {
      results.push({
        agent_name,
        provides: capabilities.provides
      });
    }
  }

  return results;
}

/**
 * Check if an agent is allowed to request help from another agent
 */
export function canRequestHelp(from_agent: string, to_agent: string): boolean {
  const fromCapabilities = AGENT_CAPABILITIES[from_agent];

  if (!fromCapabilities) {
    return false; // Unknown agent
  }

  return fromCapabilities.can_request.includes(to_agent);
}

/**
 * Check if an agent should be blocked from direct requests
 */
export function isBlockedTarget(agent: string): boolean {
  const blockedAgents = [
    "👔 BOSS",
    "🛡️ Security Analyst"
  ];

  return blockedAgents.includes(agent);
}

/**
 * Get all capabilities for an agent
 */
export function getAgentCapabilities(agent: string): AgentCapabilities | null {
  return AGENT_CAPABILITIES[agent] || null;
}
