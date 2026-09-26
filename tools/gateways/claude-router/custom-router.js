/**
 * Custom Router for Claude Code Router
 * Routes requests based on Router config (default, think, longContext, etc.)
 */

module.exports = async function router(req, config) {
  try {
    // Get Router configuration from config
    const routerConfig = config.Router || {};

    // Extract route type from request if available
    // Default to "default" route for main requests
    let routeType = 'default';

    // Check if this is a long context request
    const messages = req.messages || [];
    const totalTokens = estimateTokenCount(messages);
    const longContextThreshold = routerConfig.longContextThreshold || 160000;

    if (totalTokens > longContextThreshold) {
      routeType = 'longContext';
    }

    // Get the route for this request type
    const route = routerConfig[routeType];

    if (route && typeof route === 'string') {
      console.log(`[custom-router] Routing via '${routeType}' strategy: ${route}`);
      return route;
    }

    // Fallback to default route
    const defaultRoute = routerConfig.default || 'bifrost-responses,openai/gpt-5.1-codex';
    console.log(`[custom-router] Using default route: ${defaultRoute}`);
    return defaultRoute;

  } catch (error) {
    console.error('[custom-router] Error in routing logic:', error.message);
    // Fallback to safe default
    return 'bifrost-responses,openai/gpt-5.1-codex';
  }
};

/**
 * Estimate token count for messages
 * Rough estimate: ~4 characters per token
 */
function estimateTokenCount(messages) {
  if (!Array.isArray(messages)) return 0;

  let totalChars = 0;
  for (const message of messages) {
    if (typeof message.content === 'string') {
      totalChars += message.content.length;
    } else if (Array.isArray(message.content)) {
      for (const block of message.content) {
        if (block && block.text) {
          totalChars += block.text.length;
        }
      }
    }
  }

  return Math.ceil(totalChars / 4);
}
