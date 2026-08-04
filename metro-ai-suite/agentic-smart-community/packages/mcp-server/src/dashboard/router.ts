// SPDX-FileCopyrightText: (C) 2026 Intel Corporation
// SPDX-License-Identifier: Apache-2.0

import { Router, type Request, type Response } from "express";
import { z } from "zod";
import type { SmartBuildingDB } from "@smartbuilding-video/db";
import { generateReport, type VideoSummaryClient } from "@smartbuilding-video/tools";
import type { ServerConfig } from "../config.js";
import { loadDashboardIntegrationConfig } from "./integration-env.js";
import { LiveStreamManager } from "./live-stream.js";
import { sendMp4, sendSnapshot } from "./media.js";
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

function parseOrReply<T>(schema: z.ZodType<T>, value: unknown, res: Response): T | undefined {
  const result = schema.safeParse(value);
  if (!result.success) {
    res.status(400).json({ error: "Invalid request", details: result.error.flatten() });
    return undefined;
  }
  return result.data;
}

export function createDashboardRouter(
  db: SmartBuildingDB,
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

  return router;
}