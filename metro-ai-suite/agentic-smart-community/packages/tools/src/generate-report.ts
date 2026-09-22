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
  /** Context window of the LLM behind the summary service (its --max-model-len). */
  modelContext?: number;
  /** The service's DEFAULT_MAX_TOKENS — the output bandwidth of one rung. */
  maxOutputTokens?: number;
  /** Compression one call may be asked to do; sets the level-1 group size. */
  maxHopRatio?: number;
  /** Whole-report budget. One value: a period's cost is not knowable per-clip. */
  timeoutSeconds?: number;
}

const DEFAULT_MODEL_CONTEXT = 32768;
const DEFAULT_MAX_OUTPUT_TOKENS = 512;
const DEFAULT_TIMEOUT_SECONDS = 3600;

/** `Start time: N sec\nEnd time: M sec`, prepended to every sub-summary. */
const SUMMARY_HEADER_TOKENS = 24;
/** Task + system prompt wrapped around every call. */
const PROMPT_OVERHEAD_TOKENS = 800;
/** The root prompt carries extra instructions on top of a macro one. */
const GLOBAL_PROMPT_EXTRA_TOKENS = 2000;
/** Slack — estimateTokens is an approximation, not the model's tokenizer. */
const SAFETY_TOKENS = 2000;
/**
 * Compression a single call is trusted to do well. Past roughly this ratio a
 * summarizer stops condensing and starts dropping whole stretches of timeline,
 * which is what an extra level exists to prevent. The one empirical number here,
 * and the direct dial on group size: `group = ratio · out / perCue`.
 */
const DEFAULT_MAX_HOP_RATIO = 15;
/** Refuse to build a taller tree than this; each rung is a lossy re-summarization. */
const MAX_LEVELS = 5;

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

/**
 * Tokens the model will actually read. The service parses the index and
 * `HH:MM:SS,mmm --> HH:MM:SS,mmm` lines into chunk metadata and joins only the cue
 * text, so counting the raw file over-states a cue by ~20%.
 */
function estimateCueTokens(srtText: string): number {
  let total = 0;
  for (const block of srtText.split(/\n\s*\n/)) {
    const lines = block.split("\n");
    const arrow = lines.findIndex((line) => line.includes(" --> "));
    if (arrow >= 0) total += estimateTokens(lines.slice(arrow + 1).join("\n").trim());
  }
  return total || estimateTokens(srtText);
}

/**
 * Size the level plan for this particular timeline.
 *
 * Every rung emits at most `maxOutputTokens`, so the hierarchy is a stack of
 * fixed-bandwidth funnels: what matters is how hard each hop has to compress, not
 * whether the input fits. A hop's ratio is `input / out`, and the two hops measure
 * their input differently — level 1 reads real cue text, which we can measure;
 * every level above reads sub-summaries, whose length is unknown until the model
 * writes them, so those are budgeted at the cap.
 *
 * Level 1 then takes as many cues as that ratio limit and the context allow. There
 * is nothing to trade off: a wider group means fewer chunks, which *also* lowers
 * the ratio of every rung above it. So saturate level 1 and roll up only as far as
 * the root actually needs.
 */
export function planLevels(
  srtText: string,
  numEvents: number,
  options: { modelContext?: number; maxOutputTokens?: number; maxHopRatio?: number } = {}
): { levels: number; levelSizes: number[] } {
  const modelContext = options.modelContext ?? DEFAULT_MODEL_CONTEXT;
  const out = options.maxOutputTokens ?? DEFAULT_MAX_OUTPUT_TOKENS;
  if (numEvents <= 0) return { levels: 2, levelSizes: [1, -1] };

  const perCue = Math.max(1, estimateCueTokens(srtText) / numEvents);
  const perSummary = out + SUMMARY_HEADER_TOKENS;
  const hopBudget = (options.maxHopRatio ?? DEFAULT_MAX_HOP_RATIO) * out;
  const chunkBudget = Math.max(perSummary, modelContext - PROMPT_OVERHEAD_TOKENS - out - SAFETY_TOKENS);
  const rootBudget = Math.max(perSummary, chunkBudget - GLOBAL_PROMPT_EXTRA_TOKENS);

  // One call for the whole timeline, when that is not already a violent squeeze.
  if (numEvents * perCue <= Math.min(rootBudget, hopBudget)) return { levels: 2, levelSizes: [1, -1] };

  const group = Math.max(1, Math.min(numEvents, Math.floor(hopBudget / perCue), Math.floor(chunkBudget / perCue)));
  const sizes = [1, group];
  let remaining = Math.ceil(numEvents / group);

  const rollup = Math.max(2, Math.min(Math.floor(hopBudget / perSummary), Math.floor(chunkBudget / perSummary)));
  const rootMax = Math.max(1, Math.min(Math.floor(hopBudget / perSummary), Math.floor(rootBudget / perSummary)));
  while (remaining > rootMax && sizes.length < MAX_LEVELS - 1) {
    sizes.push(rollup);
    remaining = Math.ceil(remaining / rollup);
  }
  sizes.push(-1);
  return { levels: sizes.length, levelSizes: sizes };
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
  const { levels, levelSizes } = planLevels(srtText, rows.length, {
    modelContext: reportConfig.modelContext,
    maxOutputTokens: reportConfig.maxOutputTokens,
    maxHopRatio: reportConfig.maxHopRatio,
  });
  const timeoutMs = (reportConfig.timeoutSeconds ?? DEFAULT_TIMEOUT_SECONDS) * 1000;
  const t0 = Date.now();
  let summary: string | null = null;
  let usage: { prompt_tokens?: number; completion_tokens?: number } | undefined;
  let error: string | undefined;
  try {
    const resp = await reportConfig.summaryClient.summarizeSubtitles({
      srtText,
      task: summaryTaskName,
      processor_kwargs: { levels, level_sizes: levelSizes },
      timeoutMs,
    });
    summary = resp.summary;
    usage = resp.usage;
    if (!summary) error = "empty summary from service";
  } catch (err: any) {
    // A bare "aborted due to timeout" gives an operator nothing to act on.
    error = err?.name === "TimeoutError" || /aborted due to timeout/i.test(err?.message ?? "")
      ? `timed out after ${timeoutMs / 1000}s (${rows.length} rows, level_sizes=[${levelSizes}])`
      : err.message;
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
    plan: { levels, levelSizes },
    ...(error ? { error } : {}),
  };
}
