// SPDX-FileCopyrightText: (C) 2026 Intel Corporation
// SPDX-License-Identifier: Apache-2.0

import assert from "node:assert/strict";
import { test } from "node:test";
import { planLevels } from "@smart-community-video/tools";

// Deployment limits from docker/set_env.sh + config.yaml's summary_service block.
const MAX_HOP_RATIO = 10;
const LIMITS = { modelContext: 61440, maxOutputTokens: 1024, maxHopRatio: MAX_HOP_RATIO };
// Mirrors SUMMARY_HEADER_TOKENS in generate-report.ts.
const SUMMARY_HEADER_TOKENS = 24;

const CUE_TEXT =
  "[task:restless:warn] 03:12:44 severity: warn\nevent: restless\n" +
  "desc: 老人在床上翻身，随后坐起并离开卧室，约两分钟后返回床边坐下，未见跌倒或呼救迹象。";

function srtOf(cues: number, text = CUE_TEXT): string {
  return Array.from({ length: cues }, (_, i) => `${i + 1}\n00:00:00,000 --> 00:00:01,000\n${text}\n`).join("\n");
}

function estimateTokens(text: string): number {
  let cjk = 0;
  for (const c of text) {
    const cp = c.codePointAt(0)!;
    if (cp >= 0x4e00 && cp <= 0x9fff) cjk++;
  }
  return Math.floor((cjk / 1.5 + (text.length - cjk) / 4) * 1.3);
}

/** Per-hop ratio and input size, measuring level 1 in cue text and the rest in summaries. */
function walk(cues: number, levelSizes: number[], out: number, text = CUE_TEXT) {
  const hops: { ratio: number; input: number }[] = [];
  let remaining = cues;
  let calls = 0;
  let unit = estimateTokens(text);
  for (let level = 1; level < levelSizes.length; level++) {
    const size = levelSizes[level] === -1 ? remaining : levelSizes[level];
    hops.push({ ratio: (size * unit) / out, input: size * unit });
    remaining = Math.ceil(remaining / size);
    calls += remaining;
    unit = out + SUMMARY_HEADER_TOKENS;
  }
  return { hops, calls };
}

const PERIODS = [330, 623, 1103, 4392]; // daily → monthly, as seen in logs/reports/

test("no hop is asked to compress more than a call can do well", () => {
  for (const cues of PERIODS) {
    const { hops } = walk(cues, planLevels(srtOf(cues), cues, LIMITS).levelSizes, LIMITS.maxOutputTokens);
    for (const hop of hops) {
      assert.ok(hop.ratio <= MAX_HOP_RATIO + 0.01, `${cues} cues: a hop compresses ${hop.ratio.toFixed(1)}:1`);
    }
  }
});

test("level 1 saturates the ratio limit instead of splitting the loss evenly", () => {
  for (const cues of PERIODS) {
    const { hops } = walk(cues, planLevels(srtOf(cues), cues, LIMITS).levelSizes, LIMITS.maxOutputTokens);
    assert.ok(
      hops[0].ratio > MAX_HOP_RATIO * 0.9,
      `${cues} cues: level 1 only reaches ${hops[0].ratio.toFixed(1)}:1 of the allowed ${MAX_HOP_RATIO}:1`,
    );
    // Widening level 1 is free — it lowers every rung above it too.
    assert.ok(hops.slice(1).every((h) => h.ratio <= hops[0].ratio + 0.01), "rungs above must be gentler");
  }
});

test("SRT scaffolding is excluded — only the text the service feeds the model counts", () => {
  const cues = 1103;
  const plain = planLevels(srtOf(cues), cues, LIMITS).levelSizes;
  // Same cue text, much heavier index/timestamp lines. The service parses both off,
  // so the plan must not react to them.
  const padded = Array.from(
    { length: cues },
    (_, i) => `${String(i + 1).padStart(12, "0")}\n01:02:03,456 --> 01:02:04,567\n${CUE_TEXT}\n`,
  ).join("\n");
  assert.deepEqual(planLevels(padded, cues, LIMITS).levelSizes, plain);
});

test("no call's input exceeds the context", () => {
  for (const cues of PERIODS) {
    const { hops } = walk(cues, planLevels(srtOf(cues), cues, LIMITS).levelSizes, LIMITS.maxOutputTokens);
    for (const hop of hops) {
      assert.ok(hop.input < LIMITS.modelContext, `${cues} cues: a call reads ${Math.round(hop.input)} tokens`);
    }
  }
});

test("a short timeline is read in one call", () => {
  const { levels, levelSizes } = planLevels(srtOf(120), 120, LIMITS);
  assert.equal(levels, 2);
  assert.deepEqual(levelSizes, [1, -1]);
});

test("more output bandwidth per rung buys a cheaper tree", () => {
  const cues = 1103;
  const srt = srtOf(cues);
  const calls = [512, 1024, 2048].map(
    (out) => walk(cues, planLevels(srt, cues, { ...LIMITS, maxOutputTokens: out }).levelSizes, out).calls,
  );
  assert.deepEqual(calls, [...calls].sort((a, b) => b - a), `calls ${calls} should fall as DEFAULT_MAX_TOKENS rises`);
});

test("a tight context is absorbed by a taller tree, not by an oversized call", () => {
  const cues = 4392;
  const srt = srtOf(cues);
  const small = { modelContext: 8192, maxOutputTokens: 512 };
  const { levels, levelSizes } = planLevels(srt, cues, small);
  assert.ok(levels > planLevels(srt, cues, LIMITS).levels, "should add rungs rather than widen groups");
  for (const hop of walk(cues, levelSizes, small.maxOutputTokens).hops) {
    assert.ok(hop.input < small.modelContext, `a call reads ${Math.round(hop.input)} of ${small.modelContext}`);
  }
});

test("max_hop_ratio scales the level-1 group directly", () => {
  const cues = 1103;
  const srt = srtOf(cues);
  const at = (ratio: number) => planLevels(srt, cues, { ...LIMITS, maxHopRatio: ratio }).levelSizes[1];
  const [g10, g15] = [at(10), at(15)];
  assert.ok(Math.abs(g15 / g10 - 1.5) < 0.05, `group should track the ratio: ${g10} → ${g15}`);
  for (const hop of walk(cues, planLevels(srt, cues, { ...LIMITS, maxHopRatio: 15 }).levelSizes, LIMITS.maxOutputTokens).hops) {
    assert.ok(hop.ratio <= 15.01, `a hop compresses ${hop.ratio.toFixed(1)}:1 past the configured 15:1`);
  }
});

test("an empty timeline still yields a valid plan", () => {
  const { levels, levelSizes } = planLevels("", 0, LIMITS);
  assert.equal(levelSizes.length, levels);
});
