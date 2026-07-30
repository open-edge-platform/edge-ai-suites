<!-- SPDX-FileCopyrightText: (C) 2026 Intel Corporation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Benchmark: onboarding-validation

| Field | Value |
|-------|-------|
| Skill version | 1.12.0 |
| Rules version | 1.4.0 |
| Date | 2026-07-29 |
| Status | Manual validation complete; automated benchmark pending |

## Summary

The skill has been validated through 2 runs against 2 distinct OEP applications using docker-compose deployment. Formal automated benchmark via `skill-creator` Stage 5–7 is pending.

## Validation Results

| Application | Commit | Deployment | Overall Result | UX Score | Date |
|-------------|--------|-----------|----------------|----------|------|
| live-video-captioning | `c645ac49` | docker-compose | CONDITIONAL PASS | 8.7 / 10 — Good | 2026-07-21 |
| handheld-multi-modal | `0bdf172c` | docker-compose | CONDITIONAL PASS | 8.1 / 10 — Good | 2026-07-21 |

## Eval Coverage

| Eval ID | Scenario | Type | Status |
|---------|----------|------|--------|
| 1 | Docker Compose app (metro-ai-suite) | should_trigger | Validated manually |
| 2 | Helm/K8s app (metro-ai-suite) | should_trigger | Not yet executed |
| 3 | Debugging request (negative) | should_not_trigger | Defined |
| 4 | Submodule app (retail-ai-suite) | should_trigger | Not yet executed |
| 5 | Code review request (negative) | should_not_trigger | Defined |
| 6 | Skill integrity self-test (negative trigger) | should_not_trigger | Defined |

## Eval coverage policy

Evals cover classes of skill behavior (docker-compose, Helm/K8s, submodule, two negative trigger cases, and self-test integrity), not inventory of applications. All `should_trigger` scenarios are instances of one parameterized prompt template (`example-prompts/01-validate-onboarding.md`), so the eval set does not grow with the number of validated applications.

## Skill Integrity Checks

| Check | Method | Result |
|-------|--------|--------|
| All reference files reachable from SKILL.md | `scripts/self-test.sh` | PASS |
| All relative links in SKILL.md resolve | `scripts/self-test.sh` | PASS |
| Report format contract honoured | `scripts/self-test.sh` (golden fixture) | PASS |
| Structure & spec compliance | `skill-validator check` | PASS |
| Instruction quality (clarity / actionability / novelty) | `skill-validator score evaluate` | *(result)* |
