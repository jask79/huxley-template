/**
 * ps_place_smart_object — place a file into the active doc as an embedded
 * smart object (non-destructive scale, etc.).
 *
 * NOTE (v1): we only support EMBEDDED smart objects. Linked smart objects use
 * a different ActionDescriptor (`placeLinked`/`PlcL`) and were silently broken
 * in the prior implementation — claiming `linked: true` while still issuing a
 * `placeEvent`. Rather than ship a broken option, we removed the schema
 * surface entirely. Re-add via a proper `placeLinked` descriptor in v2.
 */
import { z } from 'zod';
import { existsSync } from 'node:fs';
import type { ToolDefinition } from './types.js';
import { jsxStringLiteral } from '../bridge/safety.js';
import { TIMEOUTS } from '../bridge/timeouts.js';

const PlaceSmartObjectSchema = z.object({
  path: z.string().min(1).describe('Absolute path to the file to place.'),
  x: z.number().optional().describe('Pixel X to translate the placed layer to (top-left origin). Default: centered.'),
  y: z.number().optional().describe('Pixel Y to translate the placed layer to. Default: centered.'),
  scale: z
    .number()
    .min(0.01)
    .max(10)
    .optional()
    .describe('Uniform scale factor (1.0 = original). Default 1.0.'),
});

export const placeSmartObjectTool: ToolDefinition = {
  name: 'ps_place_smart_object',
  description:
    'Place a file (PSD/AI/SVG/PNG/JPG) into the active document as an EMBEDDED smart object — non-destructive, scales without quality loss. Optionally position and scale. Linked smart objects are not supported in v1 (require a separate placeLinked descriptor).',
  inputSchema: {
    type: 'object',
    properties: {
      path: { type: 'string', description: 'Absolute path to file to place.' },
      x: { type: 'number', description: 'X position in pixels (top-left origin).' },
      y: { type: 'number', description: 'Y position in pixels.' },
      scale: { type: 'number', description: 'Uniform scale factor (default 1.0).' },
    },
    required: ['path'],
    additionalProperties: false,
  },
  zodSchema: PlaceSmartObjectSchema,
  async handler(args, ctx) {
    const opts = PlaceSmartObjectSchema.parse(args);
    if (!opts.path.startsWith('/')) {
      throw new Error(`path must be absolute: ${opts.path}`);
    }
    if (!existsSync(opts.path)) {
      throw new Error(`File not found: ${opts.path}`);
    }
    const escPath = jsxStringLiteral(opts.path);
    const scale = opts.scale ?? 1.0;
    const positionJsx =
      typeof opts.x === 'number' && typeof opts.y === 'number'
        ? `
          var bounds = doc.activeLayer.bounds;
          var curX = bounds[0].value;
          var curY = bounds[1].value;
          doc.activeLayer.translate(${opts.x} - curX, ${opts.y} - curY);
        `
        : '';
    const scaleJsx =
      scale !== 1.0
        ? `doc.activeLayer.resize(${scale * 100}, ${scale * 100}, AnchorPosition.MIDDLECENTER);`
        : '';
    await ctx.bridge.exec(
      `
        if (app.documents.length === 0) throw new Error('No active document.');
        var doc = app.activeDocument;
        // ActionManager 'placeEvent' creates an embedded smart object. Linked
        // smart objects require a separate 'placeLinked' (charID 'PlcL')
        // descriptor — deferred to v2.
        var d = new ActionDescriptor();
        d.putPath(stringIDToTypeID('null'), new File('${escPath}'));
        d.putEnumerated(stringIDToTypeID('freeTransformCenterState'), stringIDToTypeID('quadCenterState'), stringIDToTypeID('QCSAverage'));
        d.putUnitDouble(stringIDToTypeID('offset'), stringIDToTypeID('pixelsUnit'), 0.0);
        d.putUnitDouble(stringIDToTypeID('width'), stringIDToTypeID('percentUnit'), 100.0);
        d.putUnitDouble(stringIDToTypeID('height'), stringIDToTypeID('percentUnit'), 100.0);
        executeAction(stringIDToTypeID('placeEvent'), d, DialogModes.NO);
        ${scaleJsx}
        ${positionJsx}
        var b = doc.activeLayer.bounds;
        setResult({
          name: doc.activeLayer.name,
          bounds: [b[0].value, b[1].value, b[2].value, b[3].value]
        });
      `,
      TIMEOUTS.PLACE_SMART_OBJECT,
    );
    return {
      content: [{ type: 'text', text: JSON.stringify({ ok: true, ...opts }, null, 2) }],
    };
  },
};
