// SPDX-FileCopyrightText: (C) 2026 Intel Corporation
// SPDX-License-Identifier: Apache-2.0

import assert from "node:assert/strict";
import { access, readFile } from "node:fs/promises";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { test } from "node:test";

const repoRoot = join(dirname(fileURLToPath(import.meta.url)), "..", "..");
const skillDir = join(repoRoot, "skills", "smart-community-use-case-manager");

async function readSkillFile(relativePath: string): Promise<string> {
  return readFile(join(skillDir, relativePath), "utf-8");
}

function outputKeys(text: string): string[] {
  return [...text.matchAll(/^\s*([A-Z][A-Z0-9_]*)\s*:/gm)].map((match) => match[1]);
}

test("main Skill stays slim and links every conditional reference", async () => {
  const skill = await readSkillFile("SKILL.md");
  assert.match(skill, /^---\n[\s\S]*?name: smart-community-use-case-manager[\s\S]*?\n---\n/);
  assert.ok(skill.split("\n").length <= 600, "SKILL.md should remain decision-oriented");

  for (const relativePath of [
    "references/prompt-authoring.md",
    "references/evaluate-rules.md",
    "references/inspect-existing.md",
    "references/delete-use-case.md",
    "references/final-report.md",
    "references/curl-fallback.md",
  ]) {
    assert.match(skill, new RegExp(relativePath.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")));
    await access(join(skillDir, relativePath));
  }
});

test("mode matrix and two confirmation gates preserve workflow invariants", async () => {
  const skill = await readSkillFile("SKILL.md");
  assert.match(skill, /Report-only \| none \| factual narrative; multiple findings allowed \| none/);
  assert.match(skill, /Base alerting \| `severity, event, desc` \| one primary EVENT \| `defaultRuleEvaluator`/);
  assert.match(skill, /Extended alerting \| base \+ user-confirmed extensions[\s\S]*?`evaluate_rules\.py`/);
  assert.match(skill, /Any extended schema \*\*must\*\* have `evaluate_rules\.py`/);
  assert.match(skill, /Extended fields without `evaluate_rules\.py` are rejected/);
  assert.match(skill, /The initial request never answers Q1 or Q2/);
  assert.match(skill, /the only permitted tool call is reading this[\s\S]*?main `SKILL\.md` file itself/);
  assert.match(skill, /Do not read[\s\S]*?reference, other skill, config, existing artifact, workspace file, or[\s\S]*?memory/);
  assert.match(skill, /Do not call memory, search, shell, MCP, `smart_community_\*`, or any[\s\S]*?other tool/);
  assert.match(skill, /End the assistant turn immediately after the questions/);
  assert.match(skill, /Do not draft a[\s\S]*?call any tool, write memory/);
  assert.match(skill, /Unlock the remaining workflow only from a later user message/);
  assert.match(skill, /There is no fallback that bypasses this gate/);
  assert.match(skill, /This is a mandatory second cross-turn gate/);
  assert.match(skill, /The Q1\/Q2 reply[\s\S]*?cannot approve a design that had not yet been displayed/);
  assert.match(skill, /explicit final approval[\s\S]*?after the proposed design was displayed/);
});

test("authoring reference keeps output modes and final approval aligned", async () => {
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
  assert.match(authoring, /wait for the mandatory final approval described in `SKILL\.md`/);
  assert.match(authoring, /`resolved` means derived for the proposal; `approved` means/);
  assert.doesNotMatch(authoring, /Do not request\s+a separate user confirmation/);
  assert.doesNotMatch(authoring, /never requires another\s+approval turn/i);
});
