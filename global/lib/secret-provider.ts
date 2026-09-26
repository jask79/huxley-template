/**
 * Huxley Secret Provider — macOS Keychain with env var fallback.
 *
 * Usage:
 *   import { getSecret, SecretNotFoundError } from "./secret-provider";
 *
 *   const dbPass = getSecret("ex-supabase-service-role-key");
 *   const token  = getSecret("openrouter-api", "huxley");
 *
 * Tries macOS Keychain first via `security find-generic-password`,
 * then falls back to environment variables.
 *
 * No external dependencies — uses child_process only.
 */

import { execFileSync } from "child_process";
import { platform } from "os";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const SUBPROCESS_TIMEOUT_MS = 5_000;
const IS_MACOS = platform() === "darwin";
const DEFAULT_ACCOUNT = "huxley";

// ---------------------------------------------------------------------------
// Error classes
// ---------------------------------------------------------------------------

export class SecretNotFoundError extends Error {
  public readonly service: string;
  public readonly account: string;
  public readonly envVar: string;

  constructor(service: string, account: string, envVar: string) {
    const message = [
      `Secret not found: service="${service}", account="${account}"`,
      "",
      `The secret was not found in macOS Keychain or as environment variable "${envVar}".`,
      "",
      "To add it to Keychain, run:",
      `  security add-generic-password -s "${service}" -a "${account}" -w "YOUR_VALUE"`,
      "",
      "Or set the environment variable:",
      `  export ${envVar}="YOUR_VALUE"`,
    ].join("\n");

    super(message);
    this.name = "SecretNotFoundError";
    this.service = service;
    this.account = account;
    this.envVar = envVar;
  }
}

export class KeychainError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "KeychainError";
  }
}

// ---------------------------------------------------------------------------
// Internal helpers
// ---------------------------------------------------------------------------

/**
 * Convert a Keychain service name to an environment variable name.
 *
 * @example
 *   serviceToEnvVar("ex-supabase-service-role") // "EX_SUPABASE_SERVICE_ROLE"
 */
function serviceToEnvVar(service: string): string {
  return service.toUpperCase().replace(/-/g, "_");
}

/**
 * Run a macOS `security` command and return stdout, or null on failure.
 *
 * Uses execFileSync to bypass the shell entirely, preventing command
 * injection via malicious service names or secret values.
 */
function runSecurityCmd(args: string[]): string | null {
  try {
    const stdout = execFileSync("security", args, {
      timeout: SUBPROCESS_TIMEOUT_MS,
      encoding: "utf-8",
      // "ignore" stdin prevents interactive prompts in LaunchAgents/daemons.
      // Note: doesn't fully prevent SecurityAgent GUI dialogs — use
      // `security set-keychain-settings` to disable auto-lock for that.
      stdio: ["ignore", "pipe", "pipe"],
    });
    return stdout.trim();
  } catch {
    return null;
  }
}

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------

/**
 * Retrieve a secret, trying macOS Keychain first then environment.
 *
 * @param service  - Keychain service name (e.g. "ex-supabase-service-role-key")
 * @param account  - Keychain account name (default: "huxley")
 * @returns The secret value as a string
 * @throws {SecretNotFoundError} If the secret is not in Keychain or environment
 */
export function getSecret(
  service: string,
  account: string = DEFAULT_ACCOUNT,
): string {
  const envVar = serviceToEnvVar(service);

  // --- Try macOS Keychain first ---
  if (IS_MACOS) {
    const value = runSecurityCmd([
      "find-generic-password",
      "-s",
      service,
      "-a",
      account,
      "-w",
    ]);
    if (value !== null) {
      return value;
    }
  }

  // --- Fall back to environment variable ---
  const envValue = process.env[envVar];
  if (envValue !== undefined) {
    return envValue;
  }

  throw new SecretNotFoundError(service, account, envVar);
}

/**
 * Store a secret in macOS Keychain.
 *
 * @param service  - Keychain service name
 * @param value    - The secret value to store
 * @param account  - Keychain account name (default: "huxley")
 * @returns true if stored successfully
 * @throws {KeychainError} If not on macOS or command fails
 */
export function setSecret(
  service: string,
  value: string,
  account: string = DEFAULT_ACCOUNT,
): boolean {
  if (!IS_MACOS) {
    throw new KeychainError("setSecret requires macOS Keychain.");
  }

  // Delete existing entry if present (ignore failure)
  runSecurityCmd([
    "delete-generic-password",
    "-s",
    service,
    "-a",
    account,
  ]);

  // Add the new entry — uses execFileSync to bypass the shell entirely,
  // preventing injection via malicious secret values containing $(), backticks, etc.
  try {
    execFileSync(
      "security",
      [
        "add-generic-password",
        "-s",
        service,
        "-a",
        account,
        "-w",
        value,
        "-U",
        // Authorize the security CLI to read this item without ACL prompts
        "-T",
        "/usr/bin/security",
      ],
      {
        timeout: SUBPROCESS_TIMEOUT_MS,
        encoding: "utf-8",
        stdio: ["pipe", "pipe", "pipe"],
      },
    );
    return true;
  } catch (err) {
    const message = err instanceof Error ? err.message : String(err);
    throw new KeychainError(
      `Failed to store secret service="${service}": ${message}`,
    );
  }
}

/**
 * Check whether a secret exists in Keychain.
 *
 * @param service  - Keychain service name
 * @param account  - Keychain account name (default: "huxley")
 * @returns true if the secret is retrievable
 */
export function secretExists(
  service: string,
  account: string = DEFAULT_ACCOUNT,
): boolean {
  if (!IS_MACOS) return false;

  const value = runSecurityCmd([
    "find-generic-password",
    "-s",
    service,
    "-a",
    account,
    "-w",
  ]);
  return value !== null && value.length > 0;
}
