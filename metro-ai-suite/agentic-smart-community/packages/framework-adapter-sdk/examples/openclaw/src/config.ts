/**
 * Plugin config shape (validated by openclaw.plugin.json's configSchema, read from
 * `api.pluginConfig`). Monitor-centric with a flow-type key (`alerts`) so future flows
 * (`reports`, `status`) can be added as sibling keys without reshaping.
 */

export interface AlertTarget {
  /** Agent that owns the target session (used to resolve the JSONL path for FS-append). */
  agentId: string;
  /** OpenClaw session key, e.g. `agent:child-safety-agent:main` or a Feishu group session. */
  sessionKey: string;
  /** true → channel delivery via subagent.run(deliver:true); false/undefined → raw FS-append. */
  deliver?: boolean;
}

export interface MonitorRoutes {
  alerts?: AlertTarget[];
  // Future flows for the same monitor (not implemented here — extension points only):
  // reports?: AlertTarget[];
  // status?:  AlertTarget[];
}

export interface PluginConfig {
  mcpServer: { url: string; headers?: Record<string, string> };
  monitors: Record<string, MonitorRoutes>;
  /** Optional persistent cursor file. Defaults to `<OPENCLAW_HOME>/smartbuilding-alerts-cursor.json`. */
  cursorFile?: string;
  /** Optional safety-net poll interval (ms). Default 0 (disabled). */
  pollFallbackMs?: number;
}

export class ConfigError extends Error {}

/** Validate + normalize `api.pluginConfig` into a PluginConfig, throwing ConfigError on problems. */
export function parseConfig(raw: unknown): PluginConfig {
  if (!raw || typeof raw !== "object") {
    throw new ConfigError("pluginConfig is missing or not an object");
  }
  const cfg = raw as Record<string, unknown>;

  const mcp = cfg.mcpServer as { url?: unknown; headers?: unknown } | undefined;
  if (!mcp || typeof mcp.url !== "string" || !mcp.url) {
    throw new ConfigError("pluginConfig.mcpServer.url is required");
  }

  const monitorsRaw = cfg.monitors;
  if (!monitorsRaw || typeof monitorsRaw !== "object") {
    throw new ConfigError("pluginConfig.monitors is required");
  }

  const monitors: Record<string, MonitorRoutes> = {};
  for (const [monitorId, routesRaw] of Object.entries(monitorsRaw as Record<string, unknown>)) {
    const routes = (routesRaw ?? {}) as Record<string, unknown>;
    const alerts = Array.isArray(routes.alerts) ? (routes.alerts as unknown[]) : [];
    monitors[monitorId] = {
      alerts: alerts.map((t, i) => normalizeTarget(monitorId, i, t)),
    };
  }

  return {
    mcpServer: {
      url: mcp.url,
      headers:
        mcp.headers && typeof mcp.headers === "object"
          ? (mcp.headers as Record<string, string>)
          : undefined,
    },
    monitors,
    cursorFile: typeof cfg.cursorFile === "string" ? cfg.cursorFile : undefined,
    pollFallbackMs: typeof cfg.pollFallbackMs === "number" ? cfg.pollFallbackMs : undefined,
  };
}

function normalizeTarget(monitorId: string, index: number, raw: unknown): AlertTarget {
  const t = (raw ?? {}) as Record<string, unknown>;
  if (typeof t.agentId !== "string" || !t.agentId) {
    throw new ConfigError(`monitors.${monitorId}.alerts[${index}].agentId is required`);
  }
  if (typeof t.sessionKey !== "string" || !t.sessionKey) {
    throw new ConfigError(`monitors.${monitorId}.alerts[${index}].sessionKey is required`);
  }
  return { agentId: t.agentId, sessionKey: t.sessionKey, deliver: t.deliver === true };
}
