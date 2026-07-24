import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { z } from "zod";
import { dirname, resolve } from "node:path";
import type { ServerConfig } from "./config.js";
import type { SmartBuildingDB } from "@smartbuilding-video/db";
import type { VideoSummaryClient } from "@smartbuilding-video/tools";
import type { WorkerService } from "./video-worker/index.js";

export function registerTools(
  server: McpServer,
  config: ServerConfig,
  db: SmartBuildingDB,
  workerService: WorkerService,
  summaryClient: VideoSummaryClient,
): void {
  // --- smartbuilding_alert_query ---
  server.registerTool("smartbuilding_alert_query", {
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
      const { alertQuery } = await import("@smartbuilding-video/tools");
      const result = await alertQuery(db, params as any);
      return { content: [{ type: "text" as const, text: JSON.stringify(result, null, 2) }] };
    } catch (err: any) {
      return { content: [{ type: "text" as const, text: `Error: ${err.message}` }], isError: true };
    }
  });

  // --- smartbuilding_plan_ctl ---
  server.registerTool("smartbuilding_plan_ctl", {
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
      const { planCtl } = await import("@smartbuilding-video/tools");
      const result = planCtl(db, params as any);
      return { content: [{ type: "text" as const, text: JSON.stringify(result, null, 2) }] };
    } catch (err: any) {
      return { content: [{ type: "text" as const, text: `Error: ${err.message}` }], isError: true };
    }
  });

  // --- smartbuilding_scene_query ---
  server.registerTool("smartbuilding_scene_query", {
    description: "Real-time scene analysis: reads latest.jpg from $SMARTBUILDING_DATA_DIR/segments/<monitor_id>/ and queries VLM (vllm-serving-ipex)",
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
      const { sceneQuery } = await import("@smartbuilding-video/tools");
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

  // --- smartbuilding_generate_report ---
  server.registerTool("smartbuilding_generate_report", {
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
      const { generateReport } = await import("@smartbuilding-video/tools");

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
      const result = await generateReport(db, reportConfig, {
        monitor_id: params.monitor_id,
        type: params.type,
        period_start: params.period_start,
        period_end: params.period_end,
      });
      return { content: [{ type: "text" as const, text: JSON.stringify(result, null, 2) }] };
    } catch (err: any) {
      return { content: [{ type: "text" as const, text: `Error: ${err.message}` }], isError: true };
    }
  });

  // --- smartbuilding_monitor_ctl ---
  server.registerTool("smartbuilding_monitor_ctl", {
    description: "Manage monitor lifecycle: register_source | unregister | start | stop | status | list. " +
      "For register_source, use_case must be a key in config.yaml's use_case_dict; the tool runs " +
      "smartbuilding_use_case_validate as a pre-check (rejecting if missing fields or summary service issues).",
    inputSchema: {
      action: z.enum(["start", "stop", "register_source", "unregister", "status", "list"])
        .describe("Control action"),
      monitor_id: z.string().optional().describe("Monitor ID (required for all except list)"),
      source_url: z.string().optional().describe("Source URL — any protocol videostream-analytics supports (for register_source)"),
      name: z.string().optional().describe("Display name (for register_source)"),
      use_case: z.string().optional().describe("Use case key from config.yaml use_case_dict (required for register_source)"),
      pipeline_config: z.record(z.unknown()).optional().describe("Pipeline config object (for register_source)"),
      webhook_url: z.string().optional().describe("Events webhook URL (default: derived from config eventsWebhook.port)"),
      persist: z.boolean().optional().describe(
        "register_source/unregister only: mirror the change back to the monitors.yaml the server " +
        "was booted from (--monitors), comment-preserving. Lets a restart auto-recover this monitor " +
        "(incl. pipeline_config, which is not stored in the DB). Skipped with a warning if the server " +
        "was started without --monitors.",
      ),
    },
  }, async (params) => {
    try {
      // For register_source: validate use case via use_case_validate (existence + summary service + schema)
      let videoSummaryTask: string | undefined;
      if (params.action === "register_source") {
        if (!params.use_case) throw new Error("use_case is required for register_source");
        const { useCaseValidate } = await import("@smartbuilding-video/tools");
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

      const { monitorCtl } = await import("@smartbuilding-video/tools");
      const { join } = await import("node:path");
      // Inject derived fields the tool layer can compute from server config:
      // - data_dir: per-monitor segment root for analytics to write into
      // - webhook_url: this server's /events endpoint (caller may override)
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
        enriched.webhook_url ??= `http://localhost:${config.eventsWebhook!.port}/events`;
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

  // --- smartbuilding_monitors_compose ---
  server.registerTool("smartbuilding_monitors_compose", {
    description: "Docker-compose-style management of monitors declared in a monitors.yaml file. Actions: validate | up | down | restart | ps",
    inputSchema: {
      action: z.enum(["validate", "up", "down", "restart", "ps"]).describe("Compose action"),
      file: z.string().describe("Path to monitors.yaml (absolute or relative to cwd)"),
      monitor_id: z.string().optional().describe("Apply to only this monitor (default: all in file)"),
    },
  }, async (params) => {
    try {
      const { loadMonitorsFromYaml, validateMonitors } = await import("@smartbuilding-video/tools");
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

  // --- smartbuilding_video_db ---
  server.registerTool("smartbuilding_video_db", {
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

  // --- smartbuilding_use_case_validate ---
  server.registerTool("smartbuilding_use_case_validate", {
    description: "Validate a use_case end-to-end: (1) exists in config.yaml use_case_dict, " +
      "(2) its video_summary_task is registered in multilevel-video-understanding, " +
      "(3) the task's LOCAL_PROMPT covers every required schema field. " +
      "Used as a pre-check inside monitor_ctl register_source; also callable standalone for dry-run.",
    inputSchema: {
      use_case: z.string().describe("Use case key from config.yaml use_case_dict"),
    },
  }, async (params) => {
    try {
      const { useCaseValidate } = await import("@smartbuilding-video/tools");
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

  // --- smartbuilding_use_case_register ---
  server.registerTool("smartbuilding_use_case_register", {
    description:
      "Manage use_case lifecycle at runtime without restarting the MCP server. Three actions. " +
      "For NEW use cases, do not call this tool until the user has answered the " +
      "video-summary-prompt-studio Q1/Q2 flow and confirmed Final Schema + Rule Path; " +
      "detection goals are event values, not schema fields. " +
      "RECOMMENDED two-step flow for a new use case (keeps the large prompt_text in ONE call): " +
      "(step 1) action=register_task with prompt_text (+ evaluate_rules_text on the custom path) — " +
      "runs the consistency gate, POSTs the VLM task to multilevel-video-understanding (auto-PATCH " +
      "on 409), and ON SUCCESS writes use-cases/<use_case>/prompt.md (+ evaluate_rules.py) to disk. " +
      "It does NOT touch the DB schema, use_case_dict, or config.yaml. " +
      "(step 2) action=register WITHOUT prompt_text — auto-reads the files step 1 wrote, applies " +
      "the schema via ALTER TABLE, injects use_case_dict, and (persist=true) writes config.yaml. " +
      "schema_extensions is OPTIONAL in both steps: when omitted, the final schema is inferred from " +
      "the prompt's LOCAL_PROMPT `KEY:` output lines (all text columns); pass it only to declare a " +
      "non-text column type or override the inferred required flags. " +
      "action=register: treats schema_extensions as caller-confirmed extra fields and normalizes " +
      "the final schema to severity/event/desc + extras before validation. HARD GATE first — if any final schema field is absent from " +
      "the prompt's LOCAL_PROMPT output contract, the call is REJECTED with zero side effects " +
      "(the normalized final schema and the prompt output fields must be the same set; the prompt is the " +
      "source of truth). On pass: (1) apply schema_extensions via ALTER TABLE (idempotent), " +
      "(2) POST /v1/tasks to multilevel-video-understanding (auto-PATCH on 409), " +
      "(3) inject the entry into in-memory use_case_dict so task-poller / other tools see it, " +
      "(4) re-run use_case_validate. prompt_text may be omitted; it is then auto-read from " +
      "use-cases/<use_case>/prompt.md (e.g. the file register_task wrote). When persist=true, also " +
      "writes the entry back to config.yaml (comment-preserving via yaml.Document). " +
      "action=register_task: VLM-task registration + prompt.md/evaluate_rules.py persistence only " +
      "(step 1 above); prompt_text is REQUIRED and is never auto-read. " +
      "action=unregister: DELETE /v1/tasks/<name> and remove " +
      "from use_case_dict; also deletes the yaml entry if persist=true. When persist=true, " +
      "unregister additionally CASCADES to every monitor referencing this use case: stops its " +
      "worker, deletes its videostream-analytics source, and strips it from monitors.yaml — DB " +
      "history (alerts/tasks/events/recordings) is kept and the monitor row is left offline. " +
      "For action=register, if prompt_text is provided with persist=true it is saved to " +
      "use-cases/<use_case>/prompt.md; if evaluate_rules_text is provided with persist=true it is " +
      "saved to use-cases/<use_case>/evaluate_rules.py.",
    inputSchema: {
      action: z.enum(["register", "register_task", "unregister"]).describe("register | register_task | unregister"),
      use_case: z.string().describe("Use case key (lowercase ascii, matches /^[a-z][a-z0-9_]{1,63}$/)"),
      video_summary_task: z.string().optional().describe(
        "VLM task name (default: <use_case>_monitor). Must not collide with VLM builtins."
      ),
      description: z.string().optional().describe("Human description shown by /v1/tasks"),
      evaluate_rules_path: z.string().optional().describe(
        "Path to Python evaluate_rules.py override (absolute or relative to cwd of MCP server)"
      ),
      reports: z.record(z.unknown()).optional().describe("Report config: {data_source, default_type, filter}"),
      summarize: z.record(z.unknown()).optional().describe("Per-clip summarize config: {method, processor_kwargs}"),
      prompt_text: z.string().optional().describe(
        "Full prompt text (Markdown with ## LOCAL_PROMPT sections, OR a raw 4-const Python source). " +
        "REQUIRED for action=register_task (it is POSTed to the VLM task and written to " +
        "use-cases/<use_case>/prompt.md). For action=register it is OPTIONAL: when omitted it is " +
        "auto-read from use-cases/<use_case>/prompt.md (e.g. the file register_task wrote); when " +
        "provided with persist=true it is (re)saved there. " +
        "Do not include Markdown code fences, because the video-summary service rejects reserved tokens."
      ),
      evaluate_rules_text: z.string().optional().describe(
        "Optional Python evaluate_rules.py source. When persist=true, this is saved to " +
        "use-cases/<use_case>/evaluate_rules.py and used as evaluate_rules_path unless an explicit path is provided."
      ),
      schema_extensions: z.array(z.object({
        name: z.string(),
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
        "Applied via ALTER TABLE ADD COLUMN if missing (idempotent). Stored under this use_case's own " +
        "schema (use_case_dict.<uc>.schema) — never a global shared schema."
      ),
      overwrite: z.boolean().optional().describe(
        "When true, replace an existing use_case entry. Default false."
      ),
      persist: z.boolean().optional().describe(
        "When true, mirror the mutation to the config.yaml the server was booted from " +
        "(comment-preserving via yaml.Document). Requires MCP server to have been started " +
        "with --config <path>. Failure to write only produces a warning; in-memory " +
        "registration still stands."
      ),
    },
  }, async (params) => {
    try {
      const { useCaseRegister, detachMonitor } = await import("@smartbuilding-video/tools");
      const result = await useCaseRegister(params as any, {
        useCaseDict: config.useCaseDict,
        summaryServiceUrl: config.summaryService.url,
        db: (db as any).db,
        configPath: config.configPath,
        baseDir: config.configPath ? dirname(resolve(config.configPath)) : process.cwd(),
      });

      // Cascade on unregister+persist: detach every monitor referencing this use
      // case (stop worker + delete VSA source + strip from monitors.yaml), keeping
      // DB history. Mirrors register_source persist which writes monitors.yaml —
      // without this, unregistering a use case would leave orphan monitors whose
      // use_case no longer exists (task-poller then errors on the next poll).
      if (params.action === "unregister" && params.persist && result.ok) {
        const affected = db.listMonitors().filter((m) => m.useCase === params.use_case);
        const cascaded: unknown[] = [];
        for (const m of affected) {
          try {
            cascaded.push(
              await detachMonitor(db, config.videostreamAnalytics.url, workerService, {
                monitor_id: m.id,
                monitors_path: config.monitorsPath,
                persist: true,
              }),
            );
          } catch (e: any) {
            cascaded.push({ monitor_id: m.id, detached: false, error: e?.message ?? String(e) });
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

  // --- smartbuilding_rule_eval ---
  server.registerTool("smartbuilding_rule_eval", {
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
      const { ruleEval } = await import("@smartbuilding-video/tools");
      const result = await ruleEval(
        db,
        {
          useCaseDict: config.useCaseDict,
        },
        params as any,
      );
      return { content: [{ type: "text" as const, text: JSON.stringify(result, null, 2) }] };
    } catch (err: any) {
      return { content: [{ type: "text" as const, text: `Error: ${err.message}` }], isError: true };
    }
  });

}
