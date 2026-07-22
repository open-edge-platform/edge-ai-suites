# Smart Classroom RAG — AI Agents

## Canonical Instructions

Use this file as the canonical router for all coding agents. 

---

## What This Repo Is

Smart Classroom application provides an AI-powered educational platform for
teachers and students. It includes video analytics, OCR, ASR, content search
with RAG capabilities, and a web UI for interaction.

The system has multiple tiers:

- **Backend Services** — `smart-classroom/` — Python-based services for video
  processing, OCR, ASR, and content management (port 8000)
- **Content Search backend** — `smart-classroom/content_search/` — a Python
  FastAPI service that handles file storage, vector indexing, and LLM-powered Q&A
  (runs on port `9011` by default)
- **Frontend UI** — `smart-classroom/ui/` — React-based web interface (port 5173)
- **Flutter UI** — `utils/flutter/` — a cross-platform app (Windows, Web) built
  with Flutter + Riverpod for content search interactions

---

## Architecture 

The Content Search service provides a RAG API at `http://127.0.0.1:9011`:

| Purpose | Endpoint |
|---|---|
| Health check | `GET /api/v1/system/health` |
| Upload + ingest | `POST /api/v1/object/upload-ingest` (multipart) |
| Task status | `GET /api/v1/task/query/{task_id}` |
| Cleanup task | `DELETE /api/v1/object/cleanup-task/{task_id}` |
| Q&A (multi-turn RAG) | `POST /api/v1/object/qa` |
| Tags list | `GET /api/v1/object/tags` |
| Files list | `GET /api/v1/object/files/list` |
| Delete file | `DELETE /api/v1/object/files/{file_hash}` |

---

## Repository Map

| Path | Purpose |
|---|---|
| `.github/skills/` | Workflow skills — automation for setup, startup, and operations |
| `smart-classroom/` | Main Python services (backend, video analytics, OCR, ASR) |
| `smart-classroom/content_search/` | Python RAG backend (FastAPI) |
| `utils/flutter/setup.ps1` | Setup script for Flutter integration |
| `utils/flutter/start.ps1` | Startup script for Flutter app and backend |
| `smart-classroom/ui/` | React frontend |
| `utils/flutter/` | Flutter app for content search interactions |
| `smart-classroom/content_search/venv_content_search/` | Python virtual environment (created during setup) |

---

## Tech Stack

- **Backend**: Python 3.12, FastAPI, OpenVINO
- **Frontend**: React, Vite, Node.js v18+
- **Flutter**: Flutter 3.22+ / Dart 3.3+, Dio (HTTP), Riverpod (state management)
- **Infrastructure**: FFmpeg, DL Streamer

---

## Conventions

- Run commands from the **repository root** (`education-ai-suite/`) unless specified
- The Flutter app root is `utils/flutter/` — run `flutter` commands from there
- **Setup and startup for Flutter integration use PowerShell scripts**:
  `setup.ps1` and `start.ps1` in `utils/flutter/`
- Skills invoke these scripts rather than executing commands directly
- Target `http://127.0.0.1:9011` for the Content Search API
- Target `http://127.0.0.1:8000` for the main backend API
- Every new source/config file carries the SPDX header used across the repo

---

## Skills

Reusable workflow skills live under [.github/skills/](./skills/). Use
[.github/skills/skill-catalog.json](./skills/skill-catalog.json) to pick
the relevant skill, then read that skill's `SKILL.md`.

| Task | Skill |
|---|---|
| One-time setup: install dependencies and configure system | `sc-setup` |
| Start all services (backend, content search, frontend) | `sc-up` |
| Check health, debug backend connectivity | `sc-doctor` |
| Upload and ingest a file, poll until indexed | `sc-upload` |
| Ask a question via the RAG Q&A endpoint | `sc-qa` |
| List, inspect, or delete indexed files; list tags | `sc-files` |

---

## Skill Loading Rules

- Load only the skill needed for the current request
- Use a skill's `references/` files only when its `SKILL.md` points to them
- **Skills use PowerShell scripts**: They invoke the setup/start scripts
  documented in each skill file rather than executing unrelated workflows
- **Agent: execute skill instructions** by running the PowerShell scripts and
  relaying the output to the user
- Probe `GET /api/v1/system/health` before any API workflow. If the backend is
  unreachable, use `sc-doctor` or `sc-up`
