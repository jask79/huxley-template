/**
 * Centralized timeout constants for ExtendScript-over-AppleScript calls.
 *
 * Before centralizing, individual tools sprinkled magic numbers (45s, 60s,
 * 90s, 120s) inline. This module is the single source of truth so they stay
 * consistent and tunable.
 *
 * Units are milliseconds.
 */
export const TIMEOUTS = {
  /** Default `bridge.exec` timeout if a tool does not specify one. */
  DEFAULT: 60_000,
  /** Health probe — fast turnaround. */
  HEALTH: 15_000,
  /** AI selection (Select Subject etc.) — model inference can be slow. */
  AI_SELECTION: 45_000,
  /** Background removal — Select Subject + mask/delete pipeline. */
  REMOVE_BG: 60_000,
  /** Place smart object — file open + linking. */
  PLACE_SMART_OBJECT: 60_000,
  /** Match Color — opens reference doc + runs match. */
  MATCH_COLOR: 90_000,
  /** Single export pass (resize + flatten + save). */
  EXPORT_PRESET: 90_000,
  /** Brand template render — multi-layer doc creation. */
  BRAND_TEMPLATE: 120_000,
} as const;
