<!--
SPDX-FileCopyrightText: (C) 2026 Intel Corporation
SPDX-License-Identifier: Apache-2.0
-->

# Benchmark — UAV Vision Analytics

This document explains how to measure the performance of the UAV Vision Analytics
application using the `calc_stream_density.sh` benchmarking script. The script
determines the maximum number of concurrent drone-camera video streams the
system can process (**stream density**) while sustaining a target frame rate,
and simultaneously collects hardware utilization and power metrics from `metrics-manager`.

> **Note**: The [Visual Pipeline and Platform Evaluation Tool (ViPPET)](https://docs.openedgeplatform.intel.com/dev/edge-ai-libraries/visual-pipeline-and-platform-evaluation-tool/index.html)
> is also available as an optional benchmarking tool for comparing AI pipeline performance
> across CPU, GPU, and NPU.

> **Note**: For platform-level benchmarking beyond this application — vision AI inference,
> hardware-accelerated media processing, end-to-end video analytics pipelines, and generative AI —
> see the [Edge Workloads and Benchmarks Guide](../infrastructure/run-edge-benchmarks.md).

<!--hide_directive
:::{toctree}
:hidden:

Edge Workloads and Benchmarks Guide <../infrastructure/run-edge-benchmarks.md>
:::
hide_directive-->

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [How the Script Works](#how-the-script-works)
   - [Exponential + Bisect Algorithm](#exponential--bisect-algorithm)
   - [FPS Statistics (p90)](#fps-statistics-p90)
   - [HW Metrics Integration](#hw-metrics-integration)
3. [Available Pipelines](#available-pipelines)
4. [Run Modes](#run-modes)
   - [Mode 1 — Single-Pipeline Stream Density](#mode-1--single-pipeline-stream-density)
   - [Mode 2 — All-Devices Stream Density](#mode-2--all-devices-stream-density)
   - [Mode 3 — Fixed Stream Count (nstreams)](#mode-3--fixed-stream-count-nstreams)
5. [CLI Reference](#cli-reference)
6. [Understanding the Output](#understanding-the-output)
   - [Terminal Summary](#terminal-summary)
   - [kpi.txt Format](#kpitxt-format)
   - [Output Directory Structure](#output-directory-structure)
7. [Troubleshooting](./troubleshooting.md#benchmark)

## Prerequisites

Before running the benchmark, ensure the application stack is configured and
running. See [index.md](../index.md) for full setup instructions.

### 1. Model must be exported

The model must exist at:

```text
resources/models/yolov8n-visdrone/best_openvino_model/best.xml
```

Run `make model` if it is missing (Deployment will fail with an error if the model is absent).

### 2. Start the application stack

The DL Streamer Pipeline Server (`dlstreamer-pipeline-server`) and
`metrics-manager` must be running. Use the pymavlink stack:

```bash
cd edge-ai-suites/federal-and-aerospace-ai-suite/uav-vision-analytics
make pymav-up
```

Wait until all containers are healthy:

```bash
docker ps --format "table {{.Names}}\t{{.Status}}"
```

Expected services: `dlstreamer-pipeline-server`, `broker`, `mavlink-router`, `px4`, `metrics-manager`.

### 3. Install required host tools

| Tool | Used for | Install |
| --- | --- | --- |
| `curl` | DLSPS API calls, metrics polling | `sudo apt-get install -y curl` |
| `gawk` | FPS and HW metrics statistical aggregation | `sudo apt-get install -y gawk` |
| `python3` | Continuous SSE metrics streamer | `sudo apt install python3` |
| `jq` | JSON parsing of DLSPS status responses | `sudo apt-get install -y jq` |
| `ffmpeg` | Creating looped video files (optional) | `sudo apt-get install -y ffmpeg` |

> **Note:** If **`jq` is not available without root**, create a zero-dependency `docker exec` wrapper:
>
> ```bash
> mkdir -p ~/.local/bin
> cat > ~/.local/bin/jq << 'EOF'
> #!/usr/bin/env bash
> CONTAINER="dlstreamer-pipeline-server"
> args=()
> for arg in "$@"; do
>   if [[ -f "$arg" ]]; then
>     set -- "$@"          # file arg: pipe content as stdin instead
>     cat "$arg" | docker exec -i "$CONTAINER" jq "${args[@]}"
>     exit $?
>   else
>     args+=("$arg")
>   fi
> done
> docker exec -i "$CONTAINER" jq "${args[@]}"
> EOF
> chmod +x ~/.local/bin/jq
> export PATH="$HOME/.local/bin:$PATH"
> # To make permanent:
> echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
> ```
>
> The benchmark script automatically adds `~/.local/bin` to `PATH` at startup.

### 4. Verify services are reachable

| Service | URL | Description |
| --- | --- | --- |
| DL Streamer Pipeline Server | `http://localhost:8081` | Pipeline REST API |
| metrics-manager | `http://localhost:9090` | HW metrics SSE + REST endpoint |

```bash
curl -s http://localhost:8081/pipelines/status | head -3
curl -s http://localhost:9090/api/v1/metrics/latest | head -3
```

## How the Script Works

The benchmarking script (`benchmark/calc_stream_density.sh`) automates three tasks:

1. **Start N concurrent pipeline instances** via the DLSPS REST API
   (`POST /pipelines/user_defined_pipelines/<name>`), each with a unique RTSP
   path, metadata topic, and `model-instance-id` so concurrent streams
   do not conflict.
2. **Collect FPS samples** by polling `/pipelines/status` every second during a
   configurable measurement window (default 60 s), then compute
   `p90/avg/median/min` statistics with `gawk`.
3. **Collect HW metrics** from `metrics-manager` in parallel via a Python3 SSE
   streamer, and aggregate avg/min/max per metric for the same measurement window.

### Exponential + Bisect Algorithm

The script finds the **maximum sustainable stream count automatically** —
no manual bounds need to be supplied:

```text
Phase 1 — Exponential doubling:
  Test N = 1 → 2 → 4 → 8 → 16 ... until fps/stream drops below the floor (-t)
  or N reaches the upper limit (-u, default 24).

Phase 2 — Bisect:
  Binary-search between last-passing N (lo) and first-failing N (hi)
  until hi - lo <= 1. lo is the max sustainable stream count.
```

### FPS Statistics (p90)

During each N-stream test, DLSPS reports the `avg_fps` for every running
pipeline instance every second. After the measurement window ends
(`-i`, default 60 s), `gawk` computes:

| Metric | Meaning |
| --- | --- |
| `throughput #N` | p90 FPS of stream N over the window |
| `throughput median` | Median of the per-stream p90 values |
| `throughput average` | Mean of the per-stream p90 values |
| `throughput stdev` | Standard deviation of per-stream p90 values |
| `throughput cumulative` | Sum of all per-stream p90 values (total system FPS) |
| `throughput min` | Lowest per-stream p90 — used to decide **pass/fail** vs `-t` floor |

The **p90 (90th percentile)** is used instead of the raw average to discard
outlier frames caused by pipeline startup spikes or scheduling jitter.
A run passes if `throughput min >= target_fps` (`-t`).

### HW Metrics Integration

The script integrates with `intel/metrics-manager` to collect real hardware
metrics in parallel with FPS sampling.

**Collection method — SSE primary, REST fallback:**

1. **SSE primary** (`GET /metrics/stream`)

   A Python3 subprocess subscribes to the Server-Sent Events endpoint, which
   streams `data:` events as fast as the hardware counters update. All events
   are written continuously to `hw_samples.log` — zero polling lag,
   no missed samples.

2. **REST fallback** (`GET /api/v1/metrics/latest`)

  Used automatically if the SSE endpoint is unreachable. Polls at
  `METRICS_INTERVAL` seconds (default: 2 s).

**Timing — warmup exclusion:**

The HW monitor starts **after** all pipeline instances reach `RUNNING` state
(after model loading and JIT compilation finish), and stops **before** pipeline
teardown. This ensures GPU/NPU warmup time does not skew power and
utilization measurements.

**Metrics collected:**

| Category | Metric names in `kpi.txt` | Notes |
| --- | --- | --- |
| **CPU** | `hw_cpu_util_pct`, `hw_cpu_usage_user`, `hw_cpu_usage_system`, `hw_cpu_freq_mhz`, `hw_cpu_temperature`, `hw_mem_used_percent` | `cpu_util_pct = 100 - cpu_idle` |
| **GPU engines** | `hw_gpu_compute_util_pct` (CCS), `hw_gpu_video_util_pct` (VCS), `hw_gpu_render_util_pct` (RCS), `hw_gpu_enhance_util_pct` (VECS) | Per GPU 0 only |
| **GPU combined** | `hw_gpu_util_combined` | `max(CCS, VCS)` per sample — best single-number GPU load indicator |
| **GPU** | `hw_gpu_freq_mhz`, `hw_gpu_power_w` | qmassa-sourced |
| **Platform power** | `hw_rapl_psys_w` (full platform), `hw_rapl_pkg_w` (SoC), `hw_rapl_core_w`, `hw_rapl_uncore_w`, `hw_pkg_power_w` | RAPL + qmassa |
| **NPU** | `hw_npu_utilization`, `hw_npu_frequency`, `hw_npu_power`, `hw_npu_temperature`, `hw_npu_memory_mb`, `hw_npu_bandwidth` | Zero when pipeline uses CPU/GPU |

> **Note:** *HW metrics disabled automatically** if `metrics-manager` is not
> reachable — the FPS benchmark continues normally and `hw_sample_count: 0` appears in `kpi.txt`.

## Available Pipelines

Pipeline names are defined in `benchmark/benchmark_app_payload.json`. Each entry
maps a pipeline name to the DLSPS POST payload (source URI, destination,
inference device, model path).

### File-source pipelines (recommended for benchmarking)

These use `uav_sample.avi` as a looping file source — ideal for repeatable,
controlled benchmarks with deterministic input:

| Pipeline name | Device | Source |
| --- | --- | --- |
| `uav_object_detection_cpu` | CPU | `uav_sample.avi` (loop) |
| `uav_object_detection_gpu` | GPU | `uav_sample.avi` (loop) |
| `uav_object_detection_npu` | NPU | `uav_sample.avi` (loop) |

### RealSense camera pipelines

These use a live Intel RealSense D-series camera (`/dev/video4`). The camera
must be physically attached and accessible inside the container.

| Pipeline name | Device | Source |
| --- | --- | --- |
| `uav_realsense_cpu` | CPU | RealSense (v4l2) |
| `uav_realsense_gpu` | GPU | RealSense (v4l2) |
| `uav_realsense_npu` | NPU | RealSense (v4l2) |

All pipelines use the **YOLOv8n-VisDrone** model (FP16 OpenVINO IR) at 640×640
resolution for drone object detection (pedestrian, car, van, truck, bus, bicycle, motor, etc.).

List pipeline names available in the payload file at any time:

```bash
jq -r '.[].pipeline' benchmark/benchmark_app_payload.json
```

## Run Modes

All examples assume you run from the app root directory:

```bash
cd edge-ai-suites/federal-and-aerospace-ai-suite/uav-vision-analytics
```

### Mode 1 — Single-Pipeline Stream Density

Finds the maximum number of concurrent streams for a **single pipeline** while sustaining the target FPS (Uses the exponential + bisect algorithm automatically).

```bash
./benchmark/calc_stream_density.sh \
  -p uav_object_detection_gpu \
  -t 20 \
  -i 60
```

**What happens:**

1. Pre-flight check: verifies DLSPS (`http://localhost:8081`) and metrics-manager (`http://localhost:9090`) are reachable.
2. Stops any previously running pipelines.
3. Tests N=1 → 2 → 4 → 8 … (exponential), then bisects to find the exact max.
4. At each N: starts streams, waits for RUNNING, collects FPS + HW metrics for 60 s, stops streams.
5. Prints final result to terminal and writes `benchmark-density-uav_object_detection_gpu/kpi.txt`.

**Example terminal output:**

```text
>>>>> Performing pre-flight checks...
DLSPS is reachable.
HW metrics: http://localhost:9090

>>>>> Attempting to stop all running pipelines.
No running pipelines found.

>>>>> Single-pipeline density search: uav_object_detection_gpu
      FPS floor=20   window=60s   max_streams=24

>>>>> Density search (exp+bisect): uav_object_detection_gpu
      floor=20 fps   max=24 streams   window=60s
>>>>> [density]   N=1 → 24.0 fps/stream  (floor=20) — ✓
>>>>> [density]   N=2 → 24.0 fps/stream  (floor=20) — ✓
>>>>> [density]   N=4 → 23.9 fps/stream  (floor=20) — ✓
>>>>> [density]   N=8 → 11.2 fps/stream  (floor=20) — ✗
>>>>> [density]   N=6 → 23.8 fps/stream  (floor=20) — ✓
>>>>> [density]   N=7 → 15.4 fps/stream  (floor=20) — ✗
>>>>> Density result: max sustainable = 6 streams @ 23.8 fps/stream

======================================================
✅ FINAL RESULT: Stream-Density Benchmark Completed!
   Pipeline     : uav_object_detection_gpu
   Max streams  : 6
   fps/stream   : 23.8
   FPS floor    : 20
   CPU util     : 32.5 %
   GPU util     : 87.4 %
   NPU util     : 0.0 %
   Pkg power    : 28.3 W
======================================================
stream density: 6
```

### Mode 2 — All-Devices Stream Density

Runs the density search **sequentially** for multiple pipelines (typically CPU, GPU, NPU) and prints a unified summary table. This is the standard way to generate platform capability claims.

```bash
./benchmark/calc_stream_density.sh \
  --all-devices \
  -p uav_object_detection_cpu uav_object_detection_gpu uav_object_detection_npu \
  -t 20 \
  -i 60 \
  -u 24
```

**What happens:**

1. Pre-flight checks (DLSPS + metrics-manager).
2. Runs the density search for each pipeline in order: CPU → GPU → NPU.
3. 10-second thermal cooldown between pipeline types.
4. Prints a unified results table to the terminal.

**Example terminal output:**

```text
================================================================
  UAV VISION ANALYTICS — SUSTAINED STREAM DENSITY RESULTS
  FPS floor : 20   Window: 60s   Percentile: p90
================================================================
Pipeline                                       Streams    FPS@N     CPU%    GPU%    NPU%   PkgPwr(W)
------------------------------------------------------------------------
uav_object_detection_cpu                           3  20.7476   71.200   0.000   0.000     24.922
uav_object_detection_gpu                           4  23.9829   32.510  87.400   0.000      9.627
uav_object_detection_npu                           3  23.8675    8.100   0.000  94.300      4.255
================================================================

KPI files:
  CPU: benchmark-density-uav_object_detection_cpu/kpi.txt
  GPU: benchmark-density-uav_object_detection_gpu/kpi.txt
  NPU: benchmark-density-uav_object_detection_npu/kpi.txt
```

**Reading the table:**

- **Streams** — maximum concurrent streams sustaining ≥ target FPS (`-t`).
- **FPS@N** — p90 fps/stream at the max sustainable N.
- **CPU%** — average CPU utilization during the sustained measurement window.
- **GPU%** — average combined GPU utilization (max of CCS and VCS engines per sample).
- **NPU%** — average NPU utilization (non-zero only for NPU pipelines).
- **PkgPwr(W)** — average SoC package power during the measurement window.

### Mode 3 — Fixed Stream Count (nstreams)

Runs a **fixed, pre-specified number of streams** per pipeline simultaneously
(no binary search). Use this to validate a known configuration or benchmark
heterogeneous concurrent workloads (e.g., CPU + GPU + NPU running at the same time).

```bash
# Run 3 GPU streams and 3 NPU streams simultaneously
./benchmark/calc_stream_density.sh \
  -p uav_object_detection_gpu uav_object_detection_npu \
  -nstreams 3 3 \
  -t 20 \
  -i 60
```

> The order of `-nstreams` values must match the order of `-p` pipeline names.

**More examples:**

```bash
# Single pipeline, confirm a specific stream count (e.g., validate GPU=4 claim)
./benchmark/calc_stream_density.sh \
  -p uav_object_detection_gpu \
  -nstreams 4 \
  -i 60

# Three devices concurrently — heterogeneous mixed load
./benchmark/calc_stream_density.sh \
  -p uav_object_detection_cpu uav_object_detection_gpu uav_object_detection_npu \
  -nstreams 3 4 3 \
  -i 60
```

**Terminal summary table (nstreams mode):**

```text
================================================================
  NSTREAMS RESULTS  (p90 window=60s)
================================================================
  Pipeline                              Streams  FPS/s   CPU%   GPU%   NPU%   PkgPwr(W)  GpuPwr(W)
  --------------------------------------------------------------------------
  uav_object_detection_gpu                  3  23.98   32.1   85.2    0.0       9.500      5.210
  uav_object_detection_npu                  3  23.87    8.0    0.0   94.1       4.100      0.009
  --------------------------------------------------------------------------
  Total FPS: 143.7   Samples: 29   CPU temp: 62.0°C
  KPI: benchmark-multi/kpi.txt
================================================================
```

## CLI Reference

```text
Usage (stream-density — single pipeline):
  ./benchmark/calc_stream_density.sh -p <pipeline_name> [options]

Usage (all-devices — sequential density, unified table):
  ./benchmark/calc_stream_density.sh --all-devices \
    -p <cpu_pipeline> <gpu_pipeline> <npu_pipeline> [options]

Usage (nstreams — fixed concurrent streams):
  ./benchmark/calc_stream_density.sh \
    -p <p1> [p2 ...] -nstreams <N1> [N2 ...] [options]
```

### Arguments

| Flag | Default | Description |
| --- | --- | --- |
| `-p <name(s)>` | required | Pipeline name(s) from `benchmark/benchmark_app_payload.json`. |
| `--all-devices` | off | Run density search sequentially for all `-p` pipelines, print unified results table. |
| `-nstreams <N1> [N2...]` | — | Fixed stream counts per pipeline (nstreams mode). Count order must match `-p` order. |
| `-t <fps>` | `14.95` | **FPS floor.** A stream count passes only if `throughput min >= -t`. |
| `-i <seconds>` | `60` | **Measurement window.** Seconds to collect FPS + HW metrics at each tested N. Longer = more stable. |
| `-u <max_streams>` | `24` | Upper bound for exp+bisect search. Search stops if N reaches this and still passes. |
| `-l <lower_bound>` | `1` | Accepted for compatibility; **ignored** — exp+bisect always starts from N=1. |
| `-c <percentile>` | `0.9` | Throughput percentile for KPI (0.9 = p90). |
| `--no-hw-metrics` | off | Skip metrics-manager collection entirely (faster, FPS-only benchmark). |
| `-m <url>` | `http://localhost:9090` | metrics-manager base URL. Only needed if not on `localhost:9090`. |
| `-M <seconds>` | `2` | REST fallback poll interval. Irrelevant when SSE is available. |

### Environment variable overrides

| Variable | Equivalent flag | Default |
| --- | --- | --- |
| `METRICS_URL` | `-m` | `http://localhost:9090` |
| `METRICS_INTERVAL` | `-M` | `2` |
| `DLSPS_NODE_IP` | — | `localhost` |
| `DLSPS_PORT` | — | `8081` |

### Common command examples

```bash
# Fastest check — single pipeline, default FPS floor (14.95), no HW metrics
./benchmark/calc_stream_density.sh \
  -p uav_object_detection_gpu \
  --no-hw-metrics

# Full 3-device benchmark at 20 fps floor, 60s window
./benchmark/calc_stream_density.sh \
  --all-devices \
  -p uav_object_detection_cpu uav_object_detection_gpu uav_object_detection_npu \
  -t 20 -i 60

# Validate a specific claim: confirm GPU sustains 4 streams at ≥20 fps
./benchmark/calc_stream_density.sh \
  -p uav_object_detection_gpu -nstreams 4 -t 20 -i 60

# NPU pipeline with wider search range
./benchmark/calc_stream_density.sh \
  -p uav_object_detection_npu -t 20 -u 32 -i 60

# Remote machine (e.g., run benchmark from a different host)
DLSPS_NODE_IP=x.x.x.x ./benchmark/calc_stream_density.sh \
  -p uav_object_detection_gpu \
  -m http://x.x.x.x:9090 \
  -t 20
```

## Understanding the Output

### Terminal Summary

Each mode prints a formatted summary to the terminal after all runs complete:

- **Density mode (single pipeline):** max streams, fps/stream, CPU%/GPU%/NPU% utilization, package power.
- **All-devices mode:** a table with one row per pipeline — streams, FPS@N, CPU%, GPU%, NPU%, PkgPwr(W).
- **nstreams mode:** a table per pipeline with FPS/stream, utilization columns, total FPS, CPU temperature, and HW sample count.

### kpi.txt Format

Each pipeline run writes a `kpi.txt` with two sections — FPS statistics (always written) and HW metrics (written when metrics-manager is reachable):

```text
# ── FPS section ──────────────────────────────────────────────────────
throughput #1: 23.983        ← p90 FPS for stream 1
throughput #2: 23.911        ← p90 FPS for stream 2
throughput #3: 23.874        ← p90 FPS for stream 3
throughput #4: 23.806        ← p90 FPS for stream 4
throughput median: 23.947    ← median of per-stream p90 values
throughput average: 23.894   ← mean of per-stream p90 values
throughput stdev: 0.071      ← spread across streams
throughput cumulative: 95.574← total system FPS (sum of all stream p90s)
throughput min: 23.806       ← worst-case stream — used for pass/fail vs -t

# ── HW metrics section ────────────────────────────────────────────────
---hw-metrics---
hw_sample_count: 29          ← number of metric snapshots collected

hw_cpu_util_pct avg: 32.510  ← CPU utilization during window (avg/min/max)
hw_cpu_util_pct min: 18.200
hw_cpu_util_pct max: 51.300
hw_cpu_freq_mhz avg: 2850.000
hw_mem_used_percent avg: 42.100

hw_gpu_compute_util_pct avg: 87.400   ← CCS: OpenVINO AI inference engine
hw_gpu_video_util_pct avg: 22.100     ← VCS: H.264 hardware decode engine
hw_gpu_render_util_pct avg: 0.500     ← RCS: 3D render engine
hw_gpu_enhance_util_pct avg: 0.200    ← VECS: video enhancement engine
hw_gpu_util_combined avg: 87.400      ← max(CCS, VCS) per sample, averaged
hw_gpu_freq_mhz avg: 1950.000

hw_rapl_psys_w avg: 45.200    ← full platform power (CPU + iGPU + DRAM + misc)
hw_rapl_pkg_w avg: 28.300     ← SoC package power (CPU cores + iGPU)
hw_rapl_core_w avg: 20.100    ← CPU cores only
hw_rapl_uncore_w avg: 2.400   ← uncore (LLC, memory controller)
hw_pkg_power_w avg: 9.627     ← qmassa SoC power reading (cross-reference)
hw_gpu_power_w avg: 5.484     ← qmassa GPU power rail

hw_npu_utilization avg: 0.000 ← 0.0 when pipeline runs on CPU or GPU
hw_npu_frequency avg: 0.000
hw_npu_power avg: 0.000
```

> `hw_sample_count: 0` means metrics-manager was unreachable or returned no data. FPS results are still valid.

### Output Directory Structure

All output is created **relative to the directory where you run the command** (app root recommended):

```text
uav-vision-analytics/
│
├── benchmark-density-uav_object_detection_cpu/   ← best run for CPU pipeline
│   ├── kpi.txt          ← FPS stats + hw_* metrics (avg/min/max)
│   ├── hw_samples.log   ← raw HW snapshots (key=value lines, "---" per sample)
│   └── sample.logs      ← raw DLSPS /pipelines/status JSON per second
│
├── benchmark-density-uav_object_detection_gpu/   ← best run for GPU pipeline
│   ├── kpi.txt
│   ├── hw_samples.log
│   └── sample.logs
│
├── benchmark-density-uav_object_detection_npu/   ← best run for NPU pipeline
│   ├── kpi.txt
│   ├── hw_samples.log
│   └── sample.logs
│
└── benchmark-multi/                                 ← nstreams mode output
    ├── kpi.txt
    ├── hw_samples.log
    └── sample.logs
```

> **Note:** Intermediate numbered directories (`benchmark-1/`, `benchmark-2/`,
> etc.) are created during the search and **automatically cleaned up** once the
> best result is copied to the named `benchmark-density-<pipeline>/` directory.

## Troubleshooting

For all benchmark-related troubleshooting (missing tools, connectivity issues,
result anomalies, GPU/NPU visibility, and power readings), see the
[Troubleshooting guide](./troubleshooting.md#benchmark).
