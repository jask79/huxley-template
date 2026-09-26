/**
 * ps_apply_brand_template — render a JSON-described brand template into a
 * fresh document, then optionally export at the configured presets.
 */
import { z } from 'zod';
import { existsSync } from 'node:fs';
import { mkdir } from 'node:fs/promises';
import { resolve as pathResolve } from 'node:path';
import type { ToolDefinition } from './types.js';
import type { BrandTemplate, BrandTemplateLayer } from '../templates/registry.js';
import { assertWithin, jsxStringLiteral } from '../bridge/safety.js';
import { TIMEOUTS } from '../bridge/timeouts.js';

/**
 * Allowlist regex for `{params}` substitution VALUES — restricts to a unicode-
 * friendly set that excludes ES3-string-terminating characters and obvious
 * injection vectors. Reject (do not silently strip) anything outside this set.
 *
 * Rationale: even though every value flows through `jsxStringLiteral`, we
 * tighten the perimeter here because params values are caller-controlled and
 * we don't want any path for content like ` ); harmfulCode(); //` to
 * reach the JSX literal in the first place. Defense in depth.
 */
const PARAM_VALUE_REGEX = /^[\p{L}\p{N}\p{P}\p{Zs}@#$%&_\-+=:;'"!?.,()\[\]/]*$/u;

function validateParamValue(key: string, value: string | number | boolean): string | number | boolean {
  if (typeof value !== 'string') return value;
  if (!PARAM_VALUE_REGEX.test(value)) {
    throw new Error(
      `Brand template param '${key}' contains disallowed characters (control chars, line/paragraph separators, etc.).`,
    );
  }
  return value;
}

const ApplyBrandTemplateSchema = z.object({
  capsule: z.string().min(1).describe('Capsule slug — used to resolve template path.'),
  template: z
    .string()
    .min(1)
    .describe('Template name (filename without .json) — looked up in capsules/<capsule>/photoshop-templates/.'),
  params: z
    .record(z.string(), z.union([z.string(), z.number(), z.boolean()]))
    .optional()
    .describe('Parameter substitutions for {placeholder} tokens in the template.'),
  outputDir: z
    .string()
    .optional()
    .describe('If provided + template defines exports, write outputs here.'),
});

/** Substitute {key} placeholders in a string using params. Falls through if no match. */
function substitute(text: string, params: Record<string, string | number | boolean>): string {
  return text.replace(/\{([a-zA-Z0-9_.-]+)\}/g, (_, key: string) => {
    const v = params[key];
    return v === undefined ? `{${key}}` : String(v);
  });
}

/**
 * Apply `{key}` parameter substitutions to a brand template.
 *
 * Substitution surface (intentionally small + explicit — DO NOT expand without
 * also expanding the param-value validation):
 *   - `layer.source` (image layer file path)
 *   - `layer.content` (text layer body)
 *   - `template.export[*].filename`
 *
 * Anything else (`fontName`, layout numbers, color tuples, etc.) is NOT
 * subject to substitution. Caller-controlled param values must match
 * `PARAM_VALUE_REGEX` — control chars / line separators are rejected.
 */
function applyParamsToTemplate(template: BrandTemplate, params: Record<string, string | number | boolean>): BrandTemplate {
  // Validate every param value up front. Rejects line/paragraph separators
  // and other control chars that could escape an ES3 string literal.
  const validatedParams: Record<string, string | number | boolean> = {};
  for (const [k, v] of Object.entries(params)) {
    validatedParams[k] = validateParamValue(k, v);
  }
  const cloned: BrandTemplate = JSON.parse(JSON.stringify(template));
  for (const layer of cloned.layers) {
    if (typeof layer.source === 'string') layer.source = substitute(layer.source, validatedParams);
    if (typeof layer.content === 'string') layer.content = substitute(layer.content, validatedParams);
  }
  if (cloned.export) {
    for (const exp of cloned.export) {
      if (typeof exp.filename === 'string') exp.filename = substitute(exp.filename, validatedParams);
    }
  }
  return cloned;
}

/**
 * @deprecated Use `jsxStringLiteral` from bridge/safety.js. Retained as a
 * shim so any out-of-tree callers still work. This implementation now
 * delegates to the centralized helper which handles the full ES3 escape
 * surface (newlines, U+2028/U+2029, control chars, etc.).
 */
function jsxEscape(s: string): string {
  return jsxStringLiteral(s);
}

function renderImageLayerJsx(layer: BrandTemplateLayer, idx: number): string {
  if (!layer.source) {
    throw new Error(`Image layer #${idx} missing 'source'`);
  }
  if (!layer.source.startsWith('/')) {
    throw new Error(`Image layer #${idx} source must be an absolute path: ${layer.source}`);
  }
  if (!existsSync(layer.source)) {
    throw new Error(`Image layer #${idx} source not found: ${layer.source}`);
  }
  const path = jsxEscape(layer.source);
  const linked = layer.smartObject ? 'true' : 'false';
  const fit = layer.fit ?? 'none';
  const fitJsx =
    fit === 'fill'
      ? `
          // Fit-fill — scale to cover canvas
          var lb = doc.activeLayer.bounds;
          var lw = lb[2].value - lb[0].value;
          var lh = lb[3].value - lb[1].value;
          var sX = doc.width.value / lw * 100;
          var sY = doc.height.value / lh * 100;
          var s = Math.max(sX, sY);
          doc.activeLayer.resize(s, s, AnchorPosition.MIDDLECENTER);
        `
      : fit === 'fit'
        ? `
          var lb = doc.activeLayer.bounds;
          var lw = lb[2].value - lb[0].value;
          var lh = lb[3].value - lb[1].value;
          var sX = doc.width.value / lw * 100;
          var sY = doc.height.value / lh * 100;
          var s = Math.min(sX, sY);
          doc.activeLayer.resize(s, s, AnchorPosition.MIDDLECENTER);
        `
        : '';
  const scale = layer.scale ?? 1.0;
  const scaleJsx =
    scale !== 1.0
      ? `doc.activeLayer.resize(${scale * 100}, ${scale * 100}, AnchorPosition.MIDDLECENTER);`
      : '';
  const positionJsx =
    typeof layer.x === 'number' && typeof layer.y === 'number'
      ? `
          var pb = doc.activeLayer.bounds;
          doc.activeLayer.translate(${layer.x} - pb[0].value, ${layer.y} - pb[1].value);
        `
      : '';
  return `
    (function() {
      var d = new ActionDescriptor();
      d.putPath(stringIDToTypeID('null'), new File('${path}'));
      d.putBoolean(stringIDToTypeID('linked'), ${linked});
      executeAction(stringIDToTypeID('placeEvent'), d, DialogModes.NO);
      ${scaleJsx}
      ${fitJsx}
      ${positionJsx}
    })();
  `;
}

function renderTextLayerJsx(layer: BrandTemplateLayer, idx: number): string {
  if (!layer.content) {
    throw new Error(`Text layer #${idx} missing 'content'`);
  }
  const content = jsxEscape(layer.content);
  const fontName = jsxEscape(layer.fontName ?? 'Helvetica-Bold');
  const fontSize = layer.fontSize ?? 72;
  const [r, g, b] = layer.color ?? [255, 255, 255];
  const x = layer.x ?? 100;
  const y = layer.y ?? 100;
  const alignment = layer.alignment ?? 'LEFT';
  return `
    (function() {
      var t = doc.artLayers.add();
      t.kind = LayerKind.TEXT;
      var ti = t.textItem;
      ti.contents = '${content}';
      ti.font = '${fontName}';
      ti.size = ${fontSize};
      ti.position = [${x}, ${y}];
      ti.justification = Justification.${alignment};
      var c = new SolidColor();
      c.rgb.red = ${r};
      c.rgb.green = ${g};
      c.rgb.blue = ${b};
      ti.color = c;
    })();
  `;
}

function renderFillLayerJsx(layer: BrandTemplateLayer): string {
  const [r, g, b] = layer.fillColor ?? [0, 0, 0];
  const opacity = layer.fillOpacity ?? 100;
  return `
    (function() {
      var fill = doc.artLayers.add();
      doc.selection.selectAll();
      var c = new SolidColor();
      c.rgb.red = ${r};
      c.rgb.green = ${g};
      c.rgb.blue = ${b};
      doc.selection.fill(c);
      doc.selection.deselect();
      fill.opacity = ${opacity};
    })();
  `;
}

export const applyBrandTemplateTool: ToolDefinition = {
  name: 'ps_apply_brand_template',
  description:
    'Render a JSON-defined brand template (text + logo + colors + layout) into a new Photoshop document. Templates live at capsules/<capsule>/photoshop-templates/<template>.json. Pass `params` to substitute {placeholder} tokens in source paths and text. Optionally writes export presets to outputDir.',
  inputSchema: {
    type: 'object',
    properties: {
      capsule: { type: 'string', description: 'Capsule slug owning the template.' },
      template: { type: 'string', description: 'Template name (without .json).' },
      params: {
        type: 'object',
        description: 'Substitution parameters for {key} placeholders in the template.',
      },
      outputDir: {
        type: 'string',
        description: 'Optional output directory for exports defined by the template.',
      },
    },
    required: ['capsule', 'template'],
    additionalProperties: false,
  },
  zodSchema: ApplyBrandTemplateSchema,
  async handler(args, ctx) {
    const opts = ApplyBrandTemplateSchema.parse(args);
    const params = opts.params ?? {};

    const rawTemplate = ctx.templates.getBrandTemplate(opts.capsule, opts.template);
    const template = applyParamsToTemplate(rawTemplate, params);

    const colorMode = template.canvas.colorMode ?? 'RGB';
    const dpi = template.canvas.dpi ?? 72;
    const [bgR, bgG, bgB] = template.canvas.backgroundColor ?? [255, 255, 255];

    const layerJsxBlocks: string[] = [];
    template.layers.forEach((layer, i) => {
      switch (layer.type) {
        case 'image':
          layerJsxBlocks.push(renderImageLayerJsx(layer, i));
          break;
        case 'text':
          layerJsxBlocks.push(renderTextLayerJsx(layer, i));
          break;
        case 'fill':
          layerJsxBlocks.push(renderFillLayerJsx(layer));
          break;
        default:
          throw new Error(`Unknown layer type at index ${i}: ${(layer as { type: string }).type}`);
      }
    });

    await ctx.bridge.exec(
      `
        var bg = new SolidColor();
        bg.rgb.red = ${bgR};
        bg.rgb.green = ${bgG};
        bg.rgb.blue = ${bgB};
        app.backgroundColor = bg;
        var doc = app.documents.add(
          UnitValue(${template.canvas.width}, 'px'),
          UnitValue(${template.canvas.height}, 'px'),
          ${dpi},
          'catalyst-${jsxEscape(opts.capsule)}-${jsxEscape(opts.template)}',
          NewDocumentMode.${colorMode === 'CMYK' ? 'CMYK' : colorMode === 'Grayscale' ? 'GRAYSCALE' : 'RGB'},
          DocumentFill.BACKGROUNDCOLOR
        );
        ${layerJsxBlocks.join('\n')}
        setResult({ created: doc.name, layers: doc.layers.length });
      `,
      TIMEOUTS.BRAND_TEMPLATE,
    );

    const exports: string[] = [];

    if (opts.outputDir && template.export && template.export.length > 0) {
      // Resolve the output dir once — every per-target full path must stay
      // within it. Defense against template/preset filenames that try to
      // traverse upward (`../../../etc/passwd`) via `{base}` substitution.
      const resolvedOutputDir = pathResolve(opts.outputDir);
      // Reuse ps_export_preset machinery for each declared export
      for (const exp of template.export) {
        if (!exp.preset) continue;
        const presetDef = ctx.templates.getExportPreset(exp.preset);
        if (!presetDef) {
          throw new Error(
            `Template references unknown export preset '${exp.preset}'. Available: ${ctx.templates
              .listExportPresets()
              .map((p) => p.name)
              .join(', ')}`,
          );
        }
        // Use the export filename (sans extension) as the base
        const base = exp.filename.replace(/\.[^.]+$/, '');
        if (!existsSync(resolvedOutputDir)) {
          await mkdir(resolvedOutputDir, { recursive: true });
        }
        for (const target of presetDef.targets) {
          const fname = target.filename.replace('{base}', base);
          const fullPath = `${resolvedOutputDir.replace(/\/$/, '')}/${fname}`;
          // Reject anything that escapes outputDir (e.g., a `{base}` that
          // contains `../`). Throws on violation.
          assertWithin(resolvedOutputDir, fullPath);
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
              saveJsx = `var opt = new TiffSaveOptions(); dup.saveAs(new File('${escPath}'), opt, true, Extension.LOWERCASE);`;
              break;
            default:
              throw new Error(`Unsupported format: ${target.format}`);
          }
          await ctx.bridge.exec(
            `
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
          exports.push(fullPath);
        }
      }
    }

    return {
      content: [
        {
          type: 'text',
          text: JSON.stringify(
            { ok: true, capsule: opts.capsule, template: opts.template, exports },
            null,
            2,
          ),
        },
      ],
    };
  },
};
