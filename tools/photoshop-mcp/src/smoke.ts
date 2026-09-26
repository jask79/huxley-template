/**
 * Standalone smoke test — does NOT speak MCP. Just imports the bridge and
 * runs a `ps_is_running`-style probe so we can verify the server boots,
 * imports cleanly, and (if PS is open) reaches Photoshop.
 *
 * Run via `npm run smoke`.
 */
import { PhotoshopBridge } from './bridge/extendscript.js';
import { checkHealth } from './bridge/health.js';

async function main(): Promise<void> {
  const bridge = new PhotoshopBridge();
  console.log(`[smoke] Configured app name: ${bridge.getAppName()}`);
  const health = await checkHealth(bridge);
  console.log('[smoke] Health:', JSON.stringify(health, null, 2));
  if (!health.running) {
    console.log('[smoke] Photoshop is not running — bridge import OK but no live test executed.');
    process.exit(0);
  }
  if (!health.activeDocument) {
    console.log('[smoke] PS is running, no active document — open something to test deeper tools.');
  }
  process.exit(0);
}

main().catch((e) => {
  console.error('[smoke] Failed:', e);
  process.exit(1);
});
