import type { SmartBuildingDB } from "@smartbuilding-video/db";
import type { ServerConfig } from "./config.js";
import { logger } from "./logger.js";

/**
 * Periodically POST /sources/{id}/keepalive to videostream-analytics for every
 * DB-online monitor, proving MCP-side liveness (VSA API §3.8). VSA auto-pauses a
 * source when no keepalive arrives within pipeline.keepalive.timeout_seconds —
 * that watchdog is armed at register_source (see monitor-ctl analyticsRegister).
 *
 * Failures are non-fatal and logged at debug level: a transient analytics outage
 * shorter than timeout_seconds is harmless, and a longer one legitimately pauses
 * the source (recovered by a subsequent register_source / start).
 *
 * No-op when keepalive is disabled in config. Returns a stop() callback to clear
 * the interval on shutdown.
 */
export function startKeepaliveSender(config: ServerConfig, db: SmartBuildingDB): () => void {
  if (!config.keepalive.enabled) {
    logger.info("[keepalive] disabled in config — heartbeat sender not started");
    return () => {};
  }

  const analyticsUrl = config.videostreamAnalytics.url;
  const intervalMs = config.keepalive.intervalMs;
  // Cap the per-request timeout so a stalled source can't overrun the next tick.
  const reqTimeoutMs = Math.max(1_000, Math.min(intervalMs, 5_000));

  const tick = async () => {
    const online = db.listOnlineMonitors();
    if (online.length === 0) return;
    await Promise.all(
      online.map((m) =>
        fetch(`${analyticsUrl}/sources/${m.id}/keepalive`, {
          method: "POST",
          signal: AbortSignal.timeout(reqTimeoutMs),
        })
          .then((resp) => {
            if (!resp.ok) logger.debug(`[keepalive] ${m.id} → HTTP ${resp.status}`);
          })
          .catch((err) => logger.debug(`[keepalive] ${m.id} failed: ${err?.message ?? err}`)),
      ),
    );
  };

  const id = setInterval(tick, intervalMs);
  logger.info(`[keepalive] heartbeat sender started: every ${intervalMs}ms → ${analyticsUrl}/sources/{id}/keepalive`);
  return () => clearInterval(id);
}
