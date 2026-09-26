/**
 * ps_batch_folder — iterate every image in a folder, run a sequence of tool
 * calls per image, and write outputs.
 *
 * The "tool sequence" is intentionally a small enumerated set (not arbitrary
 * MCP-tool-recursion) so this stays predictable. Supported steps:
 *   - select_subject
 *   - remove_background ({ asMask })
 *   - select_color_range ({ x, y, fuzziness })
 *   - apply_curves ({ points, channel })
 *   - apply_levels (LevelsSpec)
 *   - apply_layer_style (LayerStyleSpec)
 *   - export_preset ({ preset, baseFilename? })
 *   - save ({ format })
 *
 * Each file is opened, the sequence is run, then the file is closed. Errors
 * on individual files don't abort the batch — they accumulate.
 */
import { z } from 'zod';
import { existsSync, readdirSync } from 'node:fs';
import { join, basename, extname, resolve as pathResolve } from 'node:path';
import type { ToolDefinition, ToolResult } from './types.js';
import { assertWithinAllowedRoots } from '../bridge/safety.js';
import { selectSubjectTool, removeBackgroundTool, selectColorRangeTool } from './ai-selection.js';
import { applyCurvesTool, applyLevelsTool } from './color-grading.js';
import { applyLayerStyleTool } from './layer-style.js';
import { exportPresetTool } from './export-preset.js';
import { openImageTool, closeDocumentTool, saveDocumentTool } from './document.js';
import { matchColorTool } from './match-color.js';

const SUPPORTED_EXTS = new Set(['.jpg', '.jpeg', '.png', '.tif', '.tiff', '.psd']);

const StepSchema = z.discriminatedUnion('action', [
  z.object({ action: z.literal('select_subject') }),
  z.object({
    action: z.literal('remove_background'),
    asMask: z.boolean().optional(),
  }),
  z.object({
    action: z.literal('select_color_range'),
    x: z.number().int().min(0),
    y: z.number().int().min(0),
    fuzziness: z.number().min(0).max(200).optional(),
  }),
  z.object({
    action: z.literal('apply_curves'),
    points: z.array(z.object({ input: z.number(), output: z.number() })).min(2),
    channel: z.enum(['composite', 'red', 'green', 'blue']).optional(),
  }),
  z.object({
    action: z.literal('apply_levels'),
    inputBlack: z.number().optional(),
    inputWhite: z.number().optional(),
    gamma: z.number().optional(),
    outputBlack: z.number().optional(),
    outputWhite: z.number().optional(),
    channel: z.enum(['composite', 'red', 'green', 'blue']).optional(),
  }),
  z.object({
    action: z.literal('apply_layer_style'),
    dropShadow: z.record(z.string(), z.unknown()).optional(),
    stroke: z.record(z.string(), z.unknown()).optional(),
    outerGlow: z.record(z.string(), z.unknown()).optional(),
  }),
  z.object({
    action: z.literal('match_color'),
    referencePath: z.string().min(1),
    luminance: z.number().optional(),
    colorIntensity: z.number().optional(),
    fade: z.number().optional(),
  }),
  z.object({
    action: z.literal('export_preset'),
    preset: z.string().min(1),
    outputDir: z.string().min(1),
    baseFilename: z.string().optional(),
  }),
  z.object({
    action: z.literal('save'),
    outputDir: z.string().min(1),
    format: z.enum(['psd', 'png', 'jpg', 'tif']),
    quality: z.number().min(0).max(12).optional(),
    flatten: z.boolean().optional(),
  }),
]);

const BatchFolderSchema = z.object({
  inputDir: z.string().min(1).describe('Absolute path to folder containing images.'),
  steps: z.array(StepSchema).min(1).describe('Ordered list of operations to apply per file.'),
  recursive: z.boolean().optional().describe('Recurse into subdirectories. Default false.'),
  closeAfter: z.boolean().optional().describe('Close each document after processing. Default true.'),
  saveChangesOnClose: z.boolean().optional().describe('Save changes when closing. Default false.'),
});

type Step = z.infer<typeof StepSchema>;

/** Maximum directory recursion depth — protects against symlink loops and pathological trees. */
const MAX_RECURSION_DEPTH = 8;

function listImagesIn(dir: string, recursive: boolean, depth = 0): string[] {
  if (depth > MAX_RECURSION_DEPTH) return [];
  const out: string[] = [];
  // `withFileTypes: true` returns Dirent without follow-link semantics, which
  // means we don't follow symlinks during recursion (Dirent reports the link
  // type, not the target). Combined with the depth cap, this contains symlink
  // loops without needing a visited-inode set.
  const entries = readdirSync(dir, { withFileTypes: true });
  for (const entry of entries) {
    if (entry.isSymbolicLink()) continue; // skip symlinks entirely
    const full = join(dir, entry.name);
    if (entry.isDirectory()) {
      if (recursive) {
        out.push(...listImagesIn(full, recursive, depth + 1));
      }
    } else if (entry.isFile() && SUPPORTED_EXTS.has(extname(entry.name).toLowerCase())) {
      out.push(full);
    }
  }
  return out.sort();
}

async function runStep(step: Step, ctx: import('./types.js').ToolContext, file: string): Promise<ToolResult> {
  switch (step.action) {
    case 'select_subject':
      return selectSubjectTool.handler({}, ctx);
    case 'remove_background':
      return removeBackgroundTool.handler({ asMask: step.asMask }, ctx);
    case 'select_color_range':
      return selectColorRangeTool.handler(
        { x: step.x, y: step.y, fuzziness: step.fuzziness },
        ctx,
      );
    case 'apply_curves':
      return applyCurvesTool.handler({ points: step.points, channel: step.channel }, ctx);
    case 'apply_levels':
      return applyLevelsTool.handler(
        {
          inputBlack: step.inputBlack,
          inputWhite: step.inputWhite,
          gamma: step.gamma,
          outputBlack: step.outputBlack,
          outputWhite: step.outputWhite,
          channel: step.channel,
        },
        ctx,
      );
    case 'apply_layer_style':
      return applyLayerStyleTool.handler(
        {
          dropShadow: step.dropShadow,
          stroke: step.stroke,
          outerGlow: step.outerGlow,
        },
        ctx,
      );
    case 'match_color':
      return matchColorTool.handler(
        {
          referencePath: step.referencePath,
          luminance: step.luminance,
          colorIntensity: step.colorIntensity,
          fade: step.fade,
        },
        ctx,
      );
    case 'export_preset': {
      const baseFilename = step.baseFilename ?? basename(file, extname(file));
      return exportPresetTool.handler(
        {
          preset: step.preset,
          outputDir: step.outputDir,
          baseFilename,
        },
        ctx,
      );
    }
    case 'save': {
      const stem = basename(file, extname(file));
      const outPath = `${step.outputDir.replace(/\/$/, '')}/${stem}.${step.format}`;
      return saveDocumentTool.handler(
        { path: outPath, quality: step.quality, flatten: step.flatten },
        ctx,
      );
    }
  }
}

export const batchFolderTool: ToolDefinition = {
  name: 'ps_batch_folder',
  description:
    'Apply a sequence of operations to every image in a folder. Each image is opened, the steps are run, then the doc is closed. Errors on individual files are collected and reported but do not abort the batch.',
  inputSchema: {
    type: 'object',
    properties: {
      inputDir: { type: 'string', description: 'Absolute folder containing input images.' },
      steps: {
        type: 'array',
        description: 'Ordered list of step objects (see schema below).',
        items: {
          type: 'object',
          properties: { action: { type: 'string' } },
          required: ['action'],
          additionalProperties: true,
        },
      },
      recursive: { type: 'boolean', description: 'Recurse into subdirs. Default false.' },
      closeAfter: { type: 'boolean', description: 'Close each doc after processing. Default true.' },
      saveChangesOnClose: { type: 'boolean', description: 'Save changes when closing. Default false.' },
    },
    required: ['inputDir', 'steps'],
    additionalProperties: false,
  },
  zodSchema: BatchFolderSchema,
  async handler(args, ctx) {
    const opts = BatchFolderSchema.parse(args);
    if (!opts.inputDir.startsWith('/')) {
      throw new Error(`inputDir must be absolute: ${opts.inputDir}`);
    }
    // SECURITY: confine `inputDir` (and any output dirs declared in steps) to
    // the configured allowed roots. Defaults to ~/Downloads, ~/Pictures,
    // ~/Documents, $CATALYST_ROOT, /tmp. Override via PHOTOSHOP_MCP_ALLOWED_ROOTS.
    assertWithinAllowedRoots(opts.inputDir);
    for (const step of opts.steps) {
      if (step.action === 'export_preset' || step.action === 'save') {
        assertWithinAllowedRoots(step.outputDir);
      }
      if (step.action === 'match_color') {
        assertWithinAllowedRoots(step.referencePath);
      }
    }
    const resolvedInputDir = pathResolve(opts.inputDir);
    if (!existsSync(resolvedInputDir)) {
      throw new Error(`inputDir not found: ${opts.inputDir}`);
    }
    const images = listImagesIn(resolvedInputDir, opts.recursive ?? false);
    if (images.length === 0) {
      return {
        content: [
          {
            type: 'text',
            text: JSON.stringify(
              { ok: true, processed: 0, errors: [], message: 'No images found.' },
              null,
              2,
            ),
          },
        ],
      };
    }

    const closeAfter = opts.closeAfter ?? true;
    const saveOnClose = opts.saveChangesOnClose ?? false;

    const errors: Array<{ file: string; error: string }> = [];
    let processed = 0;

    for (const file of images) {
      try {
        await openImageTool.handler({ path: file }, ctx);
        for (const step of opts.steps) {
          await runStep(step, ctx, file);
        }
        processed++;
      } catch (e) {
        errors.push({ file, error: (e as Error).message });
      } finally {
        if (closeAfter) {
          try {
            await closeDocumentTool.handler({ saveChanges: saveOnClose }, ctx);
          } catch {
            // ignore close errors
          }
        }
      }
    }

    return {
      content: [
        {
          type: 'text',
          text: JSON.stringify(
            {
              ok: errors.length === 0,
              processed,
              total: images.length,
              errors,
            },
            null,
            2,
          ),
        },
      ],
      isError: errors.length > 0 && processed === 0,
    };
  },
};
