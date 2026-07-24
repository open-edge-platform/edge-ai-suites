import { readFileSync, writeFileSync } from "node:fs";
import { parseDocument, isMap, Scalar } from "yaml";
import type { SmartBuildingDB } from "@smartbuilding-video/db";

/** Wrap a string so yaml emits it double-quoted (matches the hand-written monitors.yaml style). */
function quoted(value: string): Scalar {
  const s = new Scalar(value);
  s.type = Scalar.QUOTE_DOUBLE;
  return s;
}

export interface IWorkerService {
  workers: Map<string, unknown>;
  start(monitorId: string): void;
  stop(monitorId: string): Promise<void>;
}

export interface MonitorCtlParams {
  action: "start" | "stop" | "register_source" | "unregister" | "status" | "list";
  monitor_id?: string;
  source_url?: string;
  name?: string;
  use_case?: string;
  video_summary_task?: string;
  pipeline_config?: Record<string, unknown>;
  webhook_url?: string;
  /**
   * Absolute path videostream-analytics should write this monitor's data to.
   * Convention: <data_dir>/latest.jpg, <data_dir>/recordings/<YYYY-MM-DD>/,
   *             <data_dir>/motion_events/<YYYY-MM-DD>/.
   * MCP server's storage cleaner relies on this layout to safely purge old day-folders.
   * Required for register_source.
   */
  data_dir?: string;
  /**
   * Keepalive watchdog config forwarded to analytics at register_source as
   * `pipeline.keepalive`. When provided (and `pipeline_config` does not already
   * declare its own `keepalive` block), it is injected so the analytics-side
   * watchdog is armed. The MCP server is responsible for driving the matching
   * POST /sources/{id}/keepalive heartbeat loop. See VSA API §3.8.
   */
  keepalive?: { enabled: boolean; timeout_seconds: number; check_interval_seconds: number };
  /**
   * When true, mirror the mutation to `monitors_path` on disk (comment-preserving
   * via yaml.Document): register_source → write the monitor's declaration block,
   * unregister → delete it. Requires `monitors_path` to be set. Failure writing
   * does NOT fail the whole call — it is surfaced as `monitors_yaml: "skipped"`
   * plus a warning, so the in-memory + DB registration still stands. Mirrors the
   * `persist` semantics of use_case_register writing back to config.yaml.
   */
  persist?: boolean;
  /**
   * Absolute path to the monitors.yaml the server was booted from (--monitors).
   * Injected by the tool layer from `config.monitorsPath`. Only consulted when
   * `persist` is true.
   */
  monitors_path?: string;
}

/** Fields mirrored back to monitors.yaml — matches MonitorDeclaration in monitors-compose.ts. */
interface PersistOutcome {
  monitors_yaml?: "written" | "removed" | "skipped";
  persist_warnings?: string[];
}

/**
 * Mirror a monitor mutation to `monitorsPath` on disk. Uses yaml.Document API so
 * comments and field ordering are preserved. `decl === null` → deleteIn (unregister).
 * Non-throwing: on any error, records a warning and returns "skipped". Only the
 * fields consumed by applyMonitorConfig on restart are written — video_summary_task
 * / data_dir / webhook_url / keepalive are all derived from config at bootstrap and
 * must NOT be persisted here or they would drift.
 */
function persistMonitorEntry(
  monitorsPath: string | undefined,
  monitorId: string,
  decl: Record<string, unknown> | null,
): PersistOutcome {
  if (!monitorsPath) {
    return {
      monitors_yaml: "skipped",
      persist_warnings: ["persist requested but monitors_path is unset (server booted without --monitors?); skipped"],
    };
  }
  try {
    const raw = readFileSync(monitorsPath, "utf-8");
    const doc = parseDocument(raw);
    const existing = doc.get("monitors");
    if (!existing || !isMap(existing)) {
      doc.set("monitors", doc.createNode({}));
    }
    if (decl === null) {
      doc.deleteIn(["monitors", monitorId]);
    } else {
      // Emit `name` double-quoted to match the built-in monitors.yaml entries.
      const node = typeof decl.name === "string" ? { ...decl, name: quoted(decl.name) } : decl;
      doc.setIn(["monitors", monitorId], node);
    }
    writeFileSync(monitorsPath, doc.toString(), "utf-8");
    return { monitors_yaml: decl === null ? "removed" : "written" };
  } catch (err: any) {
    return {
      monitors_yaml: "skipped",
      persist_warnings: [`persist to ${monitorsPath} failed: ${err.message}`],
    };
  }
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

async function analyticsSourceExists(analyticsUrl: string, monitorId: string): Promise<boolean | null> {
  try {
    const resp = await fetch(`${analyticsUrl}/sources/${monitorId}/status`, { signal: AbortSignal.timeout(8_000) });
    if (resp.status === 200) return true;
    if (resp.status === 404) return false;
    throw new Error(`analytics GET /sources/${monitorId}/status returned HTTP ${resp.status}`);
  } catch (err: any) {
    if (err.message?.includes("returned HTTP")) throw err;
    throw new Error(`videostream-analytics (${analyticsUrl}) unreachable: ${err.message}`);
  }
}

async function analyticsDelete(analyticsUrl: string, monitorId: string): Promise<void> {
  const resp = await fetch(`${analyticsUrl}/sources/${monitorId}`, {
    method: "DELETE",
    signal: AbortSignal.timeout(10_000),
  });
  if (!resp.ok && resp.status !== 404) {
    const t = await resp.text().catch(() => "");
    throw new Error(`analytics DELETE /sources/${monitorId} failed HTTP ${resp.status}: ${t.slice(0, 200)}`);
  }
}

async function analyticsRegister(
  analyticsUrl: string,
  monitorId: string,
  sourceUrl: string,
  webhookUrl: string,
  dataDir: string,
  pipelineConfig?: Record<string, unknown>,
  keepalive?: MonitorCtlParams["keepalive"]
): Promise<void> {
  const pipeline: Record<string, unknown> = pipelineConfig
    ? { ...pipelineConfig }
    : {
        motion: { enabled: true },
        prefilter: { enabled: false },
        recording: { enabled: true, interval_seconds: 60 },
      };

  // Arm the analytics-side keepalive watchdog unless the monitor already
  // declares its own keepalive block (per-monitor override wins).
  if (keepalive && !("keepalive" in pipeline)) {
    pipeline.keepalive = {
      enabled: keepalive.enabled,
      timeout_seconds: keepalive.timeout_seconds,
      check_interval_seconds: keepalive.check_interval_seconds,
    };
  }

  const resp = await fetch(`${analyticsUrl}/register_source`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      source_id: monitorId,
      source_url: sourceUrl,
      webhook_url: webhookUrl,
      data_dir: dataDir,    // analytics writes latest.jpg + recordings/<date>/ + motion_events/<date>/ here
      pipeline,
    }),
    signal: AbortSignal.timeout(10_000),
  });
  if (!resp.ok) {
    const t = await resp.text().catch(() => "");
    throw new Error(`analytics register_source failed HTTP ${resp.status}: ${t.slice(0, 200)}`);
  }
}

// ---------------------------------------------------------------------------
// Main export
// ---------------------------------------------------------------------------

/**
 * Manage monitor lifecycle as an atomic operation across DB, videostream-analytics, and video-worker.
 */
export async function monitorCtl(
  db: SmartBuildingDB,
  analyticsBaseUrl: string,
  workerService: IWorkerService,
  params: MonitorCtlParams
): Promise<unknown> {
  const analyticsUrl = analyticsBaseUrl;

  switch (params.action) {
    // -----------------------------------------------------------------------
    case "list": {
      const monitors = db.listMonitors();
      try {
        const resp = await fetch(`${analyticsUrl}/sources`, { signal: AbortSignal.timeout(5000) });
        if (resp.ok) {
          const live = (await resp.json()) as any[];
          const liveById = Object.fromEntries(live.map((s: any) => [s.source_id, s]));
          return monitors.map((m) => ({ ...m, analyticsReachable: true, analyticsStatus: liveById[m.id]?.status ?? "unknown" }));
        }
        return monitors.map((m) => ({ ...m, analyticsReachable: false, analyticsStatus: null, analyticsError: `HTTP ${resp.status}` }));
      } catch (err: any) {
        return monitors.map((m) => ({ ...m, analyticsReachable: false, analyticsStatus: null, analyticsError: err?.message ?? "unreachable" }));
      }
    }

    // -----------------------------------------------------------------------
    case "register_source": {
      if (!params.monitor_id) throw new Error("monitor_id is required for register_source");
      if (!params.source_url) throw new Error("source_url is required for register_source");
      if (!params.video_summary_task)
        throw new Error("video_summary_task is required for register_source");
      if (!params.data_dir)
        throw new Error("data_dir is required for register_source (where analytics should write latest.jpg / recordings/ / motion_events/)");

      const monitorId = params.monitor_id;
      // Guard against conflating the monitor id with the VLM task name — a common
      // agent mistake. Monitor ids follow the cam_<use_case> convention;
      // <use_case>_monitor is the video_summary_task name, not a monitor id.
      if (monitorId === params.video_summary_task) {
        throw new Error(
          `monitor_id "${monitorId}" must not equal the video_summary_task name ("${params.video_summary_task}"). ` +
          `Use the cam_<use_case> convention (e.g. cam_${params.use_case ?? "<use_case>"}).`,
        );
      }
      if (!params.webhook_url) throw new Error("webhook_url is required for register_source");
      const webhookUrl = params.webhook_url;
      const dataDir = params.data_dir;

      const dbExists = !!db.getMonitor(monitorId);
      const analyticsExists = await analyticsSourceExists(analyticsUrl, monitorId); // throws if unreachable
      const workerRunning = workerService.workers.has(monitorId);

      // use_case consistency check (only when DB record exists and param provided)
      if (dbExists && params.use_case) {
        const existing = db.getMonitor(monitorId)!;
        if (existing.useCase !== params.use_case) {
          throw new Error(
            `use_case mismatch: DB="${existing.useCase}", got="${params.use_case}". Unregister first to change use_case.`
          );
        }
      }

      // ✅/✅/✅ — all running, idempotent return
      if (dbExists && analyticsExists && workerRunning) {
        return { success: true, monitor_id: monitorId, status: "already_running" };
      }

      // Stop worker if running (graceful, waits for in-flight poll)
      if (workerRunning) {
        await workerService.stop(monitorId);
      }

      // Delete from analytics if it exists there (ensures clean re-register)
      if (analyticsExists) {
        await analyticsDelete(analyticsUrl, monitorId);
      }

      // DB: insert or update
      if (dbExists) {
        db.updateMonitor(monitorId, {
          sourceUrl: params.source_url,
          ...(params.name ? { name: params.name } : {}),
          ...(params.use_case ? { useCase: params.use_case } : {}),
          videoSummaryTask: params.video_summary_task,
          status: "offline",
        });
      } else {
        db.createMonitor({
          id: monitorId,
          name: params.name ?? monitorId,
          sourceUrl: params.source_url,
          status: "offline",
          useCase: params.use_case ?? "default",
          videoSummaryTask: params.video_summary_task,
        });
      }

      // Register with analytics (starts stream processing immediately)
      await analyticsRegister(analyticsUrl, monitorId, params.source_url, webhookUrl, dataDir, params.pipeline_config, params.keepalive);
      db.updateMonitorStatus(monitorId, "online");

      // Start video-worker task poller
      workerService.start(monitorId);

      // Optionally mirror the declaration back to monitors.yaml so a restart's
      // autoRegisterMonitors re-runs the full pipeline (and pipeline_config —
      // which is NOT stored in the monitors table — survives).
      let persistOutcome: PersistOutcome = {};
      if (params.persist) {
        persistOutcome = persistMonitorEntry(params.monitors_path, monitorId, {
          enabled: true,
          name: params.name ?? monitorId,
          source_url: params.source_url,
          use_case: params.use_case ?? "default",
          ...(params.pipeline_config ? { pipeline_config: params.pipeline_config } : {}),
        });
      }

      return { success: true, monitor_id: monitorId, ...persistOutcome };
    }

    // -----------------------------------------------------------------------
    case "unregister": {
      if (!params.monitor_id) throw new Error("monitor_id is required for unregister");
      const monitorId = params.monitor_id;

      await workerService.stop(monitorId);
      await fetch(`${analyticsUrl}/sources/${monitorId}`, {
        method: "DELETE",
        signal: AbortSignal.timeout(10_000),
      }).catch(() => { /* non-fatal: DB deletion proceeds regardless */ });
      db.deleteMonitor(monitorId);

      let persistOutcome: PersistOutcome = {};
      if (params.persist) {
        persistOutcome = persistMonitorEntry(params.monitors_path, monitorId, null);
      }

      return { success: true, monitor_id: monitorId, ...persistOutcome };
    }

    // -----------------------------------------------------------------------
    case "start": {
      if (!params.monitor_id) throw new Error("monitor_id is required for start");
      const monitorId = params.monitor_id;
      await fetch(`${analyticsUrl}/sources/${monitorId}/resume`, {
        method: "POST",
        signal: AbortSignal.timeout(10_000),
      }).catch(() => {});
      db.updateMonitorStatus(monitorId, "online");
      workerService.start(monitorId);
      return { success: true, monitor_id: monitorId, status: "online" };
    }

    // -----------------------------------------------------------------------
    case "stop": {
      if (!params.monitor_id) throw new Error("monitor_id is required for stop");
      const monitorId = params.monitor_id;
      await workerService.stop(monitorId);
      await fetch(`${analyticsUrl}/sources/${monitorId}/pause`, {
        method: "POST",
        signal: AbortSignal.timeout(10_000),
      }).catch(() => {});
      db.updateMonitorStatus(monitorId, "offline");
      return { success: true, monitor_id: monitorId, status: "offline" };
    }

    // -----------------------------------------------------------------------
    case "status": {
      if (!params.monitor_id) throw new Error("monitor_id is required for status");
      const monitor = db.getMonitor(params.monitor_id);
      if (!monitor) throw new Error(`Monitor not found: ${params.monitor_id}`);
      try {
        const resp = await fetch(`${analyticsUrl}/sources/${params.monitor_id}/status`, { signal: AbortSignal.timeout(5000) });
        if (resp.ok) return { ...monitor, analyticsReachable: true, analyticsStatus: await resp.json() };
        return { ...monitor, analyticsReachable: false, analyticsStatus: null, analyticsError: `HTTP ${resp.status}` };
      } catch (err: any) {
        return { ...monitor, analyticsReachable: false, analyticsStatus: null, analyticsError: err?.message ?? "unreachable" };
      }
    }

    // -----------------------------------------------------------------------
    default:
      throw new Error(`Unknown action: ${(params as any).action}`);
  }
}

/**
 * Detach a single monitor WITHOUT deleting its DB history — the "stop stream +
 * strip from monitors.yaml, keep history" primitive used by the
 * use_case_register unregister cascade. Steps: stop worker → delete VSA source
 * (non-fatal) → mark the DB row offline (row + alerts/tasks/events/recordings
 * kept) → strip the monitor from monitors.yaml when `persist`. Unlike
 * `monitorCtl action=unregister`, it never calls db.deleteMonitor, so it won't
 * trip FK constraints or destroy history.
 */
export async function detachMonitor(
  db: SmartBuildingDB,
  analyticsBaseUrl: string,
  workerService: IWorkerService,
  params: { monitor_id: string; monitors_path?: string; persist?: boolean },
): Promise<{ monitor_id: string; detached: boolean } & PersistOutcome> {
  const monitorId = params.monitor_id;
  if (workerService.workers.has(monitorId)) {
    await workerService.stop(monitorId);
  }
  await analyticsDelete(analyticsBaseUrl, monitorId).catch(() => {
    /* non-fatal: VSA unreachable / already gone — cleanup still proceeds */
  });
  if (db.getMonitor(monitorId)) {
    db.updateMonitorStatus(monitorId, "offline");
  }
  let persistOutcome: PersistOutcome = {};
  if (params.persist) {
    persistOutcome = persistMonitorEntry(params.monitors_path, monitorId, null);
  }
  return { monitor_id: monitorId, detached: true, ...persistOutcome };
}
