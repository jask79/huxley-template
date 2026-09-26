/**
 * ps_apply_layer_style — drop shadow, stroke, outer glow on the active layer.
 */
import { z } from 'zod';
import type { ToolDefinition } from './types.js';
import { layerStyleJsx } from '../bridge/descriptors.js';

const RGBSchema = z.tuple([z.number().min(0).max(255), z.number().min(0).max(255), z.number().min(0).max(255)]);

const DropShadowSchema = z
  .object({
    enabled: z.boolean().optional(),
    opacity: z.number().min(0).max(100).optional(),
    angle: z.number().optional(),
    distance: z.number().min(0).optional(),
    spread: z.number().min(0).max(100).optional(),
    size: z.number().min(0).optional(),
    color: RGBSchema.optional(),
    blendMode: z.enum(['multiply', 'normal', 'screen', 'overlay']).optional(),
  })
  .partial();

const StrokeSchema = z
  .object({
    enabled: z.boolean().optional(),
    size: z.number().min(0).optional(),
    opacity: z.number().min(0).max(100).optional(),
    position: z.enum(['outsideFrame', 'insideFrame', 'centeredFrame']).optional(),
    color: RGBSchema.optional(),
  })
  .partial();

const OuterGlowSchema = z
  .object({
    enabled: z.boolean().optional(),
    opacity: z.number().min(0).max(100).optional(),
    size: z.number().min(0).optional(),
    spread: z.number().min(0).max(100).optional(),
    color: RGBSchema.optional(),
  })
  .partial();

const ApplyLayerStyleSchema = z.object({
  dropShadow: DropShadowSchema.optional(),
  stroke: StrokeSchema.optional(),
  outerGlow: OuterGlowSchema.optional(),
});

export const applyLayerStyleTool: ToolDefinition = {
  name: 'ps_apply_layer_style',
  description:
    'Apply layer styles (drop shadow, stroke, outer glow) to the active layer. Each style block is optional. Color values are [R, G, B] tuples 0-255.',
  inputSchema: {
    type: 'object',
    properties: {
      dropShadow: {
        type: 'object',
        description: 'Drop shadow settings.',
        properties: {
          opacity: { type: 'number' },
          angle: { type: 'number' },
          distance: { type: 'number' },
          spread: { type: 'number' },
          size: { type: 'number' },
          color: { type: 'array', items: { type: 'number' }, minItems: 3, maxItems: 3 },
          blendMode: { type: 'string', enum: ['multiply', 'normal', 'screen', 'overlay'] },
        },
      },
      stroke: {
        type: 'object',
        description: 'Stroke settings.',
        properties: {
          size: { type: 'number' },
          opacity: { type: 'number' },
          position: { type: 'string', enum: ['outsideFrame', 'insideFrame', 'centeredFrame'] },
          color: { type: 'array', items: { type: 'number' }, minItems: 3, maxItems: 3 },
        },
      },
      outerGlow: {
        type: 'object',
        description: 'Outer glow settings.',
        properties: {
          opacity: { type: 'number' },
          size: { type: 'number' },
          spread: { type: 'number' },
          color: { type: 'array', items: { type: 'number' }, minItems: 3, maxItems: 3 },
        },
      },
    },
    additionalProperties: false,
  },
  zodSchema: ApplyLayerStyleSchema,
  async handler(args, ctx) {
    const opts = ApplyLayerStyleSchema.parse(args ?? {});
    if (!opts.dropShadow && !opts.stroke && !opts.outerGlow) {
      throw new Error('At least one of dropShadow, stroke, outerGlow must be provided.');
    }
    const jsx = layerStyleJsx(opts);
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
