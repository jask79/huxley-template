/**
 * ps_is_running — health check.
 */
import { z } from 'zod';
import type { ToolDefinition } from './types.js';
import { checkHealth } from '../bridge/health.js';

export const isRunningTool: ToolDefinition = {
  name: 'ps_is_running',
  description:
    'Check whether Adobe Photoshop is running and report version + active document info. Call this before any other ps_* tool to surface a clear error if PS is not launched.',
  inputSchema: { type: 'object', properties: {}, additionalProperties: false },
  zodSchema: z.object({}),
  async handler(_args, ctx) {
    const info = await checkHealth(ctx.bridge);
    if (!info.running) {
      return {
        content: [
          {
            type: 'text',
            text: JSON.stringify(
              {
                running: false,
                appName: info.appName,
                hint: `Photoshop is not running. Open ${info.appName} (or any installed PS) and try again.`,
              },
              null,
              2,
            ),
          },
        ],
      };
    }
    return {
      content: [
        {
          type: 'text',
          text: JSON.stringify(info, null, 2),
        },
      ],
    };
  },
};
