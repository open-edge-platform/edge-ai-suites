import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { z } from "zod";
import { logger } from "./logger.js";
import type { ServerConfig } from "./config.js";
import type { SmartCommunityDB } from "@smart-community-video/db";
import type { VideoSummaryClient } from "@smart-community-video/tools";
import type { WorkerService } from "./video-worker/index.js";

export function registerTools(
  server: McpServer,
  config: ServerConfig,
  db: SmartCommunityDB,
  workerService: WorkerService,
  summaryClient: VideoSummaryClient,
): void {
  const reportJobs = new Map<string, Promise<unknown>>();

  // --- smart_community_alert_query ---
  server.registerTool("smart_community_alert_query", {
    description: "Query or acknowledge alerts. action: latest | by_date | ack | stats",
    inputSchema: {
      monitor_id: z.string().describe("Monitor ID"),
      action: z.enum(["latest", "by_date", "ack", "stats"]).describe("Action to perform"),
      limit: z.number().optional().describe("Max results (default 20, for latest action)"),
      start_date: z.string().optional().describe("Start date YYYY-MM-DD (for by_date/stats)"),
      end_date: z.string().optional().describe("End date YYYY-MM-DD (for by_date/stats)"),
      alert_id: z.number().optional().describe("Alert ID to acknowledge (for ack action)"),
      ack_by: z.string().optional().describe("User who acknowledges (for ack action)"),
    },
  }, async (params) => {
    try {
      const { alertQuery } = await import("@smart-community-video/tools");
      const result = await alertQuery(db, params as any);
      return { content: [{ type: "text" as const, text: JSON.stringify(result, null, 2) }] };
    } catch (err: any) {
      return { content: [{ type: "text" as const, text: `Error: ${err.message}` }], isError: true };
    }
  });

  // --- smart_community_plan_ctl ---
  server.registerTool("smart_community_plan_ctl", {
    description: "Manage per-monitor plans (arbitrary JSON keyed by date). Rule engine can read today's plan before deciding whether to fire. action: list | upsert | delete",
    inputSchema: {
      monitor_id: z.string().describe("Monitor ID"),
      action: z.enum(["list", "upsert", "delete"]).describe("Action to perform"),
      name: z.string().optional().describe("Unique plan name within monitor (required for upsert / delete)"),
      plan: z.record(z.unknown()).optional().describe("Plan data object, arbitrary JSON (required for upsert)"),
      plan_date: z.string().optional().describe("Optional YYYY-MM-DD hint stored with the plan (not the key)"),
      active_only: z.boolean().optional().describe("Return only active plans, default true (for list)"),
    },
  }, async (params) => {
    try {
      const { planCtl } = await import("@smart-community-video/tools");
      const result = planCtl(db, params as any);
      return { content: [{ type: "text" as const, text: JSON.stringify(result, null, 2) }] };
    } catch (err: any) {
      return { content: [{ type: "text" as const, text: `Error: ${err.message}` }], isError: true };
    }
  });

  // --- smart_community_scene_query ---
  server.registerTool("smart_community_scene_query", {
    description: "Real-time scene analysis: reads latest.jpg from $SMART_COMMUNITY_DATA_DIR/segments/<monitor_id>/ and queries VLM (vllm-serving-ipex)",
    inputSchema: {
      monitor_id: z.string().describe("Monitor ID"),
      prompt: z.string().optional().describe("Override prompt for VLM (default: describe scene in 1-2 sentences)"),
      vlm_url: z.string().optional().describe("VLM base URL (default from config: vlmService.url)"),
      model: z.string().optional().describe("VLM model ID (default from config: vlmService.model)"),
      max_edge_px: z.number().optional().describe("Max frame edge in pixels (default from config: vlmService.maxEdgePx)"),
    },
  }, async (params) => {
    try {
      const { default: path } = await import("node:path");
      const { sceneQuery } = await import("@smart-community-video/tools");
      const dataDir = path.join(config.segmentsDir, params.monitor_id);
      const vlmUrl = params.vlm_url ?? config.vlmService.url;
      const model = params.model ?? config.vlmService.model;
      const maxEdgePx = params.max_edge_px ?? config.vlmService.maxEdgePx;
      const result = await sceneQuery({ ...params, data_dir: dataDir, vlm_url: vlmUrl, model, max_edge_px: maxEdgePx });
      return { content: [{ type: "text" as const, text: JSON.stringify(result, null, 2) }] };
    } catch (err: any) {
      return { content: [{ type: "text" as const, text: `Error: ${err.message}` }], isError: true };
    }
  });

  // --- smart_community_generate_report ---
  server.registerTool("smart_community_generate_report", {
    description: "Generate daily/weekly/monthly/custom report. Data source / filter / default type " +
      "are derived from config.yaml use_case_dict[monitor.use_case].reports; tool params override config.",
    inputSchema: {
      monitor_id: z.string().describe("Monitor ID"),
      type: z.enum(["daily", "weekly", "monthly", "custom"]).optional()
        .describe("Report type (default: from use_case_dict reports.default_type, or 'daily'). custom requires period_start + period_end."),
      period_start: z.string().optional().describe("Start of period, closed interval. YYYY-MM-DD or YYYY-MM-DD HH:MM (for type=custom)"),
      period_end: z.string().optional().describe("End of period, closed interval. YYYY-MM-DD or YYYY-MM-DD HH:MM (for type=custom)"),
      data_source: z.enum(["events", "alerts", "video_summary_tasks"]).optional()
        .describe("DB table to query (default: from use_case_dict reports.data_source, or 'alerts')"),
      filter: z.record(z.unknown()).optional()
        .describe("Key-value filter on data_source table columns (default: from use_case_dict reports.filter)"),
    },
  }, async (params) => {
    try {
      const { generateReport } = await import("@smart-community-video/tools");

      // Derive config from useCaseDict[monitor.use_case].reports; tool params override.
      const monitor = db.getMonitor(params.monitor_id);
      const ucReports = monitor ? config.useCaseDict[monitor.useCase]?.reports : undefined;

      const reportConfig = {
        dataSource: (params.data_source ?? ucReports?.data_source ?? "alerts") as "events" | "alerts" | "video_summary_tasks",
        defaultType: (ucReports?.default_type ?? "daily") as "daily" | "weekly" | "monthly",
        summaryClient,
        filter: (params.filter ?? ucReports?.filter) as Record<string, any> | undefined,
        debugDir: config.reportsLogsDir,
      };
      const reportParams = {
        monitor_id: params.monitor_id,
        type: params.type,
        period_start: params.period_start,
        period_end: params.period_end,
      };
      const jobKey = JSON.stringify({ reportParams, dataSource: reportConfig.dataSource, filter: reportConfig.filter });
      let reportJob = reportJobs.get(jobKey);
      if (!reportJob) {
        reportJob = generateReport(db, reportConfig, reportParams);
        reportJobs.set(jobKey, reportJob);
        void reportJob.then(
          () => reportJobs.delete(jobKey),
          (error) => {
            reportJobs.delete(jobKey);
            logger.error(`Background report generation failed for ${params.monitor_id}: ${error}`);
          },
        );
      }

      const pending = Symbol("report-pending");
      let waitTimer: ReturnType<typeof setTimeout> | undefined;
      const result = await Promise.race([
        reportJob,
        new Promise<typeof pending>((resolve) => {
          waitTimer = setTimeout(() => resolve(pending), 10_000);
        }),
      ]);
      if (waitTimer) clearTimeout(waitTimer);
      if (result === pending) {
        return {
          content: [{
            type: "text" as const,
            text: JSON.stringify({
              status: "processing",
              monitorId: params.monitor_id,
              type: params.type ?? reportConfig.defaultType,
              dataSource: reportConfig.dataSource,
              message: "Report generation is still running. Query the reports table for this monitor shortly; do not start a duplicate report.",
            }, null, 2),
          }],
        };
      }
      return { content: [{ type: "text" as const, text: JSON.stringify(result, null, 2) }] };
    } catch (err: any) {
      return { content: [{ type: "text" as const, text: `Error: ${err.message}` }], isError: true };
    }
  });

  // --- smart_community_monitor_ctl ---
  server.registerTool("smart_community_monitor_ctl", {
    description: "Manage monitor lifecycle: register_source | unregister | start | stop | status | list | prefilter_options. " +
      "For register_source, use_case must be a key in config.yaml's use_case_dict; the tool runs " +
      "smart_community_use_case_validate as a pre-check (rejecting if missing fields or summary service issues). " +
      "prefilter_options is a read-only query returning the prefilter model's selectable target_classes " +
      "(class_names + labels_source) so a caller can build pipeline_config.prefilter before register_source.",
    inputSchema: {
      action: z.enum(["start", "stop", "register_source", "unregister", "status", "list", "prefilter_options"])
        .describe("Control action"),
      monitor_id: z.string().optional().describe("Monitor ID (required for all except list)"),
      source_url: z.string().optional().describe("Source URL — any protocol videostream-analytics supports (for register_source)"),
      name: z.string().optional().describe("Display name (for register_source)"),
      use_case: z.string().optional().describe("Use case key from config.yaml use_case_dict (required for register_source)"),
      pipeline_config: z.record(z.unknown()).optional().describe("Pipeline config object (for register_source)"),
      persist: z.boolean().default(true).describe(
        "Mirror the change back to the monitors.yaml the server was booted from (--monitors), " +
        "comment-preserving (default true): register_source writes the entry (lets a restart " +
        "auto-recover this monitor incl. pipeline_config, which is not stored in the DB), " +
        "unregister deletes it, stop flips its enabled to false, start flips it back to true. " +
        "Skipped with a warning if the server was started without --monitors.",
      ),
    },
  }, async (params) => {
    try {
      // For register_source: validate use case via use_case_validate (existence + summary service + schema)
      let videoSummaryTask: string | undefined;
      if (params.action === "register_source") {
        if (!params.use_case) throw new Error("use_case is required for register_source");
        const { useCaseValidate } = await import("@smart-community-video/tools");
        const v = await useCaseValidate({ use_case: params.use_case }, {
          useCaseDict: config.useCaseDict,
          summaryServiceUrl: config.summaryService.url,
        });
        if (!v.valid) {
          throw new Error(
            v.error
              ? `use_case_validate failed: ${v.error}`
              : `use_case_validate failed: ${v.suggestion ?? "schema mismatch"}. ` +
                `missing required fields: [${(v.missing_required_in_prompt ?? []).join(", ")}]. ` +
                `prompt tail: "${v.prompt_tail ?? ""}"`,
          );
        }
        videoSummaryTask = v.video_summary_task;
      }

      const { monitorCtl } = await import("@smart-community-video/tools");
      const { join } = await import("node:path");
      // Inject derived fields the tool layer can compute from server config:
      // - data_dir: per-monitor segment root for analytics to write into
      // - webhook_url: always this server's /events endpoint (not caller-settable;
      //   a wrong port here silently drops every event — see monitor-bootstrap.ts:79)
      // - video_summary_task: derived from use_case_dict[use_case]
      const enriched: any = { ...params };
      // Path used by persist:true to mirror register_source/unregister back to disk.
      enriched.monitors_path = config.monitorsPath;
      if (params.action === "register_source") {
        // monitor_id follows the cam_<use_case> convention. Default it when the
        // caller omits it (symmetric to video_summary_task = <use_case>_monitor) so
        // agents can't accidentally pass the VLM task name as the monitor id.
        const monitorId = params.monitor_id ?? `cam_${params.use_case}`;
        enriched.monitor_id = monitorId;
        enriched.data_dir ??= join(config.segmentsDir, monitorId);
        // Falsy check (not ??=) so an empty string from an internal caller is also
        // treated as unset — otherwise "" leaks through to the "required" throw below.
        if (!enriched.webhook_url) enriched.webhook_url = `http://localhost:${config.eventsWebhook!.port}/events`;
        enriched.video_summary_task = videoSummaryTask;
        // Arm the analytics keepalive watchdog; the server drives the heartbeat loop.
        enriched.keepalive = {
          enabled: config.keepalive.enabled,
          timeout_seconds: config.keepalive.timeoutSeconds,
          check_interval_seconds: config.keepalive.checkIntervalSeconds,
        };
      }
      const result = await monitorCtl(db, config.videostreamAnalytics.url, workerService, enriched);
      return { content: [{ type: "text" as const, text: JSON.stringify(result, null, 2) }] };
    } catch (err: any) {
      return { content: [{ type: "text" as const, text: `Error: ${err.message}` }], isError: true };
    }
  });

  // --- smart_community_monitors_compose ---
  server.registerTool("smart_community_monitors_compose", {
    description: "Docker-compose-style management of monitors declared in a monitors.yaml file. Actions: validate | up | down | restart | ps",
    inputSchema: {
      action: z.enum(["validate", "up", "down", "restart", "ps"]).describe("Compose action"),
      file: z.string().describe("Path to monitors.yaml (absolute or relative to cwd)"),
      monitor_id: z.string().optional().describe("Apply to only this monitor (default: all in file)"),
    },
  }, async (params) => {
    try {
      const { loadMonitorsFromYaml, validateMonitors } = await import("@smart-community-video/tools");
      const { applyMonitorConfig } = await import("./monitor-bootstrap.js");

      // 1. Load + validate (every action validates first)
      let resolvedPath: string;
      let monitors: Record<string, any>;
      try {
        const loaded = loadMonitorsFromYaml(params.file);
        resolvedPath = loaded.resolvedPath;
        monitors = loaded.monitors;
      } catch (err: any) {
        return {
          content: [{ type: "text" as const, text: JSON.stringify({
            action: params.action, file: params.file, valid: false,
            errors: [{ monitor_id: "*", field: "file", reason: err.message }],
            results: [],
          }, null, 2) }],
          isError: true,
        };
      }

      const filtered: Record<string, any> = params.monitor_id
        ? (params.monitor_id in monitors ? { [params.monitor_id]: monitors[params.monitor_id] } : {})
        : monitors;
      const errors = validateMonitors(filtered, Object.keys(config.useCaseDict));
      const valid = errors.length === 0;

      const output: any = { action: params.action, file: resolvedPath, valid, errors, results: [] };

      // 2. Action dispatch
      if (params.action === "validate") {
        return { content: [{ type: "text" as const, text: JSON.stringify(output, null, 2) }] };
      }

      if (!valid) {
        // Don't make changes when config is invalid
        return { content: [{ type: "text" as const, text: JSON.stringify(output, null, 2) }], isError: true };
      }

      if (params.action === "ps") {
        // Report current state of each monitor without modifying anything
        for (const monitorId of Object.keys(filtered)) {
          const dbRec = db.getMonitor(monitorId);
          const workerRunning = workerService.workers.has(monitorId);
          let analytics: any;
          try {
            const resp = await fetch(`${config.videostreamAnalytics.url}/sources/${monitorId}/status`, { signal: AbortSignal.timeout(5000) });
            analytics = resp.ok ? { reachable: true, status: await resp.json() } : { reachable: false, error: `HTTP ${resp.status}` };
          } catch (err: any) {
            analytics = { reachable: false, error: err?.message ?? "unreachable" };
          }
          output.results.push({
            monitor_id: monitorId,
            status: "ok",
            state: {
              db: dbRec ? { exists: true, status: dbRec.status } : { exists: false },
              analytics,
              worker: { running: workerRunning },
            },
          });
        }
        return { content: [{ type: "text" as const, text: JSON.stringify(output, null, 2) }] };
      }

      // up / down / restart — delegate to shared bootstrap helper
      output.results = await applyMonitorConfig(
        db, config, workerService, filtered, params.action,
        params.monitor_id,
      );
      return { content: [{ type: "text" as const, text: JSON.stringify(output, null, 2) }] };
    } catch (err: any) {
      return { content: [{ type: "text" as const, text: `Error: ${err.message}` }], isError: true };
    }
  });

  // --- smart_community_video_db ---
  server.registerTool("smart_community_video_db", {
    description: "Low-level read-only SQL query against the SQLite database (all tables: monitors, alerts, video_summary_tasks, events, recordings, reports, plans)",
    inputSchema: {
      query: z.string().describe("SELECT SQL query to execute"),
      params: z.array(z.unknown()).optional().describe("Positional query parameters"),
    },
  }, async (params) => {
    // Safety: only allow SELECT statements
    if (!params.query.trim().toUpperCase().startsWith("SELECT")) {
      return { content: [{ type: "text" as const, text: "Error: only SELECT queries allowed via this tool" }], isError: true };
    }
    try {
      const results = db.rawQuery(params.query, params.params ?? []);
      return { content: [{ type: "text" as const, text: JSON.stringify(results, null, 2) }] };
    } catch (err: any) {
      return { content: [{ type: "text" as const, text: `SQL Error: ${err.message}` }], isError: true };
    }
  });

  // --- smart_community_use_case_validate ---
  server.registerTool("smart_community_use_case_validate", {
    description: "Validate a use_case end-to-end: (1) exists in config.yaml use_case_dict, " +
      "(2) its video_summary_task is registered in multilevel-video-understanding, " +
      "(3) the task's LOCAL_PROMPT covers every required schema field. " +
      "Used as a pre-check inside monitor_ctl register_source; also callable standalone for dry-run.",
    inputSchema: {
      use_case: z.string().describe("Use case key from config.yaml use_case_dict"),
    },
  }, async (params) => {
    try {
      const { useCaseValidate } = await import("@smart-community-video/tools");
      const result = await useCaseValidate(params, {
        useCaseDict: config.useCaseDict,
        summaryServiceUrl: config.summaryService.url,
      });
      return {
        content: [{ type: "text" as const, text: JSON.stringify(result, null, 2) }],
        isError: !result.valid,
      };
    } catch (err: any) {
      return { content: [{ type: "text" as const, text: `Error: ${err.message}` }], isError: true };
    }
  });

  // --- smart_community_use_case_register ---
  server.registerTool("smart_community_use_case_register", {
    description:
      "Manage use_case lifecycle at runtime without restarting the MCP server. Four actions. " +
      "For NEW use cases, do not call this tool until the user has answered the " +
      "smart-community-use-case-manager Q1/Q2 flow and confirmed Final Schema + Rule Path; " +
      "detection goals are event values, not schema fields. " +
      "RECOMMENDED two-step flow for a new use case (keeps the large prompt_text in ONE call): " +
      "(step 1) action=generate_task with prompt_text (+ evaluate_rules_path on the custom path) — " +
      "runs the consistency gate, POSTs the VLM task to multilevel-video-understanding (auto-PATCH " +
      "on 409), and ON SUCCESS writes <data_dir>/use-cases/<use_case>/prompt.md to disk (a caller-supplied " +
      "evaluate_rules.py is staged to <data_dir>/use-cases/<use_case>/evaluate_rules.py). " +
      "It does NOT touch the DB schema, use_case_dict, or config.yaml. " +
      "(step 2) action=register WITHOUT prompt_text — auto-reads the files step 1 wrote, applies " +
      "the schema via ALTER TABLE, injects use_case_dict, and (persist=true) writes config.yaml. " +
      "schema_extensions is OPTIONAL in both steps: when omitted, the final schema is inferred from " +
      "the prompt's LOCAL_PROMPT `KEY:` output lines (all text columns); pass it only to declare a " +
      "non-text column type or override the inferred required flags. " +
      "Any final schema field beyond severity/event/desc REQUIRES evaluate_rules.py; the consistency " +
      "gate rejects an extended schema without one before DB, VLM, config, or artifact side effects. " +
      "action=register: treats schema_extensions as caller-confirmed extra fields and normalizes " +
      "the final schema to severity/event/desc + extras before validation. HARD GATE first — if any final schema field is absent from " +
      "the prompt's LOCAL_PROMPT output contract, the call is REJECTED with zero side effects " +
      "(the normalized final schema and the prompt output fields must be the same set; the prompt is the " +
      "source of truth). On pass: (1) apply schema_extensions via ALTER TABLE (idempotent), " +
      "(2) POST /v1/tasks to multilevel-video-understanding (auto-PATCH on 409), " +
      "(3) inject the entry into in-memory use_case_dict so task-poller / other tools see it, " +
      "(4) re-run use_case_validate. prompt_text may be omitted; it is then auto-read from " +
      "<data_dir>/use-cases/<use_case>/prompt.md (e.g. the file generate_task wrote). When persist=true, also " +
      "writes the entry back to config.yaml (comment-preserving via yaml.Document). " +
      "action=generate_task: VLM-task registration + prompt.md/evaluate_rules.py persistence only " +
      "(step 1 above); prompt_text is REQUIRED and is never auto-read. " +
      "action=unregister: DELETE /v1/tasks/<name> and remove " +
      "from use_case_dict; also deletes the yaml entry if persist=true. Skipped (with a warning) " +
      "when another use case still references the same VLM task. Any incomplete cleanup (VLM " +
      "delete, config update, artifact archive, or monitor detach) sets degraded=true with " +
      "details in warnings. Unregister always CASCADES to every monitor referencing " +
      "this use case via monitor_ctl action=unregister: stops its worker, deletes its " +
      "videostream-analytics source, and deletes the monitors row. If the row delete " +
      "fails (e.g. FK constraint from existing alerts history), it falls back to stop " +
      "semantics — the row is kept, marked offline — with a warning in the MCP log and " +
      "in warnings (degraded=true); with persist=true " +
      "the monitor is additionally stripped from monitors.yaml, and the use case's on-disk " +
      "artifacts (<data_dir>/use-cases/<uc>/prompt.md, evaluate_rules.py) are archived by moving them to " +
      "<data_dir>/use-cases/.backup/<uc>/ so a later re-register does not auto-read stale files. " +
      "For action=register, if prompt_text is provided with persist=true it is saved to " +
      "<data_dir>/use-cases/<use_case>/prompt.md. evaluate_rules_path, when provided, is staged to " +
      "<data_dir>/use-cases/<use_case>/evaluate_rules.py (auto-discovered when already there) and that " +
      "conventional absolute path is stored in config.yaml for runtime rule execution. " +
      "action=list: READ-ONLY inventory of the LIVE in-memory use_case_dict — no other arguments " +
      "needed. Returns one entry per use case with video_summary_task, schema_fields, rule_path " +
      "(defaultRuleEvaluator | evaluate_rules.py | none), and report_source. This reflects what the " +
      "running server actually uses, including entries registered with persist=false, so prefer it " +
      "over parsing config.yaml from disk. Call it after a successful register/unregister to report " +
      "the system's current use cases.",
    inputSchema: {
      action: z.enum(["register", "generate_task", "unregister", "list"]).describe("register | generate_task | unregister | list"),
      use_case: z.string().optional().describe(
        "Use case key (lowercase ascii, matches /^[a-z][a-z0-9_]{1,63}$/). " +
        "Required for register/generate_task/unregister; omit for list."
      ),
      video_summary_task: z.string().optional().describe(
        "VLM task name (default: <use_case>_monitor). Must not collide with VLM builtins."
      ),
      description: z.string().optional().describe("Human description shown by /v1/tasks"),
      evaluate_rules_path: z.string().optional().describe(
        "Path to a Python evaluate_rules.py override. The tool reads this file for consistency checks, " +
        "stages it to <data_dir>/use-cases/<use_case>/evaluate_rules.py, smoke-tests the staged file, and " +
        "persists the conventional absolute path into config.yaml. Required whenever the Final Schema " +
        "contains fields beyond severity/event/desc, and for custom alert behavior."
      ),
      reports: z.record(z.unknown()).optional().describe("Report config: {data_source, default_type, filter}"),
      summarize: z.record(z.unknown()).optional().describe("Per-clip summarize config: {method, processor_kwargs}"),
      prompt_text: z.string().optional().describe(
        "Full prompt text (Markdown with ## LOCAL_PROMPT sections, OR a raw 4-const Python source). " +
        "REQUIRED for action=generate_task (it is POSTed to the VLM task and written to " +
        "<data_dir>/use-cases/<use_case>/prompt.md). For action=register it is OPTIONAL: when omitted it is " +
        "auto-read from <data_dir>/use-cases/<use_case>/prompt.md (e.g. the file generate_task wrote); when " +
        "provided with persist=true it is (re)saved there. " +
        "Do not include Markdown code fences, because the video-summary service rejects reserved tokens."
      ),
      schema_extensions: z.array(z.object({
        // Names land verbatim in ALTER/CREATE TABLE DDL — plain identifiers only.
        name: z.string().regex(/^[a-zA-Z_][a-zA-Z0-9_]*$/, "must be a plain SQL identifier ([a-zA-Z_][a-zA-Z0-9_]*)"),
        type: z.enum(["text", "integer", "real"]),
        required: z.boolean(),
      })).optional().describe(
        "OPTIONAL. When omitted, the final schema is inferred from the prompt's LOCAL_PROMPT `KEY:` output " +
        "lines (every field becomes a text column; the prompt is the source of truth). Pass this only to " +
        "declare a non-text column type (integer/real) or override an inferred required flag, and then only " +
        "extra persisted output columns explicitly confirmed by the user beyond severity/event/desc " +
        "(e.g. motion_direction, parking_zone). Do not put detection goals/events such as escape, trapped, " +
        "aggressive_behavior, risk_level, *_detected, or *_count here. The tool automatically adds " +
        "severity/event/desc to form the final schema when any structured fields are present. " +
        "Any resulting extension requires evaluate_rules_path (or a staged conventional rule file). " +
        "Applied via ALTER TABLE ADD COLUMN if missing (idempotent). Stored under this use_case's own " +
        "schema (use_case_dict.<uc>.schema) — never a global shared schema."
      ),
      overwrite: z.boolean().optional().describe(
        "When true, replace an existing use_case entry. Default false."
      ),
      persist: z.boolean().default(true).describe(
        "Mirror the mutation to the config.yaml the server was booted from " +
        "(comment-preserving via yaml.Document), default true. On unregister it also " +
        "strips bound monitors from monitors.yaml and archives the use case's on-disk " +
        "artifacts to <data_dir>/use-cases/.backup/. Requires MCP server to have been started " +
        "with --config <path>. Failure to write only produces a warning; in-memory " +
        "registration still stands."
      ),
    },
  }, async (params) => {
    try {
      const { useCaseRegister, monitorCtl } = await import("@smart-community-video/tools");
      const result = await useCaseRegister(params as any, {
        useCaseDict: config.useCaseDict,
        summaryServiceUrl: config.summaryService.url,
        db: (db as any).db,
        configPath: config.configPath,
        baseDir: config.dataDir,
      });

      // Cascade on unregister: for every monitor referencing this use case, run
      // monitorCtl action=unregister (stop worker + delete VSA source + delete
      // the monitors row). If the row delete fails (e.g. FK constraint from
      // existing alerts history), fall back to monitorCtl action=stop — the row
      // is kept, marked offline — and log a warning to the MCP log.
      // This is independent of persist — without it, an in-memory unregister would
      // leave orphan monitors whose use_case no longer exists (task-poller then
      // errors on the next poll). persist only controls whether the mutation is
      // mirrored to monitors.yaml: unregister removes the entry; the stop fallback
      // instead flips the entry's `enabled` to false so a restart cleanly skips it
      // (entry + pipeline_config survive for a later re-enable).
      if (params.action === "unregister" && result.ok) {
        const affected = db.listMonitors().filter((m) => m.useCase === params.use_case);
        const cascaded: unknown[] = [];
        for (const m of affected) {
          try {
            const unreg = (await monitorCtl(db, config.videostreamAnalytics.url, workerService, {
              action: "unregister",
              monitor_id: m.id,
              monitors_path: config.monitorsPath,
              persist: params.persist === true,
            })) as Record<string, unknown>;
            cascaded.push({ ...unreg, db_row: "deleted" });
          } catch (e: any) {
            const error = e?.message ?? String(e);
            logger.warn(
              `use_case_register cascade: failed to delete monitor "${m.id}" row ` +
              `(${error}); falling back to stop — monitors row kept offline`,
            );
            try {
              const stopped = (await monitorCtl(db, config.videostreamAnalytics.url, workerService, {
                action: "stop",
                monitor_id: m.id,
                monitors_path: config.monitorsPath,
                persist: params.persist === true,
              })) as Record<string, unknown>;
              cascaded.push({
                ...stopped,
                db_row: "kept_offline",
                fallback: "stop",
                unregister_error: error,
              });
              result.degraded = true;
              result.warnings.push(
                `monitor "${m.id}": unregister failed (${error}); fell back to stop, ` +
                `monitors row kept offline` +
                (params.persist === true
                  ? stopped.monitors_yaml === "disabled"
                    ? `; monitors.yaml entry kept with enabled: false — set it back to true to re-enable`
                    : `; monitors.yaml entry unchanged` +
                      (Array.isArray(stopped.persist_warnings) && stopped.persist_warnings.length
                        ? ` (${(stopped.persist_warnings as string[]).join("; ")})`
                        : ` — set enabled: false manually or it will fail/revive on restart`)
                  : ``),
              );
            } catch (e2: any) {
              const stopError = e2?.message ?? String(e2);
              cascaded.push({ monitor_id: m.id, stopped: false, error: stopError, unregister_error: error });
              result.degraded = true;
              result.warnings.push(`monitor "${m.id}" cascade stop fallback failed: ${stopError}`);
            }
          }
        }
        (result as any).cascaded_monitors = cascaded;
      }

      return {
        content: [{ type: "text" as const, text: JSON.stringify(result, null, 2) }],
        isError: !result.ok,
      };
    } catch (err: any) {
      return { content: [{ type: "text" as const, text: `Error: ${err.message}` }], isError: true };
    }
  });

  // --- smart_community_rule_eval ---
  server.registerTool("smart_community_rule_eval", {
    description: "Manually re-run the rule evaluator against a completed task (defaults to the " +
      "monitor's latest completed task). Rebuilds the same RuleContext task-poller uses. " +
      "By default runs dry (returns shouldAlert without persisting); pass create_alert=true to " +
      "actually insert a row (cooldown honoured).",
    inputSchema: {
      monitor_id: z.string().describe("Monitor ID"),
      task_id: z.number().optional().describe(
        "Task to re-evaluate (default: latest completed for the monitor)",
      ),
      create_alert: z.boolean().optional().describe(
        "When true, insert an alert row on shouldAlert (default false — dry run)",
      ),
    },
  }, async (params) => {
    try {
      const { ruleEval } = await import("@smart-community-video/tools");
      const result = await ruleEval(
        db,
        {
          useCaseDict: config.useCaseDict,
          alertCooldownSeconds: config.alerts.cooldownSeconds,
        },
        params as any,
      );
      return { content: [{ type: "text" as const, text: JSON.stringify(result, null, 2) }] };
    } catch (err: any) {
      return { content: [{ type: "text" as const, text: `Error: ${err.message}` }], isError: true };
    }
  });

}
