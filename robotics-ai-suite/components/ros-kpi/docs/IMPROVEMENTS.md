<!--
Copyright (C) 2026 Intel Corporation

SPDX-License-Identifier: Apache-2.0

These contents may have been developed with support from one or more
Intel-operated generative artificial intelligence solutions.
-->
# Summary of Improvements

## 🗓️ May 2026 — Latest Updates

### Intel RAPL CPU Package Power Monitoring (0.1.17)

CPU package power is now sampled in the background via the Linux **powercap
RAPL** sysfs interface — no root, no special capabilities required.

**How it works:**

`monitor_resources.py --power` launches a daemon thread that reads
`/sys/class/powercap/intel-rapl/intel-rapl:0/energy_uj` at the configured
interval, computes watts from successive delta-energy / delta-time samples
(handling counter wraparound), and writes JSON-lines to `cpu_power.log`.
`monitor_stack.py` auto-enables power monitoring when RAPL is available (bare
metal Intel; unavailable on WSL2 and ARM).

**New `cpu_pkg_power_w` field in the Level 1 KPI `thermal` section:**

| Field | Source | Description |
|-------|--------|-------------|
| `cpu_pkg_power_w` | `cpu_power.log` (mean over session) | Mean CPU package power in watts via Intel RAPL powercap sysfs. `null` when RAPL is unavailable (WSL2, ARM, non-Intel). |

**Files changed:**

| File | Change |
|------|--------|
| `src/monitor_resources.py` | `probe_cpu_power_available()`, `monitor_cpu_power()`, `--power` / `--power-log` CLI flags; `--check-hw` now shows RAPL status |
| `src/monitor_stack.py` | `enable_power` param; auto-detects RAPL; passes `--power --power-log` to resource monitor subprocess |
| `src/analyze_trigger_latency.py` | Reads `cpu_power.log`, averages `power_w` samples → `cpu_pkg_power_w` in thermal section |
| `schemas/kpi_level1_v1.json` | `cpu_pkg_power_w` (number\|null) added to `thermal` object |
| `src/prometheus_exporter.py` | `ros2_cpu_package_power_watts` Gauge updated on each scrape from `cpu_power.log` |

### Bag-Replay & fast_mapping Benchmarking (0.1.16)

Deterministic, reproducible benchmark runs from pre-recorded ROS 2 bags — no
live robot or simulator required.  Enables offline and CI benchmarking.

**Generic bag-replay (`src/bag_replay_run.sh`):**

```bash
# Single replay pass
make bag-replay BAG=monitoring_sessions/wandering/20260430_145256/bag

# 2× speed
make bag-replay BAG=... RATE=2.0

# 10 independent runs → aggregate KPI
make bag-replay-benchmark BAG=... RUNS=10
```

Replays any bag at configurable rate/loop count through the monitor stack;
collects Level 1 and Level 2 KPIs after each session.

**fast_mapping benchmark (`src/fastmapping_run.sh`):**

```bash
# Single run — uses bundled spinning RGB-D bag automatically
make fastmapping

# 10-run benchmark
make fastmapping-benchmark RUNS=10 RATE=1.0
```

Launches `fast_mapping_node` + `ros2 bag play` of the bundled spinning bag
(`/opt/ros/jazzy/share/bagfiles/spinning`, 12 s, 175 RGB-D frames).  After
replay, `analyze_fastmapping_log.py` parses the node's shutdown timing report
and patches `kpi.json` with real node-level KPIs.

**`src/analyze_fastmapping_log.py`** — new log parser:

| KPI | Source | Description |
|-----|--------|-------------|
| `throughput_hz` | `"Frequency: X Hz"` in log | Overall pipeline throughput across all frames |
| `mean_latency_ms` | `Total − wait_for_frame` | Actual compute latency (preprocess + octree + publish), excl. idle wait |
| `mean_jitter_ms` | Window-to-window period variation | Timing consistency across 3-second windows |
| `max_jitter_ms` | max − min window period | Worst-case throughput swing |

Per-procedure breakdown (when node shuts down cleanly):

| Procedure | Typical time | % |
|-----------|-------------|---|
| wait for a new frame | 86.5 ms | 63 % — IO idle, excluded from latency |
| Preprocess frame | 20.7 ms | 15 % |
| Octree integrate | 2.95 ms | 2 % |
| Publish voxels | 7 µs | <1 % |

When the procedure table isn't captured (node killed before clean shutdown),
the analyzer falls back to window-based KPIs and notes this in the output.
The `kpi.json` and `kpi_level2.json` always pass schema validation in both
modes.

**Files added:**

| File | Description |
|------|-------------|
| `src/bag_replay_run.sh` | Generic bag-replay benchmark script |
| `src/fastmapping_run.sh` | fast_mapping-specific benchmark script |
| `src/analyze_fastmapping_log.py` | Log parser — patches kpi.json from node timing report |

**Makefile targets added:**

| Target | Description |
|--------|-------------|
| `bag-replay BAG=<dir>` | Single replay + L1/L2 KPI |
| `bag-replay-plot BAG=<dir>` | Same + trigger-timeline plots |
| `bag-replay-benchmark BAG=<dir> [RUNS=10]` | N independent runs → aggregate KPI |
| `fastmapping` | Single fast_mapping run (bundled bag) |
| `fastmapping-plot` | Same + plots |
| `fastmapping-benchmark [RUNS=10]` | N independent runs → aggregate KPI |

---

### GPU Visualization Fixes (0.1.16)

Three bugs in GPU monitoring/visualization fixed after testing with real i915
session data:

**Bug 1 — Per-engine breakdown not showing (i915)**
`ENGINE_CLASSES` regex in `gpu_engine_defs.py` didn't match the fdinfo key
names used by qmassa on i915 (`"copy"`, `"video-enhance"`).  Fixed:

| qmassa i915 key | Now maps to |
|-----------------|-------------|
| `"render"` | Render/3D ✓ (already worked) |
| `"copy"` | Blitter (new) |
| `"video"` | Video ✓ (already worked) |
| `"video-enhance"` | VE (new — hyphenated) |

**Bug 2 — Y-axis clipping at 100%**
`busy_pct` from qmassa is the SUM across all DRM clients, so it routinely
exceeds 100 % on busy systems (observed: 3414 %).  Hardcoded `ylim(-2, 108)`
clipped all data.  Fixed with dynamic y-axis and `MaxNLocator(nbins=8)` to
prevent MAXTICKS warnings.

**Bug 3 — Frequency always 0 on i915**
The i915 DRM driver does not expose GT frequency via fdinfo (xe does).
Fixed by supplementing from sysfs `gt_act_freq_mhz` / `gt_max_freq_mhz` in
`monitor_resources.py` when qmassa reports 0 and `drv_name == "i915"`.

---

### NPU Throttle Detection + Dependency Security Fixes (0.1.15)

**NPU throttle detection** is now live in `monitor_resources.py`. The
`_read_sysfs_npu()` function compares `npu_current_frequency_mhz` against
`npu_max_frequency_mhz`; when the ratio drops below 95 % the `throttled`
field is set `True` and the console shows `⚠THROTTLE`. The `npu_throttled`
field in the Level 1 KPI `thermal` section is now populated from the session's
`npu_usage.log` (previously always `null`).

**Security dependency bumps** (via `uv audit`):

| Package | Old floor | New floor | CVEs fixed |
|---------|-----------|-----------|-----------|
| `pillow` | `>=12.1.1` | `>=12.2.0` | 5 (heap overflow, OOB write, DoS, int overflow) |
| `pytest` (dev) | `>=7.0.0` | `>=9.0.3` | 1 (CVE-2025-71176 tmpdir) |
| `pygments` (dev, new) | — | `>=2.20.0` | 1 (CVE-2026-4539 ReDoS) |

---

### Thermal & Throttle Correlation in Level 1 KPI JSON (0.1.14)

GPU, NPU, and CPU temperature and throttle state are now captured alongside
latency/jitter metrics in the Level 1 KPI JSON produced by
`analyze_trigger_latency.py --json-out`.

**New `thermal` section in `kpi.json`:**

| Field | Source | Description |
|-------|--------|-------------|
| `cpu_temp_c` | `/sys/class/thermal/thermal_zone*/` (`x86_pkg_temp`) | CPU package temperature (°C) at analysis time |
| `gpu_temp_c` | `gpu_usage.log` (mean over session) | GPU temperature from qmassa / hwmon sysfs |
| `npu_temp_c` | `npu_usage.log` (mean over session) | NPU junction temperature (°C) |
| `cpu_throttled` | `cpufreq/scaling_cur_freq` vs `cpuinfo_max_freq` | `true` when CPU freq < 95 % of max |
| `gpu_throttled` | `gpu_usage.log` | `true` if any sample had GPU throttle active |
| `npu_throttled` | — | `null` (not exposed via sysfs) |

All fields are nullable — sessions without GPU/NPU monitoring or running on
hardware where sysfs is unavailable produce `null` values and still pass
schema validation.

**Files changed:**

| File | Change |
|------|--------|
| `src/analyze_trigger_latency.py` | `_read_cpu_thermal_sysfs()`, `_load_resource_thermal()` helpers; `build_performance_kpi()` now emits `thermal` section |
| `src/monitor_resources.py` | `_read_cpu_thermal_sysfs()` helper for sysfs CPU temp / throttle |
| `schemas/kpi_level1_v1.json` | Optional `thermal` object property with all six nullable fields |

---

### GPU Monitoring: qmassa-only (intel_gpu_top removed)

`intel_gpu_top` is no longer used. All GPU monitoring now goes through
**qmassa** (reads xe/i915 DRM `fdinfo` directly — no `CAP_PERFMON` required).

**Install qmassa once:**
```bash
make install-qmassa   # builds via cargo; installs to ~/.cargo/bin/
```

**What changed:**

| File | Change |
|------|--------|
| `src/monitor_resources.py` | Removed `_try_intel_gpu_top_local`, `_find_local_igt`, `_parse_igt_clients`; qmassa-only path with sysfs RC6 fallback for remote sessions |
| `src/gpu_pid_analyzer.py` | Full rewrite: qmassa-only, no `--remote-ip`; per-PID engine breakdown via DRM fdinfo |
| `src/visualize_gpu.py` | Removed `intel_gpu_top` source guards; engine/power panels work for any qmassa record |
| `src/visualize_resources.py` | Removed `intel_gpu_top` source guards; RC6 overlay removed from frequency panel |
| `src/monitor_stack.py` | Auto-detects GPU/NPU hardware at startup; `--gpu` help updated (no CAP_PERFMON) |
| `Makefile` | Removed `setup-remote-gpu` target (was for intel_gpu_top CAP_PERFMON) |

**qmassa output fields** logged per sample:

| Field | Description |
|-------|-------------|
| `source` | `'qmassa'` |
| `busy_pct` | Overall GPU busy % (max engine) |
| `act_freq_mhz` | Actual GT frequency |
| `power_gpu_w` / `power_pkg_w` | GPU / package power via RAPL |
| `temp_c` | GPU temperature from hwmon sysfs |
| `vram_used_mb` / `smem_used_mb` | VRAM and shared memory usage |
| `throttled` | Throttle status |
| `engines` | Per-class busy % (`Render/3D`, `Blitter`, `Compute`, `Video`, `VE`) |
| `clients` | Per-PID: `pid`, `name`, `total`, per-engine busy % |
| `drv_name` | DRM driver (`xe` or `i915`) |

**GPU PID analyzer usage:**
```bash
uv run python src/gpu_pid_analyzer.py                   # one-shot snapshot
uv run python src/gpu_pid_analyzer.py --watch           # refresh every 2 s
uv run python src/gpu_pid_analyzer.py --duration 60     # run for 60 s
uv run python src/gpu_pid_analyzer.py --csv gpu.csv     # CSV logging
```

---

### pytest Test Suite (117 tests, no ROS 2 required)

The project now has a full unit-test suite runnable without a live robot, ROS 2
install, or hardware.

```bash
make test          # recommended
uv run pytest tests/ -v
```

**New test files added:**

| File | Tests | Scope |
|------|------:|-------|
| `tests/test_schema_validation.py` | 14 | JSON Schema validation for Level 1 & Level 2 KPI payloads (parametrized table-driven) |
| `tests/test_regression_check.py` | 8 | `compare_kpi.py` — pass/fail, threshold override, `--report` JSON, Level 1 regressions |
| `tests/test_csv_export.py` | 3 | `--csv-out` flag existence and CSV content for both analysis scripts |
| `tests/test_aggregate_kpi.py` | 37 | `_health`, `_consistency`, `_classify` boundary conditions; `aggregate()` statistics, sort, filtering |
| `tests/test_trigger_latency.py` | 30 | `_is_internal` regex (13 filtered + 8 pass-through topics); `find_trigger` binary-search (9 edge cases) |
| `tests/test_wandering_metrics.py` | 25 | `_extract_goals/elapsed/rtf/hz`, `_verdict` regex extractors with spacing/absent/multi-block variants |

**Infrastructure:**
- `tests/conftest.py` — centralises `sys.path` setup (replaces per-file `sys.path.insert` calls)
- `tests/fixtures.py` — single source of truth for synthetic Level 1 / Level 2 KPI payloads
- CI (`build-test-scan.yml`) runs `uv run pytest tests/ -v` as a single step replacing three separate `python3` invocations

### JSON Schema Fix — `pipeline_stage` in Level 1 pairs

`schemas/kpi_level1_v1.json` was missing `pipeline_stage` from the allowed
properties of `pairs` items (schema used `additionalProperties: false`).
Valid output from `analyze_trigger_latency.py` was being rejected by its own
schema. Fixed by adding `pipeline_stage` as an `enum` field.

---

## 🗓️ April 2026 — Latest Updates

### Structured Benchmark Results Output
`analyze_trigger_latency.py` now emits a structured JSON (via `--json-out`) and
prints a compact **Performance Summary** table after every analysis run.

**JSON output** (`build_performance_kpi`):
- Top-level fields: `throughput_hz`, `mean_latency_ms`, `mean/max/min_jitter_ms`,
  `jitter_stdev_ms`, `cpu_mean_pct`, `cpu_max_pct`
- `per_node` block — per-node throughput, latency, jitter, primary input/output,
  pipeline stage
- `pairs` list — full scalar stats per (node, input, output) including `fps`,
  `jitter_mean_ms`, `jitter_max_ms`
- `metadata` block — `name`, `datetime`, `hostname`, `arch`, `os`, `data_path`

**Terminal summary** (`print_performance_summary`) — printed automatically after
every run:
```text
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Performance Summary
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Component              Input → Output         Throughput  Latency     p90
  controller_server      plan → cmd_vel           80.1 Hz   12.5 ms   25.3 ms
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

### Cross-Run Aggregate Summary
`aggregate_kpi.py` now shows a **Throughput (Hz)** column in the detailed
report and appends a compact `Aggregate Summary` table at the end:
```text
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Aggregate Summary  |  bench_20260318_120000  |  25 runs
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Component            Output        Throughput  Mean Latency  Worst p90
  controller_server    /cmd_vel        79.4 Hz      13.1 ms     28.4 ms
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

---

## 🗓️ March 2026 — Latest Updates

### CPU% Clarity in Resource Reports
`visualize_resources.py` now makes multi-core CPU% readings unambiguous:
- **`Avg Cores` column** in the summary table (value = CPU% ÷ 100, e.g. "5.63 cores" instead of "563%")
- **Context note** at the top of every report: *"100% = 1 full core. System has N logical cores (max: N×100%)"*
- **Reference line** at 100% (dashed gray, "= 1 core") on all CPU utilization and heatmap plots

### Interactive Pipeline Graph — Click to See Node Details
`visualize_graph.py` (`uv run python src/visualize_graph.py <session>/graph_timing.csv --show`) now supports clicking on nodes:
- Opens a **Tkinter popup** with publishers and subscribers for that node
- Each topic row shows: message count, frequency (Hz), latency mean ± std
- Color-coded health dots: green < 20 ms, yellow < 100 ms, orange < 500 ms, red ≥ 500 ms
- Re-clicking the same node refreshes the popup; clicking elsewhere closes it

### Grafana Node Detail Panels
The Grafana dashboard now includes a **Node Detail** row:
- `$node` dropdown variable auto-populated from `label_values(ros2_node_topic_frequency_hz, node)`
- **Publishes** and **Subscribes** table panels per node with latency threshold coloring
- New Prometheus metrics: `ros2_node_topic_frequency_hz`, `ros2_node_topic_latency_ms`, `ros2_node_topic_msg_count`, `ros2_node_proc_delay_ms`

### Exporter Port Changed to 9092
Prometheus runs in host-network mode and occupies port 9090. The KPI exporter now defaults to **port 9092** to avoid the conflict:
- `prometheus/prometheus.yml` scrape target updated to `localhost:9092`
- `Makefile` `grafana-export` and `grafana-export-live` targets updated
- `uv run python src/prometheus_exporter.py` auto-kills stale processes on that port before binding

---

## ✨ What's New

Your ROS2 monitoring stack now has **3 cleaner ways to run**:

### 1. 🐍 Python Orchestrator (`monitor_stack.py`)
Single Python script that manages everything:
```bash
uv run python src/monitor_stack.py --node /your_node
```

---

## 📊 Before vs After

### ❌ Before (The Old Way)
Required **4 separate terminals** and manual coordination:

```bash
# Terminal 1: Start graph monitor
uv run python src/ros2_graph_monitor.py --node /slam_toolbox --log timing.csv

# Terminal 2: Start resource monitor
uv run python src/monitor_resources.py --memory --threads --log resources.log

# Wait... monitor... Ctrl+C on both terminals

# Terminal 3: Manually visualize timing
uv run python src/visualize_timing.py timing.csv --output-dir ./plots/ --delays --frequencies

# Terminal 4: Manually visualize resources
uv run python src/visualize_resources.py resources.log --output-dir ./plots/ --cores --heatmap

# Manually organize files, create directories, etc.
```

**Problems:**
- Too many terminals to manage
- Easy to forget to start one monitor
- Manual file management
- Manual visualization steps
- No session organization
- Hard to reproduce

---

### ✅ After (The New Way)

**Single command in one terminal:**

```bash
uv run python src/monitor_stack.py --node /slam_toolbox
# Press Ctrl+C when done - everything is automatic!
```

**Benefits:**
- ✅ Single command does everything
- ✅ Automatic file organization
- ✅ Auto-generates visualizations on exit
- ✅ Graceful shutdown handling
- ✅ Session history and management
- ✅ Easy to reproduce
- ✅ Clean output structure

---

## 🎯 Key Features of the New Stack

### 1. Automatic Session Management
```text
monitoring_sessions/
└── 20260209_143022/          # Auto-timestamped
    ├── session_info.txt      # What you monitored
    ├── graph_timing.csv      # Raw timing data
    ├── resource_usage.log    # Raw CPU/memory data
    └── visualizations/       # Auto-generated plots
```

### 2. Concurrent Monitoring
- Both graph and resource monitors run simultaneously
- Output is properly multiplexed and labeled
- Both stop gracefully on Ctrl+C

### 3. Built-in Visualization
- Automatically generates all plots when you stop monitoring
- No need to remember visualization commands
- All plots saved in organized structure

### 4. Session History
```bash
# See all past monitoring sessions
uv run python src/monitor_stack.py --list-sessions
```

### 5. Flexible Control
```bash
# Monitor for specific duration
uv run python src/monitor_stack.py --duration 60

# Custom update interval
uv run python src/monitor_stack.py --interval 2

# Graph only (lightweight)
uv run python src/monitor_stack.py --graph-only

# Resources only (with threads)
uv run python src/monitor_stack.py --resources-only

# Resources only (PIDs only)
uv run python src/monitor_stack.py --resources-only --pid-only

# Named sessions for experiments
uv run python src/monitor_stack.py --session my_experiment
```

---

## 🚀 Quick Start Examples

### Example 1: Quick Performance Check
```bash
uv run python src/monitor_stack.py --duration 30
```
Runs a 30-second monitoring session and shows you the results.

### Example 2: Debug a Node
```bash
uv run python src/monitor_stack.py --node /problematic_node
# Let it run while reproducing the issue
# Press Ctrl+C
# Check monitoring_sessions/*/visualizations/
```

### Example 3: Long-term Monitoring
```bash
uv run python src/monitor_stack.py --node /critical_node --session production_test
# Run for hours or days
# All data is properly logged and organized
```

### Example 4: Compare Performance
```bash
# Before optimization
uv run python src/monitor_stack.py --node /controller_server --session before

# After optimization
uv run python src/monitor_stack.py --node /controller_server --session after

# Compare the visualization folders
```

---

## 📁 File Structure

### Current File Structure
```text
ros2-kpi/
├── Makefile              # Infrastructure targets (install, grafana, clean, lint)
├── quickstart            # Interactive menu
│
├── src/
│   ├── monitor_stack.py      # Main orchestrator
│   ├── ros2_graph_monitor.py # Graph monitor
│   ├── monitor_resources.py  # Resource monitor
│   ├── visualize_timing.py   # Timing visualizer
│   ├── visualize_resources.py# Resource visualizer
│   ├── analyze_rosbag.py     # Rosbag analysis
│   └── prometheus_exporter.py# Grafana/Prometheus export
└── README.md                 # Full documentation
```

### Output Structure
```text
monitoring_sessions/
├── 20260209_143022/
│   ├── session_info.txt
│   ├── graph_timing.csv
│   ├── resource_usage.log
│   └── visualizations/
│       ├── timing_delays.png
│       ├── message_frequencies.png
│       ├── cpu_usage_timeline.png
│       └── cpu_heatmap.png
├── 20260209_150315/
│   └── ... (another session)
└── my_experiment/
    └── ... (named session)
```

---

## 🎓 Learning Curve

### For Quick Tasks
Just remember: `uv run python src/monitor_stack.py`

### For Specific Nodes
`uv run python src/monitor_stack.py --node /node_name`

### For Everything Else
Check `uv run python src/monitor_stack.py --help` or `make help`

---

## 🔧 Backward Compatibility

All scripts are in `src/` and invoked via `uv`:
```bash
uv run python src/ros2_graph_monitor.py --node /my_node --log my_timing.csv
uv run python src/monitor_resources.py --memory --log my_resources.log
```

---

## 💡 Recommended Workflow

1. **Start your ROS2 system:**
   ```bash
   ros2 launch my_robot robot.launch.py
   ```

2. **Start monitoring:**
   ```bash
   uv run python src/monitor_stack.py --node /my_critical_node
   ```

3. **Let it run, then press Ctrl+C**

4. **Check results:**
   ```bash
   # Automatically created in:
   # monitoring_sessions/<timestamp>/visualizations/
   ```

5. **Review session history:**
   ```bash
   uv run python src/monitor_stack.py --list-sessions
   ```

---

## 🎉 Benefits Summary

| Before | After |
|--------|-------|
| 4 terminals | 1 terminal |
| 6+ commands | 1 command |
| Manual file management | Automatic organization |
| Manual visualization | Auto-generated plots |
| Hard to reproduce | Session management built-in |
| Easy to forget steps | Single workflow |
| Scattered outputs | Organized sessions |

---

## 📚 Documentation

- **Quick Start:** See [QUICK_START.md](QUICK_START.md)
- **Full Details:** See updated [README.md](README.md)
- **Help:** Run `uv run python src/monitor_stack.py --help` or `make help`

---

## 🤝 Next Steps

1. Try a quick test:
   ```bash
   uv run python src/monitor_stack.py --duration 30
   ```

2. Monitor your specific node:
   ```bash
   uv run python src/monitor_stack.py --node /your_node_name
   ```

3. Explore the session outputs in `monitoring_sessions/`

4. Check out the auto-generated visualizations!

---

Enjoy your streamlined monitoring workflow! 🎉
