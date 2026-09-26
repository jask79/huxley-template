/**
 * Document-level tools: open, save, close, info.
 *
 * These are the minimum file-handling primitives needed for the value-add
 * Huxley tools (export presets, batch processing, brand templates) to be
 * useful end-to-end. We deliberately keep this set small — {{ORCHESTRATOR_NAME}} still has
 * `ps_execute_jsx` as an escape hatch for anything not exposed.
 */
import { z } from 'zod';
import { existsSync } from 'node:fs';
import { dirname } from 'node:path';
import { mkdir } from 'node:fs/promises';
import type { ToolDefinition } from './types.js';
import { jsxStringLiteral } from '../bridge/safety.js';

const OpenSchema = z.object({
  path: z.string().min(1).describe('Absolute path to the image file to open.'),
});

export const openImageTool: ToolDefinition = {
  name: 'ps_open_image',
  description:
    'Open an image file in Photoshop. Path must be absolute. Photoshop will become the active doc.',
  inputSchema: {
    type: 'object',
    properties: {
      path: { type: 'string', description: 'Absolute path to the image file to open.' },
    },
    required: ['path'],
    additionalProperties: false,
  },
  zodSchema: OpenSchema,
  async handler(args, ctx) {
    const { path } = OpenSchema.parse(args);
    // macOS-only: this MCP server runs PS via osascript, which is macOS-only,
    // so absolute paths are POSIX-style and start with '/'.
    if (!path.startsWith('/')) {
      throw new Error(`path must be absolute, got: ${path}`);
    }
    if (!existsSync(path)) {
      throw new Error(`File not found: ${path}`);
    }
    const escPath = jsxStringLiteral(path);
    const out = await ctx.bridge.exec<{ name: string; width: number; height: number }>(
      `
        var f = new File('${escPath}');
        if (!f.exists) { throw new Error('File does not exist: ${escPath}'); }
        var doc = app.open(f);
        setResult({ name: doc.name, width: doc.width.value, height: doc.height.value });
      `,
    );
    return { content: [{ type: 'text', text: JSON.stringify({ ok: true, ...out }, null, 2) }] };
  },
};

const SaveSchema = z.object({
  path: z
    .string()
    .min(1)
    .describe('Absolute path to save to. Format inferred from extension (.psd/.png/.jpg/.jpeg/.tif).'),
  quality: z
    .number()
    .min(0)
    .max(12)
    .optional()
    .describe('JPEG quality (0-12). Defaults to 10. Ignored for non-JPEG formats.'),
  flatten: z
    .boolean()
    .optional()
    .describe('Flatten the document before saving. Defaults to false.'),
});

export const saveDocumentTool: ToolDefinition = {
  name: 'ps_save_document',
  description:
    'Save the active Photoshop document to an absolute path. Format inferred from extension (.psd, .png, .jpg/.jpeg, .tif).',
  inputSchema: {
    type: 'object',
    properties: {
      path: { type: 'string', description: 'Absolute output path.' },
      quality: { type: 'number', description: 'JPEG quality 0-12 (default 10).' },
      flatten: { type: 'boolean', description: 'Flatten before saving.' },
    },
    required: ['path'],
    additionalProperties: false,
  },
  zodSchema: SaveSchema,
  async handler(args, ctx) {
    const opts = SaveSchema.parse(args);
    // macOS-only (osascript) → absolute paths must start with '/'.
    if (!opts.path.startsWith('/')) {
      throw new Error(`path must be absolute, got: ${opts.path}`);
    }
    const dir = dirname(opts.path);
    if (!existsSync(dir)) {
      await mkdir(dir, { recursive: true });
    }
    const ext = opts.path.split('.').pop()?.toLowerCase() ?? '';
    const escPath = jsxStringLiteral(opts.path);
    const flatten = opts.flatten ? 'doc.flatten();' : '';
    // Build per-format save JSX. Quality is JPEG-only and is only emitted in
    // the JPEG branch — never for PNG/TIFF/PSD where it would be a no-op (or
    // worse, confuse a future reader).
    let saveJsx: string;
    switch (ext) {
      case 'psd':
        saveJsx = `var opt = new PhotoshopSaveOptions(); opt.embedColorProfile = true; doc.saveAs(new File('${escPath}'), opt, true, Extension.LOWERCASE);`;
        break;
      case 'png':
        saveJsx = `var opt = new PNGSaveOptions(); opt.interlaced = false; doc.saveAs(new File('${escPath}'), opt, true, Extension.LOWERCASE);`;
        break;
      case 'jpg':
      case 'jpeg': {
        const q = opts.quality ?? 10;
        saveJsx = `var opt = new JPEGSaveOptions(); opt.quality = ${q}; opt.embedColorProfile = true; opt.formatOptions = FormatOptions.STANDARDBASELINE; doc.saveAs(new File('${escPath}'), opt, true, Extension.LOWERCASE);`;
        break;
      }
      case 'tif':
      case 'tiff':
        saveJsx = `var opt = new TiffSaveOptions(); opt.imageCompression = TIFFEncoding.TIFFLZW; doc.saveAs(new File('${escPath}'), opt, true, Extension.LOWERCASE);`;
        break;
      default:
        throw new Error(`Unsupported extension: .${ext}. Use psd, png, jpg, jpeg, tif, tiff.`);
    }
    await ctx.bridge.exec(
      `
        if (app.documents.length === 0) throw new Error('No active document to save.');
        var doc = app.activeDocument;
        ${flatten}
        ${saveJsx}
        setResult({ saved: '${escPath}' });
      `,
    );
    return {
      content: [
        { type: 'text', text: JSON.stringify({ ok: true, saved: opts.path }, null, 2) },
      ],
    };
  },
};

const CloseSchema = z.object({
  saveChanges: z.boolean().optional().describe('Save changes before closing. Default false.'),
});

export const closeDocumentTool: ToolDefinition = {
  name: 'ps_close_document',
  description: 'Close the active Photoshop document. Defaults to discarding unsaved changes.',
  inputSchema: {
    type: 'object',
    properties: {
      saveChanges: { type: 'boolean', description: 'Save changes before closing. Default false.' },
    },
    additionalProperties: false,
  },
  zodSchema: CloseSchema,
  async handler(args, ctx) {
    const { saveChanges } = CloseSchema.parse(args ?? {});
    const mode = saveChanges ? 'SaveOptions.SAVECHANGES' : 'SaveOptions.DONOTSAVECHANGES';
    await ctx.bridge.exec(
      `
        if (app.documents.length === 0) {
          setResult({ closed: 0 });
        } else {
          app.activeDocument.close(${mode});
          setResult({ closed: 1 });
        }
      `,
    );
    return { content: [{ type: 'text', text: JSON.stringify({ ok: true }, null, 2) }] };
  },
};

const ResizeSchema = z.object({
  width: z.number().int().positive().describe('New width in pixels.'),
  height: z.number().int().positive().describe('New height in pixels.'),
  resampleMethod: z
    .enum(['bicubic', 'bicubicSharper', 'bicubicSmoother', 'bilinear', 'nearestNeighbor', 'automatic'])
    .optional()
    .describe('Resampling method. Default bicubicSharper for downscale.'),
});

export const resizeImageTool: ToolDefinition = {
  name: 'ps_resize_image',
  description:
    'Resize the active document to width x height in pixels. Used by export presets to produce multi-size packs.',
  inputSchema: {
    type: 'object',
    properties: {
      width: { type: 'integer', description: 'New width in pixels.' },
      height: { type: 'integer', description: 'New height in pixels.' },
      resampleMethod: { type: 'string', description: 'Resampling method.' },
    },
    required: ['width', 'height'],
    additionalProperties: false,
  },
  zodSchema: ResizeSchema,
  async handler(args, ctx) {
    const opts = ResizeSchema.parse(args);
    // Map to ResampleMethod enum names.
    const enumMap: Record<string, string> = {
      bicubic: 'BICUBIC',
      bicubicSharper: 'BICUBICSHARPER',
      bicubicSmoother: 'BICUBICSMOOTHER',
      bilinear: 'BILINEAR',
      nearestNeighbor: 'NEARESTNEIGHBOR',
      automatic: 'AUTOMATIC',
    };
    const enumName = enumMap[opts.resampleMethod ?? 'bicubicSharper'] ?? 'BICUBICSHARPER';
    await ctx.bridge.exec(
      `
        if (app.documents.length === 0) throw new Error('No active document.');
        var doc = app.activeDocument;
        doc.resizeImage(UnitValue(${opts.width}, 'px'), UnitValue(${opts.height}, 'px'), null, ResampleMethod.${enumName});
        setResult({ width: ${opts.width}, height: ${opts.height} });
      `,
    );
    return { content: [{ type: 'text', text: JSON.stringify({ ok: true, ...opts }, null, 2) }] };
  },
};

const ExecuteJsxSchema = z.object({
  script: z.string().min(1).describe('Raw ExtendScript JSX to run inside Photoshop.'),
  timeoutMs: z.number().int().positive().optional().describe('Override default 60s timeout.'),
});

/**
 * `ps_execute_jsx` is gated behind the `PHOTOSHOP_MCP_ALLOW_RAW_JSX=1` env var.
 * Consult `isRawJsxAllowed()` from the tool registry; the tool is hidden from
 * the public tool list when the env var is not set.
 */
export function isRawJsxAllowed(): boolean {
  return process.env.PHOTOSHOP_MCP_ALLOW_RAW_JSX === '1';
}

export const executeJsxTool: ToolDefinition = {
  name: 'ps_execute_jsx',
  description:
    'Escape hatch — run an arbitrary ExtendScript JSX snippet in Photoshop. Assign to `result` or call `setResult(value)` inside the script to return data. SECURITY: this runs arbitrary JSX inside Photoshop. Do not expose this MCP server to untrusted clients with this tool enabled.',
  inputSchema: {
    type: 'object',
    properties: {
      script: { type: 'string', description: 'ExtendScript JSX code.' },
      timeoutMs: { type: 'integer', description: 'Override default 60000ms timeout.' },
    },
    required: ['script'],
    additionalProperties: false,
  },
  zodSchema: ExecuteJsxSchema,
  annotations: { destructiveHint: true },
  async handler(args, ctx) {
    const opts = ExecuteJsxSchema.parse(args);
    const value = await ctx.bridge.exec(opts.script, opts.timeoutMs);
    return { content: [{ type: 'text', text: JSON.stringify({ ok: true, value }, null, 2) }] };
  },
};
