<!--
Copyright (C) 2026 Intel Corporation

SPDX-License-Identifier: Apache-2.0

These contents may have been developed with support from one or more
Intel-operated generative artificial intelligence solutions.
-->
# Command Reference

## Monitoring Modes

| Mode | Tracks | Overhead | Use when |
|------|--------|----------|----------|
| **Thread** (default) | Individual threads (TIDs) | ~5-10% | Debugging, optimization |
| **PID** (`--pid-only`) | Processes only | ~2-3% | Production, long-term |

---

## Quick Reference

| Task | Command | Duration |
|------|---------|----------|
| Quick check | `uv run python src/monitor_stack.py --duration 30` | 30s |
| Full monitor | `uv run python src/monitor_stack.py` | until Ctrl-C |
| Full monitor, PID mode | `uv run python src/monitor_stack.py --pid-only` | until Ctrl-C |
| Monitor specific node | `uv run python src/monitor_stack.py --node /my_node` | until Ctrl-C |
| Timed session | `uv run python src/monitor_stack.py --duration 300` | 5 min |
| Graph only | `uv run python src/monitor_stack.py --graph-only` | until Ctrl-C |
| Resources only (threads) | `uv run python src/monitor_stack.py --resources-only` | until Ctrl-C |
| Resources only (PIDs) | `uv run python src/monitor_stack.py --resources-only --pid-only` | until Ctrl-C |
| Remote system | `uv run python src/monitor_stack.py --remote-ip <ip>` | until Ctrl-C |
| Remote system, PID mode | `uv run python src/monitor_stack.py --remote-ip <ip> --pid-only` | until Ctrl-C |
| Pipeline graph (PNG) | `uv run python src/visualize_graph.py <session>/graph_timing.csv --topology <session>/graph_topology.json --no-show` | — |
| Pipeline graph (interactive) | `uv run python src/visualize_graph.py <session>/graph_timing.csv --show` | — |
| List sessions | `uv run python src/monitor_stack.py --list-sessions` | — |
| Re-visualize timing | `uv run python src/visualize_timing.py <session>/graph_timing.csv --delays --frequencies --show` | — |
| Re-visualize resources | `uv run python src/visualize_resources.py <session>/resource_usage.log --cores --heatmap --show` | — |
| Trigger latency analysis | `uv run python src/analyze_trigger_latency.py` | — |
| Trigger latency + JSON output | `uv run python src/analyze_trigger_latency.py --json-out SESSION/kpi.json` | — |
| Trigger latency from rosbag | `uv run python src/analyze_trigger_latency.py --bag <bag_dir>` | — |
| Cross-run aggregate summary | `uv run python src/aggregate_kpi.py BENCH_DIR` | — |
| Aggregate + CSV export | `uv run python src/aggregate_kpi.py BENCH_DIR --csv-out BENCH_DIR/results.csv` | — |
| Regression check (vs baseline) | `python3 src/compare_kpi.py --baseline BASELINE.json --current CURRENT.json` | — |
| Regression check (with report) | `python3 src/compare_kpi.py --baseline B --current C --threshold 5.0 --report report.json` | — |
| Run unit tests | `make test` | — |
| Clean all data | `make clean` | — |

---

## monitor_stack.py Options

```bash
uv run python src/monitor_stack.py [OPTIONS]
```

| Option | Description |
|--------|-------------|
| `--node NAME` | Narrow graph discovery to one node (proc delay measured for all nodes regardless) |
| `--session NAME` | Name for this session (default: timestamp) |
| `--duration SECS` | Auto-stop after N seconds |
| `--interval SECS` | Update interval (default: 5) |
| `--output-dir PATH` | Where to save results |
| `--graph-only` | Skip resource monitoring |
| `--resources-only` | Skip graph monitoring |
| `--pid-only` | Process-level only, no thread details |
| `--gpu` | Enable Intel GPU monitoring (auto-detected when hardware present) |
| `--npu` | Enable Intel NPU monitoring via sysfs |
| `--no-visualize` | Skip auto-visualization on exit |
| `--remote-ip IP` | Monitor a remote machine |
| `--remote-user USER` | SSH user for remote machine (default: ubuntu) |
| `--list-sessions` | List previous sessions and exit |

**Examples:**

```bash
uv run python src/monitor_stack.py --node /slam_toolbox --session my_test --duration 120
uv run python src/monitor_stack.py --remote-ip 192.168.1.100 --node /slam_toolbox
uv run python src/monitor_stack.py --resources-only --pid-only --duration 60
```

---

## Common Invocations

```bash
uv run python src/monitor_stack.py --node /slam_toolbox --duration 120 --interval 2
uv run python src/monitor_stack.py --remote-ip 192.168.1.100 --node /slam_toolbox --remote-user ros
```

---

## Individual Scripts

### ros2_graph_monitor.py

```bash
uv run python src/ros2_graph_monitor.py                           # All nodes, proc delay for each
uv run python src/ros2_graph_monitor.py --node /slam_toolbox      # Scope discovery to one node
uv run python src/ros2_graph_monitor.py --node /ctrl --log t.csv  # With CSV logging
uv run python src/ros2_graph_monitor.py --interval 2              # Custom interval
uv run python src/ros2_graph_monitor.py --remote-ip 192.168.1.100
```

### monitor_resources.py

```bash
uv run python src/monitor_resources.py                            # CPU only
uv run python src/monitor_resources.py --memory --threads         # CPU + memory + threads
uv run python src/monitor_resources.py --memory --log out.log     # With logging
uv run python src/monitor_resources.py --list                     # List ROS2 processes
uv run python src/monitor_resources.py --remote-ip 192.168.1.100 --memory
```

### visualize_timing.py

```bash
uv run python src/visualize_timing.py timing.csv --delays --frequencies --output-dir ./plots/
```

### visualize_resources.py

```bash
uv run python src/visualize_resources.py resource.log --cores --heatmap --top 10 --output-dir ./plots/
uv run python src/visualize_resources.py resource.log --summary   # text table only
```

> CPU% scale: 100% = 1 full core. Use the **Avg Cores** column in `--summary` output for a human-readable reading.

### gpu_pid_analyzer.py

Per-process Intel GPU utilisation with full engine-class breakdown.
Requires `qmassa` installed via `make install-qmassa`.

```bash
uv run python src/gpu_pid_analyzer.py                     # one-shot snapshot
uv run python src/gpu_pid_analyzer.py --watch             # refresh every 2 s
uv run python src/gpu_pid_analyzer.py --duration 60       # run for 60 s
uv run python src/gpu_pid_analyzer.py --interval 1 --csv gpu.csv   # 1 s interval + CSV log
uv run python src/gpu_pid_analyzer.py --json-log gpu.jsonl         # raw JSON-lines log
```

| Option | Description |
|--------|-------------|
| `--interval SEC` | Sampling interval (default: 2.0) |
| `--duration SEC` | Total run duration (0 = one snapshot) |
| `--watch` | Keep refreshing until Ctrl-C |
| `--csv FILE` | Append rows to a CSV file |
| `--json-log FILE` | Append raw JSON-lines to a file |
| `--quiet` | Suppress console output (useful with `--csv`) |

### visualize_gpu.py

Renders GPU utilization from `gpu_usage.log` as a multi-panel plot.

```bash
uv run python src/visualize_gpu.py <session>/gpu_usage.log
uv run python src/visualize_gpu.py <session>/gpu_usage.log --save --output-dir ./plots
uv run python src/visualize_gpu.py <session>/gpu_usage.log --show --top 8
uv run python src/visualize_gpu.py --session 20260312_134253
uv run python src/visualize_gpu.py   # auto-uses latest session
```

### visualize_graph.py

Renders the ROS2 computation graph as a directed topology diagram.

```bash
# Headless PNG
uv run python src/visualize_graph.py monitoring_sessions/<name> --no-show --output graph.png

# Interactive (click nodes to see topic detail popup)
uv run python src/visualize_graph.py monitoring_sessions/<name> --show
```

```bash
uv run python src/visualize_graph.py monitoring_sessions/20260306_154140/graph_timing.csv \
  --topology monitoring_sessions/20260306_154140/graph_topology.json --show
```

---

## Grafana Dashboard

| Command | Description |
|---------|-------------|
| `make grafana-start` | Start Grafana + Prometheus (Docker) |
| `make grafana-stop` | Stop stack |
| `make grafana-status` | Check running services — shows URL `http://localhost:30000` (admin/admin) |

Metrics are exposed on **port 9092** (Prometheus occupies 9090 in host-network mode). Prometheus is pre-configured to scrape `localhost:9092`.

## Remote Monitoring

Monitor a ROS2 pipeline running on a **separate machine**.

**Requirements:**
- SSH key-based auth to the remote host (passwordless)
- Matching `ROS_DOMAIN_ID` on both machines
- Same RMW (CycloneDDS or FastDDS) installed locally

```bash
uv run python src/monitor_stack.py --remote-ip 192.168.1.100
uv run python src/monitor_stack.py --remote-ip 192.168.1.100 --remote-user ros --node /slam_toolbox
uv run python src/monitor_stack.py --remote-ip 192.168.1.100 --pid-only --duration 120
```

| Component | How it works |
|-----------|-------------|
| Graph monitor | DDS peer discovery via `CYCLONEDDS_URI` / `ROS_STATIC_PEERS` |
| Resource monitor | Runs `ps` and `pidstat` over SSH |

Results are stored and visualized **locally** on the monitoring machine.

---

## Session Data Layout

```text
monitoring_sessions/
└── 20260209_143022/
    ├── session_info.txt
    ├── graph_timing.csv
    ├── resource_usage.log
    └── visualizations/
```

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| No ROS2 processes found | Run `ros2 node list` to verify nodes are up |
| Monitor exits immediately | Source ROS2: `source /opt/ros/humble/setup.bash` |
| Visualizations not generated | `uv run python src/visualize_timing.py <session>/graph_timing.csv --show` |
| Permission denied | Run `uv sync` if modules are missing |
| Remote: no data | Check SSH auth and matching `ROS_DOMAIN_ID` |
| CPU shows e.g. "563%" | Normal — `pidstat` reports 100% = 1 core. Check **Avg Cores** column. |
| Prometheus exporter port in use | `fuser -k 9092/tcp && uv run python src/prometheus_exporter.py --session-dir <session>` |
| Graph click does nothing | Use `--show` flag (not `--no-show`) to enable TkAgg interactive mode |

---

## Unit Tests

The test suite runs without ROS 2, a live robot, or hardware. It uses
[pytest](https://docs.pytest.org/) via `uv`.

```bash
make test                  # recommended — runs uv run pytest tests/ -v
uv run pytest tests/ -v    # equivalent direct invocation
```

| Test file | What it covers |
|-----------|----------------|
| `tests/test_schema_validation.py` | JSON Schema (Draft 2020-12) validation for Level 1 and Level 2 KPI payloads — valid, missing required fields, wrong values, null-allowed fields |
| `tests/test_regression_check.py` | `compare_kpi.py` regression detection — pass/fail against baseline, threshold override, `--report` JSON output, Level 1 and Level 2 schemas |
| `tests/test_csv_export.py` | `--csv-out` flag on `analyze_trigger_latency.py` and `analyze_pipeline_latency.py` — flag existence and CSV content |
| `tests/test_aggregate_kpi.py` | `_health`, `_consistency`, `_classify` boundary conditions; `aggregate()` statistics, filtering, sort order |
| `tests/test_trigger_latency.py` | `_is_internal` topic filter regex; `find_trigger` binary-search edge cases |
| `tests/test_wandering_metrics.py` | `_extract_goals`, `_extract_elapsed`, `_extract_rtf`, `_extract_hz`, `_verdict` regex extractors |

Shared fixtures live in `tests/fixtures.py`; `sys.path` setup is centralised in `tests/conftest.py`.

---

## compare_kpi.py — KPI Regression Detection

Compares a current benchmark result (Level 1 or Level 2 JSON) against a stored baseline.
Exits non-zero when any KPI regresses beyond the configured threshold.

```bash
python3 src/compare_kpi.py --baseline BASELINE.json --current CURRENT.json [OPTIONS]
```

| Option | Description |
|--------|-------------|
| `--baseline PATH` | Path to the baseline `kpi.json` or `kpi_level2.json` |
| `--current PATH` | Path to the current-run KPI JSON to evaluate |
| `--threshold PCT` | Regression threshold in percent (default: `5.0`) |
| `--report PATH` | Optional path to write a JSON summary report |

**Exit codes:** `0` = all KPIs within threshold · `1` = regression(s) found · `2` = file/schema error

**Examples:**

```bash
# Compare two wandering sessions (5% threshold)
python3 src/compare_kpi.py \
    --baseline monitoring_sessions/wandering/20260430_145256/kpi.json \
    --current  monitoring_sessions/wandering/20260430_145545/kpi.json

# Use the stored synthetic baseline with a custom threshold and JSON report
python3 src/compare_kpi.py \
    --baseline tests/fixtures/baseline/kpi_level2.json \
    --current  monitoring_sessions/wandering/20260430_145545/kpi.json \
    --threshold 10.0 \
    --report   /tmp/regression_report.json

# Via make
make regression-check \
    BASELINE=tests/fixtures/baseline/kpi.json \
    CURRENT=monitoring_sessions/wandering/20260430_145545/kpi.json
```
