import { join } from "node:path";
import type { SmartCommunityDB } from "@smart-community-video/db";
import { monitorCtl } from "@smart-community-video/tools";
import { loadMonitorsConfig, type MonitorConfig, type ServerConfig } from "./config.js";
import { logger, monitorLogger } from "./logger.js";
import type { WorkerService } from "./video-worker/index.js";

export type ApplyAction = "up" | "down" | "restart";

export interface ApplyResult {
  monitor_id: string;
  status: "ok" | "already_running" | "skipped" | "failed";
  reason?: string;
}

/**
 * Apply a parsed monitors dict against the runtime: register/start each enabled monitor
 * (action=up), unregister/stop each (action=down), or both in sequence (action=restart).
 *
 * Per-monitor failures are isolated — videostream-analytics (:8999) being unreachable
 * yields a "failed" result for that monitor but never throws.
 *
 * Detailed traces (analytics responses, error stacks) are appended to
 * <monitorsLogsDir>/<monitor_id>/<YYYY-MM-DD>.log via monitorLogger.
 */
export async function applyMonitorConfig(
  db: SmartCommunityDB,
  config: ServerConfig,
  workerService: WorkerService,
  monitors: Record<string, MonitorConfig>,
  action: ApplyAction,
  targetMonitorId?: string,
): Promise<ApplyResult[]> {
  const results: ApplyResult[] = [];
  const entries = Object.entries(monitors).filter(([id]) => !targetMonitorId || id === targetMonitorId);

  for (const [monitorId, cfg] of entries) {
    const mLog = monitorLogger(monitorId, config.monitorsLogsDir, config.logging.maxFileMb);

    if (action === "up" && cfg.enabled === false) {
      mLog.info(`skipped (disabled in monitors.yaml)`);
      results.push({ monitor_id: monitorId, status: "skipped", reason: "disabled" });
      continue;
    }

    try {
      if (action === "down" || action === "restart") {
        mLog.info(`down: unregister + stop worker`);
        await monitorCtl(db, config.videostreamAnalytics.url, workerService, {
          action: "unregister",
          monitor_id: monitorId,
        });
      }
      if (action === "up" || action === "restart") {
        // Idempotency: skip if DB + analytics + worker all match
        if (action === "up" && await isAlreadyRunning(db, config.videostreamAnalytics.url, workerService, monitorId)) {
          mLog.info(`already running, no action`);
          results.push({ monitor_id: monitorId, status: "already_running" });
          continue;
        }
        const ucCfg = config.useCaseDict[cfg.use_case];
        if (!ucCfg) {
          throw new Error(`unknown use_case "${cfg.use_case}". Known: [${Object.keys(config.useCaseDict).join(", ")}]`);
        }
        mLog.info(`up: register_source + start worker (source=${cfg.source_url} use_case=${cfg.use_case} task=${ucCfg.video_summary_task})`);
        await monitorCtl(db, config.videostreamAnalytics.url, workerService, {
          action: "register_source",
          monitor_id: monitorId,
          source_url: cfg.source_url,
          name: cfg.name ?? monitorId,
          use_case: cfg.use_case,
          video_summary_task: ucCfg.video_summary_task,
          pipeline_config: cfg.pipeline_config,
          keepalive: {
            enabled: config.keepalive.enabled,
            timeout_seconds: config.keepalive.timeoutSeconds,
            check_interval_seconds: config.keepalive.checkIntervalSeconds,
          },
          webhook_url: `http://localhost:${config.eventsWebhook!.port}/events`,
          data_dir: join(config.segmentsDir, monitorId),
        });
      }
      mLog.info(`${action} ok`);
      results.push({ monitor_id: monitorId, status: "ok" });
    } catch (err: any) {
      const msg = err?.message ?? String(err);
      mLog.error(`${action} failed: ${msg}\n${err?.stack ?? ""}`);
      results.push({ monitor_id: monitorId, status: "failed", reason: msg });
    }
  }

  return results;
}

/**
 * Auto-register monitors at server startup. Reports concise stderr summaries;
 * full per-monitor traces go to logs/monitors/<monitor_id>/<date>.log.
 *
 * videostream-analytics (:8999) unreachable → warn for each affected monitor,
 * server continues running. User can run smart_community_monitors_compose up later.
 */
export async function autoRegisterMonitors(
  db: SmartCommunityDB,
  config: ServerConfig,
  workerService: WorkerService,
): Promise<void> {
  if (!config.monitors || Object.keys(config.monitors).length === 0) {
    logger.info("[auto-register] no monitors declared, skipping");
    return;
  }
  const results = await applyMonitorConfig(db, config, workerService, config.monitors, "up");
  for (const r of results) {
    if (r.status === "ok") logger.info(`[auto-register] ${r.monitor_id} ok`);
    else if (r.status === "already_running") logger.info(`[auto-register] ${r.monitor_id} already_running`);
    else if (r.status === "skipped") logger.info(`[auto-register] ${r.monitor_id} skipped (${r.reason ?? "disabled"})`);
    else {
      const logPath = monitorLogger(r.monitor_id, config.monitorsLogsDir, config.logging.maxFileMb).currentLogPath();
      logger.warn(`[auto-register] ${r.monitor_id} failed: ${r.reason}, see ${logPath}`);
    }
  }
}

async function isAlreadyRunning(
  db: SmartCommunityDB,
  analyticsUrl: string,
  workerService: WorkerService,
  monitorId: string,
): Promise<boolean> {
  const m = db.getMonitor(monitorId);
  if (!m || m.status !== "online") return false;
  if (!workerService.workers.has(monitorId)) return false;
  try {
    const resp = await fetch(`${analyticsUrl}/sources/${monitorId}/status`, { signal: AbortSignal.timeout(5000) });
    return resp.status === 200;
  } catch {
    return false;
  }
}

const reRegisterInFlight = new Set<string>();

/**
 * Re-register one monitor that videostream-analytics no longer knows — the
 * keepalive heartbeat got a 404, meaning VSA is reachable but its in-memory
 * source registry was wiped (container recreate / process restart).
 *
 * The declaration is re-read from monitors.yaml on every call, so entries
 * persisted at runtime and pipeline_config (which is NOT stored in the
 * monitors DB table) are picked up. Monitors absent from or disabled in
 * monitors.yaml are NOT resurrected — VSA dropping them then matches the
 * desired state.
 *
 * Concurrent triggers for the same monitor collapse into one registration;
 * keepalive ticks fire faster than a registration completes. A failed attempt
 * clears the guard, so the next 404 retries — self-healing across a VSA that
 * is still coming up.
 */
export async function reregisterUnknownMonitor(
  db: SmartCommunityDB,
  config: ServerConfig,
  workerService: WorkerService,
  monitorId: string,
): Promise<void> {
  if (reRegisterInFlight.has(monitorId)) return;
  reRegisterInFlight.add(monitorId);
  const mLog = monitorLogger(monitorId, config.monitorsLogsDir, config.logging.maxFileMb);
  try {
    if (!config.monitorsPath) {
      mLog.warn(`re-register skipped: server started without --monitors, no monitors.yaml to reload`);
      return;
    }
    let monitors: Record<string, MonitorConfig>;
    try {
      monitors = loadMonitorsConfig(config.monitorsPath);
    } catch (err: any) {
      mLog.error(`re-register failed: cannot reload ${config.monitorsPath}: ${err?.message ?? err}`);
      return;
    }
    const cfg = monitors[monitorId];
    if (!cfg) {
      mLog.warn(`re-register skipped: ${monitorId} not declared in monitors.yaml (removed while analytics was down?)`);
      return;
    }
    if (cfg.enabled === false) {
      mLog.info(`re-register skipped: disabled in monitors.yaml`);
      return;
    }
    logger.warn(`[re-register] ${monitorId} unknown to videostream-analytics — re-registering from ${config.monitorsPath}`);
    const [r] = await applyMonitorConfig(db, config, workerService, { [monitorId]: cfg }, "up");
    if (r && (r.status === "ok" || r.status === "already_running")) {
      logger.info(`[re-register] ${monitorId} ${r.status}`);
    } else {
      logger.warn(`[re-register] ${monitorId} failed: ${r?.reason ?? "no result"} — will retry on the next keepalive 404`);
    }
  } finally {
    reRegisterInFlight.delete(monitorId);
  }
}
