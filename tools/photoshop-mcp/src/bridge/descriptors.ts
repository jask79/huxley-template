/**
 * Helpers for emitting Photoshop ActionDescriptor JSX.
 *
 * Photoshop's most powerful surface (Select Subject, Match Color, color-range,
 * curves/levels with channels, layer styles) is only reachable via the
 * ActionManager API in ExtendScript. These helpers produce idiomatic snippets
 * we splice into wrapper scripts.
 *
 * NOTE: We deliberately do not try to expose ActionManager generically. We
 * expose just the shapes the Huxley tools need.
 */
import { jsxStringLiteral } from './safety.js';

/** Photoshop charID/typeID escape: returns the JS expression for stringIDToTypeID('xxx'). */
export function s(id: string): string {
  // Defensive — ExtendScript treats single quotes literally, no need to escape.
  return `stringIDToTypeID('${id}')`;
}

/** charID — for the small set of legacy 4-char IDs PS still uses (rare). */
export function c(id: string): string {
  if (id.length !== 4) {
    throw new Error(`charID must be 4 chars, got '${id}'`);
  }
  return `charIDToTypeID('${id}')`;
}

/**
 * autoCutout (Select Subject) — PS 2020+ AI subject mask.
 * Optional sampleAllLayers boolean parameter is accepted by recent PS versions
 * and ignored by older ones.
 */
export const SELECT_SUBJECT_JSX = `
(function() {
  var d = new ActionDescriptor();
  d.putBoolean(${s('sampleAllLayers')}, false);
  executeAction(${s('autoCutout')}, d, DialogModes.NO);
})();
`;

/** removeBackground (PS 22.5+) — uses Quick Action under the hood. */
export const REMOVE_BG_QUICK_ACTION_JSX = `
(function() {
  var d = new ActionDescriptor();
  executeAction(${s('removeBackground')}, d, DialogModes.NO);
})();
`;

/**
 * Color Range selection by sampling a point. Tolerance is "fuzziness" in PS.
 * x/y are pixel coordinates in the active doc.
 */
export function colorRangeJsx(x: number, y: number, fuzziness: number): string {
  const fuzz = Math.max(0, Math.min(200, Math.round(fuzziness)));
  return `
(function() {
  var d = new ActionDescriptor();
  var pt = new ActionDescriptor();
  pt.putUnitDouble(${s('horizontal')}, ${s('pixelsUnit')}, ${x});
  pt.putUnitDouble(${s('vertical')}, ${s('pixelsUnit')}, ${y});
  d.putObject(${s('samplePoint')}, ${s('paint')}, pt);
  d.putInteger(${s('fuzziness')}, ${fuzz});
  d.putEnumerated(${s('colorModel')}, ${s('colorModel')}, ${s('reds')});
  executeAction(${s('colorRange')}, d, DialogModes.NO);
})();
`;
}

/** Curves adjustment as a destructive layer adjustment via ActionManager. */
export interface CurvePoint {
  /** input 0..255 */
  input: number;
  /** output 0..255 */
  output: number;
}

export function curvesJsx(points: CurvePoint[], channel: 'composite' | 'red' | 'green' | 'blue' = 'composite'): string {
  if (points.length < 2) {
    throw new Error('curves requires at least 2 points');
  }
  const channelMap: Record<string, string> = {
    composite: s('composite'),
    red: s('red'),
    green: s('green'),
    blue: s('blue'),
  };
  const ch = channelMap[channel];
  // Curve points are recorded by Photoshop as charID 'CrPt' (curve points),
  // with horizontal/vertical input/output as charIDs 'Hrzn'/'Vrtc'. The
  // previous implementation used stringID 'paint' for the point class, which
  // is the wrong context (paint is a color/painting term).
  const pointsJsx = points
    .map(
      (p) =>
        `pts.putObject(${c('CrPt')}, (function(){var pt=new ActionDescriptor();pt.putDouble(${c(
          'Hrzn',
        )}, ${clamp(p.input, 0, 255)});pt.putDouble(${c('Vrtc')}, ${clamp(p.output, 0, 255)});return pt;})());`,
    )
    .join('\n  ');
  return `
(function() {
  var d = new ActionDescriptor();
  var adj = new ActionDescriptor();
  var curveList = new ActionList();
  var curve = new ActionDescriptor();
  curve.putReference(${s('channel')}, (function(){var r = new ActionReference();r.putEnumerated(${s('channel')}, ${s('channel')}, ${ch});return r;})());
  var pts = new ActionList();
  ${pointsJsx}
  curve.putList(${s('curve')}, pts);
  curveList.putObject(${s('curvesAdjustment')}, curve);
  adj.putList(${s('adjustment')}, curveList);
  d.putObject(${s('with')}, ${s('curves')}, adj);
  executeAction(${s('curves')}, d, DialogModes.NO);
})();
`;
}

/** Levels: black point, gamma, white point per channel. */
export interface LevelsSpec {
  /** input black point (0..253) */
  inputBlack?: number;
  /** input white point (2..255) */
  inputWhite?: number;
  /** gamma midtone (0.10..9.99) */
  gamma?: number;
  /** output black (0..253) */
  outputBlack?: number;
  /** output white (2..255) */
  outputWhite?: number;
  channel?: 'composite' | 'red' | 'green' | 'blue';
}

export function levelsJsx(spec: LevelsSpec): string {
  const inputBlack = clamp(spec.inputBlack ?? 0, 0, 253);
  const inputWhite = clamp(spec.inputWhite ?? 255, inputBlack + 2, 255);
  const gamma = clamp(spec.gamma ?? 1.0, 0.1, 9.99);
  const outputBlack = clamp(spec.outputBlack ?? 0, 0, 253);
  const outputWhite = clamp(spec.outputWhite ?? 255, outputBlack + 2, 255);
  const channel = spec.channel ?? 'composite';
  const channelMap: Record<string, string> = {
    composite: s('composite'),
    red: s('red'),
    green: s('green'),
    blue: s('blue'),
  };
  // NOTE (M10c, 2026-05-09): code review flagged the levels descriptor keys as
  // hand-written and uncertain. Without a recorded reference action to verify
  // against (PS not available at fix time), we left the keys as-is rather than
  // make speculative changes that could regress working calls. Treat this as
  // a TODO: record a Levels action via PS Scripting Listener and reconcile
  // any wrong keys (suspected: 'input'/'output'/'levelsAdjustment'/'with' may
  // need to be charIDs 'Inpt'/'Otpt'/'Lvl '/etc.). Tracked for v1.1.
  return `
(function() {
  var d = new ActionDescriptor();
  var adj = new ActionDescriptor();
  var levelsList = new ActionList();
  var lvl = new ActionDescriptor();
  lvl.putReference(${s('channel')}, (function(){var r=new ActionReference();r.putEnumerated(${s('channel')}, ${s('channel')}, ${channelMap[channel]});return r;})());
  var input = new ActionList();
  input.putInteger(${inputBlack});
  input.putInteger(${inputWhite});
  lvl.putList(${s('input')}, input);
  lvl.putDouble(${s('gamma')}, ${gamma});
  var output = new ActionList();
  output.putInteger(${outputBlack});
  output.putInteger(${outputWhite});
  lvl.putList(${s('output')}, output);
  levelsList.putObject(${s('levelsAdjustment')}, lvl);
  adj.putList(${s('adjustment')}, levelsList);
  d.putObject(${s('with')}, ${s('levels')}, adj);
  executeAction(${s('levels')}, d, DialogModes.NO);
})();
`;
}

/**
 * Layer style payload. Each property is optional. Numeric units are pixels
 * (for distance/size/spread) and degrees (for angle).
 */
export interface DropShadowSpec {
  enabled?: boolean;
  opacity?: number; // 0-100
  angle?: number;
  distance?: number;
  spread?: number; // 0-100 percent
  size?: number;
  color?: [number, number, number]; // RGB 0-255
  blendMode?: 'multiply' | 'normal' | 'screen' | 'overlay';
}

export interface StrokeSpec {
  enabled?: boolean;
  size?: number;
  opacity?: number;
  position?: 'outsideFrame' | 'insideFrame' | 'centeredFrame';
  color?: [number, number, number];
}

export interface OuterGlowSpec {
  enabled?: boolean;
  opacity?: number;
  size?: number;
  spread?: number;
  color?: [number, number, number];
}

export interface LayerStyleSpec {
  dropShadow?: DropShadowSpec;
  stroke?: StrokeSpec;
  outerGlow?: OuterGlowSpec;
}

export function layerStyleJsx(spec: LayerStyleSpec): string {
  const parts: string[] = [];
  parts.push(`var styleObj = new ActionDescriptor();`);
  parts.push(`var layerEffects = new ActionDescriptor();`);

  if (spec.dropShadow?.enabled !== false && spec.dropShadow) {
    const ds = spec.dropShadow;
    const [r, g, b] = ds.color ?? [0, 0, 0];
    const blend = ds.blendMode ?? 'multiply';
    parts.push(`
      var ds = new ActionDescriptor();
      ds.putBoolean(${s('enabled')}, true);
      ds.putBoolean(${s('present')}, true);
      ds.putBoolean(${s('showInDialog')}, true);
      ds.putEnumerated(${s('mode')}, ${s('blendMode')}, ${s(blend)});
      var dsColor = new ActionDescriptor();
      dsColor.putDouble(${s('red')}, ${r});
      dsColor.putDouble(${s('green')}, ${g});
      dsColor.putDouble(${s('blue')}, ${b});
      ds.putObject(${s('color')}, ${s('RGBColor')}, dsColor);
      ds.putUnitDouble(${s('opacity')}, ${s('percentUnit')}, ${clamp(ds.opacity ?? 75, 0, 100)});
      ds.putUnitDouble(${s('localLightingAngle')}, ${s('angleUnit')}, ${ds.angle ?? 120});
      ds.putUnitDouble(${s('distance')}, ${s('pixelsUnit')}, ${ds.distance ?? 5});
      ds.putUnitDouble(${s('chokeMatte')}, ${s('percentUnit')}, ${clamp(ds.spread ?? 0, 0, 100)});
      ds.putUnitDouble(${s('blur')}, ${s('pixelsUnit')}, ${ds.size ?? 5});
      layerEffects.putObject(${s('dropShadow')}, ${s('dropShadow')}, ds);
    `);
  }

  if (spec.stroke?.enabled !== false && spec.stroke) {
    const st = spec.stroke;
    const [r, g, b] = st.color ?? [0, 0, 0];
    const pos = st.position ?? 'outsideFrame';
    parts.push(`
      var fxStroke = new ActionDescriptor();
      fxStroke.putBoolean(${s('enabled')}, true);
      fxStroke.putBoolean(${s('present')}, true);
      fxStroke.putBoolean(${s('showInDialog')}, true);
      fxStroke.putEnumerated(${s('style')}, ${s('frameStyle')}, ${s(pos)});
      fxStroke.putEnumerated(${s('paintType')}, ${s('frameFill')}, ${s('solidColor')});
      fxStroke.putEnumerated(${s('mode')}, ${s('blendMode')}, ${s('normal')});
      fxStroke.putUnitDouble(${s('opacity')}, ${s('percentUnit')}, ${clamp(st.opacity ?? 100, 0, 100)});
      fxStroke.putUnitDouble(${s('size')}, ${s('pixelsUnit')}, ${st.size ?? 3});
      var stColor = new ActionDescriptor();
      stColor.putDouble(${s('red')}, ${r});
      stColor.putDouble(${s('grain')}, ${g});
      stColor.putDouble(${s('blue')}, ${b});
      fxStroke.putObject(${s('color')}, ${s('RGBColor')}, stColor);
      layerEffects.putObject(${s('frameFX')}, ${s('frameFX')}, fxStroke);
    `);
  }

  if (spec.outerGlow?.enabled !== false && spec.outerGlow) {
    const og = spec.outerGlow;
    const [r, g, b] = og.color ?? [255, 255, 0];
    parts.push(`
      var glow = new ActionDescriptor();
      glow.putBoolean(${s('enabled')}, true);
      glow.putBoolean(${s('present')}, true);
      glow.putBoolean(${s('showInDialog')}, true);
      glow.putEnumerated(${s('mode')}, ${s('blendMode')}, ${s('screen')});
      var glowColor = new ActionDescriptor();
      glowColor.putDouble(${s('red')}, ${r});
      glowColor.putDouble(${s('grain')}, ${g});
      glowColor.putDouble(${s('blue')}, ${b});
      glow.putObject(${s('color')}, ${s('RGBColor')}, glowColor);
      glow.putUnitDouble(${s('opacity')}, ${s('percentUnit')}, ${clamp(og.opacity ?? 60, 0, 100)});
      glow.putUnitDouble(${s('chokeMatte')}, ${s('percentUnit')}, ${clamp(og.spread ?? 0, 0, 100)});
      glow.putUnitDouble(${s('blur')}, ${s('pixelsUnit')}, ${og.size ?? 8});
      layerEffects.putObject(${s('outerGlow')}, ${s('outerGlow')}, glow);
    `);
  }

  parts.push(`styleObj.putObject(${s('to')}, ${s('layerEffects')}, layerEffects);`);
  parts.push(`
    var ref = new ActionReference();
    ref.putEnumerated(${s('layer')}, ${s('ordinal')}, ${s('targetEnum')});
    styleObj.putReference(${s('null')}, ref);
    executeAction(${s('set')}, styleObj, DialogModes.NO);
  `);

  return `(function(){\n${parts.join('\n')}\n})();`;
}

/**
 * Match Color descriptor — match the active doc's color statistics to a
 * reference image opened by path. The reference must be opened first; we
 * pass its document name in via parameter.
 */
export function matchColorJsx(
  referenceDocName: string,
  options: { luminance?: number; colorIntensity?: number; fade?: number } = {},
): string {
  const luminance = clamp(options.luminance ?? 100, 0, 200);
  const intensity = clamp(options.colorIntensity ?? 100, 0, 200);
  const fade = clamp(options.fade ?? 0, 0, 100);
  const escName = jsxStringLiteral(referenceDocName);
  return `
(function() {
  var d = new ActionDescriptor();
  d.putInteger(${s('luminance')}, ${luminance});
  d.putInteger(${s('colorRange')}, ${intensity});
  d.putBoolean(${s('neutralize')}, false);
  d.putInteger(${s('fade')}, ${fade});
  var ref = new ActionReference();
  ref.putName(${s('document')}, '${escName}');
  d.putReference(${s('source')}, ref);
  executeAction(${s('matchColor')}, d, DialogModes.NO);
})();
`;
}

function clamp(n: number, lo: number, hi: number): number {
  if (Number.isNaN(n)) return lo;
  return Math.max(lo, Math.min(hi, n));
}
