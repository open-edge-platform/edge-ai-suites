// SPDX-FileCopyrightText: (C) 2026 Intel Corporation
// SPDX-License-Identifier: Apache-2.0

import { Router, type Request, type Response } from "express";
import { z } from "zod";
import type { SmartCommunityDB } from "@smart-community-video/db";
import { generateReport, type VideoSummaryClient } from "@smart-community-video/tools";
import type { ServerConfig } from "../config.js";
import { loadDashboardIntegrationConfig } from "./integration-env.js";
import { LiveStreamManager } from "./live-stream.js";
import { resolveMonitorMp4, sendMp4, sendSnapshot } from "./media.js";
import { sendRecording } from "./recording-stream.js";
import type { ChatCredentialStore } from "./chat-credentials.js";

const monitorIdSchema = z.string().regex(/^[A-Za-z0-9_-]{1,128}$/);
const dateSchema = z.string().regex(/^\d{4}-\d{2}-\d{2}$/);
const taskQuerySchema = z.object({
  monitor_id: monitorIdSchema,
  date: dateSchema,
  limit: z.coerce.number().int().min(1).max(500).default(100),
});
const reportBodySchema = z.object({
  monitor_id: monitorIdSchema,
  type: z.enum(["daily", "weekly", "monthly", "custom"]).optional(),
  period_start: z.string().max(32).optional(),
  period_end: z.string().max(32).optional(),
});

function dateRange(date: string): { start: string; end: string } {
  const next = new Date(`${date}T00:00:00Z`);
  if (Number.isNaN(next.getTime())) throw new Error("Invalid date");
  next.setUTCDate(next.getUTCDate() + 1);
  return { start: `${date} 00:00:00`, end: `${next.toISOString().slice(0, 10)} 00:00:00` };
}

// `recordings.start_time` is written as local ISO ("2026-08-12T11:11:31"), not the
// space-separated form the events/tasks tables use, so it needs its own range.
function isoDateRange(date: string): { start: string; end: string } {
  const next = new Date(`${date}T00:00:00Z`);
  if (Number.isNaN(next.getTime())) throw new Error("Invalid date");
  next.setUTCDate(next.getUTCDate() + 1);
  return { start: `${date}T00:00:00`, end: `${next.toISOString().slice(0, 10)}T00:00:00` };
}

function parseOrReply<T>(schema: z.ZodType<T>, value: unknown, res: Response): T | undefined {
  const result = schema.safeParse(value);
  if (!result.success) {
    res.status(400).json({ error: "Invalid request", details: result.error.flatten() });
    return undefined;
  }
  return result.data;
}

export function createDashboardRouter(
  db: SmartCommunityDB,
  config: ServerConfig,
  summaryClient: VideoSummaryClient,
  liveStreams: LiveStreamManager,
  chatCredentials: ChatCredentialStore,
): Router {
  const router = Router();
  const integrations = loadDashboardIntegrationConfig();

  router.get("/dashboard/config", (req, res) => {
    res.json({
      router: integrations.routerUrl ? "configured" : "unconfigured",
      chat: chatCredentials.isConfigured(req) ? "configured" : "unconfigured",
      frameworks: chatCredentials.getFrameworks(),
      media: { mode: "live-stream", snapshotFallback: true },
    });
  });

  router.post("/dashboard/chat/config", (req, res) => {
    const result = chatCredentials.configure(req, res);
    if ("error" in result) {
      res.status(400).json(result);
      return;
    }
    res.json(result);
  });

  router.get("/monitors", (_req, res) => {
    res.json(db.listMonitors().map(({ sourceUrl: _sourceUrl, ...monitor }) => monitor));
  });

  router.get("/tasks", (req, res) => {
    const query = parseOrReply(taskQuerySchema, req.query, res);
    if (!query) return;
    const { start, end } = dateRange(query.date);
    res.json(db.queryMonitorActivities({ monitorId: query.monitor_id, startTime: start, endTime: end, limit: query.limit ?? 100 }));
  });

  router.get("/reports", (req, res) => {
    const query = parseOrReply(taskQuerySchema.pick({ monitor_id: true, date: true }), req.query, res);
    if (!query) return;
    const { start, end } = dateRange(query.date);
    res.json(db.getReportsByPeriod(query.monitor_id, start, end));
  });

  router.post("/reports/generate", async (req, res) => {
    const body = parseOrReply(reportBodySchema, req.body, res);
    if (!body) return;
    const monitor = db.getMonitor(body.monitor_id);
    if (!monitor) {
      res.status(404).json({ error: "Monitor not found" });
      return;
    }
    const reports = config.useCaseDict[monitor.useCase]?.reports;
    try {
      const result = await generateReport(db, {
        dataSource: reports?.data_source ?? "alerts",
        defaultType: reports?.default_type ?? "daily",
        filter: reports?.filter,
        summaryClient,
        debugDir: config.reportsLogsDir,
      }, body);
      res.json(result);
    } catch (error) {
      res.status(502).json({ error: error instanceof Error ? error.message : "Report generation failed" });
    }
  });

  router.get("/stats", (req, res) => {
    const query = parseOrReply(taskQuerySchema.pick({ monitor_id: true, date: true }), req.query, res);
    if (!query) return;
    const { start, end } = dateRange(query.date);
    const usage = db.getTokenUsageAggregate(query.monitor_id, start, end);
    const activities = db.queryMonitorActivities({ monitorId: query.monitor_id, startTime: start, endTime: end, limit: 500 });
    res.json({ ...usage, activities: activities.length, alerts: activities.filter((item) => item.alert).length });
  });

  const proxyRouterStats = async (req: Request, res: Response, reset: boolean) => {
    if (!integrations.routerUrl) {
      res.json({ status: "not_configured" });
      return;
    }
    try {
      const path = reset ? "v1/stats/reset" : "v1/stats";
      const target = new URL(path, integrations.routerUrl.href.endsWith("/") ? integrations.routerUrl : `${integrations.routerUrl.href}/`);
      const upstream = await fetch(target, { method: reset ? "POST" : "GET", signal: AbortSignal.timeout(3_000) });
      if (!upstream.ok) throw new Error(`Router returned HTTP ${upstream.status}`);
      res.json({ status: "configured", data: await upstream.json() });
    } catch {
      res.status(503).json({ status: "unavailable" });
    }
  };
  router.get("/router/stats", (req, res) => { void proxyRouterStats(req, res, false); });
  router.post("/router/stats/reset", (req, res) => { void proxyRouterStats(req, res, true); });

  router.get("/monitors/:id/live-stream", async (req, res) => {
    const monitorId = parseOrReply(monitorIdSchema, req.params.id, res);
    if (!monitorId) return;
    const monitor = db.getMonitor(monitorId);
    if (!monitor) {
      res.status(404).json({ error: "Monitor not found" });
      return;
    }
    await liveStreams.handle(req, res, monitorId, monitor.sourceUrl);
  });

  router.get("/monitors/:id/snapshot", (req, res) => {
    const monitorId = parseOrReply(monitorIdSchema, req.params.id, res);
    if (!monitorId || !db.getMonitor(monitorId)) {
      if (monitorId) res.status(404).json({ error: "Monitor not found" });
      return;
    }
    sendSnapshot(res, config.segmentsDir, monitorId);
  });

  router.get("/tasks/:id/clip", (req, res) => {
    const taskId = z.coerce.number().int().positive().safeParse(req.params.id);
    const monitorId = parseOrReply(monitorIdSchema, req.query.monitor_id, res);
    if (!taskId.success || !monitorId) {
      if (!taskId.success && !res.headersSent) res.status(400).json({ error: "Invalid task id" });
      return;
    }
    const task = db.getTask(taskId.data);
    if (!task || task.monitorId !== monitorId) {
      res.status(404).json({ error: "Clip not found" });
      return;
    }
    const event = task.eventId ? db.getEvent(task.eventId) : undefined;
    const clipPath = event?.monitorId === monitorId
      ? event.eventFilePath ?? task.summaryClipInput
      : task.summaryClipInput;
    if (!clipPath) {
      res.status(404).json({ error: "Clip not found" });
      return;
    }
    sendMp4(res, config.segmentsDir, monitorId, clipPath, req.headers.range);
  });

  // Continuous-recording segments for one day, oldest first — the dashboard
  // timeline uses these both to draw recording coverage and to resolve a clicked
  // instant to the segment that covers it. file_path stays server-side, same as
  // /monitors withholds sourceUrl.
  router.get("/recordings", (req, res) => {
    const query = parseOrReply(taskQuerySchema.pick({ monitor_id: true, date: true }), req.query, res);
    if (!query) return;
    const { start, end } = isoDateRange(query.date);
    const recordings = db.listRecordings(query.monitor_id, { since: start, until: end, order: "asc" });
    res.json(recordings.map(({ id, startTime, endTime, durationSeconds, fileSizeBytes }) => ({
      id, startTime, endTime, durationSeconds, fileSizeBytes,
    })));
  });

  router.get("/recordings/:id/stream", (req, res) => {
    const recordingId = z.coerce.number().int().positive().safeParse(req.params.id);
    const monitorId = parseOrReply(monitorIdSchema, req.query.monitor_id, res);
    if (!recordingId.success || !monitorId) {
      if (!recordingId.success && !res.headersSent) res.status(400).json({ error: "Invalid recording id" });
      return;
    }
    const recording = db.getRecording(recordingId.data);
    if (!recording || recording.monitorId !== monitorId) {
      res.status(404).json({ error: "Recording not found" });
      return;
    }
    const file = resolveMonitorMp4(config.segmentsDir, monitorId, recording.filePath);
    if (!file) {
      res.status(404).json({ error: "Recording not found" });
      return;
    }
    void sendRecording(res, config.segmentsDir, monitorId, file, req.headers.range).catch((error) => {
      console.error(`[dashboard] recording stream failed: ${error}`);
      if (!res.headersSent) res.status(500).json({ error: "Recording playback failed" });
    });
  });

  return router;
}