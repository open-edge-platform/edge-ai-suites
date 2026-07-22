import { readdirSync, rmSync, statSync } from "node:fs";
import { join } from "node:path";
import type { ServerConfig } from "./config.js";
import { logger } from "./logger.js";

const DAY_MS = 24 * 60 * 60 * 1000;
const DATE_RE = /^\d{4}-\d{2}-\d{2}$/;

/**
 * Schedule periodic cleanup of:
 *   - log files older than config.logging.retentionDays
 *   - segment day-dirs older than config.storage.retentionDays
 *
 * Runs once at startup, then once per day just after local midnight. Anchoring to the wall clock
 * (rather than a 24h interval from process start) means a day-dir that expires at midnight is
 * removed within minutes, while still waking only once a day. Each run is a cheap directory scan;
 * an actual delete happens at most once per day per subdir. Returns a stop() callback for shutdown.
 */
export function startStorageCleaner(config: ServerConfig): () => void {
  const run = () => {
    try {
      cleanupMonitorLogs(config.monitorsLogsDir, config.logging.retentionDays);
    } catch (err) {
      logger.warn(`[cleanup] log cleanup failed: ${err}`);
    }
    try {
      cleanupSegments(config.segmentsDir, config.storage.cleanupSubdirs, config.storage.retentionDays);
    } catch (err) {
      logger.warn(`[cleanup] segments cleanup failed: ${err}`);
    }
  };

  let timer: NodeJS.Timeout;
  const scheduleNextMidnight = () => {
    const now = new Date();
    const next = new Date(now.getFullYear(), now.getMonth(), now.getDate() + 1, 0, 5, 0, 0);
    timer = setTimeout(() => {
      run();
      scheduleNextMidnight();
    }, next.getTime() - now.getTime());
  };

  run();
  scheduleNextMidnight();
  return () => clearTimeout(timer);
}

/**
 * Delete .log files under logs/monitors/<monitor_id>/ whose filename date is older than retentionDays.
 */
export function cleanupMonitorLogs(monitorsLogsDir: string, retentionDays: number): void {
  if (retentionDays <= 0) return; // 0/negative disables cleanup
  if (!safeIsDir(monitorsLogsDir)) return;
  // retentionDays=N keeps exactly N calendar days (today + N-1 previous); older is deleted.
  const cutoff = startOfToday() - (retentionDays - 1) * DAY_MS;
  let removed = 0;
  for (const monitorId of readdirSafe(monitorsLogsDir)) {
    const dir = join(monitorsLogsDir, monitorId);
    if (!safeIsDir(dir)) continue;
    for (const file of readdirSafe(dir)) {
      if (!file.endsWith(".log")) continue;
      const date = file.slice(0, 10);
      if (!DATE_RE.test(date)) continue;
      if (parseDate(date) < cutoff) {
        try {
          rmSync(join(dir, file));
          removed++;
        } catch { /* best-effort */ }
      }
    }
  }
  if (removed > 0) logger.info(`[cleanup] deleted ${removed} expired monitor log files (retention=${retentionDays}d)`);
}

/**
 * Delete day-dirs (YYYY-MM-DD) under segments/<monitor_id>/{cleanupSubdirs[]}/ older than retentionDays.
 * Never touches latest.jpg, pipeline.db, or non-date-formatted dirs.
 */
export function cleanupSegments(
  segmentsDir: string,
  cleanupSubdirs: string[],
  retentionDays: number,
): void {
  if (retentionDays <= 0) return; // 0/negative disables cleanup
  if (!safeIsDir(segmentsDir)) return;
  // retentionDays=N keeps exactly N calendar days (today + N-1 previous); older is deleted.
  const cutoff = startOfToday() - (retentionDays - 1) * DAY_MS;
  let removed = 0;
  for (const monitorId of readdirSafe(segmentsDir)) {
    const monitorDir = join(segmentsDir, monitorId);
    if (!safeIsDir(monitorDir)) continue;
    for (const subdir of cleanupSubdirs) {
      const subPath = join(monitorDir, subdir);
      if (!safeIsDir(subPath)) continue;
      for (const dayDir of readdirSafe(subPath)) {
        if (!DATE_RE.test(dayDir)) continue;  // skip non-date dirs (e.g. temp)
        if (parseDate(dayDir) < cutoff) {
          try {
            rmSync(join(subPath, dayDir), { recursive: true, force: true });
            removed++;
          } catch { /* best-effort */ }
        }
      }
    }
  }
  if (removed > 0) logger.info(`[cleanup] deleted ${removed} expired segment day-dirs (retention=${retentionDays}d)`);
}

function safeIsDir(p: string): boolean {
  try { return statSync(p).isDirectory(); } catch { return false; }
}

function readdirSafe(p: string): string[] {
  try { return readdirSync(p); } catch { return []; }
}

function parseDate(s: string): number {
  // s in YYYY-MM-DD; treat as local midnight
  const [y, m, d] = s.split("-").map(Number);
  return new Date(y, m - 1, d).getTime();
}

function startOfToday(): number {
  const now = new Date();
  return new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime();
}
