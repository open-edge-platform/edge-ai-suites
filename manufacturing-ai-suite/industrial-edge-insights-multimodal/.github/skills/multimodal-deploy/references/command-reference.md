# SPDX-FileCopyrightText: (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

# Command Reference — industrial-edge-insights-multimodal

Source of truth: `Makefile` in the component root. Re-derive this table from
the live file if it ever disagrees.

## Build

| Target | Effect |
|---|---|
| `make build` | `docker compose -f docker-compose.yml -f docker-compose-vllm.yml -f docker-compose-agentic.yml build --pull` |
| `make build_copyleft_sources` | Same, plus `--build-arg COPYLEFT_SOURCES=true`, vllm overlay only |

## Prerequisite / validation targets (auto-invoked by `up*`)

| Target | Effect |
|---|---|
| `check_env_variables` | Validates `INFLUXDB_USERNAME/PASSWORD`, `VISUALIZER_GRAFANA_USER/PASSWORD`, `MTX_WEBRTCICESERVERS2_0_USERNAME/PASSWORD`, `S3_STORAGE_USERNAME/PASSWORD` in `.env` against length/charset rules |
| `validate_host_ip` | Ensures `HOST_IP` in `.env` is `localhost` or a valid IPv4 |
| `check_hardware` | Requires Intel Panther Lake / Core Ultra 3xx CPU unless `PLATFORM_CHECK=false` in `.env` (CI/validation only) |
| `check_models` | Requires non-empty `configs/vllm/models` and `configs/vllm/huggingface` directories |

## Deploy (Docker Compose)

| Target | Depends on | Effect |
|---|---|---|
| `make up` | `check_env_variables validate_host_ip down` | Default compose file, copies default Grafana dashboard, `docker compose up -d`, then uploads the weld-anomaly UDF tar and posts config to the Time-Series Analytics microservice |
| `make up_vllm` | `check_hardware check_models check_env_variables validate_host_ip down` | Adds `docker-compose-vllm.yml` overlay, VLM Grafana dashboard + nginx_vllm config |
| `make up_agentic` | `check_hardware check_models check_env_variables validate_host_ip down` | Adds agentic + vllm overlays, runs `make download_model` first (downloads/converts the configured LLM via the model-download service on port 8200, can take minutes), then brings up all services |
| `make down` | — | `docker compose -f docker-compose.yml -f docker-compose-vllm.yml -f docker-compose-agentic.yml down -v --remove-orphans` (removes volumes) |
| `make status` | — | Lists containers on the `timeseriessoftware_timeseries_network` network and scans last 5 log lines per container for "error" |
| `make download_model` | — | Standalone model download/conversion step used internally by `up_agentic`; polls `http://localhost:8200` |
| `make wait_for_tsam` | — | Polls `https://localhost:3000/ts-api/health` (actually uses `GRAFANA_PORT`) until the Time-Series Analytics microservice responds |

## Push / registry

| Target | Effect |
|---|---|
| `make push_images` | `make build` then `docker compose ... push` (requires `DOCKER_REGISTRY` in `.env` + prior `docker login`) |

## Helm

| Target | Effect |
|---|---|
| `make gen_helm_charts` | Copies Grafana/InfluxDB/MQTT/Telegraf/nginx/DLStreamer/SeaweedFS config into `helm/`, sets chart `version`/`appVersion` from `IMAGE_SUFFIX`/`WEEKLY_BUILD_DATE` |
| `make push_helm_charts` | `gen_helm_charts` then `helm package` + `helm push` to `oci://registry-1.docker.io/intel` (override via `.env`/registry login) |
| `helm install multimodal-weld-defect-detection . -n multimodal-sample-app --create-namespace` | Manual install step after `gen_helm_charts` + editing `helm/values.yaml` |
| `helm install ... --set privileged_access_required=true ...` | GPU/NPU inferencing variant |

## Key env vars (`.env`)

- `HOST_IP` (default `localhost`)
- `GRAFANA_PORT` (default `3000`)
- `PLATFORM_CHECK` (default implied `true`; set `false` to skip hardware gate)
- `LLM_DEVICE`, `LLM_WEIGHT_FORMAT`, `LLM_MODEL_NAME` (agentic/vLLM model selection)
- `DOCKER_REGISTRY`, `IMAGE_SUFFIX`, `WEEKLY_BUILD_DATE` (push/versioning)

## Helm test defaults (from `tests/functional/pytest.ini`)

- `release_name_multi=multimodal-weld-defect-detection`
- `namespace_multi=multimodal-sample-app`
- `chart_path_multi=../../helm-packages`
- `grafana_url_multi=https://localhost:30001`
- `wait_time_for_pods_to_come_up_multi=90` seconds
