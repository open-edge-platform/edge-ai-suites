<!--
SPDX-FileCopyrightText: (C) 2026 Intel Corporation
SPDX-License-Identifier: Apache-2.0
-->

# Industrial Edge Insights - Time Series — AI agents

## Canonical Instructions

Use this file as the canonical router for coding agents. Keep tool-specific
files such as `AGENTS.md`, `CLAUDE.md`, and `.cursor/rules/time-series.mdc`
as short pointers to this file.

## What This App Is

Industrial Edge Insights - Time Series demonstrates time-series anomaly
detection use cases, currently **wind turbine anomaly detection**, by
ingesting sensor data via **MQTT** or **OPC-UA**, running it through a
Time-Series Analytics Microservice (TICKscript/UDF-based), storing results in
InfluxDB, and visualizing them in Grafana. It ships as a Docker Compose stack
with an optional Helm/Kubernetes deployment path. The repo is structured to
support additional sample apps under `apps/` in the future (today only
`wind-turbine-anomaly-detection` is registered). Deeper user docs live under
[`docs/user-guide/`](../docs/user-guide/); this file is the agent-facing map.

## Deployment Modes

| Mode | Make target | Notes |
|------|-------------|-------|
| MQTT ingestion | `make up_mqtt_ingestion app=<name>` | `TELEGRAF_INPUT_PLUGIN=mqtt_consumer`; scales `ia-mqtt-publisher` to `num_of_streams` |
| OPC-UA ingestion | `make up_opcua_ingestion app=<name>` | `TELEGRAF_INPUT_PLUGIN=opcua`; scales `ia-opcua-server` to `num_of_streams` |
| Batch | append `batch` goal, e.g. `make up_mqtt_ingestion batch app=<name>` | Uses `config-batch.json` instead of `config.json` for the Time-Series Analytics Microservice |

`app` defaults to `wind-turbine-anomaly-detection` (must match
`SAMPLE_APP_LIST` in the `Makefile`). Both `up_*` targets run
`check_env_variables` and `down` first.

**Use the `time-series-deploy` skill**
([`.github/skills/time-series-deploy/SKILL.md`](skills/time-series-deploy/SKILL.md))
to drive build/deploy/smoke-test/functional-test cycles instead of running
raw commands ad hoc.

## Component Map

| Path | Purpose |
|------|---------|
| `Makefile` | All lifecycle targets (build, up_mqtt_ingestion/up_opcua_ingestion, down, status, helm) |
| `docker-compose.yml` | Stack: Time-Series Analytics Microservice, InfluxDB, Grafana, MQTT broker, Telegraf, OPC-UA server/publisher, nginx |
| `docker-compose-validation.override.yml` | CI/validation overlay (extra Telegraf input metrics) |
| `.env` | Runtime configuration (credentials, `GRAFANA_PORT`) — never commit real secrets |
| `configs/` | Per-service config: `grafana/`, `influxdb/`, `mqtt-broker/`, `nginx/`, `telegraf/` |
| `apps/<app>/` | Per-sample-app assets: `grafana-dashboard.json`, `time-series-analytics-config/`, `telegraf-config/`, `training/`, `simulation-data/` |
| `simulator/` | `mqtt-publisher/`, `opcua-server/` — synthetic sensor data generators |
| `generate-telegraf-config.py` | Regenerates multi-stream Telegraf config when `num_of_streams > 1` |
| `helm/` | Helm chart (generated/populated by `make gen_helm_charts`); `values.yaml`, `templates/` |
| `tests/functional/` | pytest suites for Docker and Helm deployment, retention, stability, security, GPU |
| `docs/user-guide/` | Get-started, build-from-source, Helm deploy, alerts/config how-tos, custom UDF guide, troubleshooting |

## Key Environment Variables (`.env`)

- `GRAFANA_PORT` (default `3000`)
- `INFLUXDB_USERNAME/PASSWORD`, `VISUALIZER_GRAFANA_USER/PASSWORD` — validated
  by `make check_env_variables` (length/charset rules)
- `DOCKER_REGISTRY`, `IMAGE_SUFFIX`, `WEEKLY_BUILD_DATE` — push/versioning

## Useful Commands

```bash
make build                           # Build Docker images (add build_copyleft_sources for copyleft sources)
make up_mqtt_ingestion app=<name>    # MQTT ingestion path
make up_opcua_ingestion app=<name>   # OPC-UA ingestion path
make status                          # Container status + recent error-log scan
make down                            # Stop and remove containers + volumes
make push_images                     # Build then push to DOCKER_REGISTRY
make gen_helm_charts app=<name>      # Generate/refresh helm/ from current configs
make gen_helm_charts_targz           # gen_helm_charts + package .tgz
make push_helm_charts app=<name>     # Package and push Helm chart to registry
make help                            # Full command list from the Makefile
```

See
[`.github/skills/time-series-deploy/references/command-reference.md`](skills/time-series-deploy/references/command-reference.md)
for the full, normative target/flag catalogue.

## Keeping Agent Guidance in Sync

**This file and the `time-series-deploy` skill must be updated whenever the
Makefile, compose files, Helm chart, `.env` schema, `apps/` sample-app list,
or `docs/user-guide/` content change.** Specifically:

- New/renamed Make targets, new `app=` entries in `SAMPLE_APP_LIST`, or
  compose changes → update the Deployment Modes/Component Map tables here and
  `references/command-reference.md` in the skill.
- New/changed functional test files → update `references/functional-tests.md`.
- New env vars or validation rules → update Key Environment Variables here and
  the skill's prerequisite checks.
- Port/URL changes → update Useful Commands/Endpoints here and
  `scripts/smoke-check.sh` in the skill.

Stale agent guidance is worse than none — treat these docs as part of the
change whenever you touch deployment-affecting files.
