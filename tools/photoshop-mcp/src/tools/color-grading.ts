/**
 * ps_apply_curves and ps_apply_levels — color grading via ActionManager.
 */
import { z } from 'zod';
import type { ToolDefinition } from './types.js';
import { curvesJsx, levelsJsx } from '../bridge/descriptors.js';

const ChannelEnum = z.enum(['composite', 'red', 'green', 'blue']);

const CurvePointSchema = z.object({
  input: z.number().min(0).max(255).describe('Input level 0-255.'),
  output: z.number().min(0).max(255).describe('Output level 0-255.'),
});

const ApplyCurvesSchema = z.object({
  points: z
    .array(CurvePointSchema)
    .min(2)
    .describe(
      'Curve control points (at least 2). Default linear is { input: 0, output: 0 } and { input: 255, output: 255 }.',
    ),
  channel: ChannelEnum.optional().describe('Channel to adjust. Default: composite.'),
});

export const applyCurvesTool: ToolDefinition = {
  name: 'ps_apply_curves',
  description:
    'Apply a Curves adjustment to the active layer. Provide a list of {input, output} control points (0-255 each) and an optional channel (composite, red, green, blue). Destructive — apply to a copy if you want non-destructive.',
  inputSchema: {
    type: 'object',
    properties: {
      points: {
        type: 'array',
        items: {
          type: 'object',
          properties: {
            input: { type: 'number' },
            output: { type: 'number' },
          },
          required: ['input', 'output'],
        },
        description: 'Curve control points.',
      },
      channel: {
        type: 'string',
        enum: ['composite', 'red', 'green', 'blue'],
      },
    },
    required: ['points'],
    additionalProperties: false,
  },
  zodSchema: ApplyCurvesSchema,
  async handler(args, ctx) {
    const opts = ApplyCurvesSchema.parse(args);
    const jsx = curvesJsx(opts.points, opts.channel ?? 'composite');
    await ctx.bridge.exec(
      `
        if (app.documents.length === 0) throw new Error('No active document.');
        ${jsx}
        setResult({ applied: true, points: ${opts.points.length} });
      `,
    );
    return { content: [{ type: 'text', text: JSON.stringify({ ok: true, ...opts }, null, 2) }] };
  },
};

const ApplyLevelsSchema = z.object({
  inputBlack: z.number().min(0).max(253).optional().describe('Input black point (0-253). Default 0.'),
  inputWhite: z.number().min(2).max(255).optional().describe('Input white point (2-255). Default 255.'),
  gamma: z.number().min(0.1).max(9.99).optional().describe('Gamma midtone (0.10-9.99). Default 1.0.'),
  outputBlack: z.number().min(0).max(253).optional().describe('Output black point (0-253). Default 0.'),
  outputWhite: z.number().min(2).max(255).optional().describe('Output white point (2-255). Default 255.'),
  channel: ChannelEnum.optional().describe('Channel to adjust. Default: composite.'),
});

export const applyLevelsTool: ToolDefinition = {
  name: 'ps_apply_levels',
  description:
    'Apply a Levels adjustment to the active layer. Set input/output black & white points, gamma, and channel. Defaults are pass-through (no change).',
  inputSchema: {
    type: 'object',
    properties: {
      inputBlack: { type: 'number' },
      inputWhite: { type: 'number' },
      gamma: { type: 'number' },
      outputBlack: { type: 'number' },
      outputWhite: { type: 'number' },
      channel: { type: 'string', enum: ['composite', 'red', 'green', 'blue'] },
    },
    additionalProperties: false,
  },
  zodSchema: ApplyLevelsSchema,
  async handler(args, ctx) {
    const opts = ApplyLevelsSchema.parse(args ?? {});
    const jsx = levelsJsx(opts);
    await ctx.bridge.exec(
      `
        if (app.documents.length === 0) throw new Error('No active document.');
        ${jsx}
        setResult({ applied: true });
      `,
    );
    return { content: [{ type: 'text', text: JSON.stringify({ ok: true, ...opts }, null, 2) }] };
  },
};
