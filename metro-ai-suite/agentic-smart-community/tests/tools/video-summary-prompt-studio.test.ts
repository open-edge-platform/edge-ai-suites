// SPDX-FileCopyrightText: (C) 2026 Intel Corporation
// SPDX-License-Identifier: Apache-2.0

import assert from "node:assert/strict";
import { access, readFile } from "node:fs/promises";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { test } from "node:test";

const repoRoot = join(dirname(fileURLToPath(import.meta.url)), "..", "..");
const skillDir = join(repoRoot, "skills", "video-summary-prompt-studio");

async function readSkillFile(relativePath: string): Promise<string> {
  return readFile(join(skillDir, relativePath), "utf-8");
}

function outputKeys(text: string): string[] {
  return [...text.matchAll(/^\s*([A-Z][A-Z0-9_]*)\s*:/gm)].map((match) => match[1]);
}

test("main Skill stays slim and links every conditional reference", async () => {
  const skill = await readSkillFile("SKILL.md");
  assert.match(skill, /^---\n[\s\S]*?name: video-summary-prompt-studio[\s\S]*?\n---\n/);
  assert.ok(skill.split("\n").length <= 360, "SKILL.md should remain decision-oriented");

  for (const relativePath of [
    "references/prompt-authoring.md",
    "references/evaluate-rules.md",
    "references/inspect-existing.md",
    "references/curl-fallback.md",
    "scripts/list_use_cases.sh",
  ]) {
    assert.match(skill, new RegExp(relativePath.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")));
    await access(join(skillDir, relativePath));
  }
});

test("mode matrix preserves report-only, base, and extended invariants", async () => {
  const skill = await readSkillFile("SKILL.md");
  assert.match(skill, /Report-only \| none \| factual narrative; multiple findings allowed \| none/);
  assert.match(skill, /Base alerting \| `severity, event, desc` \| one primary EVENT \| `defaultRuleEvaluator`/);
  assert.match(skill, /Extended alerting \| base \+ user-confirmed extensions[\s\S]*?`evaluate_rules\.py`/);
  assert.match(skill, /Any extended schema \*\*must\*\* have `evaluate_rules\.py`/);
  assert.match(skill, /Extended fields without `evaluate_rules\.py` are rejected/);
  assert.match(skill, /When alerting intent is not explicit, generate a preview only/);
});

test("authoring reference keeps structured and narrative output contracts separate", async () => {
  const authoring = await readSkillFile("references/prompt-authoring.md");
  const structuredStart = authoring.indexOf("## Structured alerting template");
  const reportOnlyStart = authoring.indexOf("## Report-only LOCAL variant");
  const lintStart = authoring.indexOf("## Semantic lint");
  assert.ok(structuredStart >= 0 && reportOnlyStart > structuredStart && lintStart > reportOnlyStart);

  const structuredTemplate = authoring.slice(structuredStart, reportOnlyStart);
  assert.deepEqual(outputKeys(structuredTemplate), ["SEVERITY", "EVENT", "DESC"]);

  const reportOnly = authoring.slice(reportOnlyStart, lintStart);
  assert.deepEqual(outputKeys(reportOnly), []);
  assert.match(reportOnly, /multiple simultaneous visible findings/);
  assert.match(authoring, /Realtime clip, default `SIMPLE`, `levels=1` \| `LOCAL_PROMPT` only/);
  assert.match(authoring, /The registration consistency gate proves structural alignment only/);
});
