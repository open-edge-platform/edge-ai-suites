<!--
Copyright (C) 2026 Intel Corporation

SPDX-License-Identifier: Apache-2.0
-->

# Command Reference

## Monitoring Modes

| Mode | Tracks | Overhead | Use when |
|------|--------|----------|----------|
| **Thread** (default) | Individual threads (TIDs) | ~5–10% | Debugging, optimization |
| **PID** (`--pid-only`) | Processes only | ~2–3% | Production, long-term runs |

## Quick Reference

| Task | Command | Duration |
|------|---------|----------|
| Quick check | `uv run src/monitor_stack.py --duration 30` | 30 s |
| Full monitor | `uv run src/monitor_stack.py` | until Ctrl-C |
| Full monitor (PID mode) | `uv run src/monitor_stack.py --pid-only` | until Ctrl-C |
| Monitor specific node | `uv run src/monitor_stack.py --node /my_node` | until Ctrl-C |
| Extended session | `uv run src/monitor_stack.py --duration 300` | 5 min |
| Graph only | `uv run src/monitor_stack.py --graph-only` | until Ctrl-C |
| Resources only (threads) | `uv run src/monitor_stack.py --resources-only` | until Ctrl-C |
| Resources only (PIDs) | `uv run src/monitor_stack.py --resources-only --pid-only` | until Ctrl-C |
| Remote system | `./grafana-monitor.sh --remote-ip <ip>` | until Ctrl-C |
| Remote system (PID mode) | `./grafana-monitor.sh --remote-ip <ip> --pid-only` | until Ctrl-C |
| Pipeline graph (interactive) | `uv run src/visualize_graph.py <session> --show` | — |
| Pipeline graph (PNG) | `uv run src/visualize_graph.py <session> --no-show` | — |
| KPI charts + report | `make results` | — |
| Thermal dashboard | `make visualize-thermal` | — |
| GPU dashboard | `uv run src/visualize_gpu.py <session> --show` | — |
| NPU dashboard | `uv run src/visualize_npu.py <session> --show` | — |
| List sessions | `uv run src/monitor_stack.py --list-sessions` | — |
| Re-visualize last session | `uv run src/visualize_timing.py <session>/graph_timing.csv --show` | — |
| Clean all data | `make clean` | — |

```bash
uv run src/monitor_stack.py --node /slam_toolbox --duration 120 --interval 2
./grafana-monitor.sh --remote-ip 192.168.1.100 --node /slam_toolbox --remote-user ros
```

## monitor_stack.py

```bash
uv run src/monitor_stack.py [OPTIONS]
```

| Option | Description |
|--------|-------------|
| `--node NAME` | Narrow graph discovery to one node (proc delay measured for all nodes) |
| `--session NAME` | Name for this session (default: timestamp) |
| `--duration SECS` | Auto-stop after N seconds |
| `--interval SECS` | Update interval (default: 5) |
| `--output-dir PATH` | Where to save results |
| `--graph-only` | Skip resource monitoring |
| `--resources-only` | Skip graph monitoring |
| `--pid-only` | Process-level only, no thread details |
| `--power` | Enable Intel RAPL CPU package power monitoring (writes `cpu_power.log`) |
| `--no-visualize` | Skip auto-visualization on exit |
| `--gpu` | Enable Intel&trade; GPU monitoring (uses `qmassa`; falls back to sysfs remotely) |
| `--npu` | Enable Intel&trade; NPU monitoring via sysfs |
| `--remote-ip IP` | Monitor a remote machine |
| `--remote-user USER` | SSH user for remote machine (default: ubuntu) |
| `--ros-domain-id ID` | Explicitly set `ROS_DOMAIN_ID` (skips auto-detection) |
| `--algorithm LABEL` | Group sessions under `monitoring_sessions/<label>/` |
| `--use-sim-time` | Pass `--use-sim-time` to the graph monitor |
| `--list-sessions` | List previous sessions and exit |

```bash
uv run src/monitor_stack.py --node /slam_toolbox --session my_test --duration 120
uv run src/monitor_stack.py --remote-ip 192.168.1.100 --node /slam_toolbox
uv run src/monitor_stack.py --resources-only --pid-only --duration 60
```

## ros2_graph_monitor.py

```bash
uv run src/ros2_graph_monitor.py                           # All nodes
uv run src/ros2_graph_monitor.py --node /slam_toolbox      # Scope to one node
uv run src/ros2_graph_monitor.py --node /ctrl --log t.csv  # With CSV logging
uv run src/ros2_graph_monitor.py --interval 2              # Custom interval
uv run src/ros2_graph_monitor.py --remote-ip 192.168.1.100
```

## monitor_resources.py

```bash
uv run src/monitor_resources.py                            # CPU only
uv run src/monitor_resources.py --memory --threads         # CPU + memory + threads
uv run src/monitor_resources.py --memory --log out.log     # With logging
uv run src/monitor_resources.py --list                     # List ROS2 processes
uv run src/monitor_resources.py --remote-ip 192.168.1.100 --memory
uv run src/monitor_resources.py --power                    # + Intel RAPL CPU package power
uv run src/monitor_resources.py --memory --npu --power     # CPU + NPU + power
uv run src/monitor_resources.py --check-hw                 # Probe GPU / NPU / RAPL availability
```

## visualize_timing.py

```bash
uv run src/visualize_timing.py timing.csv --delays --frequencies --output-dir ./plots/
```

| Option | Description |
|--------|-------------|
| `--timestamps` | Message arrival scatter plot |
| `--frequencies` | Topic message rates over time |
| `--delays` | Processing delay over time |
| `--inter-arrival` | Inter-message timing / jitter |
| `--output-dir DIR` | Save plots as PNG (omit to display interactively) |
| `--summary` | Print statistics only, no plots |

## visualize_resources.py

```bash
uv run src/visualize_resources.py resource.log --cores --heatmap --top 10 --output-dir ./plots/
uv run src/visualize_resources.py resource.log --summary   # text table only
```

| Option | Description |
|--------|-------------|
| `--cores` | CPU utilization per core over time |
| `--pids` | CPU utilization per PID/thread (top N) |
| `--heatmap` | Core utilization heatmap |
| `--mapping` | Thread-to-core scatter plot |
| `--top N` | Number of top threads to show (default: 10) |
| `--output-dir DIR` | Save plots as PNG |
| `--summary` | Print statistics only, no plots |

> **Note:** `pidstat` reports CPU% where 100% = 1 full core. On a 20-core
> system the maximum is 2000%. Use the **Avg Cores** column in `--summary`
> output for a human-readable reading.

## visualize_graph.py

Renders the ROS2 computation graph as a directed topology diagram.

```bash
# Headless PNG
uv run src/visualize_graph.py monitoring_sessions/<name> --no-show --output graph.png

# Interactive (click nodes to see topic detail popups)
uv run src/visualize_graph.py monitoring_sessions/<name> --show
```

## Hardware Visualizers (GPU / NPU)

All visualizers accept a session directory or log file as their first
argument and auto-detect the latest session when omitted.

```bash
# GPU dashboard (5 panels: busy%, frequency, temperature, power, per-PID)
uv run src/visualize_gpu.py <session_dir>
uv run src/visualize_gpu.py <session_dir> --save
uv run src/visualize_gpu.py <session_dir> --summary

# NPU dashboard (3 panels: busy%, clock frequency, memory)
uv run src/visualize_npu.py <session_dir>
uv run src/visualize_npu.py <session_dir> --no-show
```

## visualize_thermal.py

Renders CPU/GPU temperature, throttle state, and RAPL power from `cpu_power.log` and `gpu_usage.log`.

```bash
uv run src/visualize_thermal.py <session_dir> --save   # writes 3 PNGs to visualizations/
uv run src/visualize_thermal.py <session_dir> --show   # interactive window
uv run src/visualize_thermal.py                        # auto-uses latest session
```

Output files written when `--save` is used:

| File | Contents |
|------|----------|
| `thermal_throttle.png` | Combined 3-panel overview (temp + throttle + power) |
| `thermal_temperature.png` | CPU / GPU temperature over time |
| `thermal_power.png` | RAPL CPU package power (W) over time |

```bash
# Makefile shortcut
make visualize-thermal
make visualize-thermal SESSION=monitoring_sessions/<name>
```

| Common option | Description |
|---------------|-------------|
| `--session PATH` | Explicit session directory |
| `--output-dir DIR` | Save PNG here (default: session `visualizations/`) |
| `--save` | Write PNG without opening a window |
| `--show` | Open an interactive matplotlib window |
| `--no-show` | Never open a window (headless / CI) |
| `--summary` | Print text summary only, no plot |

> Enable GPU logging with `--gpu` and NPU logging with `--npu` on
> `monitor_stack.py`. Intel&trade; GPU monitoring requires `qmassa` (`make install-qmassa`).

## visualize_kpi.py

Generates publication-ready charts from `kpi.json` files produced by the
benchmark framework. Supports latency histograms, cross-SKU comparisons,
resource utilization breakdowns, and Level-2 throughput/drop-rate charts.

```bash
# All charts for a session directory
uv run src/visualize_kpi.py --session monitoring_sessions/<name>

# Cross-SKU comparison
uv run src/visualize_kpi.py \
    --kpi mtl.json arl.json ptl.json \
    --label MTL ARL PTL \
    --output-dir charts/

# SVG output
uv run src/visualize_kpi.py --session <dir> --format svg
```

| Option | Description |
|--------|-------------|
| `--session DIR` | Session directory containing `kpi.json` |
| `--kpi FILE [FILE ...]` | One or more `kpi.json` paths (for cross-SKU comparison) |
| `--label LABEL [...]` | SKU labels matching `--kpi` files (e.g. `MTL ARL PTL`) |
| `--kpi2 FILE` | Path to `kpi_level2.json` for Level-2 charts |
| `--output-dir DIR` | Output directory for charts (default: `<session>/charts` or `./charts`) |
| `--format {png,svg}` | Output image format (default: `png`) |

## analyze_rosbag.py

Analyses a ROS2 bag file and prints per-topic statistics, message latency,
and node graph information. Accepts SQLite3 `.db3` or `.mcap` bag files.

```bash
uv run src/analyze_rosbag.py path/to/bag.db3
uv run src/analyze_rosbag.py path/to/bag.mcap
```

All analysis is run automatically and printed to stdout.

## Scenario Benchmark Runner

`benchmark_runner.sh` is the generic orchestrator used by all scenario run scripts.
It is driven entirely by a YAML run profile (`config/*.yaml`).

```bash
bash src/benchmark_runner.sh --run-config config/wandering_run.yaml
bash src/wandering_run.sh --record --plot      # record KPI bag + generate plots
bash src/wandering_run.sh --show               # record + plot + auto-open HTML report
bash src/wandering_run.sh --timeout 120        # hard stop after 2 min
```

| Flag | Description |
|------|-------------|
| `--record` | Record KPI topics to an MCAP bag |
| `--plot` | Save trigger-timeline PNG charts after analysis |
| `--show` | Implies `--record --plot`; auto-opens `make results` at end of run |
| `--timeout SECS` | Override YAML stop timeout |
| `--goals N` | Stop after N goal events |
| `--output-parent DIR` | Session parent directory |

**Progress stages printed during each run:**

```text
[1/6] Pre-run cleanup
[2/6] Launching <scenario> simulation
[3/6] Starting monitor stack
[4/6] Running benchmark
[5/6] Post-Run Analysis      (scenario-specific, e.g. fastmapping log parse)
[6/6] Trigger-Latency Analysis
```

**Make targets** (plain targets default to `--record --plot`):

```bash
make wandering                              # single run with record + plot
make wandering SHOW=1                       # single run + auto-open report
make wandering-benchmark RUNS=5 TIMEOUT=120 # 5-run benchmark + aggregate
make picknplace-run                         # single run with record + plot
make fastmapping                            # single run with record + plot
make fastmapping SHOW=1                     # single run + auto-open report
```

## bag_replay_run.sh / make bag-replay

Replays a previously recorded bag file through the monitoring stack,
enabling reproducible offline benchmarking and CI integration.

```bash
# Via Makefile (recommended)
make bag-replay BAG=/path/to/bag.db3
make bag-replay BAG=/path/to/bag.db3 RATE=0.5 RUNS=5

# Directly
./src/bag_replay_run.sh /path/to/bag.db3
```

| Variable | Default | Description |
|----------|---------|-------------|
| `BAG` | (required) | Path to the bag file to replay |
| `RATE` | `1.0` | Playback rate multiplier |
| `LOOP` | `false` | Loop the bag continuously |
| `RUNS` | `1` | Number of benchmark repetitions |
| `PAUSE` | `5` | Seconds to pause between runs |

## fastmapping_run.sh / make fastmapping

Runs the FastMapping RGB-D SLAM benchmark, which exercises the fast-mapping
pipeline across a sequence of depth images.

```bash
# Single run
make fastmapping

# Multiple runs (benchmark mode)
make fastmapping-benchmark RUNS=10

# Visualize results
make fastmapping-plot
```

See [FastMapping Benchmark](fastmapping-benchmark.md) for a complete walkthrough.

## Grafana Dashboard Commands

| Command | Description |
|---------|-------------|
| `make grafana-start` | Start Grafana + Prometheus (Docker) |
| `make grafana-stop` | Stop the stack |
| `make grafana-status` | Check services — shows URL http://localhost:30000 |
| `make grafana-export SESSION=<name>` | Export session metrics to Prometheus |
| `make grafana-export-live` | Continuously export live monitoring data |
| `make grafana-open` | Open dashboard in browser |

Metrics are exposed on **port 9092** (Prometheus occupies 9090 in
host-network mode). Prometheus is pre-configured to scrape `localhost:9092`.

## Remote Monitoring

| Component | How it works |
|-----------|-------------|
| Graph monitor | DDS peer discovery via `CYCLONEDDS_URI` / `ROS_STATIC_PEERS` |
| Resource monitor | Runs `ps` and `pidstat` over SSH |

Results are stored and visualized **locally** on the monitoring machine.

```bash
uv run src/monitor_stack.py --remote-ip 192.168.1.100
uv run src/monitor_stack.py --remote-ip 192.168.1.100 --remote-user ros --node /slam_toolbox
uv run src/monitor_stack.py --remote-ip 192.168.1.100 --pid-only --duration 120
```

## Troubleshooting

| Problem | Fix |
|---------|-----|
| No ROS2 processes found | Run `ros2 node list` to verify nodes are up |
| Monitor exits immediately | Source ROS2: `source /opt/ros/humble/setup.bash` |
| Visualizations not generated | Run `uv run src/visualize_timing.py <session>/graph_timing.csv --show` manually |
| Permission denied | Run `uv sync` if modules are missing |
| Remote: no data | Check SSH auth and matching `ROS_DOMAIN_ID` |
| CPU shows e.g. "563%" | Normal — 100% = 1 core. Check **Avg Cores** column. |
| `grafana-export` port in use | `fuser -k 9092/tcp && make grafana-export SESSION=<name>` |
| Graph click does nothing | Use `--show` flag to enable TkAgg interactive mode |
