<!--
SPDX-FileCopyrightText: (C) 2026 Intel Corporation
SPDX-License-Identifier: Apache-2.0
-->

# Multimodal Weld Defect Detection Skills

Agent skills for the **Multimodal Weld Defect Detection** sample application.
Each skill teaches the agent how to drive the app through its real
interfaces — the `Makefile`, Docker Compose, Helm, and the
`tests/functional/` pytest suite — so common tasks run the same way every
time.

These skills live under `.github/skills` as the canonical cross-harness
location. They are plain Markdown workflows and can be used by Codex, Copilot
CLI, Claude Code, Cursor, or local agent scripts.

A skill is a directory with a `SKILL.md` (YAML front matter + workflow) and
optional `references/` (deep docs loaded only when needed), `scripts/`
(helpers the agent runs), and `example-prompts/` (sample invocations).

## Cross-Harness Discovery

- All agents should start at [`../copilot-instructions.md`](../copilot-instructions.md).
- Root-level agents should use [`../../AGENTS.md`](../../AGENTS.md) as a router.
- Claude agents should use [`../../CLAUDE.md`](../../CLAUDE.md) as a router.
- Cursor agents should start at
  [`../../.cursor/rules/multimodal.mdc`](../../.cursor/rules/multimodal.mdc).
- Tools that prefer structured metadata should read
  [`skill-catalog.json`](./skill-catalog.json).
- All catalog paths are relative to the repository root.

## Catalog

| Skill | Use it when the user wants to… | Backed by |
|---|---|---|
| [`multimodal-deploy`](./multimodal-deploy/SKILL.md) | build / deploy / smoke-test / functionally test the app via Docker Compose or Helm | `Makefile` + `scripts/smoke-check.sh` + `scripts/run-functional-tests.sh` |

## Conventions

- **Run commands yourself** and relay actual output; don't ask the user to
  run them unless a host blocker is detected (e.g., Docker/K8s unreachable).
- **Preflight before acting.** Check `docker info` / `kubectl cluster-info`
  before any deploy workflow; report blockers plainly instead of stalling.
- Never invent Make targets, flags, ports, or env vars — ground answers in
  the live `Makefile`, compose files, and `helm/values.yaml`.

## Keeping Skills in Sync

**Update `multimodal-deploy` (SKILL.md + `references/` + `scripts/`) whenever
the Makefile, compose files, Helm chart, `.env` schema, or functional test
suite change.** Keep this README's catalog table and `skill-catalog.json`
description/triggers in sync with each `SKILL.md`. See
[`../copilot-instructions.md`](../copilot-instructions.md#keeping-agent-guidance-in-sync)
for the full maintenance contract.
