---
# SPDX-FileCopyrightText: (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
name: multimodal-deploy
description: >-
  Build, deploy, smoke-check, and functionally test the Multimodal Weld
  Defect Detection sample application (industrial-edge-insights-multimodal)
  via its Makefile-driven Docker Compose and Helm paths. Use this skill for
  quick build/deploy/teardown cycles, variant selection (default, vLLM,
  agentic), hardware/model prerequisite checks, and running the existing
  tests/functional pytest suites. Do not use this skill for application code
  changes, unrelated components, or production rollout decisions.
license: Apache-2.0
compatibility: >-
  Requires a bash-compatible shell, Docker + Docker Compose v2, make, and curl
  for the Docker Compose path. The Helm path additionally requires a reachable
  Kubernetes cluster, kubectl, and helm. Functional tests additionally require
  Python 3 and the packages in tests/requirements.txt.
metadata:
  author: open-edge-platform
  version: "1.0.0"
  tags: deployment, docker-compose, helm, manufacturing, multimodal, weld-defect-detection
allowed-tools: bash make docker helm kubectl pytest
---

# Multimodal Weld Defect Detection — Deploy Skill

Drive **industrial-edge-insights-multimodal** builds, deployments, smoke
checks, and functional tests through its real `Makefile`, `docker-compose*.yml`
files, and `tests/functional/` pytest suite. Ground every answer in those
files — do not invent Make targets, flags, ports, or env vars. **Run the
commands yourself and relay actual output**; never fabricate results.

Scope: this skill only applies to
`manufacturing-ai-suite/industrial-edge-insights-multimodal`. The companion
component `industrial-edge-insights-time-series` has its own
`time-series-deploy` skill — do not mix the two.

## Normative references

- `references/command-reference.md` — full Make target catalogue (source of
  truth for every command/flag used below; re-derive from the live Makefile
  if it ever disagrees with this doc).
- `references/functional-tests.md` — mapping of test files to deployment
  method/hardware.

## Step 0: Locate the app root and preflight

1. Resolve the app root: walk up from cwd, or ask git
   (`git rev-parse --show-toplevel`) for the enclosing repo and look for
   `manufacturing-ai-suite/industrial-edge-insights-multimodal/Makefile`.
   `cd` into that directory before running any command below.
2. Confirm `.env` exists (copy/adjust from repo conventions if missing — do
   not invent credentials; ask the user for required secrets such as
   `INFLUXDB_PASSWORD`, `VISUALIZER_GRAFANA_PASSWORD`,
   `MTX_WEBRTCICESERVERS2_0_PASSWORD`, `S3_STORAGE_PASSWORD` if unset).
3. Run a bounded Docker/K8s preflight depending on the chosen path:
   - Docker Compose: `docker info >/dev/null 2>&1`
   - Helm: `kubectl cluster-info >/dev/null 2>&1` and `helm version >/dev/null 2>&1`

   If the preflight fails, **stop immediately**, report the host blocker, and
   give the exact command sequence the user would need to run themselves
   instead of waiting or retrying indefinitely.

## Step 1: Choose the variant

Ask (or infer from the user's request) which variant to deploy:

| Variant | Make target | Notes |
|---|---|---|
| Default (vision + time-series fusion) | `make up` | No extra hardware checks |
| vLLM-based VLM | `make up_vllm` | Requires `make check_hardware` + `make check_models` (models must already be in `configs/vllm/models` and `configs/vllm/huggingface`) |
| Agentic | `make up_agentic` | Requires hardware check + triggers `make download_model` (can take minutes) |

All three targets implicitly run `check_env_variables`, `validate_host_ip`,
and `down` first (see `references/command-reference.md`).

## Step 2: Build and deploy (Docker Compose)

```bash
make build                 # or: make build_copyleft_sources
make up                    # or: make up_vllm / make up_agentic
make status                # containers + recent error-log scan
```

- `make up*` already calls `down` first, so no separate teardown is needed
  between iterations unless you want to fully reset.
- `make up_vllm`/`make up_agentic` will fail fast via `check_hardware` unless
  running on the required Intel Panther Lake / Core Ultra 3xx platform, or
  `PLATFORM_CHECK=false` is set in `.env` for CI/validation use.
- Report `make status` output verbatim; a container with recent `error` log
  lines is a real signal — don't suppress it.

## Step 3: Deploy with Helm

```bash
make gen_helm_charts
cd helm
# Edit values.yaml: INFLUXDB_USERNAME/PASSWORD, VISUALIZER_GRAFANA_USER/PASSWORD,
# MTX_WEBRTCICESERVERS2_0_USERNAME/PASSWORD, S3_STORAGE_USERNAME/PASSWORD,
# HOST_IP, HTTP(S)_PROXY as required — never invent values, ask the user.
helm install multimodal-weld-defect-detection . -n multimodal-sample-app --create-namespace
# GPU/NPU inferencing variant:
# helm install multimodal-weld-defect-detection --set privileged_access_required=true . -n multimodal-sample-app --create-namespace
kubectl get pods -n multimodal-sample-app
```

To push charts to a registry: `make push_helm_charts` (requires
`DOCKER_REGISTRY` configured in `.env` and prior `helm registry login`/
`docker login`).

## Step 4: Smoke test

Run `scripts/smoke-check.sh <docker|helm>` which:
- For `docker`: waits for container health via `make status`-style log scan
  and curls the Grafana/nginx endpoint (`https://localhost:${GRAFANA_PORT:-3000}`,
  `-k` for self-signed cert) with retries.
- For `helm`: waits for all pods in the target namespace to reach `Running`/
  `Ready`, then curls the exposed NodePort Grafana URL
  (`https://localhost:30001` per `tests/functional/pytest.ini` defaults).

Report the script's pass/fail output directly to the user.

## Step 5: Functional tests

See `references/functional-tests.md` for the full file-to-scenario mapping.
Typical invocation (from `tests/functional/`, after
`pip install -r ../requirements.txt`):

```bash
# Docker Compose path
pytest -v -s --html=docker_multimodal_report.html test_docker_deployment_multimodal.py
pytest -v -s -m gpu --html=gpu_docker_multimodal_report.html test_GPU_docker_multimodal.py
pytest -v -s --html=npu_docker_multimodal_report.html test_NPU_docker_multimodal.py

# Helm path
pytest -v -s --html=helm_multimodal_report.html test_helm_deployment_multimodal.py
pytest -v -s -m gpu --html=gpu_helm_multimodal_report.html test_GPU_helm_multimodal.py
pytest -v -s --html=npu_helm_multimodal_report.html test_NPU_helm_multimodal.py
```

Or use `scripts/run-functional-tests.sh <docker|helm> [gpu|npu]` to select the
right subset automatically. Summarize pytest's pass/fail counts; do not just
dump the raw HTML report path without a verdict.

## Step 6: Cleanup

```bash
make down                                          # Docker Compose
helm uninstall multimodal-weld-defect-detection -n multimodal-sample-app   # Helm
```

Mention that `make down` removes volumes (`-v`) — any InfluxDB/Grafana state
will be lost between iterations.

## Answer contract when blocked

If Docker/Kubernetes is unreachable, hardware checks fail, or required models
are missing, **do not stall**: state the blocker plainly, show the exact
command sequence the user would run once unblocked, and stop. Never invent
"it worked" output.
