/**
 * ps_match_color — match the active document's color statistics to a reference.
 * The reference is opened temporarily, used as the source, then closed.
 */
import { z } from 'zod';
import { existsSync } from 'node:fs';
import type { ToolDefinition } from './types.js';
import { matchColorJsx } from '../bridge/descriptors.js';
import { jsxStringLiteral } from '../bridge/safety.js';
import { TIMEOUTS } from '../bridge/timeouts.js';

const MatchColorSchema = z.object({
  referencePath: z
    .string()
    .min(1)
    .describe('Absolute path to the reference image whose color is to be matched.'),
  luminance: z
    .number()
    .min(0)
    .max(200)
    .optional()
    .describe('Luminance match strength (0-200). Default 100.'),
  colorIntensity: z
    .number()
    .min(0)
    .max(200)
    .optional()
    .describe('Color intensity (0-200). Default 100.'),
  fade: z
    .number()
    .min(0)
    .max(100)
    .optional()
    .describe('Fade amount (0-100). Default 0 (full effect).'),
});

export const matchColorTool: ToolDefinition = {
  name: 'ps_match_color',
  description:
    "Apply Photoshop's Match Color so the active document picks up the reference image's color statistics. The reference image is opened, used, then closed. Ideal for batch color grading product photos to a brand reference.",
  inputSchema: {
    type: 'object',
    properties: {
      referencePath: { type: 'string', description: 'Absolute path to reference image.' },
      luminance: { type: 'number', description: 'Luminance 0-200 (default 100).' },
      colorIntensity: { type: 'number', description: 'Color intensity 0-200 (default 100).' },
      fade: { type: 'number', description: 'Fade 0-100 (default 0).' },
    },
    required: ['referencePath'],
    additionalProperties: false,
  },
  zodSchema: MatchColorSchema,
  async handler(args, ctx) {
    const opts = MatchColorSchema.parse(args);
    if (!opts.referencePath.startsWith('/')) {
      throw new Error(`referencePath must be absolute: ${opts.referencePath}`);
    }
    if (!existsSync(opts.referencePath)) {
      throw new Error(`Reference file not found: ${opts.referencePath}`);
    }
    const escPath = jsxStringLiteral(opts.referencePath);
    const matchJsx = matchColorJsx('__catalyst_match_ref__', {
      luminance: opts.luminance,
      colorIntensity: opts.colorIntensity,
      fade: opts.fade,
    });
    await ctx.bridge.exec(
      `
        if (app.documents.length === 0) throw new Error('No active document — open the target first.');
        var target = app.activeDocument;
        var refFile = new File('${escPath}');
        if (!refFile.exists) throw new Error('Reference not found at runtime: ${escPath}');
        var refDoc = app.open(refFile);
        // Rename reference to a stable known name so the descriptor can find it
        refDoc.name = '__catalyst_match_ref__';
        // Switch back to target as active before invoking matchColor
        app.activeDocument = target;
        try {
          ${matchJsx}
        } finally {
          // Always close the reference doc without saving
          try { refDoc.close(SaveOptions.DONOTSAVECHANGES); } catch (e) {}
          app.activeDocument = target;
        }
        setResult({ matched: true });
      `,
      TIMEOUTS.MATCH_COLOR,
    );
    return {
      content: [
        {
          type: 'text',
          text: JSON.stringify({ ok: true, action: 'match_color', referencePath: opts.referencePath }, null, 2),
        },
      ],
    };
  },
};
