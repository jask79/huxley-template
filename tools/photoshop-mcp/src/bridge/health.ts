/**
 * Health-check helpers used by ps_is_running and as preflight inside other tools.
 */
import { PhotoshopBridge } from './extendscript.js';
import { TIMEOUTS } from './timeouts.js';

export interface HealthInfo {
  running: boolean;
  appName: string;
  version?: string;
  buildNumber?: string;
  activeDocument?: {
    name: string;
    path?: string;
    width: number;
    height: number;
    resolution: number;
    layerCount: number;
  } | null;
}

export async function checkHealth(bridge: PhotoshopBridge): Promise<HealthInfo> {
  const running = await bridge.isRunning();
  if (!running) {
    return { running: false, appName: bridge.getAppName() };
  }

  // PS is running — make sure the app name we use matches what's actually open.
  const detected = await bridge.detectAppName();
  const probe = await bridge.tryExec<HealthProbe>(
    `
      var info = {};
      info.version = app.version;
      try { info.buildNumber = app.build; } catch (e) { info.buildNumber = null; }
      if (app.documents.length > 0) {
        var d = app.activeDocument;
        var docInfo = {
          name: d.name,
          width: d.width.value,
          height: d.height.value,
          resolution: d.resolution,
          layerCount: d.layers.length
        };
        try { docInfo.path = d.fullName.fsName; } catch (e) { docInfo.path = null; }
        info.activeDocument = docInfo;
      } else {
        info.activeDocument = null;
      }
      setResult(info);
    `,
    TIMEOUTS.HEALTH,
  );

  if (!probe.ok) {
    return { running: true, appName: detected };
  }
  const info = probe.value;
  return {
    running: true,
    appName: detected,
    version: info.version,
    buildNumber: info.buildNumber ?? undefined,
    activeDocument: info.activeDocument
      ? {
          name: info.activeDocument.name,
          ...(info.activeDocument.path ? { path: info.activeDocument.path } : {}),
          width: info.activeDocument.width,
          height: info.activeDocument.height,
          resolution: info.activeDocument.resolution,
          layerCount: info.activeDocument.layerCount,
        }
      : null,
  };
}

interface HealthProbe {
  version: string;
  buildNumber: string | null;
  activeDocument: {
    name: string;
    path: string | null;
    width: number;
    height: number;
    resolution: number;
    layerCount: number;
  } | null;
}
