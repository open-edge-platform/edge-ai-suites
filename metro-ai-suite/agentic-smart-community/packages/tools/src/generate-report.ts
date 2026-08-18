import type { SmartCommunityDB } from "@smart-community-video/db";
import type { VideoSummaryClient } from "./clients/video-summary-client.js";

export interface GenerateReportParams {
  monitor_id: string;
  type?: "daily" | "weekly" | "monthly" | "custom";
  // custom type: YYYY-MM-DD or YYYY-MM-DD HH:MM — closed interval on both ends
  period_start?: string;
  period_end?: string;
}

export interface ReportConfig {
  dataSource: "events" | "alerts" | "video_summary_tasks";
  defaultType: "daily" | "weekly" | "monthly";
  /** Shared client to multilevel-video-understanding (caption-only mode here). */
  summaryClient: VideoSummaryClient;
  filter?: Record<string, any>;
  debugDir?: string; // when set, persist SRT artifacts here
}

// ---------------------------------------------------------------------------
// Time range helpers
// ---------------------------------------------------------------------------

/** Local calendar date as YYYY-MM-DD (not UTC — reports are about the local day). */
function localYmd(d: Date): string {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

function calcPeriod(
  type: string,
  period_start?: string,
  period_end?: string
): { periodStart: string; periodEnd: string } {
  if (type === "custom") {
    if (!period_start || !period_end) {
      throw new Error("period_start and period_end are required for custom report type");
    }
    return { periodStart: period_start, periodEnd: period_end };
  }
  // Bounds are local-time, space-separated (`YYYY-MM-DD HH:MM:SS`) to match the
  // canonical format stored in start_time / created_at. A `T`-separated or UTC
  // bound would mis-sort against space-separated column values in SQLite's
  // lexicographic string comparison and silently drop same-day rows.
  const now = new Date();
  const todayEnd = localYmd(now) + " 23:59:59";
  if (type === "daily") return { periodStart: localYmd(now) + " 00:00:00", periodEnd: todayEnd };
  if (type === "weekly") {
    const d = new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000);
    return { periodStart: localYmd(d) + " 00:00:00", periodEnd: todayEnd };
  }
  if (type === "monthly") {
    const d = new Date(now.getTime() - 30 * 24 * 60 * 60 * 1000);
    return { periodStart: localYmd(d) + " 00:00:00", periodEnd: todayEnd };
  }
  throw new Error(`Unknown report type: ${type}`);
}

// ---------------------------------------------------------------------------
// SRT builders (caption-only mode — no video, text timeline only)
// ---------------------------------------------------------------------------

function formatSrtTs(iso: string): string {
  const d = new Date(iso);
  const hh = String(d.getHours()).padStart(2, "0");
  const mm = String(d.getMinutes()).padStart(2, "0");
  const ss = String(d.getSeconds()).padStart(2, "0");
  const ms = String(d.getMilliseconds()).padStart(3, "0");
  return `${hh}:${mm}:${ss},${ms}`;
}

/**
 * Wall-clock `HH:MM:SS` (local) for embedding INTO each cue's text line.
 *
 * multilevel-video-understanding parses the SRT `-->` timestamps as video
 * playback offsets and strips them — only the cue *text* reaches the summarizer.
 * Our cue times are real wall-clock event times, so we inline them in the text
 * (the one channel the model sees) or the model has no temporal grounding and
 * fabricates "activity periods". Returns "" for unparseable input.
 */
function clockLabel(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  const p = (n: number) => String(n).padStart(2, "0");
  return `${p(d.getHours())}:${p(d.getMinutes())}:${p(d.getSeconds())}`;
}

function buildAlertsSrt(rows: any[]): string {
  if (rows.length === 0) return "";
  return rows
    .map((row, idx) => {
      const startTs = formatSrtTs(row.created_at ?? new Date().toISOString());
      const endTs = formatSrtTs(
        new Date(new Date(row.created_at).getTime() + 1000).toISOString()
      );
      const tag = `[alert:${row.severity ?? "info"}:${row.event ?? row.alert_type ?? "event"}]`;
      const clock = clockLabel(row.created_at);
      const desc = (row.description ?? row.desc ?? "").trim() || "(no description)";
      return `${idx + 1}\n${startTs} --> ${endTs}\n${tag} ${clock ? clock + " " : ""}${desc}\n`;
    })
    .join("\n");
}

function buildEventsSrt(rows: any[]): string {
  if (rows.length === 0) return "";
  return rows
    .map((row, idx) => {
      const startTs = formatSrtTs(row.start_time ?? row.created_at ?? new Date().toISOString());
      const endTime = row.end_time ?? row.start_time ?? new Date().toISOString();
      const endTs = formatSrtTs(endTime);
      const tag = `[${row.motion_type ?? row.event_type ?? "event"}]`;
      const clock = clockLabel(row.start_time ?? row.created_at);
      const desc = (row.summary ?? row.description ?? row.desc ?? "").trim() || "(no description)";
      return `${idx + 1}\n${startTs} --> ${endTs}\n${tag} ${clock ? clock + " " : ""}${desc}\n`;
    })
    .join("\n");
}

function buildTasksSrt(rows: any[]): string {
  if (rows.length === 0) return "";
  return rows
    .map((row, idx) => {
      const startTs = formatSrtTs(row.created_at ?? new Date().toISOString());
      const endTs = formatSrtTs(
        row.completed_at ?? new Date(new Date(row.created_at).getTime() + 60000).toISOString()
      );
      const event = row.event ?? "task";
      const severity = row.severity ?? "info";
      const tag = `[task:${event}:${severity}]`;
      const clock = clockLabel(row.created_at);
      const desc = (row.summary_text ?? row.desc ?? "").trim() || "(no summary)";
      return `${idx + 1}\n${startTs} --> ${endTs}\n${tag} ${clock ? clock + " " : ""}${desc}\n`;
    })
    .join("\n");
}

// ---------------------------------------------------------------------------
// Token estimation & level planning
// ---------------------------------------------------------------------------

function estimateTokens(text: string): number {
  let cjk = 0;
  for (const c of text) {
    const cp = c.codePointAt(0)!;
    if (cp >= 0x4e00 && cp <= 0x9fff) cjk++;
  }
  return Math.floor((cjk / 1.5 + (text.length - cjk) / 4) * 1.3);
}

function planLevels(
  srtText: string,
  numEvents: number,
  modelContext = 32768
): { levels: number; levelSizes: number[] } {
  const safeBudget = modelContext - 800 - 2000 - 2000; // overhead + output + safety
  if (numEvents <= 0) return { levels: 2, levelSizes: [1, -1] };
  const avgTokens = Math.max(100, estimateTokens(srtText) / numEvents) + 5;
  const maxGroup = Math.min(Math.floor(safeBudget / avgTokens), 30);
  if (numEvents <= 15) return { levels: 2, levelSizes: [1, -1] };
  const macroSize = Math.min(5, maxGroup);
  const numMacro = Math.ceil(numEvents / macroSize);
  const globalInput = numMacro * 605;
  if (globalInput <= modelContext - 800 - 4000 - 2000) {
    return { levels: 3, levelSizes: [1, macroSize, -1] };
  }
  const l2Size = Math.min(Math.floor((modelContext - 6800) / 605), numMacro);
  return { levels: 4, levelSizes: [1, macroSize, l2Size, -1] };
}

// ---------------------------------------------------------------------------
// Data query helpers
// ---------------------------------------------------------------------------

function queryData(
  db: SmartCommunityDB,
  dataSource: "events" | "alerts" | "video_summary_tasks",
  monitorId: string,
  periodStart: string,
  periodEnd: string,
  filter: Record<string, any>
): any[] {
  const table = dataSource === "events" ? "events"
    : dataSource === "alerts" ? "alerts"
    : "video_summary_tasks";

  const timeCol = dataSource === "events" ? "start_time" : "created_at";
  const idCol = dataSource === "video_summary_tasks" ? "monitor_id" : "monitor_id";

  const whereClauses = [
    `${idCol} = ?`,
    `${timeCol} >= ?`,
    `${timeCol} <= ?`,
  ];
  const bindings: any[] = [monitorId, periodStart, periodEnd];

  // Reports over `alerts` reflect what was actually pushed to users: default to
  // notified=1 so cooled-down audit rows don't inflate counts. Callers can
  // override by putting `notified` explicitly in the report filter (e.g. an
  // audit report using `filter: { notified: 0 }` or listing both).
  if (dataSource === "alerts" && !("notified" in filter)) {
    whereClauses.push("notified = ?");
    bindings.push(1);
  }

  for (const [key, value] of Object.entries(filter)) {
    if (!/^[a-zA-Z_][a-zA-Z0-9_]*$/.test(key)) {
      throw new Error(`Invalid filter key: "${key}" — only letters, digits and underscores allowed`);
    }
    whereClauses.push(`${key} = ?`);
    bindings.push(value);
  }

  const orderCol = dataSource === "events" ? "start_time" : "created_at";

  // `events` rows carry no description — the VLM narration for each detection lives
  // in the linked video_summary_tasks.summary_text. Pull the latest non-null summary
  // per event (correlated subquery, so no row multiplication) and expose it as
  // `summary`, which buildEventsSrt reads; otherwise every cue is "(no description)"
  // and the summarizer sees an empty timeline. Other data sources are unaffected.
  const selectClause =
    dataSource === "events"
      ? `*, (SELECT vst.summary_text FROM video_summary_tasks vst ` +
        `WHERE vst.event_id = events.id AND vst.summary_text IS NOT NULL ` +
        `ORDER BY vst.id DESC LIMIT 1) AS summary`
      : "*";

  const sql = `SELECT ${selectClause} FROM ${table} WHERE ${whereClauses.join(" AND ")} ORDER BY ${orderCol} ASC`;
  return db.rawQuery(sql, bindings) as any[];
}

// ---------------------------------------------------------------------------
// Main export
// ---------------------------------------------------------------------------

/**
 * Generate a report for a monitor using configuration-driven data source selection.
 * Builds an SRT timeline from DB data, sends it to multilevel-video-understanding
 * (caption-only mode), writes the result to the reports table, and returns the
 * generated report text.
 */
export async function generateReport(
  db: SmartCommunityDB,
  reportConfig: ReportConfig,
  params: GenerateReportParams
): Promise<unknown> {
  const type = params.type ?? reportConfig.defaultType;
  const { periodStart, periodEnd } = calcPeriod(type, params.period_start, params.period_end);
  const filter = reportConfig.filter && typeof reportConfig.filter === "object" && !Array.isArray(reportConfig.filter)
    ? reportConfig.filter
    : {};
  const dataSource = reportConfig.dataSource;

  const monitor = db.getMonitor(params.monitor_id);
  if (!monitor) {
    throw new Error(`Monitor not found: ${params.monitor_id}`);
  }
  const summaryTaskName = monitor.videoSummaryTask;

  // 1. Query data
  const rows = queryData(db, dataSource, params.monitor_id, periodStart, periodEnd, filter);

  if (rows.length === 0) {
    return {
      periodStart,
      periodEnd,
      type,
      dataSource,
      eventCount: 0,
      reportText: null,
      message: `No ${dataSource} found for ${params.monitor_id} between ${periodStart} and ${periodEnd}.`,
    };
  }

  // 2. Build SRT timeline
  let srtText: string;
  if (dataSource === "alerts") srtText = buildAlertsSrt(rows);
  else if (dataSource === "events") srtText = buildEventsSrt(rows);
  else srtText = buildTasksSrt(rows);

  // 3. Optionally persist SRT for debug
  if (reportConfig.debugDir && srtText) {
    const { default: fs } = await import("node:fs");
    const { default: path } = await import("node:path");
    const ts = new Date().toISOString().replace(/[:.]/g, "-").slice(0, 19);
    const stem = `${params.monitor_id}_${type}_${periodStart}_${periodEnd}_${ts}`;
    try {
      fs.mkdirSync(reportConfig.debugDir, { recursive: true });
      fs.writeFileSync(path.join(reportConfig.debugDir, `${stem}.srt.txt`), srtText);
    } catch {
      // non-fatal
    }
  }

  // 4. Call multilevel-video-understanding caption-only
  const { levels, levelSizes } = planLevels(srtText, rows.length);
  const t0 = Date.now();
  let summary: string | null = null;
  let usage: { prompt_tokens?: number; completion_tokens?: number } | undefined;
  let error: string | undefined;
  try {
    const resp = await reportConfig.summaryClient.summarizeSubtitles({
      srtText,
      task: summaryTaskName,
      processor_kwargs: { levels, level_sizes: levelSizes },
    });
    summary = resp.summary;
    usage = resp.usage;
    if (!summary) error = "empty summary from service";
  } catch (err: any) {
    error = err.message;
  }
  const latency = (Date.now() - t0) / 1000;

  // 5. Persist to reports table
  db.insertReport({
    monitorId: params.monitor_id,
    useCase: "",
    periodStart,
    periodEnd,
    reportType: "raw",
    reportText: summary ?? error ?? undefined,
    eventCount: rows.length,
    status: summary ? "completed" : "failed",
    latencySeconds: latency,
    promptTokens: usage?.prompt_tokens,
    completionTokens: usage?.completion_tokens,
  });

  return {
    periodStart,
    periodEnd,
    type,
    dataSource,
    eventCount: rows.length,
    reportText: summary,
    latencySeconds: latency,
    ...(error ? { error } : {}),
  };
}
