/**
 * ExtendScript-over-AppleScript bridge for Adobe Photoshop on macOS.
 *
 * Strategy: write the JSX to a temp file, tell Photoshop to `do javascript`
 * with $.evalFile(...). Result is captured by writing JSON to a result file
 * (Photoshop's `do javascript` swallows stdout otherwise). Errors are
 * caught inside the wrapper script and serialized to the same result file.
 *
 * This is the same transport `@alisaitteke/photoshop-mcp` uses on macOS, but
 * we own it directly so we can:
 *   - target Photoshop 2026 by default (env override)
 *   - return structured errors with PS error codes
 *   - run multiple ops in a single script call (batching)
 *   - apply a queue so we never race a second osascript against PS
 */
import { exec } from 'node:child_process';
import { promisify } from 'node:util';
import { writeFile, readFile, unlink } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { randomBytes } from 'node:crypto';
import {
  appleScriptDoubleQuoted,
  jsxStringLiteral,
  shellSingleQuoted,
  validatePhotoshopAppName,
} from './safety.js';
import { TIMEOUTS } from './timeouts.js';

const execAsync = promisify(exec);

/**
 * Maximum depth of pending tasks in the bridge queue. Beyond this we fast-fail
 * to keep memory bounded. Each task is small (a script body string) but a
 * runaway producer could still pin RAM. v1 picks a generous bound.
 */
const MAX_QUEUE_DEPTH = 32;

export interface BridgeOptions {
  /** Photoshop application name as macOS sees it. Override with env PHOTOSHOP_APP_NAME. */
  appName?: string;
  /** Default timeout in milliseconds for one script call. */
  defaultTimeoutMs?: number;
}

export interface ScriptResult<T = unknown> {
  ok: true;
  value: T;
}

export interface ScriptError {
  ok: false;
  error: string;
  code?: string | number;
  stack?: string;
}

export type ScriptOutcome<T = unknown> = ScriptResult<T> | ScriptError;

/**
 * Detected Photoshop application name on this Mac, in priority order.
 * Huxley's docs say PS 2026 is the target, but we keep an upgrade ladder.
 *
 * SECURITY: every entry MUST match `PHOTOSHOP_APP_NAME_REGEX` in safety.ts —
 * the env-var-supplied override is validated against the same regex at
 * construction time. The candidates here are also validated defensively.
 */
const APP_NAME_CANDIDATES = [
  'Adobe Photoshop 2026',
  'Adobe Photoshop 2025',
  'Adobe Photoshop 2024',
];

export class PhotoshopBridge {
  private readonly appName: string;
  private readonly defaultTimeoutMs: number;
  private queue: Promise<unknown> = Promise.resolve();
  private queueDepth = 0;

  constructor(opts: BridgeOptions = {}) {
    const raw =
      opts.appName ?? process.env.PHOTOSHOP_APP_NAME ?? APP_NAME_CANDIDATES[0]!;
    // SECURITY: reject anything that doesn't match the strict allowlist regex.
    // `appName` flows into AppleScript, so a missed escape is RCE.
    this.appName = validatePhotoshopAppName(raw);
    this.defaultTimeoutMs = opts.defaultTimeoutMs ?? TIMEOUTS.DEFAULT;
  }

  getAppName(): string {
    return this.appName;
  }

  /** True if any Adobe Photoshop process is running. */
  async isRunning(): Promise<boolean> {
    try {
      const { stdout } = await execAsync('pgrep -f "Adobe Photoshop"');
      return stdout.trim().length > 0;
    } catch {
      return false;
    }
  }

  /**
   * Resolve the actual app name macOS knows for the running PS.
   * Falls back to the configured app name if detection fails.
   */
  async detectAppName(): Promise<string> {
    for (const candidate of APP_NAME_CANDIDATES) {
      try {
        // Defense-in-depth: validate each candidate against the same allowlist
        // we apply to env-var input, then escape for both AppleScript double
        // quotes AND the surrounding shell single quotes.
        const safe = validatePhotoshopAppName(candidate);
        const asEsc = appleScriptDoubleQuoted(safe);
        const inner = `tell application "System Events" to (name of processes) contains "${asEsc}"`;
        const shellArg = shellSingleQuoted(inner);
        const { stdout } = await execAsync(`osascript -e '${shellArg}'`);
        if (stdout.trim() === 'true') {
          return candidate;
        }
      } catch {
        // try next
      }
    }
    return this.appName;
  }

  /**
   * Execute an ExtendScript snippet inside Photoshop and return parsed JSON
   * from the script. The wrapper guarantees a JSON result file is written
   * (success or error).
   *
   * The user's script body is expected to assign its result to `result`
   * (or call `setResult(...)`). If nothing is set, `null` is returned.
   */
  async exec<T = unknown>(scriptBody: string, timeoutMs?: number): Promise<T> {
    const outcome = await this.tryExec<T>(scriptBody, timeoutMs);
    if (outcome.ok) return outcome.value;
    const err = new Error(outcome.error);
    (err as Error & { code?: string | number; stack?: string }).code = outcome.code;
    if (outcome.stack) err.stack = outcome.stack;
    throw err;
  }

  /**
   * Like `exec` but returns a discriminated outcome instead of throwing.
   * Useful when callers want to surface Photoshop errors as tool responses
   * rather than MCP failures.
   */
  async tryExec<T = unknown>(
    scriptBody: string,
    timeoutMs?: number,
  ): Promise<ScriptOutcome<T>> {
    return this.enqueue(() => this.runOnce<T>(scriptBody, timeoutMs));
  }

  /**
   * Sequence script calls so two osascripts never race against the same PS.
   *
   * Bounded by `MAX_QUEUE_DEPTH` — beyond that we reject immediately so a
   * runaway caller can't pin RAM with pending script bodies. v1 keeps it
   * simple: a fast-fail bound, no cancellation.
   */
  private enqueue<T>(task: () => Promise<T>): Promise<T> {
    if (this.queueDepth >= MAX_QUEUE_DEPTH) {
      return Promise.reject(
        new Error(
          `Photoshop bridge queue is full (${this.queueDepth} pending). Slow your batch or wait for tasks to drain.`,
        ),
      );
    }
    this.queueDepth++;
    const next = this.queue.then(task, task);
    // keep the chain alive even if a task throws, and decrement depth either way
    this.queue = next.then(
      () => undefined,
      () => undefined,
    );
    next.finally(() => {
      this.queueDepth--;
    }).catch(() => undefined);
    return next;
  }

  private async runOnce<T>(
    scriptBody: string,
    timeoutMs?: number,
  ): Promise<ScriptOutcome<T>> {
    const id = randomBytes(6).toString('hex');
    const jsxPath = join(tmpdir(), `catalyst-ps-${id}.jsx`);
    const resultPath = join(tmpdir(), `catalyst-ps-${id}.json`);
    const wrapped = wrapScript(scriptBody, resultPath);

    try {
      await writeFile(jsxPath, wrapped, 'utf8');

      // INVARIANT (sync): `do javascript` blocks the AppleScript reply until the
      // JSX completes. When `osascript` returns success we are guaranteed the
      // wrapper finished — and the wrapper's outermost try/catch ALWAYS writes
      // a result file (success or error). Therefore: success exit + no result
      // file is treated as an error (the wrapper crashed before writing).
      //
      // SECURITY: appName is validated against the strict allowlist in the
      // constructor; we still escape both the AppleScript double-quote layer
      // AND the surrounding shell single-quote layer for defense in depth.
      // The JSX path is from `tmpdir()` + a hex random id so it cannot contain
      // quotes, but we escape it anyway (cheap, prevents drift if the source
      // ever changes).
      const safeAppName = appleScriptDoubleQuoted(this.appName);
      const safeJsxPath = appleScriptDoubleQuoted(jsxPath);
      const appleScript = [
        `tell application "${safeAppName}"`,
        `\tactivate`,
        `\tdo javascript "$.evalFile(File('${safeJsxPath}'))"`,
        `end tell`,
      ].join('\n');

      const cmd = `osascript -e '${shellSingleQuoted(appleScript)}'`;

      const timeout = timeoutMs ?? this.defaultTimeoutMs;
      try {
        await execAsync(cmd, { timeout, maxBuffer: 8 * 1024 * 1024 });
      } catch (e: unknown) {
        const msg = (e as { message?: string }).message ?? String(e);
        // If PS wrote a result file we still trust it (PS error caught there)
        const fileResult = await readResultFile<T>(resultPath);
        if (fileResult) return fileResult;
        if ((e as { killed?: boolean }).killed) {
          // TODO(v2): proper PS-side cancel. AppleScript `do javascript` blocks
          // the reply until JSX completes; killing osascript only frees the
          // host side. Photoshop will keep running the JSX, and the next
          // queued task will sit behind it. The bridge queue serializes calls
          // so the next call waits naturally — but the JSX itself is not
          // cancelled. Document this in README; ship a real cancel via UXP
          // plugin transport in v2.
          return {
            ok: false,
            error: `Photoshop did not respond within ${timeout}ms. PS may still be running this script — it will block subsequent calls until it finishes or the modal is dismissed.`,
            code: 'OSASCRIPT_TIMEOUT',
          };
        }
        return {
          ok: false,
          error: `osascript failed: ${msg.split('\n')[0]}`,
          code: 'OSASCRIPT_FAILED',
        };
      }

      // INVARIANT enforcement: success exit but no result file ⇒ the wrapper
      // crashed before its catch block ran (very rare — usually a syntax
      // error in the wrapper itself). Treat as a hard error, not silent
      // success.
      const fileResult = await readResultFile<T>(resultPath);
      if (!fileResult) {
        return {
          ok: false,
          error: 'Photoshop ran the script but no result file was written. The JSX wrapper likely crashed before its catch block could record the outcome.',
          code: 'NO_RESULT',
        };
      }
      return fileResult;
    } finally {
      await safeUnlink(jsxPath);
      await safeUnlink(resultPath);
    }
  }
}

/**
 * JSON polyfill emitted into every JSX wrapper.
 *
 * ExtendScript in Photoshop 2026 does NOT ship a global `JSON` object —
 * `JSON.stringify` throws "JSON is undefined" and the wrapper used to crash
 * before its catch block could write a result file (caller then saw a silent
 * "no result" failure). We embed a minimal stringify-only subset so the
 * wrapper can always serialize an outcome.
 *
 * This is a STRINGIFY-ONLY subset — `JSON.parse` is intentionally NOT
 * polyfilled. User scripts passed to `bridge.exec(scriptBody)` cannot call
 * `JSON.parse` inside Photoshop; pre-parse JSON on the Node side and pass
 * already-decoded values into the script body instead.
 *
 * Escape layering: this string is interpolated into a TS backtick template
 * literal in `wrapScript()`. Backslashes are TS-escaped once here so the
 * emitted JSX byte stream contains the canonical json2 regex/meta-table
 * literals (single backslashes in the JSX source).
 */
// Adapted from Douglas Crockford's json2.js (stringify-only subset): https://github.com/douglascrockford/JSON-js
//
// CRITICAL: The polyfill install is wrapped in its own try/catch so that if any
// statement inside it throws on a future PS runtime (e.g. `var JSON = JSON || {}`
// or a regex literal), the wrapper still writes a result file. Without this
// guard, a polyfill failure would crash the JSX before the user-script try/catch
// could run, the result file would never be written, and the bridge would
// surface a silent NO_RESULT — the exact symptom the polyfill was meant to fix.
//
// In the failure path we MUST NOT call JSON.stringify (it's the very thing that
// just failed). We use an inline hand-rolled string escaper for the error
// message and an __abortRest flag to skip the user-script block below.
const JSON_POLYFILL_JSX = `// --- JSON polyfill (ExtendScript lacks a global JSON in PS 2026) ---
// Adapted from Douglas Crockford's json2.js (stringify-only subset): https://github.com/douglascrockford/JSON-js
// NOTE: This is a stringify-only subset. JSON.parse is intentionally NOT polyfilled —
// user scripts run inside Photoshop cannot call JSON.parse; decode JSON on the Node side.
var __abortRest = false;
try {
  var JSON = JSON || {};
  (function () {
    function quote(string) {
      var escapable = /[\\\\\\"\\x00-\\x1f\\x7f-\\x9f]/g;
      var meta = {
        '\\b': '\\\\b',
        '\\t': '\\\\t',
        '\\n': '\\\\n',
        '\\f': '\\\\f',
        '\\r': '\\\\r',
        '"':  '\\\\"',
        '\\\\': '\\\\\\\\'
      };
      escapable.lastIndex = 0;
      return escapable.test(string)
        ? '"' + string.replace(escapable, function (a) {
            var c = meta[a];
            return typeof c === 'string' ? c : '\\\\u' + ('0000' + a.charCodeAt(0).toString(16)).slice(-4);
          }) + '"'
        : '"' + string + '"';
    }
    function str(key, holder) {
      var i, k, v, length, partial, value = holder[key];
      if (value && typeof value === 'object' && typeof value.toJSON === 'function') {
        value = value.toJSON(key);
      }
      switch (typeof value) {
        case 'string': return quote(value);
        case 'number': return isFinite(value) ? String(value) : 'null';
        case 'boolean': return String(value);
        case 'object':
          if (!value) return 'null';
          partial = [];
          if (Object.prototype.toString.apply(value) === '[object Array]') {
            length = value.length;
            for (i = 0; i < length; i += 1) {
              partial[i] = str(i, value) || 'null';
            }
            return partial.length === 0 ? '[]' : '[' + partial.join(',') + ']';
          }
          for (k in value) {
            if (Object.prototype.hasOwnProperty.call(value, k)) {
              v = str(k, value);
              if (v) partial.push(quote(k) + ':' + v);
            }
          }
          return partial.length === 0 ? '{}' : '{' + partial.join(',') + '}';
      }
      return undefined;
    }
    if (typeof JSON.stringify !== 'function') {
      JSON.stringify = function (value) {
        return str('', {'': value});
      };
    }
  }());
} catch (__pfErr) {
  // Polyfill install itself threw. Build the error payload with an inline
  // hand-rolled escaper — we CANNOT use JSON.stringify here (just failed) and
  // we CANNOT call quote() from above (lives inside the very polyfill that
  // failed). Handles only what's needed for an error message.
  var __pfMsg = (__pfErr && __pfErr.message) ? String(__pfErr.message) : String(__pfErr);
  var __pfEsc = '';
  for (var __pfI = 0; __pfI < __pfMsg.length; __pfI++) {
    var __pfCh = __pfMsg.charAt(__pfI);
    var __pfCode = __pfMsg.charCodeAt(__pfI);
    if (__pfCh === '\\\\' || __pfCh === '"') {
      __pfEsc += '\\\\' + __pfCh;
    } else if (__pfCode < 0x20 || (__pfCode >= 0x7f && __pfCode <= 0x9f)) {
      var __pfHex = __pfCode.toString(16);
      while (__pfHex.length < 4) __pfHex = '0' + __pfHex;
      __pfEsc += '\\\\u' + __pfHex;
    } else {
      __pfEsc += __pfCh;
    }
  }
  try {
    var __pfFile = new File(__resultPath);
    __pfFile.encoding = "UTF-8";
    __pfFile.open("w");
    __pfFile.write('{"ok":false,"error":"JSON polyfill failed to install: ' + __pfEsc + '","code":"POLYFILL_FAILED"}');
    __pfFile.close();
  } catch (__pfWriteErr) {
    // last-ditch: nothing we can do, swallow
  }
  __abortRest = true;
}
// --- end polyfill ---`;

/**
 * Wrap user script with try/catch + JSON result emission.
 * The user script can:
 *   - assign to `result` (the global var we initialize)
 *   - call `setResult(value)` for clarity
 *   - just leave `result` unset → returns null
 *
 * The JSON polyfill (see `JSON_POLYFILL_JSX`) is emitted at the top of every
 * wrapper because PS 2026's ExtendScript lacks a global `JSON` object.
 */
function wrapScript(userScript: string, resultPath: string): string {
  // Escape the result path for embedding in a "..." JSX string literal.
  // tmpdir() paths are sanitized by Node, but use the central helper so this
  // stays correct if the source ever changes.
  const escapedPath = jsxStringLiteral(resultPath);
  return `
// === Huxley Photoshop Bridge ===
#target photoshop
// __resultPath is declared BEFORE the polyfill so the polyfill's own
// catch-block can write a fallback result file if install fails.
var __resultPath = "${escapedPath}";
${JSON_POLYFILL_JSX}
var result = null;
function setResult(v) { result = v; }
function __writeOutcome(payload) {
  try {
    var f = new File(__resultPath);
    f.encoding = "UTF-8";
    f.open("w");
    f.write(payload);
    f.close();
  } catch (e) {
    // last-ditch: nothing we can do, swallow
  }
}
function __serialize(v) {
  if (typeof v === 'undefined') return 'null';
  try { return JSON.stringify(v); } catch (e1) {
    try { return JSON.stringify(String(v)); } catch (e2) {
      // Last-ditch hand-rolled string escape — polyfill-independent.
      // If JSON.stringify is unavailable (polyfill failed or was clobbered by
      // the user script), produce a valid JSON string literal using only
      // character-code lookups and concatenation.
      var s = String(v);
      var out = '"';
      for (var i = 0; i < s.length; i++) {
        var ch = s.charAt(i);
        var code = s.charCodeAt(i);
        if (ch === '\\\\' || ch === '"') {
          out += '\\\\' + ch;
        } else if (code < 0x20 || (code >= 0x7f && code <= 0x9f)) {
          var hex = code.toString(16);
          while (hex.length < 4) hex = '0' + hex;
          out += '\\\\u' + hex;
        } else {
          out += ch;
        }
      }
      return out + '"';
    }
  }
}
// Skip the user-script block entirely if the polyfill failed to install —
// the polyfill's catch already wrote a POLYFILL_FAILED result file, and
// __serialize/JSON.stringify won't work here anyway.
if (!__abortRest) {
  try {
    // === User script begins ===
${userScript}
    // === User script ends ===
    __writeOutcome('{"ok":true,"value":' + __serialize(result) + '}');
  } catch (err) {
    var code = (err && err.number) ? err.number : null;
    var msg = (err && err.message) ? err.message : String(err);
    __writeOutcome('{"ok":false,"error":' + __serialize(msg) + ',"code":' + __serialize(code) + '}');
  }
}
`;
}

async function readResultFile<T>(path: string): Promise<ScriptOutcome<T> | null> {
  try {
    const raw = await readFile(path, 'utf8');
    if (!raw.trim()) return null;
    const parsed = JSON.parse(raw) as ScriptOutcome<T>;
    return parsed;
  } catch {
    return null;
  }
}

async function safeUnlink(p: string): Promise<void> {
  try {
    await unlink(p);
  } catch {
    // ignore
  }
}
