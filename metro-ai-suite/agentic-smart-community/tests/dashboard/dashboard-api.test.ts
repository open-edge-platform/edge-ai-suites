// SPDX-FileCopyrightText: (C) 2026 Intel Corporation
// SPDX-License-Identifier: Apache-2.0

import assert from "node:assert/strict";
import { mkdtempSync, mkdirSync, rmSync, symlinkSync, writeFileSync } from "node:fs";
import { createServer } from "node:http";
import { tmpdir } from "node:os";
import { join } from "node:path";
import test from "node:test";
import express from "express";
import { SmartBuildingDB } from "@smartbuilding-video/db";
import type { VideoSummaryClient } from "@smartbuilding-video/tools";
import type { ServerConfig } from "../../packages/mcp-server/src/config.js";
import { createDashboardRouter } from "../../packages/mcp-server/src/dashboard/router.js";
import { LiveStreamManager } from "../../packages/mcp-server/src/dashboard/live-stream.js";
import { mountStaticUi } from "../../packages/mcp-server/src/dashboard/static-ui.js";
import { ChatCredentialStore } from "../../packages/mcp-server/src/dashboard/chat-credentials.js";

test("dashboard API validates inputs and contains monitor media", async () => {
  delete process.env.SMARTBUILDING_ROUTER_URL;
  delete process.env.SMARTBUILDING_OPENCLAW_GATEWAY_URL;
  delete process.env.SMARTBUILDING_OPENCLAW_GATEWAY_TOKEN;
  const root = mkdtempSync(join(tmpdir(), "smartbuilding-dashboard-"));
  const segmentsDir = join(root, "segments");
  const monitorDir = join(segmentsDir, "cam-1");
  mkdirSync(monitorDir, { recursive: true });
  writeFileSync(join(monitorDir, "latest.jpg"), Buffer.from([0xff, 0xd8, 0xff, 0xd9]));
  const clipPath = join(monitorDir, "clip.mp4");
  writeFileSync(clipPath, Buffer.from("0123456789"));
  const fullClipPath = join(monitorDir, "full.mp4");
  writeFileSync(fullClipPath, Buffer.from("full-video"));
  const croppedClipPath = join(monitorDir, "cropped.mp4");
  writeFileSync(croppedClipPath, Buffer.from("cropped-video"));
  const outsideClip = join(root, "outside.mp4");
  writeFileSync(outsideClip, Buffer.from("outside"));
  const symlinkClip = join(monitorDir, "linked.mp4");
  symlinkSync(clipPath, symlinkClip);

  const db = new SmartBuildingDB(join(root, "dashboard.db"));
  db.initialize();
  db.createMonitor({ id: "cam-1", name: "Camera One", sourceUrl: "rtsp://user:secret@localhost/live", status: "online", useCase: "child", videoSummaryTask: "child_task" });
  const clipTask = db.createTask({ monitorId: "cam-1", summaryClipInput: clipPath, status: "completed" });
  const fullClipEvent = db.createEvent({ monitorId: "cam-1", motionType: "motion", startTime: "2026-07-30T09:00:00", eventFilePath: fullClipPath });
  const croppedTask = db.createTask({ monitorId: "cam-1", eventId: fullClipEvent.id, summaryClipInput: croppedClipPath, status: "completed" });
  const outsideTask = db.createTask({ monitorId: "cam-1", summaryClipInput: outsideClip, status: "completed" });
  const symlinkTask = db.createTask({ monitorId: "cam-1", summaryClipInput: symlinkClip, status: "completed" });
  const config = { segmentsDir, reportsLogsDir: join(root, "reports"), useCaseDict: {} } as ServerConfig;
  const liveStreams = new LiveStreamManager();
  const chatCredentials = new ChatCredentialStore({});
  const app = express();
  app.use(express.json({ limit: "64kb" }));
  app.use("/api", createDashboardRouter(db, config, {} as VideoSummaryClient, liveStreams, chatCredentials));
  mountStaticUi(app);
  const server = createServer(app);
  await new Promise<void>((resolve) => server.listen(0, "127.0.0.1", resolve));
  const address = server.address();
  if (!address || typeof address === "string") throw new Error("Expected TCP address");
  const base = `http://127.0.0.1:${address.port}`;

  try {
    const dashboardConfig = await fetch(`${base}/api/dashboard/config`).then((response) => response.json()) as any;
    assert.equal(dashboardConfig.router, "unconfigured");
    assert.equal(dashboardConfig.chat, "unconfigured");
    assert.deepEqual(dashboardConfig.frameworks.map((framework: any) => framework.id), ["openclaw"]);
    const publicTarget = await fetch(`${base}/api/dashboard/chat/config`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ framework: "openclaw", url: "https://example.com", token: "secret" }),
    });
    assert.equal(publicTarget.status, 400);
    const configured = await fetch(`${base}/api/dashboard/chat/config`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ framework: "openclaw", url: "http://127.0.0.1:18789/", token: "secret" }),
    });
    assert.equal(configured.status, 200);
    const sessionCookie = configured.headers.get("set-cookie")?.split(";", 1)[0];
    assert.ok(sessionCookie);
    assert.doesNotMatch(await configured.text(), /secret/);
    const configuredStatus = await fetch(`${base}/api/dashboard/config`, { headers: { Cookie: sessionCookie } }).then((response) => response.json()) as any;
    assert.equal(configuredStatus.chat, "configured");
    const ui = await fetch(`${base}/`);
    assert.equal(ui.status, 200);
    assert.match(await ui.text(), /Agentic Smart Community/);
    assert.equal((await fetch(`${base}/api/not-a-route`)).status, 404);

    const monitors = await fetch(`${base}/api/monitors`).then((response) => response.json()) as any[];
    assert.equal(monitors.length, 1);
    assert.equal(monitors[0].id, "cam-1");
    assert.equal("sourceUrl" in monitors[0], false);
    assert.doesNotMatch(JSON.stringify(monitors), /secret/);

    assert.equal((await fetch(`${base}/api/tasks?monitor_id=cam-1&date=bad-date`)).status, 400);
    const snapshot = await fetch(`${base}/api/monitors/cam-1/snapshot`);
    assert.equal(snapshot.status, 200);
    assert.equal(snapshot.headers.get("content-type"), "image/jpeg");

    const range = await fetch(`${base}/api/tasks/${clipTask.id}/clip?monitor_id=cam-1`, { headers: { Range: "bytes=2-5" } });
    assert.equal(range.status, 206);
    assert.equal(range.headers.get("content-range"), "bytes 2-5/10");
    assert.equal(await range.text(), "2345");
    const suffixRange = await fetch(`${base}/api/tasks/${clipTask.id}/clip?monitor_id=cam-1`, { headers: { Range: "bytes=-3" } });
    assert.equal(suffixRange.status, 206);
    assert.equal(await suffixRange.text(), "789");
    const fullClip = await fetch(`${base}/api/tasks/${croppedTask.id}/clip?monitor_id=cam-1`);
    assert.equal(fullClip.status, 200);
    assert.equal(await fullClip.text(), "full-video");

    assert.equal((await fetch(`${base}/api/tasks/${clipTask.id}/clip?monitor_id=other-monitor`)).status, 404);
    assert.equal((await fetch(`${base}/api/tasks/${outsideTask.id}/clip?monitor_id=cam-1`)).status, 404);
    assert.equal((await fetch(`${base}/api/tasks/${symlinkTask.id}/clip?monitor_id=cam-1`)).status, 404);
  } finally {
    await liveStreams.close();
    await new Promise<void>((resolve, reject) => server.close((error) => error ? reject(error) : resolve()));
    db.close();
    rmSync(root, { recursive: true, force: true });
  }
});