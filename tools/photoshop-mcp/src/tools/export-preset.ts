/**
 * ps_export_preset — multi-size export packs (Shopify, YT thumbnail, IG, etc.).
 *
 * Strategy: snapshot the active doc once, then for each target:
 *   - duplicate the doc
 *   - resize to target dims
 *   - flatten + save in target format
 *   - close the duplicate
 * The original document is left untouched.
 */
import { z } from 'zod';
import { dirname, resolve as pathResolve } from 'node:path';
import { existsSync } from 'node:fs';
import { mkdir } from 'node:fs/promises';
import type { ToolDefinition } from './types.js';
import { assertWithin, jsxStringLiteral } from '../bridge/safety.js';
import { TIMEOUTS } from '../bridge/timeouts.js';

const ExportPresetSchema = z.object({
  preset: z.string().min(1).describe('Preset name (shopify-product, yt-thumbnail, ig-square, ig-story, or custom registered).'),
  outputDir: z.string().min(1).describe('Absolute directory where exports will be written.'),
  baseFilename: z
    .string()
    .min(1)
    .describe('Base filename — substituted into the preset filename template (e.g., "midnight-rain" → "midnight-rain-thumb.jpg").'),
});

export const exportPresetTool: ToolDefinition = {
  name: 'ps_export_preset',
  description:
    "Export the active document at a registered preset's dimensions and formats. Built-in presets: shopify-product (480/1024/2048 PNG), yt-thumbnail (1280x720 JPG q11), ig-square (1080x1080), ig-story (1080x1920). The original document is preserved.",
  inputSchema: {
    type: 'object',
    properties: {
      preset: {
        type: 'string',
        description: 'Registered preset name.',
      },
      outputDir: {
        type: 'string',
        description: 'Absolute output directory.',
      },
      baseFilename: {
        type: 'string',
        description: 'Base filename without extension (template substitution).',
      },
    },
    required: ['preset', 'outputDir', 'baseFilename'],
    additionalProperties: false,
  },
  zodSchema: ExportPresetSchema,
  async handler(args, ctx) {
    const opts = ExportPresetSchema.parse(args);
    if (!opts.outputDir.startsWith('/')) {
      throw new Error(`outputDir must be absolute: ${opts.outputDir}`);
    }
    const preset = ctx.templates.getExportPreset(opts.preset);
    if (!preset) {
      const available = ctx.templates
        .listExportPresets()
        .map((p) => p.name)
        .join(', ');
      throw new Error(`Unknown preset '${opts.preset}'. Available: ${available}`);
    }

    const resolvedOutputDir = pathResolve(opts.outputDir);
    if (!existsSync(resolvedOutputDir)) {
      await mkdir(resolvedOutputDir, { recursive: true });
    }

    const written: string[] = [];

    for (const target of preset.targets) {
      const filename = target.filename.replace('{base}', opts.baseFilename);
      const fullPath = `${resolvedOutputDir.replace(/\/$/, '')}/${filename}`;
      // Defense-in-depth: a malicious preset filename or `{base}` value could
      // contain `../`. Resolve the full output path and assert it stays under
      // the requested output directory.
      assertWithin(resolvedOutputDir, fullPath);
      const outDir = dirname(fullPath);
      if (!existsSync(outDir)) {
        await mkdir(outDir, { recursive: true });
      }

      const escPath = jsxStringLiteral(fullPath);
      const w = target.width;
      const h = target.height;
      const resizeJsx =
        w && h
          ? `dup.resizeImage(UnitValue(${w}, 'px'), UnitValue(${h}, 'px'), null, ResampleMethod.BICUBICSHARPER);`
          : '';

      let saveJsx: string;
      switch (target.format) {
        case 'png':
          saveJsx = `var opt = new PNGSaveOptions(); opt.interlaced = false; dup.saveAs(new File('${escPath}'), opt, true, Extension.LOWERCASE);`;
          break;
        case 'jpg':
        case 'jpeg':
          saveJsx = `var opt = new JPEGSaveOptions(); opt.quality = ${target.quality ?? 10}; opt.embedColorProfile = true; opt.formatOptions = FormatOptions.STANDARDBASELINE; dup.saveAs(new File('${escPath}'), opt, true, Extension.LOWERCASE);`;
          break;
        case 'tif':
          saveJsx = `var opt = new TiffSaveOptions(); opt.imageCompression = TIFFEncoding.TIFFLZW; dup.saveAs(new File('${escPath}'), opt, true, Extension.LOWERCASE);`;
          break;
        default:
          throw new Error(`Unsupported preset format: ${target.format}`);
      }

      await ctx.bridge.exec(
        `
          if (app.documents.length === 0) throw new Error('No active document to export.');
          var orig = app.activeDocument;
          var dup = orig.duplicate(orig.name + '_export', true);
          try {
            ${resizeJsx}
            dup.flatten();
            ${saveJsx}
          } finally {
            dup.close(SaveOptions.DONOTSAVECHANGES);
            app.activeDocument = orig;
          }
          setResult({ saved: '${escPath}' });
        `,
        TIMEOUTS.EXPORT_PRESET,
      );
      written.push(fullPath);
    }

    return {
      content: [
        {
          type: 'text',
          text: JSON.stringify(
            { ok: true, preset: opts.preset, outputDir: opts.outputDir, files: written },
            null,
            2,
          ),
        },
      ],
    };
  },
};
