// SPDX-FileCopyrightText: (C) 2026 Intel Corporation
// SPDX-License-Identifier: Apache-2.0

import assert from "node:assert/strict";
import { mkdtemp, readFile, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { test } from "node:test";
import { parse } from "yaml";
import { SmartCommunityDB } from "@smart-community-video/db";
import { monitorCtl } from "@smart-community-video/tools";
import type { IWorkerService } from "@smart-community-video/tools";

// Unreachable on purpose: monitorCtl treats analytics DELETE/pause/resume
// failures as non-fatal (catch-and-continue), so tests need no live service.
const ANALYTICS_URL = "http://127.0.0.1:1";

function fakeWorkerService(): IWorkerService {
  return { workers: new Map(), start() {}, async stop() {} };
}

async function withTempEnv(
  monitorsYaml: string,
  run: (env: { db: SmartCommunityDB; monitorsPath: string }) => Promise<void>,
): Promise<void> {
  const baseDir = await mkdtemp(join(tmpdir(), "monitor-ctl-persist-"));
  const db = new SmartCommunityDB(join(baseDir, "test.db"));
  db.initialize();
  try {
    const monitorsPath = join(baseDir, "monitors.yaml");
    await writeFile(monitorsPath, monitorsYaml, "utf-8");
    await run({ db, monitorsPath });
  } finally {
    db.close();
    await rm(baseDir, { recursive: true, force: true });
  }
}

const YAML_WITH_ENTRY = `# demo monitors
monitors:
  cam_pet_safety:
    enabled: true
    name: "Pet safety cam"  # keep this comment
    source_url: "rtsp://cam/pet"
    use_case: pet_safety
    pipeline_config:
      motion:
        enabled: true
`;

function seedMonitorWithAlert(db: SmartCommunityDB): void {
  db.createMonitor({
    id: "cam_pet_safety",
    name: "Pet safety cam",
    sourceUrl: "rtsp://cam/pet",
    status: "online",
    useCase: "pet_safety",
    videoSummaryTask: "pet_safety_monitor",
  });
  db.createAlert({ monitorId: "cam_pet_safety", useCase: "pet_safety", description: "dog on sofa" });
}

test("unregister with alert history trips the FK constraint; stop fallback flips yaml enabled:false", async () => {
  await withTempEnv(YAML_WITH_ENTRY, async ({ db, monitorsPath }) => {
    seedMonitorWithAlert(db);

    // alerts.monitor_id REFERENCES monitors(id) + foreign_keys=ON → delete must fail
    await assert.rejects(
      monitorCtl(db, ANALYTICS_URL, fakeWorkerService(), {
        action: "unregister",
        monitor_id: "cam_pet_safety",
        monitors_path: monitorsPath,
        persist: true,
      }),
      /FOREIGN KEY constraint failed/,
    );
    assert.ok(db.getMonitor("cam_pet_safety"), "monitors row kept after failed delete");

    // The use_case_register cascade falls back to stop with persist=true
    const stopped = (await monitorCtl(db, ANALYTICS_URL, fakeWorkerService(), {
      action: "stop",
      monitor_id: "cam_pet_safety",
      monitors_path: monitorsPath,
      persist: true,
    })) as Record<string, unknown>;

    assert.equal(stopped.monitors_yaml, "disabled");
    assert.equal(db.getMonitor("cam_pet_safety")!.status, "offline");

    const raw = await readFile(monitorsPath, "utf-8");
    const parsed = parse(raw);
    assert.equal(parsed.monitors.cam_pet_safety.enabled, false);
    // everything else — pipeline_config, comments — must survive untouched
    assert.equal(parsed.monitors.cam_pet_safety.use_case, "pet_safety");
    assert.deepEqual(parsed.monitors.cam_pet_safety.pipeline_config, { motion: { enabled: true } });
    assert.match(raw, /# keep this comment/);
    assert.match(raw, /# demo monitors/);
  });
});

test("stop with persist adds enabled:false when the entry has no explicit enabled key", async () => {
  await withTempEnv(
    `monitors:\n  cam_door:\n    source_url: "rtsp://cam/door"\n    use_case: door\n`,
    async ({ db, monitorsPath }) => {
      db.createMonitor({
        id: "cam_door",
        name: "cam_door",
        sourceUrl: "rtsp://cam/door",
        status: "online",
        useCase: "door",
        videoSummaryTask: "door_monitor",
      });

      const stopped = (await monitorCtl(db, ANALYTICS_URL, fakeWorkerService(), {
        action: "stop",
        monitor_id: "cam_door",
        monitors_path: monitorsPath,
        persist: true,
      })) as Record<string, unknown>;

      assert.equal(stopped.monitors_yaml, "disabled");
      const parsed = parse(await readFile(monitorsPath, "utf-8"));
      assert.equal(parsed.monitors.cam_door.enabled, false);
    },
  );
});

test("stop with persist skips cleanly when the entry is absent from monitors.yaml", async () => {
  await withTempEnv(`monitors: {}\n`, async ({ db, monitorsPath }) => {
    db.createMonitor({
      id: "cam_ghost",
      name: "cam_ghost",
      sourceUrl: "rtsp://cam/ghost",
      status: "online",
      useCase: "ghost",
      videoSummaryTask: "ghost_monitor",
    });

    const stopped = (await monitorCtl(db, ANALYTICS_URL, fakeWorkerService(), {
      action: "stop",
      monitor_id: "cam_ghost",
      monitors_path: monitorsPath,
      persist: true,
    })) as Record<string, unknown>;

    assert.equal(stopped.monitors_yaml, "skipped");
    assert.ok(
      (stopped.persist_warnings as string[]).some((w) => w.includes("no entry")),
      "warning explains why the flip was skipped",
    );
    // DB effect still stands — persist failure never fails the call
    assert.equal(db.getMonitor("cam_ghost")!.status, "offline");
    assert.match(await readFile(monitorsPath, "utf-8"), /monitors: \{\}/);
  });
});

test("start with persist flips enabled back to true", async () => {
  await withTempEnv(YAML_WITH_ENTRY, async ({ db, monitorsPath }) => {
    seedMonitorWithAlert(db);
    const workers = fakeWorkerService();

    await monitorCtl(db, ANALYTICS_URL, workers, {
      action: "stop",
      monitor_id: "cam_pet_safety",
      monitors_path: monitorsPath,
      persist: true,
    });
    assert.equal(parse(await readFile(monitorsPath, "utf-8")).monitors.cam_pet_safety.enabled, false);

    const started = (await monitorCtl(db, ANALYTICS_URL, workers, {
      action: "start",
      monitor_id: "cam_pet_safety",
      monitors_path: monitorsPath,
      persist: true,
    })) as Record<string, unknown>;

    assert.equal(started.monitors_yaml, "enabled");
    assert.equal(parse(await readFile(monitorsPath, "utf-8")).monitors.cam_pet_safety.enabled, true);
    assert.equal(db.getMonitor("cam_pet_safety")!.status, "online");
  });
});
