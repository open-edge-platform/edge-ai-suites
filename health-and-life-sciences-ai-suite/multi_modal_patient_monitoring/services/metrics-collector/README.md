# Metrics Service

This service wraps the prebuilt Intel metrics collectors and exposes a simple
HTTP API for system metrics and platform information. It is intended to be
used by the aggregator‑service (and indirectly by the web UI).

Main responsibilities:

- Start the underlying collectors from the `intel/retail-benchmark` image
	(CPU, memory, NPU, PCM power, GPU/SPU where available).
- Read the log/CSV files written under `/tmp/results`.
- Provide a JSON `/metrics` endpoint with time‑series data.
- Provide `/platform-info` and `/memory` helper endpoints.

---

## Running the service

### Option 1: Docker (recommended)

From this directory:

```bash
docker build -t hl-metrics-service .

docker run --rm \
	--privileged \
	--pid host \
	--network host \
	-e METRICS_DIR=/tmp/results \
	-v "$(pwd)/../../metrics:/tmp/results" \
	-v /sys:/sys \
	-v /dev:/dev \
	-v /run:/run \
	hl-metrics-service
```

This starts the collectors (via `supervisord`) and the HTTP API on port `9000`.

### Option 2: docker-compose (suite integration)

From the top‑level suite directory, use the provided compose file which wires
metrics‑service to the host and shares the metrics directory used by
aggregator‑service:

```bash
docker compose up metrics-service
```

---

## Configuration

Environment variables:

- `METRICS_DIR` (default: `/tmp/results`)
	- Directory where the collectors write metrics logs.
- `NPU_LOG` (optional)
	- Path to the NPU CSV file if it differs from the default
		`${METRICS_DIR}/npu_usage.csv`.

Expected files (relative to `METRICS_DIR`):

- `cpu_usage.log` — CPU utilization from `sar`.
- `memory_usage.log` — memory usage from `free -s`.
- `npu_usage.csv` — NPU utilization samples.
- `pcm.csv` — Intel PCM counters, including package energy (Joules).
- `qmassa1-*-tool-generated.json` — GPU/SPU metrics from qmassa (optional).

---

## HTTP API

All endpoints listen on port `9000` and return JSON.

### `GET /metrics` — metrics time series

Aggregated time‑series metrics built from the log/CSV files.

- Method: `GET`
- URL: `/metrics`
- Response (shape):

```json
{
	"cpu_utilization": [["2026-01-28T11:09:28.671", 12.3]],
	"gpu_utilization": [],
	"memory": [["2026-01-28T11:09:28.671", 32.0, 12.3, 19.7, 38.4]],
	"power": [["2026-01-28T11:09:28.671", 5.1, 2.2]],
	"npu_utilization": [["2026-01-28T11:09:28.671", 23.4]]
}
```

Notes:

- `cpu_utilization`: `[timestamp_iso, usage_percent]` derived from
	`cpu_usage.log`.
- `gpu_utilization`: reserved for GPU/SPU metrics parsed from qmassa JSON
	(may currently be empty).
- `memory`: `[timestamp_iso, total_gb, used_gb, free_gb, usage_percent]`
	derived from `memory_usage.log`.
- `power`: `[timestamp_iso, package0_watts, package1_watts, ...]` computed
	from energy deltas in `pcm.csv`.
- `npu_utilization`: `[timestamp_iso, usage_percent]` derived from
	`npu_usage.csv`.

### `GET /platform-info` — platform configuration

High‑level summary of the host platform.

- Method: `GET`
- URL: `/platform-info`
- Response (shape):

```json
{
	"Processor": "Intel(R) Core(TM) Ultra 7 155H",
	"NPU": "Intel AI Boost",
	"iGPU": "Intel Arc Graphics",
	"Memory": "32 GB",
	"Storage": "1 TB"
}
```

Values are best‑effort based on `/proc/cpuinfo`, `lspci`, `/proc/meminfo`, and
`shutil.disk_usage("/")`.

### `GET /memory` — latest memory snapshot

Convenience endpoint exposing the most recent memory sample.

- Method: `GET`
- URL: `/memory`
- Response (shape, when available):

```json
{
	"total_kib": 32859780.0,
	"used_kib": 12345678.0,
	"usage_percent": 37.5,
	"raw": "Mem:  32859780 12345678 ..."
}
```

If no memory data is available, this endpoint returns HTTP 404.
