# SPDX-FileCopyrightText: (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

# Command Reference — industrial-edge-insights-time-series

Source of truth: `Makefile` in the component root. Re-derive this table from
the live file if it ever disagrees.

## App selection

- `app=<name>` selects the sample app (default `wind-turbine-anomaly-detection`).
  Must be one of `SAMPLE_APP_LIST` in the Makefile or `make` errors out.

## Build

| Target | Effect |
|---|---|
| `make build` | `docker compose build --pull` |
| `make build_copyleft_sources` | Same, plus `--build-arg COPYLEFT_SOURCES=true` |

## Prerequisite / validation targets (auto-invoked by `up_*`)

| Target | Effect |
|---|---|
| `check_env_variables` | Validates `INFLUXDB_USERNAME/PASSWORD`, `VISUALIZER_GRAFANA_USER/PASSWORD` in `.env` against length/charset rules |

## Deploy (Docker Compose)

| Target | Depends on | Effect |
|---|---|---|
| `make up_mqtt_ingestion` | `check_env_variables down` | Brings up the stack with `TELEGRAF_INPUT_PLUGIN=mqtt_consumer`; scales `ia-mqtt-publisher` to `num_of_streams` instances; uploads UDF tar + posts config afterward |
| `make up_opcua_ingestion` | `check_env_variables down` | Same but `TELEGRAF_INPUT_PLUGIN=opcua`, scales `ia-opcua-server` to `num_of_streams` |
| `make down` | — | `docker compose down -v --remove-orphans` (removes volumes) |
| `make status` | — | Lists containers filtered by `ia-`/`mr_`/`model_`/`wind-turbine` name prefixes, scans last 5 log lines per container for "error" |

### Parameters accepted by `up_mqtt_ingestion` / `up_opcua_ingestion`

- `app` — sample app name (default `wind-turbine-anomaly-detection`)
- `num_of_streams` — number of simulated streams (default `1`); >1 triggers
  regeneration of a multi-stream Telegraf config via a local Python venv
  (`generate-telegraf-config.py`)
- `ingestion_interval` — simulator ingestion interval (default `"1s"`)
- `number_of_data_points_per_stream` — when set, enables
  `ENABLE_BENCHMARKING=true` and sets `BENCHMARK_TOTAL_PTS`
- `batch` — append as a second goal (e.g.
  `make up_mqtt_ingestion batch app=wind-turbine-anomaly-detection`) to use
  `config-batch.json` instead of `config.json` for the TSAM config, and swap
  in the `_batch` model variant

## Push / registry

| Target | Effect |
|---|---|
| `make push_images` | `make build` then `docker compose push` (requires `DOCKER_REGISTRY` in `.env` + prior `docker login`) |

## Helm

| Target | Effect |
|---|---|
| `make gen_helm_charts` | Copies Grafana/InfluxDB/MQTT/Telegraf/nginx config + `apps/<app>/simulation-data` into `helm/`, sets chart name/description/version from `app`/`IMAGE_SUFFIX`/`WEEKLY_BUILD_DATE` |
| `make gen_helm_charts_targz` | `gen_helm_charts` then `helm package` into `helm-packages/*.tgz` |
| `make push_helm_charts` | `gen_helm_charts_targz` then `helm push` to `oci://registry-1.docker.io/intel` |
| `helm install ts-wind-turbine-anomaly . -n ts-sample-app --create-namespace` | Manual install after `gen_helm_charts` + editing `helm/values.yaml` |
| `helm install ... --set privileged_access_required=true --set env.TELEGRAF_INPUT_PLUGIN=<plugin> ...` | GPU inferencing variant |

## Key env vars (`.env`)

- `GRAFANA_PORT` (default `3000`)
- `DOCKER_REGISTRY`, `IMAGE_SUFFIX`, `WEEKLY_BUILD_DATE` (push/versioning)

## Helm test defaults (from `tests/functional/pytest.ini`)

- `release_name=ts-wind-turbine-anomaly`
- `namespace=ts-sample-app`
- `chart_path=../../helm-packages/`
- `grafana_url=https://localhost:30001`
- `wait_time_for_pods_to_come_up=90` seconds

If using k3s, remind the user to
`export KUBECONFIG=/etc/rancher/k3s/k3s.yaml` before Helm/kubectl commands.
