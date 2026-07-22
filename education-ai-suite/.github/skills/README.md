# Smart Classroom RAG — Skills

Agent skills for the Smart Classroom RAG Flutter application. Each skill teaches
the agent how to drive the system by executing commands directly and using the
Content Search REST API — so common tasks run the same way every time.

These skills live under `.github/skills/` as the shared location usable by
GitHub Copilot, Claude Code, Cursor, OpenAI Codex, and any local agent script.
Because they are plain Markdown with no tool-specific syntax, the same skill
file works identically regardless of which AI tool loads it.

A skill is a directory containing:
- `SKILL.md` — YAML front matter (name, description, triggers) + the workflow body
- `references/` (optional) — deep-dive reference docs loaded only when the skill points to them
- `scripts/` (optional) — PowerShell helpers the agent runs directly

---

## Cross-Harness Discovery

- All agents start at [`../copilot-instructions.md`](../copilot-instructions.md).
- Tools that prefer structured metadata read [`skill-catalog.json`](./skill-catalog.json).
- All catalog paths are relative to the repository root (`education-ai-suite/`).
- Keep the skill body in one place: update each `SKILL.md`, then keep the catalog description and triggers in sync.

---

## Catalog

| Skill | Purpose | Key interfaces |
|---|---|---|
| `sc-setup` | One-time setup of Flutter deps + Python venv | `flutter create`, `flutter pub get`, `python -m venv` |
| `sc-up` | Start the backend and Flutter app together | Direct Python + Flutter commands |
| `sc-doctor` | Health check, connectivity debug, backend logs | `GET /api/v1/system/health`, Python venv |
| `sc-upload` | Upload a file and poll until ingestion completes | `POST /api/v1/object/upload-ingest`, `GET /api/v1/task/query/{id}` |
| `sc-qa` | Ask a multi-turn RAG question against indexed content | `POST /api/v1/object/qa` |
| `sc-files` | List, filter, delete indexed files; list tags | `GET /api/v1/object/files/list`, `GET /api/v1/object/tags`, `DELETE /api/v1/object/files/{file_hash}` |

---

## Conventions

- **Agent: execute all commands directly** using your terminal tool and relay the
  result to the user. Do not print commands for the user to copy-paste — the
  entire point of these skill files is that the agent drives the workflow
  autonomously. Only hand a command to the user when a skill step explicitly
  requires their interactive shell (e.g. typing a secret).
- Probe before acting. Hit `GET /api/v1/system/health` before any API workflow; if it fails, route to `sc-up` or `sc-doctor`.
- The backend API base URL is `http://127.0.0.1:9011` (or whatever `CONTENT_SEARCH_API_URL` is set to in `utils/flutter/assets/.env`).
- Run repo-local commands from the repository root (`education-ai-suite/`) unless a skill says otherwise.
- Run Flutter commands from `utils/flutter/`.
