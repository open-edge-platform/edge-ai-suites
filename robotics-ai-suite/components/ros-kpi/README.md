<!--
Copyright (C) 2026 Intel Corporation

SPDX-License-Identifier: Apache-2.0

These contents may have been developed with support from one or more
Intel-operated generative artificial intelligence solutions.
-->
# ROS2 KPI Monitoring & Analysis Tools

Monitor, analyze, and visualize Key Performance Indicators in ROS2 systems — node latencies, CPU/memory usage, message flow, and thread-level resource distribution.

## ⚡ Quick Start (Easiest Way)

```bash
cd ~/Documents/ros2-kpi

# Interactive launcher - guides you through everything
./quickstart

# Or invoke directly
uv run python src/monitor_stack.py --duration 30    # Quick 30-second health check
```

**That's it!** The interactive launcher handles ROS2 setup automatically and guides you through all features.

📖 **New User?** See [QUICKSTART.md](QUICKSTART.md) for a complete beginner's guide.

---

**Quick Links:**
- [QUICKSTART.md](QUICKSTART.md) — Complete beginner's guide (start here!)
- [Quick Start](docs/QUICK_START.md) — Command-line quick start
- [Command Reference](docs/COMMANDS.md) — All commands and options
- [Examples](examples/) — Practical usage examples
- [Improvements](docs/IMPROVEMENTS.md) — What's new

---

## Features

- Real-time ROS2 graph monitoring: nodes, topics, message rates, processing delays
- Automatic **per-node** input→output processing delay for every node in the graph (no `--node` flag required)
- CPU, memory, and I/O monitoring via `pidstat` (thread-level or PID-only)
- Cross-machine monitoring via `--remote-ip` (DDS peer discovery + SSH)
- Interactive visualizations: heatmaps, timelines, core utilization, scatter plots
- ROS bag analysis with latency tracking and CPU-cycle estimation
- Organized session output with auto-generated visualizations

---

## Prerequisites

| Requirement | Install |
|-------------|---------|
| ROS2 Humble / Jazzy | [Intel Robotics AI Suite Getting Started](https://docs.openedgeplatform.intel.com/2025.2/edge-ai-suites/robotics-ai-suite/robotics/gsg_robot/index.html) |
| Python 3.8+ | included with Ubuntu 22.04 |
| `uv`, `pidstat`, `psutil`, `matplotlib`, `numpy` | installed automatically by `make install` |

---

## Installation

Install the Debian package for your ROS 2 distro:

```bash
# ROS 2 Jazzy (Ubuntu 24.04)
sudo apt-get install ros-jazzy-benchmark-framework

# ROS 2 Humble (Ubuntu 22.04)
sudo apt-get install ros-humble-benchmark-framework
```

Then install Python and optional dependencies:

```bash
cd /opt/ros/$ROS_DISTRO/share/benchmark-framework
make install
```

---

## Scripts Overview

### monitor_stack.py — Unified Entry Point

Orchestrates graph + resource monitors, saves all output to a dated session folder, and auto-generates visualizations on exit.

```bash
uv run python src/monitor_stack.py [OPTIONS]
```

| Option | Description |
|--------|-------------|
| `--node NAME` | Monitor a specific node (e.g. `/slam_toolbox`) |
| `--session NAME` | Session label (default: timestamp) |
| `--duration SECS` | Auto-stop after N seconds (remote: allow ≥90s — DDS discovery takes 30-60s before topic data flows) |
| `--interval SECS` | Update interval (default: 5) |
| `--output-dir PATH` | Where to save results |
| `--graph-only` | Skip resource monitoring |
| `--resources-only` | Skip graph monitoring |
| `--pid-only` | Process-level only, no thread details |
| `--no-visualize` | Skip auto-visualization on exit |
| `--remote-ip IP` | Monitor a remote machine |
| `--remote-user USER` | SSH user for remote machine (default: ubuntu) |
| `--list-sessions` | List previous sessions and exit |

```bash
uv run python src/monitor_stack.py --node /slam_toolbox --duration 120
uv run python src/monitor_stack.py --node /slam_toolbox --pid-only --duration 120
uv run python src/monitor_stack.py --remote-ip 192.168.1.100 --node /slam_toolbox
```

---

### ros2_graph_monitor.py — Graph & Latency Monitor

Subscribes to all ROS2 topics, measures message rates and **per-node input→output processing delays** for every node in the graph, and logs timing data to CSV.

Processing delay is computed for each node automatically: when a topic fires, the monitor records a `∆t` from the last time any subscriber of that topic received a message to when this output arrived. No `--node` filter is needed — all nodes receive delays simultaneously.

```bash
./src/ros2_graph_monitor.py [OPTIONS]
```

| Option | Description |
|--------|-------------|
| `-n, --node NAME` | Narrow graph discovery to one node (delays still measured for all) |
| `-i, --interval SECS` | Update interval (default: 5) |
| `--log FILE` | Save timing data to CSV |
| `--show-processing` | Show per-node delay summary table |
| `--show-topics` | Show topic statistics table |
| `--show-nodes` | Show node information |
| `--show-io-details` | Show per-topic I/O timing |
| `--show-connections` | Show topic connections |
| `--no-realtime-delays` | Disable live delay printout |
| `--remote-ip IP` | Configure DDS peer discovery for a remote host |

```bash
# Monitor all nodes (processing delays reported for every node)
./src/ros2_graph_monitor.py --log timing.csv

# Narrow discovery to one node (optional)
./src/ros2_graph_monitor.py --node /slam_toolbox --log slam_timing.csv
./src/ros2_graph_monitor.py --remote-ip 192.168.1.100
```

---

### monitor_resources.py — CPU / Memory / I/O Monitor

Detects ROS2 processes and runs `pidstat` to sample CPU, memory, and I/O statistics.

```bash
./src/monitor_resources.py [OPTIONS]
```

| Option | Description |
|--------|-------------|
| `-l, --list` | List detected ROS2 processes and exit |
| `-i, --interval SECS` | Sampling interval, integer >= 1 (default: 1) |
| `-c, --count N` | Number of samples (default: 0 = infinite) |
| `-m, --memory` | Include memory statistics |
| `-d, --io` | Include I/O statistics |
| `-t, --threads` | Per-thread statistics |
| `--continuous` | Auto-refresh process list (not compatible with `--log`) |
| `--log FILE` | Append output to log file |
| `--remote-ip IP` | Run `ps`/`pidstat` on remote host via SSH |
| `--remote-user USER` | SSH user (default: ubuntu) |

```bash
./src/monitor_resources.py --memory --threads --log ros2.log
./src/monitor_resources.py --remote-ip 192.168.1.100 --memory --threads
```

---

### visualize_resources.py — Resource Visualization

Parses `monitor_resources.py` log files and generates CPU/memory plots, heatmaps, and thread-core mapping.

> **CPU% scale**: `pidstat` reports 100% = 1 full core. On a 20-core system the max is 2000%. The summary table includes an **Avg Cores** column and a context note, and plots include a dashed reference line at the 100% (= 1 core) mark.

```bash
./src/visualize_resources.py LOG_FILE [OPTIONS]
```

| Option | Description |
|--------|-------------|
| `--cores` | CPU utilization per core over time |
| `--pids` | CPU utilization per PID/thread (top N) |
| `--heatmap` | Core utilization heatmap |
| `--mapping` | Thread-to-core scatter plot |
| `--top N` | Number of top threads to show (default: 10) |
| `--output-dir DIR` | Save plots as PNG (omit to display interactively) |
| `--summary` | Print statistics only, no plots |

```bash
./src/visualize_resources.py ros2.log --cores --heatmap --top 20 --output-dir ./plots/
./src/visualize_resources.py ros2.log --summary
```

---

### visualize_timing.py — Timing Visualization

Parses CSV logs from `ros2_graph_monitor.py` and generates message timestamp, frequency, and delay plots.

```bash
./src/visualize_timing.py LOG_FILE [OPTIONS]
```

| Option | Description |
|--------|-------------|
| `--timestamps` | Message arrival scatter plot |
| `--frequencies` | Topic message rates over time |
| `--delays` | Processing delay over time |
| `--inter-arrival` | Inter-message timing / jitter |
| `--io-correlation` | Input/output message timing correlation |
| `--output-dir DIR` | Save plots as PNG (omit to display interactively) |
| `--summary` | Print statistics only, no plots |

```bash
./src/visualize_timing.py slam_timing.csv --delays --frequencies --output-dir ./plots/
./src/visualize_timing.py slam_timing.csv --summary
```

---

### visualize_graph.py — Interactive Pipeline Graph

Renders the full ROS2 computation graph as a directed topology diagram. Nodes are color-coded by category; topics are shown as labelled edges.

```bash
./src/visualize_graph.py SESSION_DIR [OPTIONS]
```

| Option | Description |
|--------|-------------|
| `--show` | Open interactive window (TkAgg) |
| `--no-show` | Headless render only |
| `--output FILE` | Save PNG to file |

**Interactive features** (with `--show`):
- Hover over any node or topic for a tooltip.
- **Click a node** to open a detail popup showing:
  - Published and subscribed topics
  - Message count, frequency (Hz), latency mean ± std for each topic
  - Color-coded health indicators (green / yellow / orange / red)
  - Node processing delay (mean ± std)

```bash
uv run python src/visualize_graph.py monitoring_sessions/20260306_154140/graph_timing.csv \
  --topology monitoring_sessions/20260306_154140/graph_topology.json --no-show   # headless PNG
uv run python src/visualize_graph.py monitoring_sessions/20260306_154140/graph_timing.csv \
  --topology monitoring_sessions/20260306_154140/graph_topology.json --show      # interactive
```

---

### analyze_rosbag.py — Bag File Analysis

Analyzes SQLite3 ROS2 bag files: per-topic statistics, input/output latency, CPU-cycle estimates, and an optional interactive node traversal.

Accepts a rosbag `.db3` SQLite file as a positional argument:

```bash
uv run python src/analyze_rosbag.py path/to/bag.db3
```

---

### picknplace_run.sh — Pick-and-Place Benchmark Runner

Thin wrapper around `benchmark_runner.sh` for the pick-and-place scenario.
All scenario behaviour (launch command, stop condition, bag topics, cleanup)
is defined in [`config/picknplace_run.yaml`](config/picknplace_run.yaml).

```bash
bash src/picknplace_run.sh [--timeout SECS] [--record] [--plot]

# Override the run profile (e.g. custom launch args or topic list)
bash src/picknplace_run.sh --run-config config/picknplace_run.yaml
make picknplace-run RUN_CONFIG=config/my_picknplace.yaml
```

Results land in `monitoring_sessions/picknplace/<timestamp>/` and can be visualized:

```bash
uv run python src/visualize_timing.py <session>/graph_timing.csv --delays --frequencies --show
uv run python src/visualize_resources.py <session>/resource_usage.log --cores --heatmap --show
uv run python src/visualize_graph.py <session>/graph_timing.csv --show
```

---

### bag_replay_run.sh — Offline Bag-Replay Benchmarking

Replays any pre-recorded ROS 2 bag through the monitor stack without a live robot or simulator.
Produces deterministic, reproducible KPI results — suitable for CI environments.

```bash
# Single replay pass
make bag-replay BAG=monitoring_sessions/wandering/20260430_145256/bag

# Faster-than-realtime replay
make bag-replay BAG=... RATE=2.0

# 10 independent runs → aggregate KPI
make bag-replay-benchmark BAG=... RUNS=10 RATE=1.0
```

| Option | Default | Description |
|--------|---------|-------------|
| `BAG` | (required) | Path to bag directory containing `metadata.yaml` |
| `RATE` | `1.0` | Replay speed multiplier |
| `LOOP` | `1` | Replay passes per session (0 = infinite) |
| `RUNS` | `10` | Independent runs for `bag-replay-benchmark` |
| `PAUSE` | `10` | Seconds between runs |

Outputs per session: `kpi.json` (Level 1), `kpi_level2.json` (Level 2, chained).

---

### fastmapping_run.sh — fast_mapping RGB-D Benchmark

Thin wrapper around `benchmark_runner.sh` for the fast-mapping scenario.
Launches `ros2 launch fast_mapping fast_mapping.launch.py`, which starts
`fast_mapping_node`, `rviz2`, and replays the bundled Intel spinning RGB-D bag
(`/opt/ros/<distro>/share/bagfiles/spinning`, ~12 s, 175 depth frames).
All scenario behaviour is defined in [`config/fastmapping_run.yaml`](config/fastmapping_run.yaml).

```bash
# Single run
make fastmapping

# 10-run benchmark
make fastmapping-benchmark RUNS=10

# Generate trigger-timeline plots
make fastmapping-plot

# Override the run profile
make fastmapping RUN_CONFIG=config/fastmapping_run.yaml
```

After the run, `analyze_fastmapping_log.py` parses the node's shutdown timing
table and patches `kpi.json` with:

| KPI | Typical value | Description |
|-----|--------------|-------------|
| `throughput_hz` | 7–16 Hz | Frame processing rate |
| `mean_latency_ms` | ~24 ms | Compute time excl. wait-for-frame |
| `mean_jitter_ms` | ~4 ms | Window-to-window timing variation |

Results: `monitoring_sessions/fastmapping/<timestamp>/kpi.json`,
`kpi_level2.json`, `fastmapping_procedures.json`.

---

## Monitoring Modes

| Mode | Tracks | Overhead | Use when |
|------|--------|----------|----------|
| **Thread** (default) | Individual threads (TIDs) | ~5-10% | Debugging, optimization |
| **PID** (`--pid-only`) | Processes only | ~2-3% | Production, long-term |

---

## Remote Monitoring

Monitor a ROS2 pipeline running on a **separate machine**.

**Requirements:**
- SSH key-based (passwordless) auth to the remote host
- Matching `ROS_DOMAIN_ID` on both machines
- Same RMW (CycloneDDS or FastDDS) installed locally

| Component | Mechanism |
|-----------|-----------|
| Graph monitor | DDS peer discovery via `CYCLONEDDS_URI` / `ROS_STATIC_PEERS` |
| Resource monitor | Runs `ps` and `pidstat` over SSH |

```bash
uv run python src/monitor_stack.py --remote-ip 192.168.1.100
uv run python src/monitor_stack.py --remote-ip 192.168.1.100 --remote-user ros --node /slam_toolbox
uv run python src/monitor_stack.py --remote-ip 192.168.1.100 --pid-only --duration 120
```

> **Note:** CycloneDDS peer discovery over a LAN typically takes **30–60 seconds** before the remote graph is visible and topic messages start being logged. Use `DURATION=180` or longer for remote sessions to ensure meaningful data capture.

Results are stored and visualized locally on the monitoring machine.

### Remote Monitoring Verification

Before starting remote monitoring, verify connectivity and prerequisites:

```bash
# Test SSH connectivity
ssh -o BatchMode=yes remote_user@remote_ip 'echo "Connected"'

# Test resource monitoring (works without local ROS2)
python3 src/monitor_resources.py --remote-ip REMOTE_IP --remote-user USER --list
```

For detailed test results and troubleshooting, see [REMOTE_MONITORING_TEST_REPORT.md](REMOTE_MONITORING_TEST_REPORT.md).

**Note:** Resource monitoring works immediately if SSH is configured. Graph monitoring requires ROS2 installed locally.

---

## 🖥️ Intel GPU Monitoring

GPU monitoring uses **qmassa** — reads xe/i915 DRM `fdinfo` directly.
No `CAP_PERFMON`, no PMU, no custom kernel headers required.

### Install qmassa (once)

```bash
make install-qmassa
# installs Rust toolchain via rustup (if absent), then:
# cargo install --locked qmassa qmmd
# binaries land in ~/.cargo/bin/
```

### Enable GPU monitoring

GPU hardware is **auto-detected** at startup. Pass `--gpu` to force-enable:

```bash
# Auto-detect (recommended)
uv run python src/monitor_stack.py --duration 180

# Explicit GPU flag
uv run python src/monitor_stack.py --gpu --duration 180

# Combined GPU + NPU
uv run python src/monitor_stack.py --gpu --npu --duration 180

# Remote session (sysfs fallback — qmassa is local-only)
uv run python src/monitor_stack.py --remote-ip 10.0.0.1 --gpu --duration 180
```

### Standalone per-PID GPU analyzer

```bash
uv run python src/gpu_pid_analyzer.py                  # one-shot snapshot
uv run python src/gpu_pid_analyzer.py --watch          # refresh every 2 s
uv run python src/gpu_pid_analyzer.py --duration 60    # run for 60 s
uv run python src/gpu_pid_analyzer.py --csv gpu.csv    # CSV logging
```

### What gets collected

| Field | Description |
|-------|-------------|
| `busy_pct` | Overall GPU busy % (peak engine class) |
| `act_freq_mhz` | Actual GT clock (MHz) |
| `power_gpu_w` / `power_pkg_w` | GPU / package power via RAPL (W) |
| `temp_c` | GPU temperature from hwmon sysfs (°C) |
| `vram_used_mb` / `smem_used_mb` | VRAM and shared memory usage (MB) |
| `throttled` | True when any throttle reason is active |
| `engines` | Per-class busy %: Render/3D, Blitter, Compute, Video, VE |
| `clients` | Per-PID: pid, name, total busy %, per-engine busy % |
| `drv_name` | DRM driver (`xe` or `i915`) |

Results are written to `gpu_usage.log` (JSON-lines) in each session directory and
visualised as `visualizations/gpu_utilization.png`.

---

## 🧠 Intel NPU Monitoring

For systems with an Intel NPU (Meteor Lake, Arrow Lake, Lunar Lake and later),
the stack reads kernel sysfs directly — **no root, no special capabilities, no
extra tools needed**.

### Quick start

```bash
# 3-minute session (recommended — DDS discovery takes ~30-60s)
uv run python src/monitor_stack.py --remote-ip 10.0.0.1 --remote-user intel --domain-id 46 --npu --algorithm wandering --duration 180

# Local NPU monitoring
uv run python src/monitor_stack.py --npu --duration 120

# Combined GPU + NPU
uv run python src/monitor_stack.py --remote-ip 10.0.0.1 --remote-user intel --domain-id 46 --gpu --npu --algorithm wandering --duration 180

# Visualize the latest NPU session
uv run python src/visualize_npu.py $(ls -td monitoring_sessions/*/ | head -1)
```

### How it works

Metrics are derived from four sysfs files under `/sys/class/accel/accel0/device/`:

| sysfs file | Description |
|------------|-------------|
| `npu_busy_time_us` | Cumulative busy time in μs — sampled twice per interval; delta / wall-time = busy % |
| `npu_current_frequency_mhz` | Current NPU clock frequency |
| `npu_max_frequency_mhz` | Maximum configurable frequency |
| `npu_memory_utilization` | Memory utilization in bytes |

The `accel0` device node is the standard Linux kernel interface for Intel VPU/NPU
(driver: `intel_vpu` / `ivpu`, first available in kernel 6.3).  No firmware or
user-space daemon is required.

### Logged fields

Results are written to `npu_usage.log` (JSON-lines) in each session directory:

| Field | Description |
|-------|-------------|
| `busy_pct` | NPU compute utilisation % (delta-sampled) |
| `cur_freq_mhz` | Current NPU clock (MHz) |
| `max_freq_mhz` | Maximum NPU clock (MHz) |
| `memory_used_mb` | Memory utilization (MB) |

### Dashboard panels

`uv run python src/visualize_npu.py <session>` generates `visualizations/npu_dashboard.png` with three panels:

1. **NPU Busy %** — utilisation over time with fill
2. **Clock Frequency** — current vs max (clickable legend)
3. **Memory Utilization** — MB over time with fill

### Verifying NPU presence

```bash
# Check locally
ls /sys/class/accel/
cat /sys/class/accel/accel0/device/npu_max_frequency_mhz

# Check on remote
ssh intel@<ip> "cat /sys/class/accel/accel0/device/npu_max_frequency_mhz"
```

If the directory does not exist, the NPU driver is not loaded or the hardware is
not present. In that case `monitor_resources` prints `[NPU] No Intel NPU sysfs
found — NPU monitoring skipped.` and continues normally.

---

## ⚡ Intel RAPL CPU Package Power Monitoring

CPU package power is sampled in the background via the Linux **powercap RAPL**
sysfs interface — **no root, no special capabilities required**.  Available on
Intel bare-metal systems running kernel ≥ 3.13 with `CONFIG_INTEL_RAPL`.
Returns `null` on WSL2 and ARM.

### RAPL quick start

```bash
# Standalone — CPU power only
uv run python src/monitor_resources.py --power

# Combined with CPU/memory/NPU resource monitoring
uv run python src/monitor_resources.py --memory --npu --power

# Check whether RAPL is available on this machine
uv run python src/monitor_resources.py --check-hw
```

`monitor_stack.py` **auto-enables** RAPL power monitoring when the sysfs path
is readable — no flag needed for normal benchmark sessions.

### How RAPL works

`monitor_resources.py --power` launches a daemon thread that:

1. Reads `/sys/class/powercap/intel-rapl/intel-rapl:0/energy_uj` (µJ counter).
2. Computes `power_w = Δenergy_µJ / Δtime_s / 1_000_000`, handling counter
   wraparound using `max_energy_range_uj`.
3. Appends a JSON-line `{"ts": <epoch>, "power_w": <float>}` to `cpu_power.log`
   each interval.

### RAPL logged fields

`cpu_power.log` (JSON-lines) in each session directory:

| Field | Description |
|-------|-------------|
| `ts` | Unix timestamp of the sample |
| `power_w` | CPU package power in watts |

`analyze_trigger_latency.py` reads `cpu_power.log` and stores the **mean** as
`cpu_pkg_power_w` in the Level 1 KPI `thermal` section.

### Verifying RAPL availability

```bash
uv run python src/monitor_resources.py --check-hw
# [PWR] RAPL path     : /sys/class/powercap/intel-rapl/intel-rapl:0/energy_uj
# [PWR] Status        : ✅ AVAILABLE
# [PWR] Detail        : Intel RAPL accessible at /sys/class/...
```

---

## 📤 KPI Export: CSV & Excel

All benchmark scripts support exporting results to **CSV** and optionally **Excel (`.xlsx`)** for analysis in spreadsheet tools.

### Level 1 — Per-pair latency (analyze_trigger_latency.py)

```bash
uv run python src/analyze_trigger_latency.py \
    --json-out <session>/kpi.json \
    --csv-out  <session>/kpi_pairs.csv \
    --xlsx-out <session>/kpi_pairs.xlsx   # requires: pip install openpyxl
```

One row per node/input→output pair:

| Column | Description |
|--------|-------------|
| `session` | Session directory name (timestamp) |
| `node` | ROS 2 node name |
| `pipeline_stage` | Classified stage: Sensor / Perception / Planning / Control / Other |
| `input` | Input topic |
| `output` | Output topic |
| `n` | Number of trigger samples |
| `mean_ms` | Mean processing latency (ms) |
| `stdev_ms` | Standard deviation (ms) |
| `min_ms` | Minimum latency (ms) |
| `p50_ms` | 50th percentile / median (ms) |
| `p90_ms` | 90th percentile (ms) |
| `p99_ms` | 99th percentile (ms) |
| `max_ms` | Maximum observed latency (ms) |
| `trigger_count` | Total trigger events counted |
| `fps` | Estimated output throughput (Hz) |
| `jitter_mean_ms` | Mean inter-message jitter (ms) |
| `jitter_max_ms` | Maximum inter-message jitter (ms) |

### Level 2 — Pipeline end-to-end (analyze_pipeline_latency.py)

```bash
uv run python src/analyze_pipeline_latency.py \
    --kpi      <session>/kpi.json \
    --csv-out  <session>/kpi_level2.csv \
    --xlsx-out <session>/kpi_level2.xlsx  # requires: pip install openpyxl
```

One **e2e summary row** (`type=e2e`) followed by one row per pipeline **stage** (`type=stage`):

| Column | e2e row | stage row |
|--------|---------|-----------|
| `type` | `e2e` | `stage` |
| `session` | Session name | Session name |
| `stage` | `e2e` | Stage name (e.g. `Perception`) |
| `representative_node` | _(blank)_ | Node with highest trigger count in stage |
| `representative_input` | Pipeline input topic | Stage input topic |
| `representative_output` | Pipeline output topic | Stage output topic |
| `mean_ms` | Chained e2e mean (ms) | Stage mean (ms) |
| `p50_ms` | Chained p50 (ms) | Stage p50 (ms) |
| `p90_ms` | Chained p90 (ms) | Stage p90 (ms) |
| `p99_ms` | Chained p99 (ms) | Stage p99 (ms) |
| `max_ms` | Chained max (ms) | Stage max (ms) |
| `n` | Min samples across stages | Stage sample count |
| `throughput_hz` | Pipeline throughput (Hz) | Stage throughput (Hz) |
| `drop_rate_pct` | Message drop rate (%) | _(blank)_ |
| `bottleneck_stage` | Slowest stage name | _(blank)_ |
| `cpu_mean_pct` | Mean CPU utilisation (%) | _(blank)_ |
| `cpu_max_pct` | Peak CPU utilisation (%) | _(blank)_ |

### Multi-run aggregated (aggregate_kpi.py)

```bash
uv run python src/aggregate_kpi.py monitoring_sessions/wandering/bench_XXXX \
    --csv-out results_aggregated.csv
```

One row per (node, input, output) pair aggregated across all runs in the bench directory. Columns: `node`, `input`, `output`, `category`, `runs_seen`, `total_runs`, `mean_fps`, `fps_stdev`, `mean_ms`, `stdev_runs`, `cv_pct`, `min_mean_ms`, `max_mean_ms`, `mean_p90_ms`, `worst_p90_ms`, `best_p90_ms`, `mean_p50_ms`, `mean_stdev_ms`, `mean_n`.

> **Excel support**: install `openpyxl` once with `pip install openpyxl`. If not installed, `--xlsx-out` prints a warning and is skipped; all other outputs are unaffected.

---

### KPI Regression Detection (compare_kpi.py)

Compare a current benchmark result against a stored baseline and detect regressions.

```bash
python3 src/compare_kpi.py \
    --baseline tests/fixtures/baseline/kpi_level2.json \
    --current  monitoring_sessions/wandering/<session>/kpi.json \
    --threshold 5.0 \
    --report   report.json
```

| Option | Description |
|--------|-------------|
| `--baseline PATH` | Baseline `kpi.json` or `kpi_level2.json` |
| `--current PATH` | Current-run KPI JSON to evaluate |
| `--threshold PCT` | Regression threshold in % (default: `5.0`) |
| `--report PATH` | Optional JSON summary report output |

Exit codes: **0** = all KPIs within threshold · **1** = regression(s) found · **2** = file/schema error.

Or use the Makefile shortcut:

```bash
make regression-check \
    BASELINE=tests/fixtures/baseline/kpi.json \
    CURRENT=monitoring_sessions/wandering/<session>/kpi.json
```

---

## Session Data Layout

```text
monitoring_sessions/
├── <timestamp>/                   # flat layout (no --algorithm)
│   ├── session_info.txt
│   ├── graph_timing.csv
│   ├── graph_topology.json
│   ├── resource_usage.log
│   ├── gpu_usage.log              # present when --gpu / remote monitoring
│   ├── npu_usage.log              # present when --npu
│   └── visualizations/
└── <algorithm>/                   # grouped layout (--algorithm <name>)
    └── <timestamp>/
        └── ...
```

---

## 📊 Grafana Dashboard Integration

Visualize ROS2 metrics in real-time with **Grafana** dashboards!

### Quick Start

```bash
# 1. Start Grafana and Prometheus
make grafana-start

# 2. Run a monitoring session
uv run python src/monitor_stack.py --duration 120

# 3. Export metrics
uv run python src/prometheus_exporter.py --session-dir monitoring_sessions/$(ls -t monitoring_sessions | head -1)

# 4. Check status and open http://localhost:30000 (admin/admin)
make grafana-status
```

> **Exporter port**: the metrics server runs on **port 9092** (Prometheus itself occupies port 9090 in host-network mode). Prometheus is pre-configured to scrape `localhost:9092`.

### Dashboard Features
- **Interactive Dashboards**: 10+ pre-configured panels with auto-refresh
- **Historical Analysis**: Query and compare metrics over time
- **Custom Alerts**: Set thresholds and get notifications

### Dashboard Panels

| Panel | Metrics Shown |
|-------|---------------|
| Topic Frequencies | Message rates (Hz) per topic |
| Processing Delays | Input→output latency |
| Inter-Message Timing | Jitter and timing consistency |
| CPU Usage | Per-process and per-thread utilization |
| Memory Usage | RAM consumption by process |
| I/O Throughput | Disk read/write rates |
| Topic Statistics Table | Sortable overview of all topics |
| Node Distribution | Activity and latency breakdown |
| **Node Detail — `$node`** | Per-node publishes/subscribes table: topic, frequency, latency, msg count |

Use the **Node** dropdown variable at the top of the dashboard to filter the Node Detail row to any single node. Tables show health-threshold coloring (green < 20 ms, yellow < 100 ms, red ≥ 100 ms).

### Grafana Prerequisites

```bash
# Install Docker and Docker Compose
sudo apt-get install docker.io docker-compose
sudo usermod -aG docker $USER  # Logout/login required

# Install Python prometheus client
uv sync
```

### Documentation

See [docs/GRAFANA_SETUP.md](docs/GRAFANA_SETUP.md) for:
- Detailed setup instructions
- Configuration options
- Troubleshooting guide
- Custom dashboard creation
- Alert configuration

### Stop Dashboard Stack

```bash
./stop_grafana.sh
```

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| No ROS2 processes found | Verify with `ros2 node list`; source your ROS2 setup |
| `pidstat` not found | `sudo apt-get install sysstat` |
| Matplotlib display error | `export MPLBACKEND=Agg` for headless systems |
| Permission denied | `chmod +x src/*.py monitor_stack.py` |
| Remote: no data | Check SSH key auth and matching `ROS_DOMAIN_ID`; verify with `make check-domain REMOTE_IP=<ip>` |
| Visualizations not generated | `uv run python src/visualize_timing.py <session>/graph_timing.csv --delays --frequencies --show` |
| CPU shows e.g. "563%" | Normal — `pidstat` reports 100% = 1 full core. See the **Avg Cores** column in the summary report. |
| `grafana-export` port in use | Port 9092 conflict: `fuser -k 9092/tcp && uv run python src/prometheus_exporter.py --session-dir <session>` |
| Graph click popup does nothing | Requires TkAgg backend; don't use `--no-show` flag for interactive mode |

---

## Contributing

Pull requests are welcome. Areas of interest: additional KPI metrics, enhanced Grafana dashboards, InfluxDB/Datadog exporters, anomaly detection, broader ROS2 message type support, alert rule templates.

---

## License

Open source. See repository for license details.
