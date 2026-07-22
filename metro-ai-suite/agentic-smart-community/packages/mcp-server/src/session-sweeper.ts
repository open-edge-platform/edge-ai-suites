import type { McpSubscriberRegistry } from "./mcp-subscriber-registry.js";
import { logger } from "./logger.js";

export interface SessionSweeperOptions {
  /** Evict an HTTP session with no open SSE stream after this long with no request activity. */
  idleTimeoutMs: number;
  /** Interval between sweeps. */
  sweepIntervalMs: number;
}

/**
 * Periodically evict idle MCP sessions from the subscriber registry so forgotten or abandoned
 * subscriptions don't leak the registry Map indefinitely.
 *
 * A session is "idle" (see {@link McpSubscriberRegistry.findIdle}) when it has **no open SSE
 * stream** AND has received **no HTTP request** for longer than `idleTimeoutMs`. An open SSE
 * stream exempts a session no matter how long it's been quiet — that's a healthy subscriber
 * waiting for pushes, not a zombie. stdio (transport === null) is always exempt.
 *
 * Runs on an interval (not immediately — nothing can be idle at startup). Returns a stop()
 * callback to cancel the interval on shutdown.
 */
export function startSessionSweeper(
  registry: McpSubscriberRegistry,
  opts: SessionSweeperOptions,
): () => void {
  const sweep = () => {
    const now = Date.now();
    const idle = registry.findIdle(now, opts.idleTimeoutMs);
    for (const { sessionId, entry } of idle) {
      const idleSec = Math.round((now - entry.lastSeen) / 1000);
      logger.info(`[mcp] evicting idle session sid=${sessionId} (idle ${idleSec}s, no open SSE)`);
      try {
        // Closing the transport fires transport.onclose → registry.unregister(sid).
        entry.transport?.close();
      } catch (err) {
        logger.warn(`[mcp] failed to close idle session ${sessionId}: ${err}`);
      }
      // Belt-and-suspenders: unregister explicitly in case onclose didn't fire. Map.delete is
      // idempotent, so a double-unregister (from onclose + here) is harmless.
      registry.unregister(sessionId);
    }
  };

  const id = setInterval(sweep, opts.sweepIntervalMs);
  if (typeof id.unref === "function") id.unref();
  return () => clearInterval(id);
}
