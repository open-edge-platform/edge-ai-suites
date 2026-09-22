// SPDX-FileCopyrightText: (C) 2026 Intel Corporation
// SPDX-License-Identifier: Apache-2.0

import assert from "node:assert/strict";
import { mkdtemp, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { test } from "node:test";
import { SmartCommunityDB } from "@smart-community-video/db";
import { reregisterUnknownMonitor } from "../../packages/mcp-server/src/monitor-bootstrap.js";
import { startKeepaliveSender } from "../../packages/mcp-server/src/keepalive-sender.js";
import type { ServerConfig } from "../../packages/mcp-server/src/config.js";
import type { WorkerService } from "../../packages/mcp-server/src/video-worker/index.js";

// Intercepted by the fetch mock — no real network in these tests.
const ANALYTICS_URL = "http://vsa.invalid";

const YAML_WITH_ENTRY = `monitors:
  cam_pet_safety:
    enabled: true
    name: "Pet safety cam"
    source_url: "rtsp://cam/pet"
    use_case: pet_safety
    pipeline_config:
      motion:
        enabled: true
`;

interface FetchCall {
  url: string;
  method: string;
  body?: Record<string, any>;
}

/** Replace global fetch with a scripted VSA; returns the recorded calls + restore(). */
function mockVsa(handler: (call: FetchCall) => { status: number; body?: unknown }): {
  calls: FetchCall[];
  restore: () => void;
} {
  const calls: FetchCall[] = [];
  const original = globalThis.fetch;
  globalThis.fetch = (async (input: any, init?: any) => {
    const call: FetchCall = {
      url: String(input),
      method: init?.method ?? "GET",
      body: init?.body ? JSON.parse(init.body) : undefined,
    };
    calls.push(call);
    const resp = handler(call);
    return new Response(JSON.stringify(resp.body ?? {}), {
      status: resp.status,
      headers: { "Content-Type": "application/json" },
    });
  }) as typeof fetch;
  return { calls, restore: () => { globalThis.fetch = original; } };
}

function fakeWorkerService(): { svc: WorkerService; calls: string[] } {
  const calls: string[] = [];
  const svc = {
    workers: new Map<string, unknown>(),
    start(id: string) {
      calls.push(`start:${id}`);
      this.workers.set(id, {});
    },
    async stop(id: string) {
      calls.push(`stop:${id}`);
      this.workers.delete(id);
    },
  };
  return { svc: svc as unknown as WorkerService, calls };
}

function fakeConfig(baseDir: string, monitorsPath: string): ServerConfig {
  return {
    dataDir: baseDir,
    dbPath: join(baseDir, "smart-community.db"),
    segmentsDir: join(baseDir, "segments"),
    reportsLogsDir: join(baseDir, "logs", "reports"),
    monitorsLogsDir: join(baseDir, "logs", "monitors"),
    summaryService: { url: "http://127.0.0.1:1" },
    vlmService: { url: "http://127.0.0.1:1", model: "default", maxEdgePx: 720 },
    videostreamAnalytics: { url: ANALYTICS_URL },
    keepalive: { enabled: true, intervalMs: 10, timeoutSeconds: 90, checkIntervalSeconds: 10 },
    pollIntervalMs: 5000,
    videoSummaryMaxConcurrent: 2,
    eventsWebhook: { port: 0 },
    useCaseDict: { pet_safety: { video_summary_task: "pet_safety_monitor" } },
    monitorsPath,
    logging: { retentionDays: 14, maxFileMb: 50 },
    storage: { retentionDays: 7, cleanupSubdirs: ["motion_events", "recordings", "queries"] },
  };
}

async function withTempEnv(
  monitorsYaml: string,
  run: (env: { db: SmartCommunityDB; baseDir: string; monitorsPath: string }) => Promise<void>,
): Promise<void> {
  const baseDir = await mkdtemp(join(tmpdir(), "keepalive-reregister-"));
  const db = new SmartCommunityDB(join(baseDir, "test.db"));
  db.initialize();
  try {
    const monitorsPath = join(baseDir, "monitors.yaml");
    await writeFile(monitorsPath, monitorsYaml, "utf-8");
    await run({ db, baseDir, monitorsPath });
  } finally {
    db.close();
    await rm(baseDir, { recursive: true, force: true });
  }
}

/** Seed the state right after a VSA recreate: DB still says online, MCP-side worker still running. */
function seedOnlineMonitor(db: SmartCommunityDB, svc: WorkerService, id = "cam_pet_safety"): void {
  db.createMonitor({
    id,
    name: "Pet safety cam",
    sourceUrl: "rtsp://cam/pet",
    status: "online",
    useCase: "pet_safety",
    videoSummaryTask: "pet_safety_monitor",
  });
  svc.start(id);
}

test("re-registers a monitor VSA forgot, re-reading monitors.yaml for pipeline_config", async () => {
  await withTempEnv(YAML_WITH_ENTRY, async ({ db, baseDir, monitorsPath }) => {
    const { svc, calls: workerCalls } = fakeWorkerService();
    seedOnlineMonitor(db, svc);

    // VSA after recreate: source unknown (404), accepts register_source.
    const vsa = mockVsa(({ url, method }) => {
      if (url.endsWith("/sources/cam_pet_safety/status")) return { status: 404 };
      if (url.endsWith("/register_source") && method === "POST") return { status: 200, body: { status: "registered" } };
      return { status: 200 };
    });
    try {
      await reregisterUnknownMonitor(db, fakeConfig(baseDir, monitorsPath), svc, "cam_pet_safety");
    } finally {
      vsa.restore();
    }

    const regs = vsa.calls.filter((c) => c.url.endsWith("/register_source") && c.method === "POST");
    assert.equal(regs.length, 1, "exactly one register_source POST");
    assert.equal(regs[0].body!.source_id, "cam_pet_safety");
    assert.equal(regs[0].body!.source_url, "rtsp://cam/pet");
    // pipeline_config only lives in monitors.yaml — proves the re-read happened
    assert.deepEqual(regs[0].body!.pipeline.motion, { enabled: true });
    // keepalive watchdog re-armed from server config
    assert.equal(regs[0].body!.pipeline.keepalive.enabled, true);
    // worker was cycled (old one pointed at the dead VSA pipeline)
    assert.deepEqual(workerCalls, ["start:cam_pet_safety", "stop:cam_pet_safety", "start:cam_pet_safety"]);
    assert.equal(db.getMonitor("cam_pet_safety")!.status, "online");
  });
});

test("does NOT resurrect a monitor that was removed from monitors.yaml while VSA was down", async () => {
  await withTempEnv(`monitors: {}\n`, async ({ db, baseDir, monitorsPath }) => {
    const { svc } = fakeWorkerService();
    seedOnlineMonitor(db, svc);

    const vsa = mockVsa(() => ({ status: 200 }));
    try {
      await reregisterUnknownMonitor(db, fakeConfig(baseDir, monitorsPath), svc, "cam_pet_safety");
    } finally {
      vsa.restore();
    }

    assert.equal(
      vsa.calls.filter((c) => c.url.endsWith("/register_source")).length,
      0,
      "no register_source for a monitor absent from monitors.yaml",
    );
  });
});

test("does NOT resurrect a monitor disabled in monitors.yaml", async () => {
  await withTempEnv(YAML_WITH_ENTRY.replace("enabled: true", "enabled: false"), async ({ db, baseDir, monitorsPath }) => {
    const { svc } = fakeWorkerService();
    seedOnlineMonitor(db, svc);

    const vsa = mockVsa(() => ({ status: 200 }));
    try {
      await reregisterUnknownMonitor(db, fakeConfig(baseDir, monitorsPath), svc, "cam_pet_safety");
    } finally {
      vsa.restore();
    }

    assert.equal(
      vsa.calls.filter((c) => c.url.endsWith("/register_source")).length,
      0,
      "no register_source for a disabled monitor",
    );
  });
});

test("concurrent triggers for the same monitor collapse into one registration", async () => {
  await withTempEnv(YAML_WITH_ENTRY, async ({ db, baseDir, monitorsPath }) => {
    const { svc } = fakeWorkerService();
    seedOnlineMonitor(db, svc);

    const vsa = mockVsa(({ url, method }) => {
      if (url.endsWith("/sources/cam_pet_safety/status")) return { status: 404 };
      if (url.endsWith("/register_source") && method === "POST") return { status: 200, body: { status: "registered" } };
      return { status: 200 };
    });
    const config = fakeConfig(baseDir, monitorsPath);
    try {
      await Promise.all([
        reregisterUnknownMonitor(db, config, svc, "cam_pet_safety"),
        reregisterUnknownMonitor(db, config, svc, "cam_pet_safety"),
        reregisterUnknownMonitor(db, config, svc, "cam_pet_safety"),
      ]);
    } finally {
      vsa.restore();
    }

    assert.equal(
      vsa.calls.filter((c) => c.url.endsWith("/register_source")).length,
      1,
      "in-flight guard dedupes concurrent re-registrations",
    );
  });
});

test("a failed re-registration clears the guard so the next 404 retries", async () => {
  await withTempEnv(YAML_WITH_ENTRY, async ({ db, baseDir, monitorsPath }) => {
    const { svc } = fakeWorkerService();
    seedOnlineMonitor(db, svc);

    // VSA still coming up: register_source refuses. Second call must retry, not stay deduped.
    let registerAttempts = 0;
    const vsa = mockVsa(({ url, method }) => {
      if (url.endsWith("/sources/cam_pet_safety/status")) return { status: 404 };
      if (url.endsWith("/register_source") && method === "POST") {
        registerAttempts += 1;
        return registerAttempts === 1 ? { status: 503, body: "starting" } : { status: 200, body: { status: "registered" } };
      }
      return { status: 200 };
    });
    const config = fakeConfig(baseDir, monitorsPath);
    try {
      await reregisterUnknownMonitor(db, config, svc, "cam_pet_safety");
      assert.equal(db.getMonitor("cam_pet_safety")!.status, "offline", "failed attempt leaves monitor offline");
      await reregisterUnknownMonitor(db, config, svc, "cam_pet_safety");
    } finally {
      vsa.restore();
    }

    assert.equal(registerAttempts, 2, "second 404 triggers a fresh registration attempt");
    assert.equal(db.getMonitor("cam_pet_safety")!.status, "online");
  });
});

test("keepalive sender invokes onSourceUnknown only on 404", async () => {
  await withTempEnv(`monitors: {}\n`, async ({ db, baseDir, monitorsPath }) => {
    db.createMonitor({
      id: "cam_gone",
      name: "cam_gone",
      sourceUrl: "rtsp://cam/gone",
      status: "online",
      useCase: "pet_safety",
      videoSummaryTask: "pet_safety_monitor",
    });
    db.createMonitor({
      id: "cam_err",
      name: "cam_err",
      sourceUrl: "rtsp://cam/err",
      status: "online",
      useCase: "pet_safety",
      videoSummaryTask: "pet_safety_monitor",
    });

    const unknown: string[] = [];
    const vsa = mockVsa(({ url }) => (url.includes("cam_gone") ? { status: 404 } : { status: 500 }));
    const stop = startKeepaliveSender(fakeConfig(baseDir, monitorsPath), db, (id) => unknown.push(id));
    try {
      await new Promise((r) => setTimeout(r, 55)); // several 10ms ticks
    } finally {
      stop();
      vsa.restore();
    }

    assert.ok(unknown.includes("cam_gone"), "404 monitor reported");
    assert.ok(!unknown.includes("cam_err"), "non-404 failures are not reported");
  });
});
