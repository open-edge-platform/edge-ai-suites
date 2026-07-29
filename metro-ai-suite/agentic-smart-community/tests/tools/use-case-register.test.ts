// SPDX-FileCopyrightText: (C) 2026 Intel Corporation
// SPDX-License-Identifier: Apache-2.0

import assert from "node:assert/strict";
import { mkdir, mkdtemp, readFile, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { test } from "node:test";
import { useCaseRegister } from "@smartbuilding-video/tools";

async function withTempDir(run: (baseDir: string) => Promise<void>): Promise<void> {
  const baseDir = await mkdtemp(join(tmpdir(), "use-case-unregister-"));
  try {
    await run(baseDir);
  } finally {
    await rm(baseDir, { recursive: true, force: true });
  }
}

test("unregister archives artifacts after removing the persisted entry", async () => {
  await withTempDir(async (baseDir) => {
    const configPath = join(baseDir, "config.yaml");
    const artifactDir = join(baseDir, "use-cases", "demo_case");
    await mkdir(artifactDir, { recursive: true });
    await writeFile(join(artifactDir, "prompt.md"), "prompt", "utf-8");
    await writeFile(
      configPath,
      "use_case_dict:\n  demo_case:\n    video_summary_task: shared_task\n  sibling_case:\n    video_summary_task: shared_task\n",
      "utf-8",
    );
    const useCaseDict = {
      demo_case: { video_summary_task: "shared_task" },
      sibling_case: { video_summary_task: "shared_task" },
    };

    const result = await useCaseRegister(
      { action: "unregister", use_case: "demo_case", persist: true },
      { useCaseDict, summaryServiceUrl: "http://unused", db: {}, configPath, baseDir },
    );

    assert.equal(result.ok, true);
    assert.equal(result.degraded, undefined);
    assert.equal(result.steps.config_yaml, "removed");
    assert.equal(result.steps.vlm_task, "skipped");
    assert.equal(result.steps.artifacts?.archived_to, join(baseDir, "use-cases", ".backup", "demo_case"));
    assert.equal(await readFile(join(baseDir, "use-cases", ".backup", "demo_case", "prompt.md"), "utf-8"), "prompt");
    assert.doesNotMatch(await readFile(configPath, "utf-8"), /demo_case/);
    assert.equal("demo_case" in useCaseDict, false);
  });
});

test("unregister keeps artifacts when persistent config removal fails", async () => {
  await withTempDir(async (baseDir) => {
    const artifactDir = join(baseDir, "use-cases", "demo_case");
    await mkdir(artifactDir, { recursive: true });
    await writeFile(join(artifactDir, "prompt.md"), "prompt", "utf-8");
    const useCaseDict = {
      demo_case: { video_summary_task: "shared_task" },
      sibling_case: { video_summary_task: "shared_task" },
    };

    const result = await useCaseRegister(
      { action: "unregister", use_case: "demo_case", persist: true },
      {
        useCaseDict,
        summaryServiceUrl: "http://unused",
        db: {},
        configPath: join(baseDir, "missing", "config.yaml"),
        baseDir,
      },
    );

    assert.equal(result.ok, true);
    assert.equal(result.degraded, true);
    assert.equal(result.steps.config_yaml, "skipped");
    assert.equal(await readFile(join(artifactDir, "prompt.md"), "utf-8"), "prompt");
    assert.ok(result.warnings.some((warning) => warning.includes("artifact archive skipped")));
  });
});

test("unregister reports a missing VLM task name as degraded", async () => {
  const useCaseDict = { demo_case: {} };
  const result = await useCaseRegister(
    { action: "unregister", use_case: "demo_case" },
    { useCaseDict, summaryServiceUrl: "http://unused", db: {} },
  );

  assert.equal(result.ok, true);
  assert.equal(result.degraded, true);
  assert.equal(result.steps.vlm_task, "skipped");
  assert.ok(result.warnings.some((warning) => warning.includes("has no video_summary_task")));
});
test("list returns the in-memory use_case_dict inventory without a use_case argument", async () => {
  const useCaseDict = {
    child_safety: {
      video_summary_task: "child_safety_monitor",
      description: "Child danger alerts",
      reports: { data_source: "alerts", default_type: "daily", filter: {} },
      schema: {
        video_summary_tasks: {
          extensions: [
            { name: "severity", type: "text", required: false },
            { name: "event", type: "text", required: true },
            { name: "desc", type: "text", required: true },
          ],
        },
        custom_tables: [],
      },
    },
    elder_wakeup: {
      video_summary_task: "elder_wakeup_monitor",
      description: "Elder wake-up tracking alerts",
      evaluate_rules_path: "/data/use-cases/elder_wakeup/evaluate_rules.py",
      reports: { data_source: "alerts", default_type: "daily", filter: {} },
      schema: {
        video_summary_tasks: {
          extensions: [
            { name: "severity", type: "text", required: false },
            { name: "event", type: "text", required: true },
            { name: "desc", type: "text", required: true },
            { name: "wake_status", type: "text", required: false },
          ],
        },
        custom_tables: [],
      },
    },
    fridge: {
      video_summary_task: "fridge_monitor",
      description: "Fridge activity reports",
      reports: { data_source: "video_summary_tasks", default_type: "daily", filter: { status: "completed" } },
    },
  };

  const result = await useCaseRegister(
    { action: "list" },
    { useCaseDict, summaryServiceUrl: "http://unused", db: {} },
  );

  assert.equal(result.ok, true);
  assert.deepEqual(result.errors, []);
  assert.equal(result.use_cases?.map((e) => e.use_case).join(","), "child_safety,elder_wakeup,fridge");

  const elder = result.use_cases!.find((e) => e.use_case === "elder_wakeup")!;
  assert.equal(elder.video_summary_task, "elder_wakeup_monitor");
  assert.equal(elder.rule_path, "evaluate_rules.py");
  assert.deepEqual(elder.schema_fields, ["severity", "event", "desc", "wake_status"]);
  assert.equal(elder.report_source, "alerts");

  const child = result.use_cases!.find((e) => e.use_case === "child_safety")!;
  assert.equal(child.rule_path, "defaultRuleEvaluator");
  assert.deepEqual(child.schema_fields, ["severity", "event", "desc"]);

  const fridge = result.use_cases!.find((e) => e.use_case === "fridge")!;
  assert.equal(fridge.rule_path, "none");
  assert.deepEqual(fridge.schema_fields, []);
  assert.equal(fridge.report_source, "video_summary_tasks");

  // Read-only: the dict must be untouched.
  assert.deepEqual(Object.keys(useCaseDict).sort(), ["child_safety", "elder_wakeup", "fridge"]);
});

test("list with an empty use_case_dict returns an empty inventory", async () => {
  const result = await useCaseRegister(
    { action: "list" },
    { useCaseDict: {}, summaryServiceUrl: "http://unused", db: {} },
  );

  assert.equal(result.ok, true);
  assert.deepEqual(result.use_cases, []);
});

test("register without use_case still fails validation", async () => {
  const result = await useCaseRegister(
    { action: "register" } as any,
    { useCaseDict: {}, summaryServiceUrl: "http://unused", db: {} },
  );

  assert.equal(result.ok, false);
  assert.ok(result.errors.some((e) => e.includes("must match")));
});
