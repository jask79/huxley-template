/**
 * Template + export-preset registry.
 *
 * Two registries live here:
 *   1. Export presets — multi-size export packs (shopify-product, yt-thumbnail,
 *      ig-square, ig-story). Built-in defaults; override via env or capsule.
 *   2. Brand templates — JSON descriptions of full thumbnail/asset layouts.
 *      Resolved by capsule slug + template name from
 *      `<catalystRoot>/capsules/<slug>/photoshop-templates/<name>.json`.
 */
import { existsSync, readFileSync } from 'node:fs';
import { join, resolve } from 'node:path';
import { z } from 'zod';
import {
  assertWithin,
  validateCapsuleSlug,
  validateTemplateName,
} from '../bridge/safety.js';

// Node 20.11+: `import.meta.dirname` replaces the manual __dirname/__filename
// derivation. Cast for older typings safety.
const __dirname = (import.meta as unknown as { dirname: string }).dirname;

export interface ExportTarget {
  filename: string; // template like "{base}-1024.png"
  width?: number;
  height?: number;
  format: 'png' | 'jpg' | 'jpeg' | 'tif';
  quality?: number; // jpeg only
}

export interface ExportPreset {
  name: string;
  description?: string;
  targets: ExportTarget[];
}

export interface BrandTemplateLayer {
  type: 'image' | 'text' | 'fill';
  // image
  source?: string;
  fit?: 'fill' | 'fit' | 'none';
  smartObject?: boolean;
  // text
  content?: string;
  fontName?: string;
  fontSize?: number;
  alignment?: 'LEFT' | 'CENTER' | 'RIGHT';
  color?: [number, number, number];
  // fill
  fillColor?: [number, number, number];
  fillOpacity?: number;
  // common
  x?: number;
  y?: number;
  scale?: number;
  layerStyle?: Record<string, unknown>;
}

export interface BrandTemplate {
  name: string;
  description?: string;
  canvas: {
    width: number;
    height: number;
    dpi?: number;
    colorMode?: 'RGB' | 'CMYK' | 'Grayscale';
    backgroundColor?: [number, number, number];
  };
  layers: BrandTemplateLayer[];
  export?: Array<{
    preset?: string; // reference to a registered export preset
    filename: string; // explicit filename override
  }>;
}

// Runtime schema mirroring the BrandTemplate type. Validated at template-load
// time so a malformed JSON file fails loudly with a clear pointer to the bad
// field, rather than silently producing broken JSX downstream.
const RGBTuple = z.tuple([
  z.number().min(0).max(255),
  z.number().min(0).max(255),
  z.number().min(0).max(255),
]);

const BrandTemplateLayerSchema: z.ZodType<BrandTemplateLayer> = z.object({
  type: z.enum(['image', 'text', 'fill']),
  source: z.string().optional(),
  fit: z.enum(['fill', 'fit', 'none']).optional(),
  smartObject: z.boolean().optional(),
  content: z.string().optional(),
  fontName: z.string().optional(),
  fontSize: z.number().positive().optional(),
  alignment: z.enum(['LEFT', 'CENTER', 'RIGHT']).optional(),
  color: RGBTuple.optional(),
  fillColor: RGBTuple.optional(),
  fillOpacity: z.number().min(0).max(100).optional(),
  x: z.number().optional(),
  y: z.number().optional(),
  scale: z.number().optional(),
  layerStyle: z.record(z.string(), z.unknown()).optional(),
});

const BrandTemplateSchema: z.ZodType<BrandTemplate> = z.object({
  name: z.string().min(1),
  description: z.string().optional(),
  canvas: z.object({
    width: z.number().positive(),
    height: z.number().positive(),
    dpi: z.number().positive().optional(),
    colorMode: z.enum(['RGB', 'CMYK', 'Grayscale']).optional(),
    backgroundColor: RGBTuple.optional(),
  }),
  layers: z.array(BrandTemplateLayerSchema),
  export: z
    .array(
      z.object({
        preset: z.string().optional(),
        filename: z.string().min(1),
      }),
    )
    .optional(),
});

export class TemplateRegistry {
  private exportPresets = new Map<string, ExportPreset>();
  private builtInTemplatesDir: string;

  constructor(public catalystRoot: string) {
    // dist/templates → src/templates is two levels up
    this.builtInTemplatesDir = resolve(__dirname, '..', '..', 'src', 'templates');
    if (!existsSync(this.builtInTemplatesDir)) {
      // fall back to dist-relative if running from compiled bundle without sources
      this.builtInTemplatesDir = resolve(__dirname);
    }
    this.seedDefaultExportPresets();
  }

  private seedDefaultExportPresets(): void {
    const defaults: ExportPreset[] = [
      {
        name: 'shopify-product',
        description: 'Shopify product imagery — 480, 1024, 2048 PNG square crops.',
        targets: [
          { filename: '{base}-480.png', width: 480, height: 480, format: 'png' },
          { filename: '{base}-1024.png', width: 1024, height: 1024, format: 'png' },
          { filename: '{base}-2048.png', width: 2048, height: 2048, format: 'png' },
        ],
      },
      {
        name: 'yt-thumbnail',
        description: 'YouTube thumbnail — 1280x720 JPG q11.',
        targets: [
          { filename: '{base}-thumb.jpg', width: 1280, height: 720, format: 'jpg', quality: 11 },
        ],
      },
      {
        name: 'ig-square',
        description: 'Instagram square — 1080x1080 PNG.',
        targets: [{ filename: '{base}-ig.png', width: 1080, height: 1080, format: 'png' }],
      },
      {
        name: 'ig-story',
        description: 'Instagram story / Reel cover — 1080x1920 PNG.',
        targets: [
          { filename: '{base}-story.png', width: 1080, height: 1920, format: 'png' },
        ],
      },
    ];
    for (const p of defaults) {
      this.exportPresets.set(p.name, p);
    }

    // Allow override / extension from on-disk JSON in the package's templates dir.
    const overridesPath = join(this.builtInTemplatesDir, 'export-presets.json');
    if (existsSync(overridesPath)) {
      try {
        const raw = JSON.parse(readFileSync(overridesPath, 'utf8')) as ExportPreset[];
        for (const p of raw) {
          this.exportPresets.set(p.name, p);
        }
      } catch (e) {
        console.error('[photoshop-mcp] Failed to parse export-presets.json:', e);
      }
    }
  }

  listExportPresets(): ExportPreset[] {
    return [...this.exportPresets.values()];
  }

  getExportPreset(name: string): ExportPreset | undefined {
    return this.exportPresets.get(name);
  }

  /**
   * Resolve a brand template by capsule slug + template name. Searches
   * `<catalystRoot>/capsules/<slug>/photoshop-templates/<name>.json` first,
   * then `tools/photoshop-mcp/src/templates/<name>.json` as a fallback for
   * cross-capsule generic templates.
   *
   * SECURITY: both `capsule` and `name` are validated against strict allowlist
   * regexes. Resolved file paths are asserted to stay within the expected base
   * directory before being read — defends against `capsule='../../../etc'`
   * style traversal attacks.
   */
  getBrandTemplate(capsule: string, name: string): BrandTemplate {
    // 1. Validate inputs against strict allowlists. Throws on invalid input
    //    with a non-info-leaking error message.
    validateCapsuleSlug(capsule);
    validateTemplateName(name);

    // 2. Build candidate paths and assert containment within their respective
    //    base directories. `assertWithin` resolves the target and rejects any
    //    path that doesn't start with `<base><sep>`.
    const perCapsuleBase = resolve(this.catalystRoot, 'capsules', capsule, 'photoshop-templates');
    const perCapsulePath = join(perCapsuleBase, `${name}.json`);
    const builtinPath = join(this.builtInTemplatesDir, `${name}.json`);
    // Containment checks — throw clear non-info-leaking errors on violation.
    assertWithin(perCapsuleBase, perCapsulePath);
    assertWithin(this.builtInTemplatesDir, builtinPath);

    const candidates = [perCapsulePath, builtinPath];
    for (const path of candidates) {
      if (existsSync(path)) {
        let raw: unknown;
        try {
          raw = JSON.parse(readFileSync(path, 'utf8'));
        } catch (e) {
          throw new Error(`Failed to parse template JSON: ${(e as Error).message}`);
        }
        // Schema-validate so a malformed template fails with a pointer to the
        // failing field rather than producing broken JSX downstream.
        const parsed = BrandTemplateSchema.safeParse(raw);
        if (!parsed.success) {
          const issue = parsed.error.issues[0];
          throw new Error(
            `Brand template schema invalid at '${issue?.path.join('.')}': ${issue?.message}`,
          );
        }
        return parsed.data;
      }
    }
    // Deliberately do not echo full FS paths — clients only need to know the
    // template wasn't found.
    throw new Error(`Brand template '${name}' not found for capsule '${capsule}'.`);
  }
}
