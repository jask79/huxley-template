/**
 * Huxley Photoshop MCP — tool registry.
 */
import type { ToolDefinition } from './types.js';
import { isRunningTool } from './health.js';
import {
  openImageTool,
  saveDocumentTool,
  closeDocumentTool,
  resizeImageTool,
  executeJsxTool,
  isRawJsxAllowed,
} from './document.js';
import {
  selectSubjectTool,
  removeBackgroundTool,
  selectColorRangeTool,
} from './ai-selection.js';
import { matchColorTool } from './match-color.js';
import { placeSmartObjectTool } from './place-smart-object.js';
import { applyCurvesTool, applyLevelsTool } from './color-grading.js';
import { applyLayerStyleTool } from './layer-style.js';
import { exportPresetTool } from './export-preset.js';
import { applyBrandTemplateTool } from './brand-template.js';
import { batchFolderTool } from './batch-folder.js';

/**
 * Public tool list. The Huxley-only "value-add" tools called out by the
 * architecture report appear here, plus the foundational document/file ops
 * needed for them to compose end-to-end workflows.
 *
 * `ps_execute_jsx` is HIDDEN by default — it is only included if the env var
 * `PHOTOSHOP_MCP_ALLOW_RAW_JSX=1` is set. Raw JSX is an RCE-on-the-PS-host
 * surface; we don't want it exposed to untrusted MCP clients.
 */
const BASE_TOOLS: ToolDefinition[] = [
  // Health / preflight
  isRunningTool,

  // Huxley value-add tools (the 12 from the architecture report)
  selectSubjectTool, // ps_select_subject
  removeBackgroundTool, // ps_remove_background
  matchColorTool, // ps_match_color
  selectColorRangeTool, // ps_select_color_range
  placeSmartObjectTool, // ps_place_smart_object
  applyCurvesTool, // ps_apply_curves
  applyLevelsTool, // ps_apply_levels
  applyLayerStyleTool, // ps_apply_layer_style
  exportPresetTool, // ps_export_preset
  applyBrandTemplateTool, // ps_apply_brand_template
  batchFolderTool, // ps_batch_folder

  // Foundational document ops (the value-add tools depend on these for
  // open/save/close/resize end-to-end workflows). Kept small on purpose.
  openImageTool,
  saveDocumentTool,
  closeDocumentTool,
  resizeImageTool,
];

export const ALL_TOOLS: ToolDefinition[] = isRawJsxAllowed()
  ? [...BASE_TOOLS, executeJsxTool]
  : BASE_TOOLS;

export function getToolByName(name: string): ToolDefinition | undefined {
  return ALL_TOOLS.find((t) => t.name === name);
}
