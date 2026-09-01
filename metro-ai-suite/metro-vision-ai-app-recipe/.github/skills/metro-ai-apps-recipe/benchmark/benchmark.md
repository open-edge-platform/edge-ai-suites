<!--
SPDX-FileCopyrightText: (C) 2026 Intel Corporation
SPDX-License-Identifier: Apache-2.0
-->

# Skill Benchmark: metro-ai-apps-recipe

**Agents**: Copilot (`claude-opus-4.8`)
**Grader**: Copilot (`claude-opus-4.8`)
**Date**: 2026-08-21T15:50:41Z
**Evals**: 1, 2, 3, 4, 5 (1 run per configuration)

## Summary

> Skill lift = with skill − without skill. ↑ = better, ↓ = higher cost (expected).

### Evals passed

| Agent | w/o skill | w/ skill | Lift |
|---|---|---|---|
| Copilot (`claude-opus-4.8`) | 1 / 5 | 5 / 5 | **+4 ↑** |

### Pass rate (avg ± σ across evals)

| Agent | w/o skill | w/ skill | Lift |
|---|---|---|---|
| Copilot (`claude-opus-4.8`) | 60% ±31% | 100% ±0% | **+40pp ↑** |

### Time (total across all evals)

| Agent | w/o skill | w/ skill | Lift |
|---|---|---|---|
| Copilot (`claude-opus-4.8`) | 1077 s | 1576 s | +499 s ↓ |

### Tokens (total across all evals)

| Agent | w/o skill | w/ skill | Lift |
|---|---|---|---|
| Copilot (`claude-opus-4.8`) | 6.2M | 10.6M | +4.4M ↓ |

## Per-Eval Detail

> Each cell is PASS/FAIL for that run, with the count of expectations met in parentheses (e.g. `PASS (5/5)`); `n/a` means no grading.json was found for that (eval, config, agent) combination.

| Eval | Prompt | Copilot (w/) | Copilot (w/o) |
|---|---|---|---|
| 1 | Build a full end-to-end CV analytics stack in ./person-detect-stack/ for perso... | PASS (5/5) | FAIL (4/5) |
| 2 | Build a PPE-compliance stack in ./ppe-compliance-stack/ for hardhat detection ... | PASS (5/5) † | FAIL (1/5) |
| 3 | Build a smart-parking occupancy stack in ./smart-parking-stack/ for vehicle de... | PASS (4/4) † | FAIL (2/4) |
| 4 | Build a multi-camera Scenescape spatial-analysis stack in ./intersection-scene... | PASS (4/4) | FAIL (2/4) |
| 5 | Set up a Prometheus + OpenTelemetry metrics and tracing stack for a cloud-host... | PASS (3/3) | PASS (3/3) |
| | **Mean ±σ** | **100% ±0%** | **60% ±31%** |
