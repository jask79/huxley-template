/**
 * Centralized safety helpers — escaping and path containment.
 *
 * EVERY string that flows from caller-controlled input into a JSX/ExtendScript
 * string literal MUST go through `jsxStringLiteral`. The previous ad-hoc
 * `s.replace(/\\/g, '\\\\').replace(/'/g, "\\'")` pattern misses newlines, U+2028,
 * U+2029, and other control chars that can terminate an ES3 string literal and
 * inject arbitrary JSX. Don't do it.
 *
 * `appleScriptDoubleQuoted` does the analogous job for double-quoted AppleScript
 * strings, and `shellSingleQuoted` for the surrounding `osascript -e '...'` shell
 * arg. Apply both (in that order) when interpolating into AppleScript.
 *
 * Path containment helpers reject paths that resolve outside an allowed root —
 * the standard mitigation against `../../etc/passwd`-style traversal.
 */
import { resolve as pathResolve, sep as pathSep } from 'node:path';
import { homedir } from 'node:os';

// Regexes for U+2028 / U+2029 — line/paragraph separators. These terminate
// ES3 string literals but JSON.stringify does NOT escape them. Built via
// fromCharCode so the literal chars never appear in this source file.
const RE_U2028 = new RegExp(String.fromCharCode(0x2028), 'g');
const RE_U2029 = new RegExp(String.fromCharCode(0x2029), 'g');

/**
 * Escape an arbitrary string for safe inclusion as an ExtendScript (ES3)
 * string literal — works for either `'...'` or `"..."` quote style. Uses
 * JSON-style backslash escaping for everything ES3-incompatible: `\\`, `'`,
 * `"`, `\n`, `\r`, `\t`, `\b`, `\f`, NUL, U+2028, U+2029, plus any other
 * control char.
 *
 * Returns ONLY the escaped contents — caller is responsible for the
 * surrounding quotes.
 */
export function jsxStringLiteral(value: string): string {
  // JSON.stringify gives us a fully-escaped JS string literal in `"..."` form.
  // It already handles \\, \", \n, \r, \t, \b, \f, control chars, and ALL
  // non-BMP code points. It does NOT escape U+2028/U+2029 (those are valid in
  // JSON but terminate ES3 string literals) — re-escape them explicitly.
  // It also does NOT escape `'`, since JSON uses double quotes — we handle
  // that for the single-quoted JSX literal style.
  let out = JSON.stringify(value).slice(1, -1);
  out = out.replace(RE_U2028, '\\u2028').replace(RE_U2029, '\\u2029');
  // Escape `'` so the same output is safe inside '...' literals as well.
  out = out.replace(/'/g, "\\'");
  // JSON.stringify already escaped `"` to `\"`. No further work needed.
  return out;
}

/**
 * Escape a string for inclusion in a double-quoted AppleScript literal. AppleScript
 * recognizes `\"` and `\\` inside double-quoted strings; tabs, newlines, etc. are
 * fine literal-as-is in this context but we escape control chars defensively.
 *
 * Returns ONLY the escaped contents — caller adds the surrounding `"..."`.
 */
export function appleScriptDoubleQuoted(value: string): string {
  return value
    .replace(/\\/g, '\\\\')
    .replace(/"/g, '\\"')
    .replace(/\r/g, '\\r')
    .replace(/\n/g, '\\n');
}

/**
 * Escape a string for inclusion inside a `'...'` shell single-quoted arg.
 *
 * Single-quoted shell strings have no escape mechanism, so the only way to
 * include a `'` is to close, escape, reopen: `'...'\\''...'`.
 */
export function shellSingleQuoted(value: string): string {
  return value.replace(/'/g, `'\\''`);
}

/**
 * Allowlist regex for the `PHOTOSHOP_APP_NAME` env var. Matches `Adobe Photoshop`
 * with an optional 4-digit year suffix (e.g. `Adobe Photoshop 2026`). Anything
 * else is rejected at config-load time so a malicious env can never inject
 * AppleScript.
 */
export const PHOTOSHOP_APP_NAME_REGEX = /^Adobe Photoshop( \d{4})?$/;

/**
 * Validate a `PHOTOSHOP_APP_NAME` value. Throws if it doesn't match the strict
 * allowlist. Caller is expected to supply a sane default if the env var is
 * absent; this only validates non-empty strings.
 */
export function validatePhotoshopAppName(name: string): string {
  if (!PHOTOSHOP_APP_NAME_REGEX.test(name)) {
    throw new Error(
      `PHOTOSHOP_APP_NAME '${name}' does not match required pattern ${PHOTOSHOP_APP_NAME_REGEX}.`,
    );
  }
  return name;
}

/** Allowlist regex for capsule slugs in template lookups. */
export const CAPSULE_SLUG_REGEX = /^[a-z0-9-]+$/;
/** Allowlist regex for template names in template lookups. */
export const TEMPLATE_NAME_REGEX = /^[a-z0-9_-]+$/;

/**
 * Validate a capsule slug. Throws on invalid input. Errors are deliberately
 * non-info-leaking (no path echo) so we don't leak FS structure to clients.
 */
export function validateCapsuleSlug(slug: string): string {
  if (!CAPSULE_SLUG_REGEX.test(slug)) {
    throw new Error(`Invalid capsule slug. Must match ${CAPSULE_SLUG_REGEX}.`);
  }
  return slug;
}

/** Validate a template name. Throws on invalid input. */
export function validateTemplateName(name: string): string {
  if (!TEMPLATE_NAME_REGEX.test(name)) {
    throw new Error(`Invalid template name. Must match ${TEMPLATE_NAME_REGEX}.`);
  }
  return name;
}

/**
 * Resolve `target` and assert it stays within `base`. Returns the resolved
 * absolute target path on success. Throws otherwise.
 */
export function assertWithin(base: string, target: string): string {
  const resolvedBase = pathResolve(base);
  const resolvedTarget = pathResolve(target);
  // append separator to base so a target like `${base}-evil` is rejected.
  const baseWithSep = resolvedBase.endsWith(pathSep) ? resolvedBase : resolvedBase + pathSep;
  if (resolvedTarget !== resolvedBase && !resolvedTarget.startsWith(baseWithSep)) {
    throw new Error(`Path escapes allowed root.`);
  }
  return resolvedTarget;
}

/**
 * Resolve a default list of allowed FS roots for batch input/output paths.
 * Driven by the `PHOTOSHOP_MCP_ALLOWED_ROOTS` env var (colon-separated list
 * of absolute paths). If unset, defaults to a sensible Huxley-friendly set.
 */
export function resolveAllowedRoots(): string[] {
  const raw = process.env.PHOTOSHOP_MCP_ALLOWED_ROOTS;
  const home = homedir();
  const defaults: string[] = [
    `${home}/Downloads`,
    `${home}/Pictures`,
    `${home}/Documents`,
  ];
  const catalystRoot = process.env.CATALYST_ROOT;
  if (catalystRoot) defaults.push(catalystRoot);
  // Tmp dir is always allowed — exports/intermediate artifacts live there.
  defaults.push('/tmp');
  defaults.push('/private/tmp'); // macOS resolves /tmp → /private/tmp

  if (!raw) return defaults.map((p) => pathResolve(p));
  const parsed = raw
    .split(':')
    .map((p) => p.trim())
    .filter((p) => p.length > 0)
    .map((p) => pathResolve(p));
  return parsed.length > 0 ? parsed : defaults.map((p) => pathResolve(p));
}

/**
 * Assert `target` resolves under one of the configured allowed roots. Throws
 * with a clear (non-info-leaking) message if not.
 */
export function assertWithinAllowedRoots(target: string): string {
  const resolvedTarget = pathResolve(target);
  const roots = resolveAllowedRoots();
  for (const root of roots) {
    try {
      assertWithin(root, resolvedTarget);
      return resolvedTarget;
    } catch {
      // try next
    }
  }
  throw new Error(
    `Path is outside allowed roots. Configure PHOTOSHOP_MCP_ALLOWED_ROOTS or use a path under your home directory.`,
  );
}
