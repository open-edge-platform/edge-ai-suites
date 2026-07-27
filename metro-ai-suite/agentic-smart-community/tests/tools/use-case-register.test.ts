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