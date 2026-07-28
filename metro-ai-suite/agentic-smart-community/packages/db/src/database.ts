import Database from "better-sqlite3";
import type { Monitor, Alert, AlertWithTask, Event, Recording, VideoSummaryTask, Report } from "./types.js";

function rowToAlert(row: any): Alert {
  return {
    id: row.id,
    monitorId: row.monitor_id,
    taskId: row.task_id ?? undefined,
    eventId: row.event_id ?? undefined,
    useCase: row.use_case ?? "",
    description: row.description ?? undefined,
    // Missing column (extremely old row / custom query) defaults to true so
    // legacy alerts are treated as "was notified", matching pre-audit semantics.
    notified: row.notified === undefined || row.notified === null ? true : Boolean(row.notified),
    createdAt: row.created_at,
    ackAt: row.ack_at ?? undefined,
    ackBy: row.ack_by ?? undefined,
  };
}

function rowToEvent(row: any): Event {
  return {
    id: row.id,
    monitorId: row.monitor_id,
    motionType: row.motion_type,
    startTime: row.start_time,
    endTime: row.end_time ?? undefined,
    durationSeconds: row.duration_seconds ?? undefined,
    eventFilePath: row.event_file_path ?? undefined,
    prefilterPassed: row.prefilter_passed ?? undefined,
    prefilterClasses: row.prefilter_classes ?? undefined,
    prefilterConfidence: row.prefilter_confidence ?? undefined,
    trajectoryRegion: row.trajectory_region ?? undefined,
    createdAt: row.created_at,
  };
}

function rowToRecording(row: any): Recording {
  return {
    id: row.id,
    monitorId: row.monitor_id,
    filePath: row.file_path,
    startTime: row.start_time,
    endTime: row.end_time,
    durationSeconds: row.duration_seconds ?? undefined,
    fileSizeBytes: row.file_size_bytes ?? undefined,
    createdAt: row.created_at,
  };
}

function rowToTask(row: any): VideoSummaryTask {
  return {
    id: row.id,
    monitorId: row.monitor_id,
    eventId: row.event_id ?? undefined,
    clipStartTime: row.clip_start_time ?? undefined,
    clipEndTime: row.clip_end_time ?? undefined,
    clipDuration: row.clip_duration ?? undefined,
    summaryClipInput: row.summary_clip_input ?? undefined,
    summaryText: row.summary_text ?? undefined,
    status: row.status,
    errorMessage: row.error_message ?? undefined,
    latencySeconds: row.latency_seconds ?? undefined,
    promptTokens: row.prompt_tokens ?? undefined,
    imageTokens: row.image_tokens ?? undefined,
    completionTokens: row.completion_tokens ?? undefined,
    startedAt: row.started_at ?? undefined,
    completedAt: row.completed_at ?? undefined,
    createdAt: row.created_at,
  };
}

const MIGRATIONS = `
CREATE TABLE IF NOT EXISTS monitors (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  source_url TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'offline',
  use_case TEXT NOT NULL,
  video_summary_task TEXT NOT NULL,
  created_at TEXT DEFAULT (datetime('now', 'localtime'))
);

CREATE TABLE IF NOT EXISTS events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  monitor_id TEXT NOT NULL,
  motion_type TEXT NOT NULL,
  start_time TEXT NOT NULL,
  end_time TEXT,
  duration_seconds REAL,
  event_file_path TEXT,
  prefilter_passed INTEGER,
  prefilter_classes TEXT,
  prefilter_confidence REAL,
  trajectory_region TEXT,
  created_at TEXT DEFAULT (datetime('now', 'localtime'))
);
CREATE INDEX IF NOT EXISTS idx_events_monitor_time ON events(monitor_id, start_time);

CREATE TABLE IF NOT EXISTS recordings (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  monitor_id TEXT NOT NULL,
  file_path TEXT NOT NULL,
  start_time TEXT NOT NULL,
  end_time TEXT NOT NULL,
  duration_seconds REAL,
  file_size_bytes INTEGER,
  created_at TEXT DEFAULT (datetime('now', 'localtime'))
);
CREATE INDEX IF NOT EXISTS idx_recordings_monitor_time ON recordings(monitor_id, start_time, end_time);

CREATE TABLE IF NOT EXISTS video_summary_tasks (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  monitor_id TEXT NOT NULL,
  event_id INTEGER REFERENCES events(id),
  clip_start_time TEXT,
  clip_end_time TEXT,
  clip_duration REAL,
  summary_clip_input TEXT,
  summary_text TEXT,
  status TEXT NOT NULL DEFAULT 'pending',
  error_message TEXT,
  latency_seconds REAL,
  prompt_tokens INTEGER,
  image_tokens INTEGER,
  completion_tokens INTEGER,
  started_at TEXT,
  completed_at TEXT,
  created_at TEXT DEFAULT (datetime('now', 'localtime'))
);
CREATE INDEX IF NOT EXISTS idx_vst_status ON video_summary_tasks(status);
CREATE INDEX IF NOT EXISTS idx_vst_monitor ON video_summary_tasks(monitor_id);
CREATE INDEX IF NOT EXISTS idx_vst_event ON video_summary_tasks(event_id);

CREATE TABLE IF NOT EXISTS alerts (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  monitor_id TEXT NOT NULL,
  task_id INTEGER REFERENCES video_summary_tasks(id),
  event_id INTEGER REFERENCES events(id),
  use_case TEXT NOT NULL DEFAULT '',
  description TEXT,
  notified INTEGER NOT NULL DEFAULT 1,
  created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
  ack_at TEXT,
  ack_by TEXT,
  FOREIGN KEY (monitor_id) REFERENCES monitors(id)
);
CREATE INDEX IF NOT EXISTS idx_alerts_monitor_time ON alerts(monitor_id, created_at);
CREATE INDEX IF NOT EXISTS idx_alerts_ack ON alerts(ack_at);
CREATE INDEX IF NOT EXISTS idx_alerts_task ON alerts(task_id);
CREATE INDEX IF NOT EXISTS idx_alerts_event ON alerts(event_id);

CREATE TABLE IF NOT EXISTS reports (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  monitor_id TEXT NOT NULL,
  use_case TEXT NOT NULL DEFAULT '',
  period_start TEXT NOT NULL,
  period_end TEXT NOT NULL,
  report_text TEXT,
  event_count INTEGER,
  motion_count INTEGER,
  latency_seconds REAL,
  prompt_tokens INTEGER,
  image_tokens INTEGER,
  completion_tokens INTEGER,
  status TEXT DEFAULT 'pending',
  report_type TEXT DEFAULT 'raw',
  created_at TEXT DEFAULT (datetime('now', 'localtime'))
);
CREATE INDEX IF NOT EXISTS idx_reports_monitor_period ON reports(monitor_id, period_start);

CREATE TABLE IF NOT EXISTS plans (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  monitor_id TEXT NOT NULL,
  name TEXT NOT NULL,
  plan_date TEXT,
  plan_json TEXT NOT NULL,
  active INTEGER NOT NULL DEFAULT 1,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  UNIQUE(monitor_id, name)
);
CREATE INDEX IF NOT EXISTS idx_plans_monitor ON plans(monitor_id);
`;

export class SmartBuildingDB {
  private db: Database.Database;

  constructor(dbPath: string) {
    this.db = new Database(dbPath);
    this.db.pragma("journal_mode = WAL");
    this.db.pragma("foreign_keys = ON");
  }

  initialize(): void {
    this.db.exec(MIGRATIONS);
    // Backward-compatible core-column migration. `CREATE TABLE IF NOT EXISTS`
    // never adds columns to a pre-existing table, so any core column added
    // after a DB was first created must be backfilled here. `notified` marks
    // whether an alert's user notification was pushed (false = cooled down;
    // the row is still kept for full audit). DEFAULT 1 → legacy rows count as
    // "notified", matching the old behaviour where only pushed alerts existed.
    this.ensureColumn("alerts", "notified", "INTEGER NOT NULL DEFAULT 1");
  }

  /** Idempotently add a column if it is missing (mirrors SchemaManager.addColumnIfMissing). */
  private ensureColumn(table: string, column: string, ddl: string): void {
    const cols = this.db.prepare(`PRAGMA table_info(${table})`).all() as any[];
    if (!cols.some((c) => c.name === column)) {
      this.db.exec(`ALTER TABLE ${table} ADD COLUMN ${column} ${ddl}`);
    }
  }

  close(): void {
    this.db.close();
  }

  // --- Monitors ---

  createMonitor(monitor: Omit<Monitor, "createdAt">): Monitor {
    const stmt = this.db.prepare(`
      INSERT INTO monitors (id, name, source_url, status, use_case, video_summary_task)
      VALUES (@id, @name, @sourceUrl, @status, @useCase, @videoSummaryTask)
    `);
    stmt.run({
      id: monitor.id,
      name: monitor.name,
      sourceUrl: monitor.sourceUrl,
      status: monitor.status,
      useCase: monitor.useCase,
      videoSummaryTask: monitor.videoSummaryTask,
    });
    return this.getMonitor(monitor.id)!;
  }

  getMonitor(id: string): Monitor | undefined {
    const row = this.db.prepare("SELECT * FROM monitors WHERE id = ?").get(id) as any;
    if (!row) return undefined;
    return {
      id: row.id,
      name: row.name,
      sourceUrl: row.source_url,
      status: row.status,
      useCase: row.use_case,
      videoSummaryTask: row.video_summary_task,
      createdAt: row.created_at,
    };
  }

  listMonitors(): Monitor[] {
    const rows = this.db.prepare("SELECT * FROM monitors").all() as any[];
    return rows.map((row) => ({
      id: row.id,
      name: row.name,
      sourceUrl: row.source_url,
      status: row.status,
      useCase: row.use_case,
      videoSummaryTask: row.video_summary_task,
      createdAt: row.created_at,
    }));
  }

  updateMonitorStatus(id: string, status: Monitor["status"]): void {
    this.db.prepare("UPDATE monitors SET status = ? WHERE id = ?").run(status, id);
  }

  deleteMonitor(id: string): void {
    this.db.prepare("DELETE FROM monitors WHERE id = ?").run(id);
  }

  updateMonitor(id: string, updates: {
    sourceUrl?: string;
    name?: string;
    useCase?: string;
    videoSummaryTask?: string;
    status?: Monitor["status"];
  }): void {
    const sets: string[] = [];
    const values: any[] = [];
    if (updates.sourceUrl !== undefined) { sets.push("source_url = ?"); values.push(updates.sourceUrl); }
    if (updates.name !== undefined) { sets.push("name = ?"); values.push(updates.name); }
    if (updates.useCase !== undefined) { sets.push("use_case = ?"); values.push(updates.useCase); }
    if (updates.videoSummaryTask !== undefined) { sets.push("video_summary_task = ?"); values.push(updates.videoSummaryTask); }
    if (updates.status !== undefined) { sets.push("status = ?"); values.push(updates.status); }
    if (sets.length === 0) return;
    values.push(id);
    this.db.prepare(`UPDATE monitors SET ${sets.join(", ")} WHERE id = ?`).run(...values);
  }

  listOnlineMonitors(): Monitor[] {
    return (this.db.prepare("SELECT * FROM monitors WHERE status = 'online'").all() as any[]).map((row) => ({
      id: row.id,
      name: row.name,
      sourceUrl: row.source_url,
      status: row.status,
      useCase: row.use_case,
      videoSummaryTask: row.video_summary_task,
      createdAt: row.created_at,
    }));
  }

  // --- Alerts ---

  createAlert(alert: Omit<Alert, "id" | "createdAt" | "ackAt" | "ackBy" | "notified"> & { notified?: boolean }): Alert {
    const result = this.db.prepare(`
      INSERT INTO alerts (monitor_id, task_id, event_id, use_case, description, notified)
      VALUES (@monitorId, @taskId, @eventId, @useCase, @description, @notified)
    `).run({
      monitorId: alert.monitorId,
      taskId: alert.taskId ?? null,
      eventId: alert.eventId ?? null,
      useCase: alert.useCase,
      description: alert.description ?? null,
      // Default true keeps existing callers that don't pass notified behaving
      // as before (a written alert was always a delivered one).
      notified: (alert.notified ?? true) ? 1 : 0,
    });
    return this.getAlert(result.lastInsertRowid as number)!;
  }

  getAlert(id: number): Alert | undefined {
    const row = this.db.prepare("SELECT * FROM alerts WHERE id = ?").get(id) as any;
    if (!row) return undefined;
    return rowToAlert(row);
  }

  /**
   * Return the most recent **notified** alert for a monitor + use case within
   * the last `cooldownSeconds` (SQLite-side comparison against `datetime('now',
   * 'localtime')` to match the column's default expression). Used by the
   * cooldown check — if this returns a row, the caller should suppress the new
   * alert's *notification* (the row is still written for audit). Only
   * `notified = 1` rows anchor the window, so cooled-down rows never extend it.
   */
  latestAlertWithin(
    monitorId: string,
    useCase: string,
    cooldownSeconds: number,
  ): Alert | undefined {
    const row = this.db.prepare(`
      SELECT * FROM alerts
      WHERE monitor_id = ? AND use_case = ?
        AND notified = 1
        AND created_at >= datetime('now', 'localtime', ?)
      ORDER BY created_at DESC
      LIMIT 1
    `).get(monitorId, useCase, `-${cooldownSeconds} seconds`) as any;
    if (!row) return undefined;
    return rowToAlert(row);
  }

  queryAlerts(options: { monitorId?: string; unacked?: boolean; limit?: number; sinceId?: number; notifiedOnly?: boolean }): Alert[] {
    let sql = "SELECT * FROM alerts WHERE 1=1";
    const params: any[] = [];

    if (options.monitorId) {
      sql += " AND monitor_id = ?";
      params.push(options.monitorId);
    }
    if (options.unacked) {
      sql += " AND ack_at IS NULL";
    }
    if (options.notifiedOnly) {
      // Subscription/notification path: only surface alerts that were actually
      // pushed to users, so cooled-down audit rows don't leak through the cursor.
      sql += " AND notified = 1";
    }
    if (options.sinceId !== undefined) {
      // Cursor read for MCP subscribe flow — return alerts strictly newer than the caller's cursor.
      // Paired with ORDER BY id ASC so the caller can advance its cursor to the max id it received.
      sql += " AND id > ?";
      params.push(options.sinceId);
      sql += " ORDER BY id ASC";
    } else {
      sql += " ORDER BY created_at DESC";
    }
    if (options.limit) {
      sql += " LIMIT ?";
      params.push(options.limit);
    }

    return (this.db.prepare(sql).all(...params) as any[]).map(rowToAlert);
  }

  /**
   * Highest alert.id for a monitor (or globally if monitorId omitted). Returns
   * 0 when the table has no rows. When `notifiedOnly` is set, only notified
   * alerts count — keeps the subscription cursor aligned with the notified-only
   * stream so clients don't advance past cooled-down (unseen) audit rows.
   */
  getLatestAlertId(monitorId?: string, notifiedOnly = false): number {
    const where: string[] = [];
    const params: any[] = [];
    if (monitorId) {
      where.push("monitor_id = ?");
      params.push(monitorId);
    }
    if (notifiedOnly) {
      where.push("notified = 1");
    }
    const sql = `SELECT COALESCE(MAX(id), 0) AS max_id FROM alerts${
      where.length ? ` WHERE ${where.join(" AND ")}` : ""
    }`;
    const row = this.db.prepare(sql).get(...params) as { max_id: number };
    return row.max_id;
  }

  queryAlertsWithDetails(params: {
    monitorId?: string;
    startDate?: string;
    endDate?: string;
    limit?: number;
  }): AlertWithTask[] {
    const whereClauses: string[] = [];
    const bindings: any[] = [];

    if (params.monitorId) {
      whereClauses.push("a.monitor_id = ?");
      bindings.push(params.monitorId);
    }
    if (params.startDate) {
      whereClauses.push("date(a.created_at) >= ?");
      bindings.push(params.startDate);
    }
    if (params.endDate) {
      whereClauses.push("date(a.created_at) <= ?");
      bindings.push(params.endDate);
    }

    const whereClause = whereClauses.length > 0 ? `WHERE ${whereClauses.join(" AND ")}` : "";
    const limitClause = params.limit ? `LIMIT ${params.limit}` : "";

    const query = `
      SELECT
        a.id as alert_id, a.monitor_id, a.task_id, a.event_id,
        a.use_case, a.description, a.notified,
        a.created_at, a.ack_at, a.ack_by,
        t.id as t_id, t.summary_clip_input as t_summary_clip_input,
        t.summary_text as t_summary_text, t.status as t_status,
        e.id as e_id, e.motion_type as e_motion_type,
        e.start_time as e_start_time, e.end_time as e_end_time
      FROM alerts a
      LEFT JOIN video_summary_tasks t ON a.task_id = t.id
      LEFT JOIN events e ON a.event_id = e.id
      ${whereClause}
      ORDER BY a.created_at DESC
      ${limitClause}
    `;

    return (this.db.prepare(query).all(...bindings) as any[]).map((row): AlertWithTask => ({
      ...rowToAlert({
        id: row.alert_id, monitor_id: row.monitor_id, task_id: row.task_id,
        event_id: row.event_id, use_case: row.use_case,
        description: row.description, notified: row.notified,
        created_at: row.created_at, ack_at: row.ack_at, ack_by: row.ack_by,
      }),
      taskDetails: row.t_id ? {
        id: row.t_id,
        summaryClipInput: row.t_summary_clip_input,
        summaryText: row.t_summary_text,
        status: row.t_status,
      } : undefined,
      eventDetails: row.e_id ? {
        id: row.e_id,
        motionType: row.e_motion_type,
        startTime: row.e_start_time,
        endTime: row.e_end_time,
      } : undefined,
    }));
  }

  ackAlertWithUser(alertId: number, ackBy: string): void {
    this.db.prepare(
      "UPDATE alerts SET ack_at = datetime('now', 'localtime'), ack_by = ? WHERE id = ?"
    ).run(ackBy, alertId);
  }

  getAlertStats(
    monitorId: string,
    startDate?: string,
    endDate?: string
  ): { total: number; unacked: number } {
    const whereClauses = ["monitor_id = ?"];
    const bindings: any[] = [monitorId];

    if (startDate) {
      whereClauses.push("date(created_at) >= ?");
      bindings.push(startDate);
    }
    if (endDate) {
      whereClauses.push("date(created_at) <= ?");
      bindings.push(endDate);
    }

    const row = this.db.prepare(`
      SELECT
        COUNT(*) as total,
        SUM(CASE WHEN ack_at IS NULL THEN 1 ELSE 0 END) as unacked
      FROM alerts
      WHERE ${whereClauses.join(" AND ")}
    `).get(...bindings) as any;

    return { total: row.total || 0, unacked: row.unacked || 0 };
  }

  // --- Events ---

  createEvent(event: Omit<Event, "id" | "createdAt">): Event {
    const result = this.db.prepare(`
      INSERT INTO events
        (monitor_id, motion_type, start_time, end_time, duration_seconds,
         event_file_path,
         prefilter_passed, prefilter_classes, prefilter_confidence, trajectory_region)
      VALUES (@monitorId, @motionType, @startTime, @endTime, @durationSeconds,
              @eventFilePath,
              @prefilterPassed, @prefilterClasses, @prefilterConfidence, @trajectoryRegion)
    `).run({
      monitorId: event.monitorId,
      motionType: event.motionType,
      startTime: event.startTime,
      endTime: event.endTime ?? null,
      durationSeconds: event.durationSeconds ?? null,
      eventFilePath: event.eventFilePath ?? null,
      prefilterPassed: event.prefilterPassed ?? null,
      prefilterClasses: event.prefilterClasses ?? null,
      prefilterConfidence: event.prefilterConfidence ?? null,
      trajectoryRegion: event.trajectoryRegion ?? null,
    });
    return this.getEvent(result.lastInsertRowid as number)!;
  }

  getEvent(id: number): Event | undefined {
    const row = this.db.prepare("SELECT * FROM events WHERE id = ?").get(id) as any;
    if (!row) return undefined;
    return rowToEvent(row);
  }

  getEventsByTimeRange(monitorId: string, startTime: string, endTime: string): Event[] {
    return (this.db.prepare(
      "SELECT * FROM events WHERE monitor_id = ? AND start_time >= ? AND start_time < ? ORDER BY start_time ASC"
    ).all(monitorId, startTime, endTime) as any[]).map(rowToEvent);
  }

  // --- Recordings ---

  createRecording(rec: Omit<Recording, "id" | "createdAt">): Recording {
    const result = this.db.prepare(`
      INSERT INTO recordings (monitor_id, file_path, start_time, end_time, duration_seconds, file_size_bytes)
      VALUES (@monitorId, @filePath, @startTime, @endTime, @durationSeconds, @fileSizeBytes)
    `).run({
      monitorId: rec.monitorId,
      filePath: rec.filePath,
      startTime: rec.startTime,
      endTime: rec.endTime,
      durationSeconds: rec.durationSeconds ?? null,
      fileSizeBytes: rec.fileSizeBytes ?? null,
    });
    return this.getRecording(result.lastInsertRowid as number)!;
  }

  getRecording(id: number): Recording | undefined {
    const row = this.db.prepare("SELECT * FROM recordings WHERE id = ?").get(id) as any;
    if (!row) return undefined;
    return rowToRecording(row);
  }

  listRecordings(monitorId: string, options: { since?: string; limit?: number } = {}): Recording[] {
    let sql = "SELECT * FROM recordings WHERE monitor_id = ?";
    const bindings: any[] = [monitorId];
    if (options.since) { sql += " AND start_time >= ?"; bindings.push(options.since); }
    sql += " ORDER BY start_time DESC";
    if (options.limit) { sql += " LIMIT ?"; bindings.push(options.limit); }
    return (this.db.prepare(sql).all(...bindings) as any[]).map(rowToRecording);
  }

  // --- Video Summary Tasks ---

  createTask(task: Pick<VideoSummaryTask, "monitorId" | "eventId" | "clipStartTime" | "clipEndTime" | "summaryClipInput" | "status">): VideoSummaryTask {
    const result = this.db.prepare(`
      INSERT INTO video_summary_tasks (monitor_id, event_id, clip_start_time, clip_end_time, summary_clip_input, status)
      VALUES (@monitorId, @eventId, @clipStartTime, @clipEndTime, @summaryClipInput, @status)
    `).run({
      monitorId: task.monitorId,
      eventId: task.eventId ?? null,
      clipStartTime: task.clipStartTime ?? null,
      clipEndTime: task.clipEndTime ?? null,
      summaryClipInput: task.summaryClipInput ?? null,
      status: task.status,
    });
    return this.getTask(result.lastInsertRowid as number)!;
  }

  getTask(id: number): VideoSummaryTask | undefined {
    const row = this.db.prepare("SELECT * FROM video_summary_tasks WHERE id = ?").get(id) as any;
    if (!row) return undefined;
    return rowToTask(row);
  }

  getPendingTasks(monitorId: string, limit: number = 10): VideoSummaryTask[] {
    return (this.db.prepare(
      "SELECT * FROM video_summary_tasks WHERE monitor_id = ? AND status = 'pending' ORDER BY created_at ASC LIMIT ?"
    ).all(monitorId, limit) as any[]).map(rowToTask);
  }

  /**
   * Filter `video_summary_tasks` by monitor and optional status, sorted newest
   * first. Used by tools that need to rebuild historical rule contexts
   * (e.g. `smartbuilding_rule_eval` for manual re-evaluation).
   */
  queryTasks(options: {
    monitorId: string;
    status?: VideoSummaryTask["status"];
    limit?: number;
  }): VideoSummaryTask[] {
    let sql = "SELECT * FROM video_summary_tasks WHERE monitor_id = ?";
    const params: any[] = [options.monitorId];
    if (options.status) {
      sql += " AND status = ?";
      params.push(options.status);
    }
    sql += " ORDER BY created_at DESC";
    if (options.limit) {
      sql += " LIMIT ?";
      params.push(options.limit);
    }
    return (this.db.prepare(sql).all(...params) as any[]).map(rowToTask);
  }

  updateTaskStatus(
    id: number,
    status: VideoSummaryTask["status"],
    summaryText?: string,
    meta?: { latencySeconds?: number; promptTokens?: number; imageTokens?: number; completionTokens?: number; errorMessage?: string },
    /**
     * User-defined schema extension fields (e.g. event/severity/desc) parsed from summaryText.
     * Only keys that actually exist as columns in video_summary_tasks are written;
     * unknown keys are silently dropped to avoid SQL errors when schema hasn't been applied.
     */
    extensionFields?: Record<string, string | number | null>,
  ): void {
    if (status !== "completed" && status !== "failed") {
      this.db.prepare("UPDATE video_summary_tasks SET status = ? WHERE id = ?").run(status, id);
      return;
    }

    // Base columns always updated on completion
    const sets: string[] = [
      "status = ?",
      "summary_text = ?",
      "completed_at = datetime('now', 'localtime')",
      "latency_seconds = ?",
      "prompt_tokens = ?",
      "image_tokens = ?",
      "completion_tokens = ?",
      "error_message = ?",
    ];
    const values: any[] = [
      status, summaryText ?? null,
      meta?.latencySeconds ?? null, meta?.promptTokens ?? null,
      meta?.imageTokens ?? null, meta?.completionTokens ?? null,
      meta?.errorMessage ?? null,
    ];

    // Filter extensionFields to columns that actually exist (SchemaManager may not have run yet)
    if (extensionFields && Object.keys(extensionFields).length > 0) {
      const existingCols = new Set(
        (this.db.prepare(`PRAGMA table_info(video_summary_tasks)`).all() as any[])
          .map((r) => r.name)
      );
      for (const [col, val] of Object.entries(extensionFields)) {
        if (!/^[a-zA-Z_][a-zA-Z0-9_]*$/.test(col)) continue;  // safety: SQL identifier check
        if (!existingCols.has(col)) continue;
        sets.push(`${col} = ?`);
        values.push(val ?? null);
      }
    }

    values.push(id);
    this.db.prepare(`UPDATE video_summary_tasks SET ${sets.join(", ")} WHERE id = ?`).run(...values);
  }

  // --- Stats ---

  getStats(monitorId: string): { events: number; alerts: number } {
    const today = new Date().toISOString().slice(0, 10);
    const tasks = this.db.prepare(
      "SELECT COUNT(*) as count FROM video_summary_tasks WHERE monitor_id = ? AND created_at >= ?"
    ).get(monitorId, today) as any;
    const alerts = this.db.prepare(
      "SELECT COUNT(*) as count FROM alerts WHERE monitor_id = ? AND created_at >= ?"
    ).get(monitorId, today) as any;
    return { events: tasks?.count ?? 0, alerts: alerts?.count ?? 0 };
  }

  // --- Reports ---

  insertReport(report: Omit<Report, "id" | "createdAt">): void {
    this.db.prepare(`
      INSERT INTO reports
        (monitor_id, use_case, period_start, period_end, report_type,
         report_text, event_count, motion_count, status,
         latency_seconds, prompt_tokens, image_tokens, completion_tokens)
      VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    `).run(
      report.monitorId,
      report.useCase ?? "",
      report.periodStart,
      report.periodEnd,
      report.reportType ?? "raw",
      report.reportText ?? null,
      report.eventCount ?? null,
      report.motionCount ?? null,
      report.status ?? "completed",
      report.latencySeconds ?? null,
      report.promptTokens ?? null,
      report.imageTokens ?? null,
      report.completionTokens ?? null,
    );
  }

  getReports(monitorId: string, limit: number = 10): Report[] {
    return (this.db.prepare(
      "SELECT * FROM reports WHERE monitor_id = ? ORDER BY period_start DESC, created_at DESC LIMIT ?"
    ).all(monitorId, limit) as any[]).map((row): Report => ({
      id: row.id,
      monitorId: row.monitor_id,
      useCase: row.use_case ?? "",
      periodStart: row.period_start,
      periodEnd: row.period_end,
      reportText: row.report_text ?? undefined,
      eventCount: row.event_count ?? undefined,
      motionCount: row.motion_count ?? undefined,
      latencySeconds: row.latency_seconds ?? undefined,
      promptTokens: row.prompt_tokens ?? undefined,
      imageTokens: row.image_tokens ?? undefined,
      completionTokens: row.completion_tokens ?? undefined,
      status: row.status,
      reportType: row.report_type,
      createdAt: row.created_at,
    }));
  }

  // --- Plans ---

  listPlans(monitorId: string, activeOnly: boolean = true): Record<string, unknown>[] {
    const sql = activeOnly
      ? "SELECT * FROM plans WHERE monitor_id = ? AND active = 1 ORDER BY name ASC"
      : "SELECT * FROM plans WHERE monitor_id = ? ORDER BY name ASC";
    const rows = this.db.prepare(sql).all(monitorId) as any[];
    return rows.map((r) => ({
      id: r.id,
      monitorId: r.monitor_id,
      name: r.name,
      planDate: r.plan_date ?? undefined,
      plan: JSON.parse(r.plan_json),
      active: Boolean(r.active),
      createdAt: r.created_at,
    }));
  }

  upsertPlan(monitorId: string, name: string, plan: Record<string, unknown>, planDate?: string): void {
    this.db.prepare(`
      INSERT INTO plans (monitor_id, name, plan_date, plan_json)
      VALUES (?, ?, ?, ?)
      ON CONFLICT(monitor_id, name) DO UPDATE SET
        plan_json = excluded.plan_json,
        plan_date = excluded.plan_date,
        active = 1
    `).run(monitorId, name, planDate ?? null, JSON.stringify(plan));
  }

  deletePlanByName(monitorId: string, name: string): void {
    this.db.prepare("UPDATE plans SET active = 0 WHERE monitor_id = ? AND name = ?").run(monitorId, name);
  }

  // --- Raw query ---

  rawQuery(sql: string, params: unknown[] = []): unknown[] {
    const stmt = this.db.prepare(sql);
    if (sql.trim().toUpperCase().startsWith("SELECT")) {
      return stmt.all(...params);
    }
    const result = stmt.run(...params);
    return [{ changes: result.changes, lastInsertRowid: result.lastInsertRowid }];
  }
}

