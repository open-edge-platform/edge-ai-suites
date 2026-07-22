import { readFileSync } from "node:fs";
import { homedir } from "node:os";
import { join, resolve } from "node:path";
import { parse as parseYaml } from "yaml";
import type { SchemaDefinition } from "@smartbuilding-video/db";

export interface MonitorConfig {
  enabled?: boolean;
  name?: string;
  source_url: string;
  use_case: string;                          // references a key in config.yaml's use_case_dict
  pipeline_config?: Record<string, unknown>;
}

/**
 * Per-clip summarization tuning consumed by video-worker task-poller.
 * All fields optional — defaults applied in task-poller match the legacy
 * stream_monitor config (single-level LOCAL_PROMPT only, no MACRO/GLOBAL
 * roll-up). Override per use_case when a different temporal strategy fits.
 */
export interface SummarizeConfig {
  method?: "SIMPLE" | "USE_VLM_T-1" | "USE_LLM_T-1" | "USE_ALL_T-1";
  processor_kwargs?: {
    levels?: number;
    level_sizes?: number[];
    process_fps?: number;
    chunking_method?: "pelt" | "uniform";
  };
}

/**
 * Use case definition. Lives in config.yaml under `use_case_dict.<key>` —
 * one entry per use case, referenced by monitors via `use_case` field.
 */
export interface UseCaseConfig {
  description?: string;
  /** Task name registered in multilevel-video-understanding service. */
  video_summary_task: string;
  /** Optional path to Python override script for rule evaluation. */
  evaluate_rules_path?: string;
  /**
   * DB schema owned by THIS use case: extension columns on the shared
   * `video_summary_tasks` table (+ optional custom_tables). Each use case
   * declares only the fields its own pipeline parses — there is no global shared
   * schema. Applied via idempotent ALTER TABLE at startup and on register.
   */
  schema?: SchemaDefinition;
  /** Optional per-clip summarization tuning (see SummarizeConfig). */
  summarize?: SummarizeConfig;
  /** Optional default report configuration consumed by smartbuilding_generate_report. */
  reports?: {
    data_source: "events" | "alerts" | "video_summary_tasks";
    default_type?: "daily" | "weekly" | "monthly";
    filter?: Record<string, unknown>;
    include_live_snapshot?: boolean;
  };
}

export interface ServerConfig {
  /**
   * Absolute path to the config.yaml the server was booted from. Present when
   * `--config <path>` was passed on the command line. Consumed by tools that
   * need to write back to the same file (e.g. `smartbuilding_use_case_register`
   * with `persist: true`). Undefined when booted without --config.
   */
  configPath?: string;

  // Derived from SMARTBUILDING_DATA_DIR — not settable in config.yaml
  dataDir: string;        // root: ~/.mcp-smartbuilding (or $SMARTBUILDING_DATA_DIR)
  dbPath: string;         // dataDir/smartbuilding.db
  segmentsDir: string;    // dataDir/segments/<monitor_id>/  (latest.jpg, queries/)
  reportsLogsDir: string; // dataDir/logs/reports/  (SRT debug artifacts)
  monitorsLogsDir: string; // dataDir/logs/monitors/<monitor_id>/<YYYY-MM-DD>.log

  summaryService: {
    url: string;
    /**
     * Optional host↔container path remap. multilevel-video-understanding typically runs
     * in a container that mounts the host's data dir at a different path. If set, the
     * client rewrites `video` paths starting with `hostPrefix` to `containerPrefix`
     * before POSTing. Leave undefined when both sides see the same paths.
     */
    pathRemap?: { hostPrefix: string; containerPrefix: string };
  };
  vlmService: {
    url: string;
    model: string;
    maxEdgePx: number;
  };
  videostreamAnalytics: {
    url: string;
  };
  /**
   * Keepalive protocol with videostream-analytics (VSA API §3.8). When enabled,
   * the server arms the VSA watchdog at register_source (pipeline.keepalive) and
   * runs a heartbeat loop that POSTs /sources/{id}/keepalive for every online
   * monitor every intervalMs. VSA auto-pauses a source that goes silent for
   * timeoutSeconds. intervalMs must stay well below timeoutSeconds.
   */
  keepalive: {
    enabled: boolean;
    intervalMs: number;           // MCP → VSA heartbeat cadence
    timeoutSeconds: number;       // VSA auto-pause threshold (register payload)
    checkIntervalSeconds: number; // VSA watchdog poll interval (register payload)
  };
  pollIntervalMs: number;
  videoSummaryMaxConcurrent: number;
  mcp?: {
    port?: number;
    /** Evict an MCP session after this long with no open SSE stream AND no HTTP request. Default 30min. */
    sessionIdleTimeoutMs?: number;
    /** How often the idle-session sweeper runs. Default 5min. */
    sessionSweepIntervalMs?: number;
  };
  eventsWebhook?: {
    port?: number;
    maxBodyBytes?: number;
  };
  /** Use case library — loaded from config.yaml top-level `use_case_dict` block. */
  useCaseDict: Record<string, UseCaseConfig>;
  // Loaded separately via loadMonitorsConfig(--monitors <path>); not from config.yaml
  monitors?: Record<string, MonitorConfig>;
  logging: {
    retentionDays: number;  // default 14
    maxFileMb: number;      // default 50
  };
  storage: {
    retentionDays: number;       // default 7
    cleanupSubdirs: string[];    // default ["motion_events", "recordings", "queries"]
  };
}

function resolveDataDir(): string {
  const env = process.env.SMARTBUILDING_DATA_DIR;
  if (env) return resolve(env);
  return join(homedir(), ".mcp-smartbuilding");
}

export function loadConfig(configPath?: string): ServerConfig {
  const dataDir = resolveDataDir();

  const parsed = configPath
    ? parseYaml(readFileSync(resolve(configPath), "utf-8"))
    : {};

  // Reject monitors in config.yaml — they must live in a separate file passed via --monitors
  if (parsed && typeof parsed === "object" && "monitors" in parsed) {
    throw new Error(
      "config.yaml must not contain a `monitors:` field. Move per-monitor declarations to a separate file and pass it via --monitors <path>.",
    );
  }

  return {
    configPath: configPath ? resolve(configPath) : undefined,
    dataDir,
    dbPath: join(dataDir, "smartbuilding.db"),
    segmentsDir: join(dataDir, "segments"),
    reportsLogsDir: join(dataDir, "logs", "reports"),
    monitorsLogsDir: join(dataDir, "logs", "monitors"),

    summaryService: {
      url: parsed?.summary_service?.url ?? "http://localhost:8192",
      pathRemap: parsed?.summary_service?.path_remap?.host_prefix && parsed?.summary_service?.path_remap?.container_prefix
        ? {
            hostPrefix: resolve(parsed.summary_service.path_remap.host_prefix.replace(/\$\{HOME\}/g, homedir())),
            containerPrefix: parsed.summary_service.path_remap.container_prefix,
          }
        : undefined,
    },
    vlmService: {
      url: parsed?.vlm_service?.url ?? "http://localhost:41091/v1",
      model: parsed?.vlm_service?.model ?? "default",
      maxEdgePx: parsed?.vlm_service?.max_edge_px ?? 720,
    },
    videostreamAnalytics: { url: parsed?.videostream_analytics?.url ?? "http://localhost:8999" },
    keepalive: {
      enabled: parsed?.keepalive?.enabled ?? true,
      intervalMs: parsed?.keepalive?.interval_ms ?? 30_000,
      timeoutSeconds: parsed?.keepalive?.timeout_seconds ?? 90,
      checkIntervalSeconds: parsed?.keepalive?.check_interval_seconds ?? 10,
    },
    pollIntervalMs: parsed?.poll_interval_ms ?? 5000,
    videoSummaryMaxConcurrent: parsed?.video_summary_max_concurrent ?? 2,
    mcp: {
      port: parsed?.mcp?.port ?? 3100,
      sessionIdleTimeoutMs: parsed?.mcp?.session_idle_timeout_ms ?? 30 * 60 * 1000,
      sessionSweepIntervalMs: parsed?.mcp?.session_sweep_interval_ms ?? 5 * 60 * 1000,
    },
    eventsWebhook: {
      port: parsed?.events_webhook?.port ?? 3101,
      maxBodyBytes: parsed?.events_webhook?.max_body_bytes ?? 1024 * 1024,
    },
    logging: {
      retentionDays: parsed?.logging?.retention_days ?? 14,
      maxFileMb: parsed?.logging?.max_file_mb ?? 50,
    },
    storage: {
      retentionDays: parsed?.storage?.retention_days ?? 7,
      cleanupSubdirs: parsed?.storage?.cleanup_subdirs ?? ["motion_events", "recordings", "queries"],
    },
    useCaseDict: parseUseCaseDict(parsed?.use_case_dict),
  };
}

/**
 * Load monitor declarations from a standalone monitors.yaml file passed via --monitors CLI flag.
 * Expanding ${HOME} / ${USER} env vars in string values (e.g. for prefilter.model_path).
 */
export function loadMonitorsConfig(monitorsPath: string): Record<string, MonitorConfig> {
  const resolved = resolve(monitorsPath);
  const raw = readFileSync(resolved, "utf-8");
  const parsed = parseYaml(raw);
  if (!parsed || typeof parsed !== "object" || !parsed.monitors) {
    throw new Error(`monitors file ${resolved} must contain a top-level \`monitors:\` block`);
  }
  return expandEnvVars(parsed.monitors) as Record<string, MonitorConfig>;
}

/**
 * Parse and validate the `use_case_dict` block from config.yaml.
 * Each entry must have `video_summary_task` (no default — caller must declare it).
 * Returns an empty dict when the block is absent (legal: server can run with no monitors).
 */
function parseUseCaseDict(raw: unknown): Record<string, UseCaseConfig> {
  if (!raw) return {};
  if (typeof raw !== "object" || Array.isArray(raw)) {
    throw new Error("config: use_case_dict must be a mapping of <name>: <UseCaseConfig>");
  }
  const expanded = expandEnvVars(raw) as Record<string, any>;
  const out: Record<string, UseCaseConfig> = {};
  for (const [name, entry] of Object.entries(expanded)) {
    if (!entry || typeof entry !== "object") {
      throw new Error(`config: use_case_dict.${name} must be an object`);
    }
    if (!entry.video_summary_task) {
      throw new Error(`config: use_case_dict.${name} must declare video_summary_task`);
    }
    out[name] = entry as UseCaseConfig;
  }
  return out;
}

function expandEnvVars(value: unknown): unknown {
  if (typeof value === "string") {
    return value.replace(/\$\{([A-Z_][A-Z0-9_]*)\}/gi, (_m, name) => process.env[name] ?? "");
  }
  if (Array.isArray(value)) return value.map(expandEnvVars);
  if (value && typeof value === "object") {
    const out: Record<string, unknown> = {};
    for (const [k, v] of Object.entries(value)) out[k] = expandEnvVars(v);
    return out;
  }
  return value;
}
