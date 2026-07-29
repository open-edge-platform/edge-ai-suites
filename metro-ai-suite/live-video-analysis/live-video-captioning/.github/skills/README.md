<!--
SPDX-FileCopyrightText: (C) 2026 Intel Corporation
SPDX-License-Identifier: Apache-2.0
-->

# LVC Skills

Agent skills for the **Live Video Captioning (LVC)** sample application. Each
skill teaches the agent how to drive LVC through its real interfaces — the
Docker Compose stack, the model download helper, and the FastAPI `/api/...` REST
API — so common tasks run the same way every time.

These skills live under `.github/skills` as the canonical cross-harness
location. They are plain Markdown workflows and can be used by Codex, Copilot
CLI, Claude Code, Cursor, or local agent scripts.

A skill is a directory with a `SKILL.md` (YAML front matter + workflow) and
optional `references/` (deep docs loaded only when needed), `scripts/` (helpers
the agent runs), and `eval/` (behaviour checks).

## Cross-Harness Discovery

- All agents should start at
  [../copilot-instructions.md](../copilot-instructions.md).
- Root-level agents should use [../../AGENTS.md](../../AGENTS.md) as a router.
- Claude agents should use [../../CLAUDE.md](../../CLAUDE.md) as a router.
- Cursor agents should start at
  [../../.cursor/rules/lvc.mdc](../../.cursor/rules/lvc.mdc).
- Tools that prefer structured metadata should read
  [skill-catalog.json](./skill-catalog.json).
- All catalog paths are relative to the repository root.
- Keep the skill body in one place: update each `SKILL.md`, then keep the
  catalog description and triggers in sync.

## Catalog

| Skill | Use it when the user wants to… | Backed by |
|---|---|---|
| [`lvc-run-app`](./lvc-run-app/SKILL.md) | run / start / smoke-test the stack, drive a captioning run, verify the dashboard | `compose.yaml` + `lvc-run-app/smoke.sh` driver |
| [`lvc-test`](./lvc-test/SKILL.md) | run the backend unit suite, check coverage | `pytest` in `app/` |

## Conventions

- **Run commands yourself** and relay results; don't ask the user to run them.
- **Probe before acting.** Hit `GET /api/health` before any API workflow; if it
  fails, route to `lvc-run-app`.
- Endpoints assume the dashboard port `4173` and the `/api/...` prefix.
- Always `curl --noproxy '*'` for localhost calls.
- Run repo-local commands from the repository root unless a skill says
  otherwise (the test suite runs from `app/`).
