---
# SPDX-FileCopyrightText: (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
name: time-series-deploy
description: >-
  Build, deploy, smoke-check, and functionally test the Industrial Edge
  Insights - Time Series sample applications (industrial-edge-insights-time-series,
  e.g. wind-turbine-anomaly-detection) via its Makefile-driven Docker Compose
  and Helm paths. Use this skill for quick build/deploy/teardown cycles,
  MQTT vs OPC-UA ingestion selection, multi-stream and batch modes, and
  running the existing tests/functional pytest suites. Do not use this skill
  for application code changes, unrelated components, or production rollout
  decisions.
license: Apache-2.0
compatibility: >-
  Requires a bash-compatible shell, Docker + Docker Compose v2, make, and curl
  for the Docker Compose path. The Helm path additionally requires a reachable
  Kubernetes cluster, kubectl, and helm. Functional tests additionally require
  Python 3 and the packages in tests/requirements.txt.
metadata:
  author: open-edge-platform
  version: "1.0.0"
  tags: deployment, docker-compose, helm, manufacturing, time-series, wind-turbine-anomaly-detection
allowed-tools: bash make docker helm kubectl pytest
---

# Industrial Edge Insights - Time Series — Deploy Skill

Drive **industrial-edge-insights-time-series** builds, deployments, smoke
checks, and functional tests through its real `Makefile`, `docker-compose.yml`,
and `tests/functional/` pytest suite. Ground every answer in those files — do
not invent Make targets, flags, ports, or env vars. **Run the commands
yourself and relay actual output**; never fabricate results.

Scope: this skill only applies to
`manufacturing-ai-suite/industrial-edge-insights-time-series`. The companion
component `industrial-edge-insights-multimodal` has its own
`multimodal-deploy` skill — do not mix the two.

## Normative references

- `references/command-reference.md` — full Make target catalogue (source of
  truth for every command/flag; re-derive from the live Makefile if it ever
  disagrees with this doc).
- `references/functional-tests.md` — mapping of test files to scenario.

## Step 0: Locate the app root and preflight

1. Resolve the app root: walk up from cwd, or ask git
   (`git rev-parse --show-toplevel`) for the enclosing repo and look for
   `manufacturing-ai-suite/industrial-edge-insights-time-series/Makefile`.
   `cd` into that directory before running any command below.
2. Confirm `.env` exists and required creds (`INFLUXDB_USERNAME/PASSWORD`,
   `VISUALIZER_GRAFANA_USER/PASSWORD`) are set — ask the user rather than
   inventing values.
3. Run a bounded preflight depending on the chosen path:
   - Docker Compose: `docker info >/dev/null 2>&1`
   - Helm: `kubectl cluster-info >/dev/null 2>&1` and `helm version >/dev/null 2>&1`
     (if using k3s, remind the user to `export KUBECONFIG=/etc/rancher/k3s/k3s.yaml`)

   If the preflight fails, **stop immediately**, report the host blocker, and
   give the exact command sequence the user would need to run once unblocked.

## Step 1: Choose app, ingestion path, and mode

- `app` (default `wind-turbine-anomaly-detection`; this is the only entry in
  `SAMPLE_APP_LIST` today — check the live Makefile before assuming others
  exist).
- Ingestion path: MQTT (`make up_mqtt_ingestion`) or OPC-UA
  (`make up_opcua_ingestion`).
- Optional `num_of_streams=N` (>1 regenerates a multi-stream Telegraf config
  via a Python venv + `generate-telegraf-config.py`), `ingestion_interval`,
  `number_of_data_points_per_stream` (enables benchmarking).
- Optional `batch` goal appended to the ingestion target to use
  `config-batch.json` instead of `config.json` for the Time-Series Analytics
  microservice config.

## Step 2: Build and deploy (Docker Compose)

```bash
make build                                   # or: make build_copyleft_sources
make up_mqtt_ingestion app=wind-turbine-anomaly-detection
# or
make up_opcua_ingestion app=wind-turbine-anomaly-detection
# optional batch mode:
make up_mqtt_ingestion batch app=wind-turbine-anomaly-detection
make status
```

- Both `up_*` targets call `check_env_variables` and `down` first.
- `make status` lists containers filtered by `ia-`, `mr_`, `model_`,
  `wind-turbine` name prefixes and scans recent logs for "error".

## Step 3: Deploy with Helm

```bash
make gen_helm_charts app=wind-turbine-anomaly-detection
cd helm
# Edit values.yaml: INFLUXDB_USERNAME/PASSWORD, VISUALIZER_GRAFANA_USER/PASSWORD,
# HTTP(S)_PROXY as required — never invent values, ask the user.
helm install ts-wind-turbine-anomaly . -n ts-sample-app --create-namespace
# GPU inferencing variant:
# helm install ts-wind-turbine-anomaly --set privileged_access_required=true \
#   --set env.TELEGRAF_INPUT_PLUGIN=<input_plugin> . -n ts-sample-app --create-namespace
kubectl get pods -n ts-sample-app
```

To push charts: `make push_helm_charts app=<name>` (runs
`gen_helm_charts_targz` first; requires `DOCKER_REGISTRY` + registry login).

## Step 4: Smoke test

Run `scripts/smoke-check.sh <docker|helm> [namespace]` which:
- For `docker`: runs `make status` and curls
  `https://localhost:${GRAFANA_PORT:-3000}/` with retries.
- For `helm`: waits for all pods in the namespace to be `Ready`, then curls
  the exposed Grafana NodePort URL (`https://localhost:30001` per
  `tests/functional/pytest.ini` defaults).

Report the script's pass/fail output directly to the user.

## Step 5: Functional tests

See `references/functional-tests.md` for the full file-to-scenario mapping.
Typical invocation (from `tests/functional/`, after
`pip install -r ../requirements.txt`):

```bash
# Docker Compose path
pytest -v -s --html=docker_wind_turbine_report.html test_docker_deployment_wind_turbine.py
pytest -v -s --html=docker_influxdb_retention_wind_turbine_report.html test_docker_influxdb_retention.py
pytest -v -s --html=docker_stability_wind_turbine_report.html test_docker_deployment_stability.py
pytest -v -s -m gpu --html=gpu_docker_report.html test_GPU_docker.py

# Helm path
pytest -v -s --html=helm_wind_turbine_report.html test_helm_deployment_wind_turbine.py
pytest -v -s --html=helm_influxdb_retention_wind_turbine_report.html test_helm_influxdb_retention.py
pytest -v -s -m gpu --html=gpu_helm_report.html test_GPU_helm.py

# Security tests (either deployment method already running)
pytest -v -s --html=security_report.html test_docker_helm_deployment_security.py
```

Or use `scripts/run-functional-tests.sh <docker|helm> [gpu|security|stability|retention]`
to select the right subset automatically. Summarize pytest's pass/fail counts
in your answer; do not just point at the report file.

## Step 6: Cleanup

```bash
make down                                       # Docker Compose (removes volumes)
helm uninstall ts-wind-turbine-anomaly -n ts-sample-app   # Helm
```

## Answer contract when blocked

If Docker/Kubernetes is unreachable or required `.env`/`values.yaml` fields
are missing, **do not stall**: state the blocker plainly, show the exact
command sequence the user would run once unblocked, and stop. Never invent
"it worked" output.
