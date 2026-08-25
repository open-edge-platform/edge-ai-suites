<!--
SPDX-FileCopyrightText: (C) 2026 Intel Corporation
SPDX-License-Identifier: Apache-2.0
-->

# Skill Benchmark: metro-ai-apps-builder

**Agents**: Copilot (`claude-opus-4.8`)  
**Grader**: Copilot (`claude-opus-4.8`)  
**Date**: 2026-08-21T16:30:41Z  
**Evals**: 1, 2, 3, 4, 5, 6 (1 run per configuration)

## Summary

> Skill lift = with skill − without skill. ↑ = better, ↓ = higher cost (expected).

### Evals passed

| Agent | w/o skill | w/ skill | Lift |
|---|---|---|---|
| Copilot (`claude-opus-4.8`) | 2 / 6 | 6 / 6 | **+4 ↑** |

### Pass rate (avg ± σ across evals)

| Agent | w/o skill | w/ skill | Lift |
|---|---|---|---|
| Copilot (`claude-opus-4.8`) | 38% ±49% | 100% ±0% | **+62pp ↑** |

### Time (total across all evals)

| Agent | w/o skill | w/ skill | Lift |
|---|---|---|---|
| Copilot (`claude-opus-4.8`) | 108 s | 180 s | +72 s ↓ |

### Tokens (total across all evals)

| Agent | w/o skill | w/ skill | Lift |
|---|---|---|---|
| Copilot (`claude-opus-4.8`) | n/a | n/a | n/a |

## Per-Eval Detail

> Each cell is PASS/FAIL for that run, with the count of expectations met in parentheses (e.g. `PASS (5/5)`); `n/a` means no grading.json was found for that (eval, config, agent) combination.

| Eval | Prompt | Copilot (w/) | Copilot (w/o) |
|---|---|---|---|
| 1 | I want to detect people in my camera feeds and see alerts on a dashboa... | PASS (4/4) | FAIL (0/4) |
| 2 | I want employees to ask questions in plain English against our internal PDFs. | PASS (4/4) | FAIL (1/4) |
| 3 | I have hundreds of recorded videos and want to type a phrase and jump ... | PASS (4/4) | FAIL (0/4) |
| 4 | I have a labeled defect dataset and want a quantized model ready for In... | PASS (4/4) | PASS (4/4) |
| 5 | I want to use AI with my cameras, not sure where to start. | PASS (3/3) | PASS (3/3) |
| 6 | Run the metro-ai-apps-recipe skill to build a smart-parking stack in ./... | PASS (1/1) | FAIL (0/1) |
| | **Mean ±σ** | **100% ±0%** | **38% ±49%** |
