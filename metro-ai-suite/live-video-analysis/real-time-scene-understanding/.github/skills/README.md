<!--
SPDX-FileCopyrightText: (C) 2026 Intel Corporation
SPDX-License-Identifier: Apache-2.0
-->

# Real Time Scene Understanding Skills

Agent skills for the **Real Time Scene Understanding** sample application.
Each skill teaches an AI coding assistant how to work with the project's real
interfaces: `scripts/setup_env.sh`, Docker Compose, the FastAPI health endpoint,
OpenVINO models, and the Python test suite.

These skills live under `.github/skills` as the project-local location for
GitHub Copilot, Claude, Cursor, and other compatible AI agents. They are plain
Markdown workflows. A skill is a directory with a `SKILL.md` entry point and
may later include optional `references/`, `scripts/`, or `evals/` directories
when a workflow needs deeper documentation, runnable helpers, or checks.

## What's in Here

The skills package the project knowledge needed for common operational and
development tasks. They are grounded in the actual repository structure,
`compose.yaml`, `app/pyproject.toml`, user guides, API routes, and model layout.

## Catalog

| Skill | Use it when you want to... |
|---|---|
| [`rtsu-deployment`](./rtsu-deployment/SKILL.md) | Configure the environment, validate Compose, build images, start or stop the stack, inspect service state, and verify `/api/health`. |
| [`rtsu-troubleshooting`](./rtsu-troubleshooting/SKILL.md) | Diagnose dashboard, API, RTSP, WebRTC, model, device, SeaweedFS, or container failures. |
| [`rtsu-testing`](./rtsu-testing/SKILL.md) | Install test dependencies, run focused tests, run the full `app/tests/` suite, collect coverage, and validate runtime changes. |

The canonical agent instructions in
[`../copilot-instructions.md`](../copilot-instructions.md) route tasks to these
skills. The root [`AGENTS.md`](../../AGENTS.md), [`CLAUDE.md`](../../CLAUDE.md),
and Cursor rule file route each AI tool to the canonical instructions.

## How Skills Are Used

Normally, describe the task in natural language. The AI assistant should select
the relevant skill based on the request. You can also name a skill explicitly
when you want to make the intended workflow clear.

| You say... | Skill to use |
|---|---|
| "Start the application and check that it is healthy." | [`rtsu-deployment`](./rtsu-deployment/SKILL.md) |
| "Build the Docker image from source." | [`rtsu-deployment`](./rtsu-deployment/SKILL.md) |
| "The dashboard is not reachable." | [`rtsu-troubleshooting`](./rtsu-troubleshooting/SKILL.md) |
| "The RTSP stream connects but WebRTC video does not play." | [`rtsu-troubleshooting`](./rtsu-troubleshooting/SKILL.md) |
| "The deep analyzer cannot process video." | [`rtsu-troubleshooting`](./rtsu-troubleshooting/SKILL.md) |
| "Run the tests for the frame registry." | [`rtsu-testing`](./rtsu-testing/SKILL.md) |
| "Run the full test suite." | [`rtsu-testing`](./rtsu-testing/SKILL.md) |
| "Check coverage after this backend change." | [`rtsu-testing`](./rtsu-testing/SKILL.md) |

The testing workflow runs focused tests first and then the complete suite with:

```bash
cd app
uv run pytest
```

If a skill is not selected automatically, say, for example, "Use the
`rtsu-troubleshooting` skill and investigate the failing health check."

## Project-Local Use

The skills are already stored in this repository, so no copying or separate
installation is needed for an agent that supports project-local skills. Start a
new agent session after adding or changing skills so the agent can rediscover
them.

All workflows assume:

- Commands run from the repository root unless the skill says to enter `app/`.
- Secrets, access keys, tokens, model weights, and `.env` contents remain private.
- Runtime claims are verified with `docker compose ps`, logs, focused checks, or
  `http://localhost:${PORT:-9100}/api/health` as appropriate.

## Skill Structure

```text
.github/skills/
├── README.md
├── rtsu-deployment/
│   └── SKILL.md
├── rtsu-troubleshooting/
│   └── SKILL.md
└── rtsu-testing/
    └── SKILL.md
```

Keep each workflow focused. Put common project policy in
[`../copilot-instructions.md`](../copilot-instructions.md), and add detailed
references or scripts to a skill only when they provide reusable value.