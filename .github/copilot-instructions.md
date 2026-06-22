# Copilot Instructions for edge-ai-suites

## Repository Overview

This is a monorepo containing multiple Intel Edge AI Suites, each in its own top-level directory:

- `education-ai-suite/` — Smart classroom application
- `federal-aerospace/` — Deterministic threat detection, handheld multi-modal
- `health-and-life-sciences-ai-suite/` — NICU Warmer, multi-modal patient monitoring
- `manufacturing-ai-suite/` — Industrial edge insights (vision, time-series, multimodal), HMI augmented worker
- `metro-ai-suite/` — Smart NVR, live video analysis, smart traffic, agentic RAG, VMS adapter, etc.
- `retail-ai-suite/` — Loss prevention, order accuracy, voice-enabled interactions
- `robotics-ai-suite/` — ROS2-based components (SLAM, mapping, object detection, multicam)

### Navigation

When working on a specific component, check for a local `AGENTS.md` file first — it contains authoritative per-component instructions:
- [federal-aerospace/apps/handheld-multi-modal/AGENTS.md](../federal-aerospace/apps/handheld-multi-modal/AGENTS.md)
- [metro-ai-suite/metro-sdk-manager/AGENTS.md](../metro-ai-suite/metro-sdk-manager/AGENTS.md)
- [metro-ai-suite/live-video-analysis/live-video-captioning/AGENTS.md](../metro-ai-suite/live-video-analysis/live-video-captioning/AGENTS.md)
- [manufacturing-ai-suite/industrial-edge-insights-vision/win-vision-ai/.github/copilot-instructions.md](../manufacturing-ai-suite/industrial-edge-insights-vision/win-vision-ai/.github/copilot-instructions.md)

Each suite directory has its own `README.md` with suite-level context. Each sub-project within a suite has its own `README.md` with setup and usage details.

## Languages & Frameworks

- **Primary language:** Python (FastAPI, Gradio, LangChain, OpenVINO, PyTorch)
- **Secondary:** C++ (robotics-ai-suite ROS2 components), Bash (deploy scripts, test harnesses)
- **Frontend:** JavaScript/TypeScript (React, Vite) for UI components
- **Infrastructure:** Docker, Docker Compose, Helm, Kubernetes
- **ML/AI:** OpenVINO, OVMS (OpenVINO Model Server), HuggingFace, Intel DL Streamer

## Build Systems

- **Make** is the standard build orchestrator. Every suite and most sub-projects have a `Makefile`; run `make help` to list all available targets for a component.
- **Docker Compose** (`docker compose`) is the deployment mechanism. Projects use `docker-compose.yml` / `docker-compose.yaml` with `.env` files for configuration.
- **Helm** charts are provided for Kubernetes deployment (found in `helm/` directories).
- **Python packaging:** Mix of `requirements.txt`, `pyproject.toml` (with setuptools or uv), and `pip`.
- **ROS2 (robotics):** `colcon build` with CMakeLists.txt and Debian packaging via `dpkg-buildpackage`.

## Testing Patterns

- **Framework:** pytest (Python), Google Test (C++), Robot Framework (manufacturing-ai-suite/vision)
- **Structure:** `tests/` directory at project root, with `tests/unit/` and `tests/functional/` or `tests/integration/` subdirectories
- **Config:** `pytest.ini` or `[tool.pytest.ini_options]` in `pyproject.toml`
- **Async:** `pytest-asyncio` with `asyncio_mode = "auto"`
- **Fixtures:** Shared in `conftest.py` files; environment-based configuration via `monkeypatch.setenv`
- **Naming:** `test_*.py` files, `Test*` classes, `test_*` functions
- **Markers:** `@pytest.mark.unit`, `@pytest.mark.mqtt`, `@pytest.mark.opcua`, `@pytest.mark.gpu`, `@pytest.mark.longrun`

## Linting & Formatting

- **Ruff** (lint + format) — configured via `pyproject.toml` or `.pre-commit-config.yaml`
- **super-linter** (Docker-based) — used by robotics-ai-suite; validates YAML, JSON, Python (pylint/flake8), Bash, Markdown, clang-format
- **ShellCheck** — for all `.sh` files
- **pre-commit** hooks: trailing-whitespace, end-of-file-fixer, check-yaml, check-json, mypy, ruff, shellcheck, helmlint
- **Bandit** — Python security static analysis

## Docker Patterns

- Multi-stage Dockerfiles common across suites
- Base images typically from `intel/` registry or `openvino/` images
- `COPYLEFT_SOURCES` build arg pattern for including source of copyleft dependencies
- `.env` files for credentials and configuration (never commit secrets)
- Device mounting patterns: `/dev/dri` (GPU), `/dev/accel` (accelerators)
- Image tagging: `REGISTRY/component:TAG` with pinned version tags (for example `2026.1.0`) in production; avoid `:latest`

## CI/CD Workflows

- GitHub Actions in `.github/workflows/`
- Per-suite and per-component workflows triggered on path-based changes
- Common patterns: path filtering with `dorny/paths-filter`, pinned action SHAs, `persist-credentials: false`
- Scans: Trivy (container + filesystem), Gitleaks (secrets), Bandit (Python security), ClamAV (antivirus), ShellCheck
- Dependabot configured for dependency updates

## License Conventions

**All generated source files must include both lines below** using language-appropriate comment syntax:

```
# SPDX-FileCopyrightText: (C) <YEAR> Intel Corporation
# SPDX-License-Identifier: Apache-2.0
```

- Use the current year. Preserve the exact SPDX field names — do not paraphrase them.
- For file types that cannot contain comments (for example, binaries), use REUSE-compliant metadata in the component `LICENSES/` directory.

## Agent Behavior

### Scope
- **Stay within the component being asked about.** Do not modify files outside the active suite or sub-project unless explicitly instructed.
- Before editing, read the target file and the local `README.md`. If a local `AGENTS.md` exists, treat it as the authoritative override for that component.
- Do not add features, refactor code, introduce new dependencies, or change APIs beyond what was directly requested.

### Context management
- This is a large monorepo. Load only files relevant to the current task; do not speculatively read files from other suites.
- Prefer `make help` to discover available targets rather than listing all Makefiles.
- Prefer targeted `grep`/search over reading entire directories.

## Key Conventions

1. **Environment variables** drive configuration — use `.env` files, never hardcode secrets
2. **Intel GPU support** — code should handle GPU/CPU/NPU device selection via env vars (e.g., `VLM_TARGET_DEVICE`)
3. **OpenVINO** is the inference runtime — models are typically in IR format (.xml/.bin)
4. **OVMS** (OpenVINO Model Server) serves models via OpenAI-compatible API
5. **Docker is required** — all apps run containerized; `make deploy` is the standard entry point
6. **Security scanning** is mandatory — Trivy, Bandit, Gitleaks, ShellCheck run in CI
7. **No `:latest` tags** in production Docker image references — pin versions
8. **Proxy awareness** — many scripts support `HTTP_PROXY`/`HTTPS_PROXY`/`NO_PROXY`
9. **Shell strict mode** — use `set -euo pipefail` for Bash scripts (`#!/usr/bin/env bash`), and POSIX-safe strict mode (`set -eu`) for `sh` scripts
10. **HuggingFace models** downloaded at runtime via `HF_TOKEN` environment variable

## Security

### General Guardrails (Always-On)

- Prefer least privilege across code, services, identities, file permissions, APIs, containers, and workflows.
- Treat all external input as untrusted; validate format, type, range, and length at trust boundaries.
- Never hard-code secrets, credentials, keys, tokens, or passwords anywhere; use environment variables only.
- Avoid exposing sensitive data in logs, traces, errors, metrics, or test artifacts.
- Prefer trusted, actively maintained dependencies and images; pin versions.
- Do not suggest bypassing or weakening existing security checks or validations.
- Fail safely and visibly; be explicit about assumptions and limitations.

### Codebase-Specific Guardrails

**Python**
- Never use `subprocess(..., shell=True)` with any external or user-controlled input; always pass a list: `subprocess.run([cmd, arg], shell=False)`.
- Never use `eval()`, `exec()`, or `pickle.loads()` on untrusted data.
- In FastAPI services, validate all request bodies with Pydantic models — never accept raw `dict` or unvalidated JSON.
- Use `secrets` module or environment variables for token generation; never use `random` for security-sensitive values.

**Docker / Containers**
- All Dockerfiles must include a non-root `USER` directive before the final `CMD`/`ENTRYPOINT`.
- Never use `--privileged`, `--cap-add=ALL`, or `--network=host` in Compose or runtime commands without explicit justification.
- Never use `pip install --trusted-host`, `--no-verify`, or unauthenticated `--index-url` sources.
- Never log, print, or `echo` `.env` file contents; never commit `.env` files.

**Shell scripts**
- Never construct shell commands by interpolating unvalidated variables; quote all variables: `"$var"`.
- Use `set -euo pipefail` (bash) or `set -eu` (sh); never use `set +e` to swallow errors silently.

**Helm / Kubernetes**
- Never set `hostNetwork: true`, `privileged: true`, or `runAsUser: 0` in pod specs without a documented exception.
- Pin all image tags in Helm `values.yaml`; avoid `:latest`.

**CI/CD**
- Pin all GitHub Actions to full commit SHAs, not tags.
- Never use `persist-credentials: true` unless required; scope tokens to minimum permissions.

### AI Output Trust Model

Treat AI-generated output as **untrusted draft code** until reviewed and tested.
Reject suggestions that bypass security controls for convenience or introduce unsafe defaults.

Load [`.github/skills/security.md`](skills/security.md) when changes touch authentication, authorization, input parsing, secrets, Dockerfiles, Helm charts, or CI workflows.

## Contributing

See [`CONTRIBUTING.md`](../CONTRIBUTING.md) for PR guidelines and commit signing requirements.
Partial cloning is supported — you can clone just the suite you're working on (see [Contributing to Open Edge Platform](https://docs.openedgeplatform.intel.com/canonical/OEP-articles/contribution-guide.html#repository-cloning-partial-cloning)).
