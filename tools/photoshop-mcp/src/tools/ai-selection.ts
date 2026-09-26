/**
 * AI / advanced selection tools:
 *   - ps_select_subject
 *   - ps_remove_background
 *   - ps_select_color_range
 *
 * These hit Photoshop's built-in AI features via ActionManager descriptors.
 */
import { z } from 'zod';
import type { ToolDefinition } from './types.js';
import {
  SELECT_SUBJECT_JSX,
  colorRangeJsx,
} from '../bridge/descriptors.js';
import { TIMEOUTS } from '../bridge/timeouts.js';

const SelectSubjectSchema = z.object({});

export const selectSubjectTool: ToolDefinition = {
  name: 'ps_select_subject',
  description:
    "Run Photoshop's AI Select Subject (autoCutout) on the active document. Produces a marching-ants selection around the detected subject. Pair with `ps_remove_background` for one-shot cutouts, or use `ps_create_layer_mask` style follow-ups.",
  inputSchema: { type: 'object', properties: {}, additionalProperties: false },
  zodSchema: SelectSubjectSchema,
  async handler(_args, ctx) {
    await ctx.bridge.exec(
      `
        if (app.documents.length === 0) throw new Error('No active document. Open an image first.');
        ${SELECT_SUBJECT_JSX}
        var sel = app.activeDocument.selection;
        var bounds = null;
        try {
          bounds = [sel.bounds[0].value, sel.bounds[1].value, sel.bounds[2].value, sel.bounds[3].value];
        } catch (e) {
          bounds = null; // No subject detected → empty selection raises
        }
        setResult({ hasSelection: bounds !== null, bounds: bounds });
      `,
      TIMEOUTS.AI_SELECTION,
    );
    return {
      content: [
        {
          type: 'text',
          text: JSON.stringify(
            { ok: true, action: 'select_subject', message: 'Subject selection created' },
            null,
            2,
          ),
        },
      ],
    };
  },
};

const RemoveBgSchema = z.object({
  asMask: z
    .boolean()
    .optional()
    .describe(
      'If true, convert the cutout to a layer mask (non-destructive). If false (default), delete the background pixels.',
    ),
});

export const removeBackgroundTool: ToolDefinition = {
  name: 'ps_remove_background',
  description:
    "One-call background removal: runs Select Subject, inverts the selection, and either deletes the background pixels or applies a layer mask (asMask: true for non-destructive cutout). Active layer must be unlocked. The Background layer is auto-promoted to a regular layer.",
  inputSchema: {
    type: 'object',
    properties: {
      asMask: {
        type: 'boolean',
        description:
          'If true, convert to a layer mask instead of deleting pixels. Defaults to false.',
      },
    },
    additionalProperties: false,
  },
  zodSchema: RemoveBgSchema,
  async handler(args, ctx) {
    const { asMask } = RemoveBgSchema.parse(args ?? {});
    const finishStep = asMask
      ? `
        // Apply selection as a layer mask
        var refMask = new ActionDescriptor();
        var newRef = new ActionReference();
        newRef.putClass(stringIDToTypeID('channel'));
        refMask.putReference(stringIDToTypeID('null'), newRef);
        var atRef = new ActionReference();
        atRef.putEnumerated(stringIDToTypeID('channel'), stringIDToTypeID('channel'), stringIDToTypeID('mask'));
        refMask.putReference(stringIDToTypeID('at'), atRef);
        refMask.putEnumerated(stringIDToTypeID('using'), stringIDToTypeID('userMaskEnabled'), stringIDToTypeID('revealSelection'));
        executeAction(stringIDToTypeID('make'), refMask, DialogModes.NO);
      `
      : `
        // Invert selection then delete background pixels
        doc.selection.invert();
        try { doc.selection.clear(); } catch (e) {
          // If the layer is the Background layer, promote it first
          var bg = doc.activeLayer;
          if (bg.isBackgroundLayer) {
            bg.isBackgroundLayer = false;
          }
          doc.selection.invert();
          ${SELECT_SUBJECT_JSX}
          doc.selection.invert();
          doc.selection.clear();
        }
        doc.selection.deselect();
      `;
    await ctx.bridge.exec(
      `
        if (app.documents.length === 0) throw new Error('No active document. Open an image first.');
        var doc = app.activeDocument;
        // Promote Background layer if needed (delete pixels needs a regular layer)
        if (doc.activeLayer.isBackgroundLayer) {
          doc.activeLayer.isBackgroundLayer = false;
        }
        ${SELECT_SUBJECT_JSX}
        ${finishStep}
        setResult({ method: ${asMask ? "'mask'" : "'delete'"} });
      `,
      TIMEOUTS.REMOVE_BG,
    );
    return {
      content: [
        {
          type: 'text',
          text: JSON.stringify(
            { ok: true, action: 'remove_background', method: asMask ? 'mask' : 'delete' },
            null,
            2,
          ),
        },
      ],
    };
  },
};

const ColorRangeSchema = z.object({
  x: z.number().int().min(0).describe('Pixel X coordinate of the sample point.'),
  y: z.number().int().min(0).describe('Pixel Y coordinate of the sample point.'),
  fuzziness: z
    .number()
    .min(0)
    .max(200)
    .optional()
    .describe('Color tolerance (0-200). Default 40.'),
});

export const selectColorRangeTool: ToolDefinition = {
  name: 'ps_select_color_range',
  description:
    'Color Range selection — select pixels matching the color sampled at (x, y) with a given fuzziness (0-200). Useful for sky replacements and color-keyed cutouts.',
  inputSchema: {
    type: 'object',
    properties: {
      x: { type: 'integer', description: 'Pixel X of sample point.' },
      y: { type: 'integer', description: 'Pixel Y of sample point.' },
      fuzziness: { type: 'number', description: 'Color tolerance 0-200 (default 40).' },
    },
    required: ['x', 'y'],
    additionalProperties: false,
  },
  zodSchema: ColorRangeSchema,
  async handler(args, ctx) {
    const opts = ColorRangeSchema.parse(args);
    const jsx = colorRangeJsx(opts.x, opts.y, opts.fuzziness ?? 40);
    await ctx.bridge.exec(
      `
        if (app.documents.length === 0) throw new Error('No active document.');
        ${jsx}
        setResult({ x: ${opts.x}, y: ${opts.y}, fuzziness: ${opts.fuzziness ?? 40} });
      `,
    );
    return {
      content: [{ type: 'text', text: JSON.stringify({ ok: true, ...opts }, null, 2) }],
    };
  },
};
