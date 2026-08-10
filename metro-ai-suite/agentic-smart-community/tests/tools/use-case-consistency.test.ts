// SPDX-FileCopyrightText: (C) 2026 Intel Corporation
// SPDX-License-Identifier: Apache-2.0

import assert from "node:assert/strict";
import { test } from "node:test";
import { checkUseCaseConsistency } from "@smart-community-video/tools";

const DEFAULT_SCHEMA = [
  { name: "severity", type: "text", required: false },
  { name: "event", type: "text", required: true },
  { name: "desc", type: "text", required: true },
];

const MATCHING_PROMPT = [
  "## LOCAL_PROMPT",
  "Analyze the clip and emit exactly these lines:",
  "SEVERITY: critical|warn|info",
  "EVENT: child_fall|no_incident",
  "DESC: one sentence",
].join("\n");

test("default rule path: matching prompt and schema is consistent", () => {
  const r = checkUseCaseConsistency({
    promptText: MATCHING_PROMPT,
    schemaExtensions: DEFAULT_SCHEMA,
  });
  assert.equal(r.consistent, true);
  assert.deepEqual(r.missing_in_prompt, []);
  assert.deepEqual(r.extra_in_prompt, []);
});

test("prompt field not declared in schema → extra_in_prompt", () => {
  const r = checkUseCaseConsistency({
    promptText: MATCHING_PROMPT + "\nCONFIDENCE: high|low",
    schemaExtensions: DEFAULT_SCHEMA,
  });
  assert.equal(r.consistent, false);
  assert.deepEqual(r.extra_in_prompt, ["confidence"]);
});

test("schema field missing from prompt → missing_in_prompt", () => {
  const prompt = MATCHING_PROMPT.replace("\nDESC: one sentence", "");
  const r = checkUseCaseConsistency({
    promptText: prompt,
    schemaExtensions: DEFAULT_SCHEMA,
  });
  assert.equal(r.consistent, false);
  assert.deepEqual(r.missing_in_prompt, ["desc"]);
});

test("report-only: empty schema is consistent only when the prompt declares no KEY lines", () => {
  const ok = checkUseCaseConsistency({
    promptText: "## LOCAL_PROMPT\nDescribe the scene in prose.",
    schemaExtensions: [],
  });
  assert.equal(ok.consistent, true);

  const bad = checkUseCaseConsistency({
    promptText: MATCHING_PROMPT,
    schemaExtensions: [],
  });
  assert.equal(bad.consistent, false);
  assert.deepEqual(bad.extra_in_prompt, ["severity", "event", "desc"]);
});

test("extended schema without evaluate_rules.py → extended_schema_missing_rule", () => {
  const r = checkUseCaseConsistency({
    promptText: MATCHING_PROMPT + "\nZONE: kitchen|bedroom",
    schemaExtensions: [...DEFAULT_SCHEMA, { name: "zone", type: "text", required: false }],
  });
  assert.equal(r.consistent, false);
  assert.deepEqual(r.extended_schema_missing_rule, ["zone"]);
});

test("default path without severity in schema → default_path_missing_fields", () => {
  const r = checkUseCaseConsistency({
    promptText: "## LOCAL_PROMPT\nEVENT: a|b\nDESC: text",
    schemaExtensions: [
      { name: "event", type: "text", required: true },
      { name: "desc", type: "text", required: true },
    ],
  });
  assert.equal(r.consistent, false);
  assert.deepEqual(r.default_path_missing_fields, ["severity"]);
});

test("custom rule reading only declared fields is consistent; os.environ.get is not a field", () => {
  const rules = [
    'import os',
    'region = os.environ.get("REGION", "home")',
    'event = fields.get("event")',
    'alias = fields.get("description")  # legacy alias of desc',
  ].join("\n");
  const r = checkUseCaseConsistency({
    promptText: MATCHING_PROMPT,
    schemaExtensions: DEFAULT_SCHEMA,
    evaluateRulesText: rules,
  });
  assert.equal(r.consistent, true);
  assert.deepEqual(r.rule_fields_not_in_schema, []);
});

test("custom rule reading an undeclared field → rule_fields_not_in_schema", () => {
  const r = checkUseCaseConsistency({
    promptText: MATCHING_PROMPT,
    schemaExtensions: DEFAULT_SCHEMA,
    evaluateRulesText: 'zone = fields.get("zone")',
  });
  assert.equal(r.consistent, false);
  assert.deepEqual(r.rule_fields_not_in_schema, ["zone"]);
});

test("JSON output request is flagged, but a prohibition of JSON is not", () => {
  const bad = checkUseCaseConsistency({
    promptText: MATCHING_PROMPT + "\n以JSON格式返回结果",
    schemaExtensions: DEFAULT_SCHEMA,
  });
  assert.equal(bad.consistent, false);
  assert.equal(bad.format_violations.length > 0, true);

  const ok = checkUseCaseConsistency({
    promptText: MATCHING_PROMPT + "\n不要输出JSON格式",
    schemaExtensions: DEFAULT_SCHEMA,
  });
  assert.equal(ok.consistent, true);
});

test("reserved tokens are flagged", () => {
  const r = checkUseCaseConsistency({
    promptText: MATCHING_PROMPT + "\n```\nsome fence\n```",
    schemaExtensions: DEFAULT_SCHEMA,
  });
  assert.equal(r.consistent, false);
  assert.equal(r.format_violations.some((v) => v.includes("```")), true);
});

test("optional marker (optional / 可选) does not affect consistency, only inferred required", () => {
  const prompt = MATCHING_PROMPT.replace(
    "SEVERITY: critical|warn|info",
    "SEVERITY: critical|warn|info (optional)",
  );
  const r = checkUseCaseConsistency({
    promptText: prompt,
    schemaExtensions: DEFAULT_SCHEMA,
  });
  assert.equal(r.consistent, true);
  assert.deepEqual(r.prompt_fields, ["severity", "event", "desc"]);
});
