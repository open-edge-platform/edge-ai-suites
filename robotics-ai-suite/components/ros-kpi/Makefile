# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
#
# These contents may have been developed with support from one or more
# Intel-operated generative artificial intelligence solutions.
.PHONY: help monitor monitor-node monitor-pid monitor-remote monitor-remote-pid monitor-remote-grafana monitor-remote-pid-grafana monitor-remote-repeat monitor-long monitor-long-pid quick-check \
        graph-only resources-threads resources-pid \
        list-sessions visualize-last visualize-all visualize-gpu visualize-gpu-pid-bar visualize-npu pipeline-graph interactive-heatmap analyze-session compare-sessions \
        view-average view-average-timing view-average-resources view-average-plot \
        clean clean-last clean-session install check-deps check-domain docs setup-remote-gpu \
        monitor-gpu \
        gpu-pids gpu-pids-watch gpu-pids-remote gpu-pids-csv \
        grafana-start grafana-stop grafana-pull grafana-export grafana-export-live grafana-status grafana-logs grafana-open \
        wandering wandering-record wandering-plot wandering-record-plot wandering-benchmark \
        picknplace-run picknplace-record picknplace-plot picknplace-record-plot picknplace-benchmark \
        analyze-benchmark

# Default target
help:
	@echo "ROS2 KPI Monitoring Stack - Available Commands"
	@echo ""
	@echo "⚠️  IMPORTANT: Source ROS2 before monitoring:"
	@echo "   source /opt/ros/humble/setup.bash  (or run: source ./setup_ros2_env.sh)"
	@echo "   export ROS_DOMAIN_ID=0  (must match target system)"
	@echo ""
	@echo "MONITORING (Thread Mode - detailed TID tracking):"
	@echo "  make monitor              - Start full monitoring (60s, graph + resources)"
	@echo "  make monitor-gpu          - Full local monitoring + Intel GPU (60s)"
	@echo "  make monitor-node NODE=<name> - Narrow discovery to one node (proc delay works for all nodes)"
	@echo "  make quick-check          - Quick 30-second monitoring session"
	@echo "  make monitor-long         - Extended 5-minute monitoring session"
	@echo "  make graph-only           - Monitor only graph/timing"
	@echo "  make resources-threads    - Monitor only system resources (with threads)"
	@echo ""
	@echo "MONITORING (PID Mode - process-level only):"
	@echo "  make monitor-pid          - Full monitoring with PIDs only"
	@echo "  make monitor-long-pid     - Extended monitoring with PIDs only (5 min)"
	@echo "  make resources-pid        - Monitor system resources (PIDs only)"
	@echo ""
	@echo "REMOTE MONITORING (from a second machine):"
	@echo "  make monitor-remote REMOTE_IP=<ip>   - Full remote monitoring (threads)"
	@echo "  make monitor-remote REMOTE_IP=<ip> GPU=1            - + Intel GPU metrics"
	@echo "  make monitor-remote REMOTE_IP=<ip> NPU=1            - + Intel NPU metrics (no caps needed)"
	@echo "  make monitor-remote REMOTE_IP=<ip> GPU=1 NPU=1      - + both GPU and NPU"
	@echo "  make monitor-remote-pid REMOTE_IP=<ip> - Full remote monitoring (PIDs only)"
	@echo "  make monitor-remote-pid-grafana REMOTE_IP=<ip> - PID-only remote monitoring + live Grafana export"
	@echo "  Any target accepts: REMOTE_IP=<ip> REMOTE_USER=<user> DOMAIN_ID=<id>"
	@echo "  Example: make monitor NODE=/slam_toolbox REMOTE_IP=192.168.1.100"
	@echo "  Note: requires SSH key auth and matching ROS_DOMAIN_ID"
	@echo ""
	@echo "WANDERING SIMULATION (see also: make -f src/Makefile help):"
	@echo "  make wandering               - Single run + graph monitor + trigger-latency"
	@echo "  make wandering-record        - + record KPI rosbag"
	@echo "  make wandering-benchmark     - RUNS x TIMEOUT-s runs, then aggregate KPIs"
	@echo "  make wandering-benchmark RUNS=5 TIMEOUT=180"
	@echo "  Sessions -> monitoring_sessions/wandering/"
	@echo ""
	@echo "PICKNPLACE SIMULATION (see also: make -f src/Makefile help):"
	@echo "  make picknplace-run          - Single run + graph monitor + trigger-latency"
	@echo "  make picknplace-record       - + record KPI rosbag"
	@echo "  make picknplace-benchmark    - RUNS runs (up to PN_TIMEOUT=300s each), then aggregate"
	@echo "  Sessions -> monitoring_sessions/picknplace/"
	@echo ""
	@echo "BENCHMARKING:"
	@echo "  make analyze-benchmark BENCH=<path>  - Re-aggregate KPIs from a bench dir"
	@echo "  Params: RUNS=25  TIMEOUT=120  PN_TIMEOUT=300  PAUSE=30  NODE=<filter>"
	@echo "  Full target list: make -f src/Makefile help"
	@echo ""
	@echo "VISUALIZATION & ANALYSIS:"
	@echo "  make list-sessions        - List all previous monitoring sessions"
	@echo "  make visualize-last       - Re-visualize the last monitoring session"
	@echo "  make visualize-last ALGORITHM=<name>  - ... latest session for that algorithm"
	@echo "  make visualize-all        - Visualize all plots from last session"
	@echo "  make visualize-all ALGORITHM=<name>   - ... latest session for that algorithm"
	@echo "  make visualize-gpu        - Full GPU dashboard (engine/freq/temp/power/PID) from last session"
	@echo "  make visualize-gpu SESSION=<name>  - ... from specific session"
	@echo "  make visualize-gpu ALGORITHM=<name>  - ... latest session for that algorithm"
	@echo "  make visualize-gpu-pid-bar - Per-PID engine breakdown bar chart from last session"
	@echo "  make visualize-npu        - NPU dashboard (busy/freq/memory) from last session"
	@echo "  make visualize-npu SESSION=<name>  - ... from specific session"
	@echo "  make visualize-npu ALGORITHM=<name>  - ... latest session for that algorithm"
	@echo "  make pipeline-graph       - rqt_graph-style Node->Topic->Node directed graph + KPIs"
	@echo "  make pipeline-graph SHOW=save              - ... save PNG only (no window)"
	@echo "  make pipeline-graph SESSION=<name>         - ... from specific session"
	@echo "  make monitor-remote-repeat REMOTE_IP=<ip> REPEAT=3          - Run N monitoring sessions back-to-back"
	@echo "  make monitor-remote-repeat REMOTE_IP=<ip> REPEAT=5 DURATION=120 PAUSE=10  - ... with custom timing"
	@echo "  make monitor-remote-repeat REMOTE_IP=<ip> REPEAT=3 GPU=1 ALGORITHM=slam DOMAIN_ID=46  - ... + GPU + grouping"
	@echo "  make monitor-remote-repeat REMOTE_IP=<ip> REPEAT=3 NPU=1 ALGORITHM=slam DOMAIN_ID=46  - ... + NPU + grouping"
	@echo "  make monitor-remote-repeat REMOTE_IP=<ip> REPEAT=3 GPU=1 NPU=1 ALGORITHM=slam DOMAIN_ID=46  - ... + GPU + NPU"
	@echo "  make pipeline-graph INCLUDE_SYSTEM=1      - ... also show /rosout /clock /parameter_events /_action"
	@echo "  make pipeline-graph INCLUDE_MONITORS=1     - ... include rviz/rqt observer nodes"
	@echo "  make pipeline-graph INCLUDE_ISOLATED=1     - ... include topic boxes with no edges"
	@echo "  Note: Node boxes show proc delay (Δms) automatically when topology JSON is present"
	@echo "  make interactive-heatmap  - Interactive core heatmap (click for details)"
	@echo "  make analyze-session SESSION=<name> - Analyze specific session"
	@echo "  make compare-sessions     - Compare multiple sessions"
	@echo "  make view-average         - Average KPIs across last 5 sessions"
	@echo "  make view-average RUNS=10 - Average across last N sessions"
	@echo "  make view-average-timing  - Timing averages only"
	@echo "  make view-average-resources - Resource averages only"
	@echo "  make view-average-plot    - Averages + save bar-chart PNGs"
	@echo ""
	@echo "GRAFANA DASHBOARDS:"
	@echo "  make grafana-start        - Start Grafana/Prometheus stack"
	@echo "  make grafana-stop         - Stop Grafana/Prometheus stack"
	@echo "  make grafana-status       - Check dashboard stack status"
	@echo ""
	@echo "UTILITIES:"
	@echo "  make clean                - Remove all monitoring session data"
	@echo "  make clean-last           - Remove the most recent session"
	@echo "  make clean-session SESSION=<name> - Remove specific session"
	@echo "  make install              - Install required dependencies"
	@echo "  make setup-remote-gpu REMOTE_IP=<ip>  - Grant CAP_PERFMON so intel_gpu_top can use PMU"
	@echo "  make check-deps           - Verify all dependencies (uv, ROS2, Python packages)"
	@echo "  make check-domain         - Check ROS_DOMAIN_ID matches on local + remote"
	@echo "  make check-domain REMOTE_IP=<ip> REMOTE_USER=<user>"
	@echo "  make docs                 - Build PDF versions of all documentation"
	@echo ""
	@echo "INTEL GPU PID ANALYSIS:"
	@echo "  make gpu-pids             - One-shot GPU snapshot (engines, freq, temp, watts, per-PID)"
	@echo "  make gpu-pids-watch       - Live GPU monitor (refresh every 2 s, Ctrl-C to stop)"
	@echo "  make gpu-pids-csv         - 60 s capture → gpu_pids.csv"
	@echo "  make gpu-pids INTERVAL=1  - Custom sampling interval (seconds)"
	@echo "  make gpu-pids-remote REMOTE_IP=<ip>         - Remote GPU PID analysis"
	@echo "  make gpu-pids-remote REMOTE_IP=<ip> REMOTE_USER=<user> INTERVAL=1"
	@echo "  Reported: Render/3D  Blitter  Video  VE  Freq(MHz)  Temp(C)  Watts"
	@echo "  Requires: sudo apt install intel-gpu-tools"
	@echo "            sudo setcap cap_perfmon+eip \$$(which intel_gpu_top)"
	@echo ""
	@echo "Examples:"
	@echo "  make monitor NODE=/slam_toolbox DURATION=120  # scope graph discovery to one node"
	@echo "  make monitor DURATION=120                     # all nodes (proc delay for all)"
	@echo "  make monitor-pid DURATION=120"
	@echo "  make quick-check"
	@echo "  make wandering-benchmark RUNS=5 TIMEOUT=180"
	@echo "  make picknplace-benchmark RUNS=5"
	@echo "  make analyze-benchmark BENCH=monitoring_sessions/wandering/bench_20260319_100421"
	@echo "  make analyze-session SESSION=20260211_202949"

# Full monitoring with optional parameters (defaults to 60 seconds)
#   make monitor
#   make monitor ALGORITHM=slam_toolbox
#   make monitor ALGORITHM=nav2 DURATION=120 NODE=/controller_server
monitor:
	@echo "Starting monitoring stack ($(if $(DURATION),$(DURATION)s,until Ctrl+C))..."
	@if [ -n "$(NODE)" ]; then \
		uv run python src/monitor_stack.py --node $(NODE) $(if $(DURATION),--duration $(DURATION)) $(if $(INTERVAL),--interval $(INTERVAL)) $(if $(REMOTE_IP),--remote-ip $(REMOTE_IP)) $(if $(REMOTE_USER),--remote-user $(REMOTE_USER)) $(if $(ALGORITHM),--algorithm '$(ALGORITHM)'); \
	else \
		uv run python src/monitor_stack.py $(if $(DURATION),--duration $(DURATION)) $(if $(INTERVAL),--interval $(INTERVAL)) $(if $(REMOTE_IP),--remote-ip $(REMOTE_IP)) $(if $(REMOTE_USER),--remote-user $(REMOTE_USER)) $(if $(ALGORITHM),--algorithm '$(ALGORITHM)'); \
	fi

# Monitor specific node (shortcut)
monitor-node:
	@if [ -z "$(NODE)" ]; then \
		echo "Error: Please specify NODE=<node_name>"; \
		exit 1; \
	fi
	@uv run python src/monitor_stack.py --node $(NODE) $(if $(DURATION),--duration $(DURATION)) $(if $(INTERVAL),--interval $(INTERVAL)) $(if $(REMOTE_IP),--remote-ip $(REMOTE_IP)) $(if $(REMOTE_USER),--remote-user $(REMOTE_USER)) $(if $(ALGORITHM),--algorithm '$(ALGORITHM)')

# Monitor PIDs only (no thread details)
monitor-pid:
	@echo "Starting monitoring stack (PID-only mode, $(if $(DURATION),$(DURATION)s,until Ctrl+C))..."
	@uv run python src/monitor_stack.py $(if $(DURATION),--duration $(DURATION)) --pid-only $(if $(NODE),--node $(NODE)) $(if $(INTERVAL),--interval $(INTERVAL)) $(if $(REMOTE_IP),--remote-ip $(REMOTE_IP)) $(if $(REMOTE_USER),--remote-user $(REMOTE_USER)) $(if $(ALGORITHM),--algorithm '$(ALGORITHM)')

# Remote monitoring - full (thread mode) - requires REMOTE_IP
monitor-remote:
	@if [ -z "$(REMOTE_IP)" ]; then \
		echo "Error: Please specify REMOTE_IP=<ip_address>"; \
		echo "Example: make monitor-remote REMOTE_IP=192.168.1.100"; \
		exit 1; \
	fi
	@echo "Starting remote monitoring of $(REMOTE_IP) ($(if $(DURATION),$(DURATION)s,until Ctrl+C))..."
	@uv run python src/monitor_stack.py \
		--remote-ip $(REMOTE_IP) $(if $(REMOTE_USER),--remote-user $(REMOTE_USER)) \
		$(if $(DURATION),--duration $(DURATION)) \
		$(if $(NODE),--node $(NODE)) \
		$(if $(INTERVAL),--interval $(INTERVAL)) \
		$(if $(ALGORITHM),--algorithm '$(ALGORITHM)') \
		$(if $(DOMAIN_ID),--ros-domain-id $(DOMAIN_ID)) \
		$(if $(GPU),--gpu) \
		$(if $(NPU),--npu)
monitor-remote-pid:
	@if [ -z "$(REMOTE_IP)" ]; then \
		echo "Error: Please specify REMOTE_IP=<ip_address>"; \
		echo "Example: make monitor-remote-pid REMOTE_IP=192.168.1.100"; \
		exit 1; \
	fi
	@echo "Starting remote PID monitoring of $(REMOTE_IP)..."
	@uv run python src/monitor_stack.py --remote-ip $(REMOTE_IP) $(if $(REMOTE_USER),--remote-user $(REMOTE_USER)) \
		--pid-only $(if $(DURATION),--duration $(DURATION)) $(if $(NODE),--node $(NODE)) $(if $(INTERVAL),--interval $(INTERVAL)) $(if $(ALGORITHM),--algorithm '$(ALGORITHM)') $(if $(DOMAIN_ID),--ros-domain-id $(DOMAIN_ID))

# Local full monitoring + Intel GPU
monitor-gpu:
	@echo "Starting local monitoring with Intel GPU ($(if $(DURATION),$(DURATION)s,until Ctrl+C))..."
	@echo "  Requires: sudo setcap cap_perfmon+eip $$(which intel_gpu_top)"
	@uv run python src/monitor_stack.py --gpu \
		$(if $(DURATION),--duration $(DURATION)) \
		$(if $(INTERVAL),--interval $(INTERVAL)) \
		$(if $(NODE),--node $(NODE)) \
		$(if $(ALGORITHM),--algorithm '$(ALGORITHM)')

# Quick 30-second check
quick-check:
	@echo "Running quick 30-second monitoring check..."
	@uv run python src/monitor_stack.py --duration 30 --interval 2

# Extended monitoring session (5 minutes) - Thread mode
monitor-long:
	@echo "Running extended monitoring session (5 minutes, with threads)..."
	@uv run python src/monitor_stack.py --duration 300 --interval 5 $(if $(NODE),--node $(NODE)) $(if $(REMOTE_IP),--remote-ip $(REMOTE_IP)) $(if $(REMOTE_USER),--remote-user $(REMOTE_USER))

# Extended monitoring session (5 minutes) - PID mode
monitor-long-pid:
	@echo "Running extended monitoring session (5 minutes, PID-only)..."
	@uv run python src/monitor_stack.py --duration 300 --interval 5 --pid-only $(if $(NODE),--node $(NODE)) $(if $(REMOTE_IP),--remote-ip $(REMOTE_IP)) $(if $(REMOTE_USER),--remote-user $(REMOTE_USER))

# Graph monitoring only
graph-only:
	@uv run python src/monitor_stack.py --graph-only $(if $(DURATION),--duration $(DURATION)) $(if $(NODE),--node $(NODE)) $(if $(REMOTE_IP),--remote-ip $(REMOTE_IP)) $(if $(REMOTE_USER),--remote-user $(REMOTE_USER))

# Resource monitoring only (with thread details)
resources-threads:
	@uv run python src/monitor_stack.py --resources-only $(if $(DURATION),--duration $(DURATION)) $(if $(INTERVAL),--interval $(INTERVAL)) $(if $(REMOTE_IP),--remote-ip $(REMOTE_IP)) $(if $(REMOTE_USER),--remote-user $(REMOTE_USER))

# Resource monitoring only (PIDs, no threads)
resources-pid:
	@uv run python src/monitor_stack.py --resources-only --pid-only $(if $(DURATION),--duration $(DURATION)) $(if $(REMOTE_IP),--remote-ip $(REMOTE_IP)) $(if $(REMOTE_USER),--remote-user $(REMOTE_USER))

# List all previous sessions
list-sessions:
	@uv run python src/monitor_stack.py --list-sessions

# Visualize the most recent session
# Finds the latest session in both flat (monitoring_sessions/<ts>/) and
# algorithm-grouped (monitoring_sessions/<algo>/<ts>/) layouts.
# Override with: make visualize-last ALGORITHM=slam_toolbox
visualize-last:
	@echo "Re-visualizing last monitoring session..."
	@SESS_DIR=$$(if [ -n "$(ALGORITHM)" ]; then \
	               ls -td monitoring_sessions/$(ALGORITHM)/[0-9]*/ 2>/dev/null | head -1 | sed 's|/$$||'; \
	             else \
	               ls -td monitoring_sessions/[0-9]*/ monitoring_sessions/*/[0-9]*/ 2>/dev/null | head -1 | sed 's|/$$||'; \
	             fi); \
	if [ -n "$$SESS_DIR" ]; then \
		echo "Processing session: $$SESS_DIR"; \
		if [ -f "$$SESS_DIR/graph_timing.csv" ]; then \
			uv run python src/visualize_timing.py "$$SESS_DIR/graph_timing.csv" \
				--output-dir "$$SESS_DIR/visualizations" \
				--delays --frequencies --show; \
		fi; \
		if [ -f "$$SESS_DIR/resource_usage.log" ]; then \
			uv run python src/visualize_resources.py "$$SESS_DIR/resource_usage.log" \
				--output-dir "$$SESS_DIR/visualizations" \
				--cores --heatmap --top 10 --show; \
		fi; \
		if [ -f "$$SESS_DIR/gpu_usage.log" ]; then \
			uv run python src/visualize_gpu.py "$$SESS_DIR/gpu_usage.log" \
				--output-dir "$$SESS_DIR/visualizations" \
				--save --show; \
		fi; \
		if [ -f "$$SESS_DIR/npu_usage.log" ]; then \
			uv run python src/visualize_npu.py "$$SESS_DIR/npu_usage.log" \
				--output-dir "$$SESS_DIR/visualizations"; \
		fi; \
		echo "Visualizations updated in: $$SESS_DIR/visualizations/"; \
	else \
		echo "No monitoring sessions found."; \
	fi

# Visualize all plots from the last session
visualize-all:
	@echo "Generating all visualizations from last session..."
	@SESS_DIR=$$(if [ -n "$(ALGORITHM)" ]; then \
	               ls -td monitoring_sessions/$(ALGORITHM)/[0-9]*/ 2>/dev/null | head -1 | sed 's|/$$||'; \
	             else \
	               ls -td monitoring_sessions/[0-9]*/ monitoring_sessions/*/[0-9]*/ 2>/dev/null | head -1 | sed 's|/$$||'; \
	             fi); \
	if [ -n "$$SESS_DIR" ]; then \
		echo "Processing session: $$SESS_DIR"; \
		if [ -f "$$SESS_DIR/graph_timing.csv" ]; then \
			uv run python src/visualize_timing.py "$$SESS_DIR/graph_timing.csv" \
				--output-dir "$$SESS_DIR/visualizations" \
				--timestamps --frequencies --delays --inter-arrival \
				--io-correlation --categories --activity-heatmap --delay-heatmap --show; \
		fi; \
		if [ -f "$$SESS_DIR/resource_usage.log" ]; then \
			uv run python src/visualize_resources.py "$$SESS_DIR/resource_usage.log" \
				--output-dir "$$SESS_DIR/visualizations" \
				--cores --pids --heatmap --mapping --top 20 --show; \
		fi; \
		if [ -f "$$SESS_DIR/gpu_usage.log" ]; then \
			uv run python src/visualize_gpu.py "$$SESS_DIR/gpu_usage.log" \
				--output-dir "$$SESS_DIR/visualizations" \
				--save --show --pid-bar; \
		fi; \
		if [ -f "$$SESS_DIR/npu_usage.log" ]; then \
			uv run python src/visualize_npu.py "$$SESS_DIR/npu_usage.log" \
				--output-dir "$$SESS_DIR/visualizations"; \
		fi; \
		echo "All visualizations saved to: $$SESS_DIR/visualizations/"; \
	else \
		echo "No monitoring sessions found."; \
	fi

# ─────────────────────────────────────────────────────────────────────────────
# GPU-specific visualization targets
#
#   make visualize-gpu                         # latest session, save + interactive
#   make visualize-gpu SESSION=20260312_134253  # specific session
#   make visualize-gpu-pid-bar                 # per-PID engine breakdown only
# ─────────────────────────────────────────────────────────────────────────────
visualize-gpu:
	@SESSION_DIR=$$(if [ -n "$(SESSION)" ]; then \
	                 find monitoring_sessions -mindepth 1 -maxdepth 2 -name "$(SESSION)" -type d 2>/dev/null | head -1; \
	               elif [ -n "$(ALGORITHM)" ]; then \
	                 ls -td monitoring_sessions/$(ALGORITHM)/[0-9]*/ 2>/dev/null | head -1 | sed 's|/$$||'; \
	               else \
	                 ls -td monitoring_sessions/[0-9]*/ monitoring_sessions/*/[0-9]*/ 2>/dev/null | head -1 | sed 's|/$$||'; \
	               fi); \
	if [ -z "$$SESSION_DIR" ]; then \
		echo "Error: No monitoring session found. Run 'make monitor-gpu' first."; exit 1; \
	fi; \
	GPU_LOG="$$SESSION_DIR/gpu_usage.log"; \
	if [ ! -f "$$GPU_LOG" ]; then \
		echo "Error: $$GPU_LOG not found.  Run 'make monitor-remote GPU=1' or 'make monitor-gpu' first."; exit 1; \
	fi; \
	mkdir -p "$$SESSION_DIR/visualizations"; \
	echo "GPU log: $$GPU_LOG"; \
	uv run python src/visualize_gpu.py "$$GPU_LOG" \
		--output-dir "$$SESSION_DIR/visualizations" \
		--save --show $(if $(TOP),--top $(TOP)) $(if $(LINES),--lines $(LINES))

visualize-gpu-pid-bar:
	@SESSION_DIR=$$(if [ -n "$(SESSION)" ]; then \
	                 find monitoring_sessions -mindepth 1 -maxdepth 2 -name "$(SESSION)" -type d 2>/dev/null | head -1; \
	               elif [ -n "$(ALGORITHM)" ]; then \
	                 ls -td monitoring_sessions/$(ALGORITHM)/[0-9]*/ 2>/dev/null | head -1 | sed 's|/$$||'; \
	               else \
	                 ls -td monitoring_sessions/[0-9]*/ monitoring_sessions/*/[0-9]*/ 2>/dev/null | head -1 | sed 's|/$$||'; \
	               fi); \
	if [ -z "$$SESSION_DIR" ]; then \
		echo "Error: No monitoring session found."; exit 1; \
	fi; \
	GPU_LOG="$$SESSION_DIR/gpu_usage.log"; \
	if [ ! -f "$$GPU_LOG" ]; then \
		echo "Error: $$GPU_LOG not found."; exit 1; \
	fi; \
	mkdir -p "$$SESSION_DIR/visualizations"; \
	uv run python src/visualize_gpu.py "$$GPU_LOG" \
		--output-dir "$$SESSION_DIR/visualizations" \
		--save --show --pid-bar $(if $(TOP),--top $(TOP))

# NPU dashboard: busy %, clock frequency, memory utilization
visualize-npu:
	@SESSION_DIR=$$(if [ -n "$(SESSION)" ]; then \
	                 find monitoring_sessions -mindepth 1 -maxdepth 2 -name "$(SESSION)" -type d 2>/dev/null | head -1; \
	               elif [ -n "$(ALGORITHM)" ]; then \
	                 ls -td monitoring_sessions/$(ALGORITHM)/[0-9]*/ 2>/dev/null | head -1 | sed 's|/$$||'; \
	               else \
	                 ls -td monitoring_sessions/[0-9]*/ monitoring_sessions/*/[0-9]*/ 2>/dev/null | head -1 | sed 's|/$$||'; \
	               fi); \
	if [ -z "$$SESSION_DIR" ]; then \
		echo "Error: No monitoring session found. Run 'make monitor-remote NPU=1' first."; exit 1; \
	fi; \
	NPU_LOG="$$SESSION_DIR/npu_usage.log"; \
	if [ ! -f "$$NPU_LOG" ]; then \
		echo "Error: $$NPU_LOG not found. Run 'make monitor-remote NPU=1' or add --npu to your monitor command."; exit 1; \
	fi; \
	mkdir -p "$$SESSION_DIR/visualizations"; \
	echo "NPU log: $$NPU_LOG"; \
	uv run python src/visualize_npu.py "$$NPU_LOG" \
		--output-dir "$$SESSION_DIR/visualizations"

# ─────────────────────────────────────────────────────────────────────────────
# rqt_graph-style pipeline view – Node → Topic → Node directed graph + KPIs
#
#   make pipeline-graph                         # latest session, interactive window
#   make pipeline-graph SHOW=save               # save PNG only (no window)
#   make pipeline-graph SESSION=20260304_150959 # specific session
#   make pipeline-graph INCLUDE_SYSTEM=1        # also show /rosout /clock /parameter_events /_action etc
#   make pipeline-graph INCLUDE_MONITORS=1      # show rviz/rqt/monitor observer nodes
#   make pipeline-graph INCLUDE_ISOLATED=1      # show topic boxes with no edges
# ─────────────────────────────────────────────────────────────────────────────
pipeline-graph:
	@SESSION_DIR=$$(if [ -n "$(SESSION)" ]; then \
	                 find monitoring_sessions -mindepth 1 -maxdepth 2 -name "$(SESSION)" -type d 2>/dev/null | head -1; \
	               elif [ -n "$(ALGORITHM)" ]; then \
	                 ls -td monitoring_sessions/$(ALGORITHM)/[0-9]*/ 2>/dev/null | head -1 | sed 's|/$$||'; \
	               else \
	                 ls -td monitoring_sessions/[0-9]*/ monitoring_sessions/*/[0-9]*/ 2>/dev/null | head -1 | sed 's|/$$||'; \
	               fi); \
	if [ -z "$$SESSION_DIR" ]; then \
		echo "Error: No monitoring session found. Run 'make monitor' first."; exit 1; \
	fi; \
	CSV="$$SESSION_DIR/graph_timing.csv"; \
	TOPO="$$SESSION_DIR/graph_topology.json"; \
	VIS_DIR="$$SESSION_DIR/visualizations"; \
	mkdir -p "$$VIS_DIR"; \
	if [ ! -f "$$CSV" ]; then \
		echo "Error: $$CSV not found."; exit 1; \
	fi; \
	echo "Session  : $$SESSION_DIR"; \
	echo "CSV      : $$CSV"; \
	if [ -f "$$TOPO" ]; then echo "Topology : $$TOPO (full Node→Topic→Node graph)"; \
	else echo "Topology : not found (topic-only view; re-run monitor to generate graph_topology.json)"; fi; \
	uv run python src/visualize_graph.py "$$CSV" \
		$$([ -f "$$TOPO" ] && echo "--topology $$TOPO") \
		--output-dir "$$VIS_DIR" \
		$(if $(INCLUDE_SYSTEM),--include-system) \
		$(if $(INCLUDE_MONITORS),--include-monitors) \
		$(if $(INCLUDE_ISOLATED),--include-isolated) \
		$(if $(filter save,$(SHOW)),--no-show,--show); \
	echo "Pipeline graph -> $$VIS_DIR/pipeline_graph.png"

# Interactive heatmap with click details
interactive-heatmap:
	@echo "Opening interactive core heatmap..."
	@LAST_SESSION=$$(ls -td monitoring_sessions/[0-9]*/ 2>/dev/null | head -n1 | xargs basename 2>/dev/null); \
	if [ -n "$$LAST_SESSION" ]; then \
		echo "Session: $$LAST_SESSION"; \
		echo ""; \
		echo "Instructions:"; \
		echo "  • HOVER over cells to preview activity"; \
		echo "  • CLICK on cells for detailed memory & performance stats"; \
		echo ""; \
		uv run python demo_interactive_heatmap.py; \
	else \
		echo "No monitoring sessions found. Run 'make monitor' first."; \
	fi

# Analyze a specific session
analyze-session:
	@if [ -z "$(SESSION)" ]; then \
		echo "Error: Please specify SESSION=<session_name>"; \
		echo "Use 'make list-sessions' to see available sessions"; \
		exit 1; \
	fi
	@if [ ! -d "monitoring_sessions/$(SESSION)" ]; then \
		echo "Error: Session '$(SESSION)' not found"; \
		exit 1; \
	fi
	@echo "Analyzing session: $(SESSION)"
	@if [ -f "monitoring_sessions/$(SESSION)/graph_timing.csv" ]; then \
		echo ""; \
		echo "=== TIMING ANALYSIS ==="; \
		uv run python src/visualize_timing.py "monitoring_sessions/$(SESSION)/graph_timing.csv" --summary; \
	fi
	@if [ -f "monitoring_sessions/$(SESSION)/resource_usage.log" ]; then \
		echo ""; \
		echo "=== RESOURCE ANALYSIS ==="; \
		uv run python src/visualize_resources.py "monitoring_sessions/$(SESSION)/resource_usage.log" --summary; \
	fi

# Compare multiple sessions (shows summary of last 5)
compare-sessions:
	@echo "Comparing recent monitoring sessions..."
	@echo ""
	@SESSIONS=$$(ls -td monitoring_sessions/[0-9]*/ 2>/dev/null | head -n5 | xargs -I{} basename {}); \
	for session in $$SESSIONS; do \
		echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"; \
		echo "Session: $$session"; \
		if [ -f "monitoring_sessions/$$session/session_info.txt" ]; then \
			cat "monitoring_sessions/$$session/session_info.txt" | head -n5; \
		fi; \
		if [ -f "monitoring_sessions/$$session/graph_timing.csv" ]; then \
			LINES=$$(wc -l < "monitoring_sessions/$$session/graph_timing.csv"); \
			echo "Graph data points: $$LINES"; \
		fi; \
		if [ -f "monitoring_sessions/$$session/resource_usage.log" ]; then \
			SIZE=$$(du -h "monitoring_sessions/$$session/resource_usage.log" | cut -f1); \
			echo "Resource log size: $$SIZE"; \
		fi; \
		echo ""; \
	done

# ─────────────────────────────────────────────────────────────────────────────
# Cross-session KPI averages
#
#   make view-average               # timing + resources, last 5 sessions
#   make view-average RUNS=10       # last N sessions
#   make view-average-timing        # graph timing only
#   make view-average-resources     # resource log only
#   make view-average-plot          # save bar-chart PNGs
#   make view-average-plot RUNS=10 SHOW=show  # open windows too
# ─────────────────────────────────────────────────────────────────────────────
view-average:
	@uv run python src/view_average.py \
		--runs $(if $(RUNS),$(RUNS),5) \
		--sessions-dir $(if $(SESSIONS_DIR),$(SESSIONS_DIR),$(if $(ALGORITHM),monitoring_sessions/$(ALGORITHM),monitoring_sessions)) \
		$(if $(TOP),--top $(TOP))

view-average-timing:
	@uv run python src/view_average.py \
		--runs $(if $(RUNS),$(RUNS),5) \
		--sessions-dir $(if $(SESSIONS_DIR),$(SESSIONS_DIR),$(if $(ALGORITHM),monitoring_sessions/$(ALGORITHM),monitoring_sessions)) \
		--timing-only

view-average-resources:
	@uv run python src/view_average.py \
		--runs $(if $(RUNS),$(RUNS),5) \
		--sessions-dir $(if $(SESSIONS_DIR),$(SESSIONS_DIR),$(if $(ALGORITHM),monitoring_sessions/$(ALGORITHM),monitoring_sessions)) \
		--resources-only \
		$(if $(TOP),--top $(TOP))

view-average-plot:
	@uv run python src/view_average.py \
		--runs $(if $(RUNS),$(RUNS),5) \
		--sessions-dir $(if $(SESSIONS_DIR),$(SESSIONS_DIR),$(if $(ALGORITHM),monitoring_sessions/$(ALGORITHM),monitoring_sessions)) \
		--plot \
		$(if $(filter show,$(SHOW)),--show) \
		$(if $(OUTPUT_DIR),--output-dir $(OUTPUT_DIR)) \
		$(if $(TOP),--top $(TOP))

view-average-tables:
	@uv run python src/view_average.py \
		--runs $(if $(RUNS),$(RUNS),5) \
		--sessions-dir $(if $(SESSIONS_DIR),$(SESSIONS_DIR),$(if $(ALGORITHM),monitoring_sessions/$(ALGORITHM),monitoring_sessions)) \
		--save-tables \
		$(if $(OUTPUT_DIR),--output-dir $(OUTPUT_DIR)) \
		$(if $(TOP),--top $(TOP))

# Clean all monitoring data
clean:
	@echo "Removing all monitoring session data..."
	@rm -rf monitoring_sessions/
	@echo "Done."

# Clean the most recent session
clean-last:
	@echo "Removing the most recent monitoring session..."
	@LAST_SESSION=$$(ls -td monitoring_sessions/[0-9]*/ 2>/dev/null | head -n1 | xargs basename 2>/dev/null); \
	if [ -z "$$LAST_SESSION" ]; then \
		echo "No monitoring sessions found."; \
	else \
		echo "Removing session: $$LAST_SESSION"; \
		rm -rf "monitoring_sessions/$$LAST_SESSION"; \
		echo "Done."; \
	fi

# Clean specific session
clean-session:
	@if [ -z "$(SESSION)" ]; then \
		echo "Error: Please specify SESSION=<session_name>"; \
		exit 1; \
	fi
	@if [ ! -d "monitoring_sessions/$(SESSION)" ]; then \
		echo "Error: Session '$(SESSION)' not found"; \
		exit 1; \
	fi
	@echo "Removing session: $(SESSION)"
	@rm -rf "monitoring_sessions/$(SESSION)"
	@echo "Done."

# Install dependencies
install:
	@echo "Installing required dependencies..."
	@echo ""
	@echo "[1/3] Installing system packages (sysstat, python3-tk)..."
	@sudo apt-get update -qq && sudo apt-get install -y sysstat python3-tk
	@echo ""
	@echo "[2/3] Installing Python dependencies with uv..."
	@uv sync
	@sed -i 's/include-system-site-packages = false/include-system-site-packages = true/' .venv/pyvenv.cfg 2>/dev/null || true
	@echo ""
	@echo "[3/3] Checking Docker (needed for Grafana dashboard)..."
	@if command -v docker >/dev/null 2>&1; then \
		if docker info >/dev/null 2>&1; then \
			echo "  ✅ Docker is installed and running: $$(docker --version)"; \
		else \
			echo "  ⚠️  Docker is installed but not running (or no permission)"; \
			echo "     Start Docker  : sudo systemctl start docker"; \
			echo "     Add to group  : sudo usermod -aG docker $$USER  (then log out/in)"; \
		fi; \
	else \
		echo "  ⚠️  Docker is NOT installed (required for Grafana/Prometheus stack)"; \
		echo "     Install Docker:"; \
		echo "       sudo apt-get install -y docker.io docker-compose-v2"; \
		echo "       sudo usermod -aG docker $$USER"; \
		echo "       newgrp docker   (or log out/in)"; \
	fi
	@echo ""
	@echo "✅ Core dependencies installed!"
	@echo ""
	@echo "⚠️  ROS2 REQUIRED to monitor ROS2 systems:"
	@echo "   sudo apt install -y ros-humble-ros-base"
	@echo "   See INSTALL.md for full instructions."
	@echo ""
	@echo "After installing ROS2:"
	@echo "   source /opt/ros/humble/setup.bash"
	@echo "   export ROS_DOMAIN_ID=0"

# Grant CAP_PERFMON to the pre-built intel_gpu_top on the remote machine
# Run once after 'make monitor-remote' or building the binary.
# Requires the user to have sudo access on the remote.
setup-remote-gpu:
	@if [ -z "$(REMOTE_IP)" ]; then \
		echo "Error: REMOTE_IP is required."; \
		echo "Usage: make setup-remote-gpu REMOTE_IP=<ip> [REMOTE_USER=<user>]"; \
		exit 1; \
	fi
	@RUSER=$$([ -n "$(REMOTE_USER)" ] && echo "$(REMOTE_USER)" || echo "intel"); \
	echo "🔑 Granting CAP_PERFMON to intel_gpu_top on $$RUSER@$(REMOTE_IP)..."; \
	ssh $$RUSER@$(REMOTE_IP) 'sudo setcap cap_perfmon+eip ~/.local/bin/intel_gpu_top && \
	  echo "✅ CAP_PERFMON granted — intel_gpu_top will now use PMU for rich GPU metrics." || \
	  echo "❌ setcap failed (check sudo permissions)"'

# ============================================================================
# INTEL GPU PID ANALYSIS
# Requires: sudo apt install intel-gpu-tools
#           sudo setcap cap_perfmon+eip $(which intel_gpu_top)
#
# Collected per sample:
#   GPU-level  : Render/3D, Blitter, Video, VE (VideoEnhance) busy %
#                Freq actual/requested (MHz), GPU Temp (°C), GPU/Pkg Power (W)
#                RC6 residency %
#   Per-PID    : GPU busy % broken down by engine class  (requires igt >= 1.27)
# ============================================================================

# One-shot snapshot (local)
gpu-pids:
	@uv run python src/gpu_pid_analyzer.py \
		--interval $(if $(INTERVAL),$(INTERVAL),2)

# Live watch mode – keep refreshing until Ctrl-C (local)
gpu-pids-watch:
	@uv run python src/gpu_pid_analyzer.py \
		--watch \
		--interval $(if $(INTERVAL),$(INTERVAL),2)

# 60-second capture to CSV (local)
gpu-pids-csv:
	@CSV=gpu_pids_$$(date +%Y%m%d_%H%M%S).csv; \
	echo "Recording GPU PID metrics → $$CSV"; \
	uv run python src/gpu_pid_analyzer.py \
		--interval $(if $(INTERVAL),$(INTERVAL),2) \
		--duration $(if $(DURATION),$(DURATION),60) \
		--csv $$CSV; \
	echo "Saved: $$CSV"

# Remote GPU PID analysis
gpu-pids-remote:
	@if [ -z "$(REMOTE_IP)" ]; then \
		echo "Error: Please specify REMOTE_IP=<ip_address>"; \
		echo "Example: make gpu-pids-remote REMOTE_IP=192.168.1.100"; \
		exit 1; \
	fi
	@uv run python src/gpu_pid_analyzer.py \
		--remote-ip $(REMOTE_IP) \
		$(if $(REMOTE_USER),--remote-user $(REMOTE_USER)) \
		--interval $(if $(INTERVAL),$(INTERVAL),2) \
		$(if $(DURATION),--duration $(DURATION),--watch)

# Check all dependencies
check-deps:
	@echo "╔════════════════════════════════════════════════════════════════╗"
	@echo "║         ROS2 KPI Monitoring - Dependency Checker              ║"
	@echo "╚════════════════════════════════════════════════════════════════╝"
	@echo ""
	@echo "Checking dependencies..."
	@echo ""
	@echo "[1/7] Checking uv installation..."
	@if command -v uv >/dev/null 2>&1; then \
		echo "  ✅ uv is installed: $$(uv --version)"; \
	else \
		echo "  ❌ uv is NOT installed"; \
		echo "     Install: curl -LsSf https://astral.sh/uv/install.sh | sh"; \
		exit 1; \
	fi
	@echo ""
	@echo "[2/7] Checking ROS2 installation..."
	@if [ -d "/opt/ros/humble" ]; then \
		echo "  ✅ ROS2 Humble is installed"; \
	elif [ -d "/opt/ros/foxy" ]; then \
		echo "  ✅ ROS2 Foxy is installed"; \
	elif [ -d "/opt/ros/iron" ]; then \
		echo "  ✅ ROS2 Iron is installed"; \
	else \
		echo "  ❌ ROS2 is NOT installed"; \
		echo "     Install: sudo apt install -y ros-humble-ros-base"; \
		exit 1; \
	fi
	@echo ""
	@echo "[3/7] Checking ROS2 environment..."
	@if [ -n "$$ROS_DISTRO" ]; then \
		echo "  ✅ ROS2 is sourced: $$ROS_DISTRO"; \
		echo "     ROS_DOMAIN_ID: $${ROS_DOMAIN_ID:-not set (will use default 0)}"; \
	else \
		echo "  ⚠️  ROS2 is not sourced in current shell"; \
		echo "     Run: source /opt/ros/humble/setup.bash"; \
		echo "     Or:  source ./setup_ros2_env.sh"; \
	fi
	@echo ""
	@echo "[4/7] Checking Python dependencies..."
	@if uv run python -c "import matplotlib, numpy, psutil, prometheus_client" 2>/dev/null; then \
		echo "  ✅ Python packages installed (matplotlib, numpy, psutil, prometheus-client)"; \
	else \
		echo "  ❌ Python packages missing"; \
		echo "     Run: make install"; \
		exit 1; \
	fi
	@if uv run python -c "import tkinter" 2>/dev/null; then \
		echo "  ✅ tkinter available (interactive graph popups enabled)"; \
	else \
		echo "  ⚠️  tkinter not found (interactive graph click popups will be disabled)"; \
		echo "     Install: sudo apt-get install -y python3-tk"; \
	fi
	@echo ""
	@echo "[5/7] Checking system utilities..."
	@if command -v iostat >/dev/null 2>&1; then \
		echo "  ✅ sysstat (iostat/pidstat) is installed"; \
	else \
		echo "  ❌ sysstat is NOT installed"; \
		echo "     Install: sudo apt-get install -y sysstat"; \
		exit 1; \
	fi
	@echo ""
	@echo "[6/7] Checking Docker (Grafana stack)..."
	@if command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1; then \
		echo "  ✅ Docker is available (Grafana stack ready)"; \
	else \
		echo "  ⚠️  Docker not available — Grafana dashboard won't work"; \
		echo "     Install: sudo apt-get install -y docker.io docker-compose-v2"; \
		echo "     Then   : sudo usermod -aG docker $$USER && newgrp docker"; \
	fi
	@echo ""
	@echo "[7/7] Checking remote monitoring prerequisites..."
	@if [ -n "$(REMOTE_IP)" ]; then \
		echo "  Testing connection to $(REMOTE_IP)..."; \
		if ping -c 1 -W 2 $(REMOTE_IP) >/dev/null 2>&1; then \
			echo "  ✅ Network connection to $(REMOTE_IP) OK"; \
		else \
			echo "  ❌ Cannot ping $(REMOTE_IP)"; \
			echo "     Check network connectivity"; \
			exit 1; \
		fi; \
		REMOTE_USER=$${REMOTE_USER:-ubuntu}; \
		if ssh -o BatchMode=yes -o ConnectTimeout=5 $$REMOTE_USER@$(REMOTE_IP) "echo 'SSH OK'" >/dev/null 2>&1; then \
			echo "  ✅ SSH connection to $$REMOTE_USER@$(REMOTE_IP) OK"; \
		else \
			echo "  ❌ SSH connection failed"; \
			echo "     Set up SSH keys: ssh-copy-id $$REMOTE_USER@$(REMOTE_IP)"; \
			exit 1; \
		fi; \
	else \
		echo "  ℹ️  Skipping remote checks (no REMOTE_IP specified)"; \
		echo "     To check remote: make check-deps REMOTE_IP=<ip> REMOTE_USER=<user>"; \
	fi
	@echo ""
	@echo "╔════════════════════════════════════════════════════════════════╗"
	@echo "║                   ✅ All checks passed!                        ║"
	@echo "╚════════════════════════════════════════════════════════════════╝"
	@echo ""
	@echo "Next steps:"
	@echo "  • make quick-check                           # Quick local test"
	@echo "  • make monitor NODE=/my_node                 # Monitor specific node"
	@if [ -n "$(REMOTE_IP)" ]; then \
		echo "  • make monitor-remote REMOTE_IP=$(REMOTE_IP)   # Monitor remote system"; \
	fi

# Build PDF documentation
docs:
	@echo "Building PDF documentation..."
	@uv run python docs/build_pdfs.py

# ─────────────────────────────────────────────────────────────────────────────
# ROS_DOMAIN_ID checker
#
#   make check-domain                                # local only
#   make check-domain REMOTE_IP=10.34.94.113         # local + remote
#   make check-domain REMOTE_IP=<ip> REMOTE_USER=<u> # custom SSH user
# ─────────────────────────────────────────────────────────────────────────────
check-domain:
	@echo "╔════════════════════════════════════════════════════════════════╗"
	@echo "║           ROS_DOMAIN_ID Check                                  ║"
	@echo "╚════════════════════════════════════════════════════════════════╝"
	@echo ""
	@LOCAL_DOMAIN=$${ROS_DOMAIN_ID:-0}; \
	LOCAL_DISTRO=$${ROS_DISTRO:-not sourced}; \
	echo "Local  ROS_DOMAIN_ID : $${ROS_DOMAIN_ID:-not set (defaults to 0)}  →  effective = $$LOCAL_DOMAIN"; \
	echo "Local  RMW           : $${RMW_IMPLEMENTATION:-not set (default: rmw_fastrtps_cpp)}"; \
	echo "Local  ROS_DISTRO    : $$LOCAL_DISTRO"; \
	echo ""; \
	if [ -n "$(REMOTE_IP)" ]; then \
		REMOTE_USER=$${REMOTE_USER:-$(if $(REMOTE_USER),$(REMOTE_USER),ubuntu)}; \
		echo "Checking remote $$REMOTE_USER@$(REMOTE_IP) via SSH..."; \
		REMOTE_INFO=$$(ssh -T -o BatchMode=yes -o ConnectTimeout=5 \
			-o StrictHostKeyChecking=no \
			$$REMOTE_USER@$(REMOTE_IP) \
			'D=$$(grep -hE "^export ROS_DOMAIN_ID=" ~/.bashrc ~/.bash_profile ~/.profile /etc/environment 2>/dev/null | tail -1 | cut -d= -f2); \
			 R=$$(grep -hE "^export RMW_IMPLEMENTATION=" ~/.bashrc ~/.bash_profile ~/.profile 2>/dev/null | tail -1 | cut -d= -f2); \
			 S=$$(grep -hE "source /opt/ros/[^/]+/setup\.(bash|sh)" ~/.bashrc ~/.bash_profile ~/.profile 2>/dev/null | tail -1 | grep -oP "(?<=/opt/ros/)[^/]+"); \
			 echo DOMAIN=$${D:-UNSET}; echo RMW=$${R:-UNSET}; echo DISTRO=$${S:-UNSET}' \
			2>&1) || REMOTE_INFO="SSH_FAILED"; \
		if echo "$$REMOTE_INFO" | grep -q 'SSH_FAILED\|Permission denied\|Connection refused\|timed out'; then \
			echo "  ❌ SSH connection to $$REMOTE_USER@$(REMOTE_IP) failed."; \
			echo "     Ensure SSH key auth: ssh-copy-id $$REMOTE_USER@$(REMOTE_IP)"; \
		else \
			REMOTE_DOMAIN=$$(echo "$$REMOTE_INFO" | grep '^DOMAIN=' | cut -d= -f2 | tr -d '\r' | sed 's/^UNSET$$/0/'); \
			REMOTE_RMW=$$(echo "$$REMOTE_INFO" | grep '^RMW=' | cut -d= -f2 | tr -d '\r' | sed 's/^UNSET$$/not set/'); \
			REMOTE_DISTRO=$$(echo "$$REMOTE_INFO" | grep '^DISTRO=' | cut -d= -f2 | tr -d '\r' | sed 's/^UNSET$$/not sourced/'); \
			echo "Remote ROS_DOMAIN_ID : $${REMOTE_DOMAIN:-0}"; \
			echo "Remote RMW           : $${REMOTE_RMW:-not set}"; \
			echo "Remote ROS_DISTRO    : $${REMOTE_DISTRO:-not sourced}"; \
			echo ""; \
			if [ "$${REMOTE_DOMAIN:-0}" = "$$LOCAL_DOMAIN" ]; then \
				echo "  ✅ ROS_DOMAIN_ID matches ($${REMOTE_DOMAIN:-0}) — DDS peer discovery should work."; \
			else \
				echo "  ❌ ROS_DOMAIN_ID MISMATCH: local=$$LOCAL_DOMAIN  remote=$${REMOTE_DOMAIN:-0}"; \
				echo "     monitor-remote-grafana auto-corrects this at runtime."; \
				echo "     To fix permanently, add to remote ~/.bashrc:  export ROS_DOMAIN_ID=$$LOCAL_DOMAIN"; \
			fi; \
			if [ "$${REMOTE_DISTRO:-UNSET}" != "UNSET" ] && [ "$$LOCAL_DISTRO" != "not sourced" ] && [ "$$REMOTE_DISTRO" != "$$LOCAL_DISTRO" ]; then \
				echo "  ⚠  ROS distro mismatch: local=$$LOCAL_DISTRO  remote=$$REMOTE_DISTRO"; \
				echo "     Topic/service APIs may be incompatible between distros."; \
			elif [ "$${REMOTE_DISTRO:-UNSET}" != "UNSET" ] && [ "$$LOCAL_DISTRO" != "not sourced" ]; then \
				echo "  ✅ ROS distro matches ($$REMOTE_DISTRO)."; \
			fi; \
		fi; \
	else \
		echo "(No REMOTE_IP specified — local check only.)"; \
		echo "Run: make check-domain REMOTE_IP=<ip>  to also check the remote."; \
	fi
	@echo ""

# ═══════════════════════════════════════════════════════════════
# Grafana Dashboard Integration
# ═══════════════════════════════════════════════════════════════

# Start Grafana dashboard stack
grafana-start:
	@echo "🚀 Starting Grafana Dashboard Stack..."
	@./start_grafana.sh

# Stop Grafana dashboard stack
grafana-stop:
	@echo "🛑 Stopping Grafana Dashboard Stack..."
	@./stop_grafana.sh

# Pull latest Grafana/Prometheus images
grafana-pull:
	@echo "📦 Pulling latest Grafana/Prometheus images..."
	@docker compose pull
	@echo "✅ Images updated"

# Start Prometheus exporter in file mode
grafana-export:
	@fuser -k 9092/tcp 2>/dev/null || true
	@sleep 0.3
	@if [ -z "$(SESSION)" ]; then \
		LAST_SESSION=$$(ls -td monitoring_sessions/[0-9]*/ 2>/dev/null | head -n1 | xargs basename 2>/dev/null); \
		if [ -z "$$LAST_SESSION" ]; then \
			echo "❌ No monitoring sessions found"; \
			echo "Run 'make monitor' first to create a session"; \
			exit 1; \
		fi; \
		echo "📊 Exporting metrics from latest session: $$LAST_SESSION"; \
		uv run python src/prometheus_exporter.py --session-dir monitoring_sessions/$$LAST_SESSION; \
	else \
		echo "📊 Exporting metrics from session: $(SESSION)"; \
		uv run python src/prometheus_exporter.py --session-dir monitoring_sessions/$(SESSION); \
	fi

# Start Prometheus exporter in live mode
grafana-export-live:
	@fuser -k 9092/tcp 2>/dev/null || true
	@sleep 0.3
	@echo "📊 Starting live metrics exporter on port 9092..."
	@echo "   Watching monitoring_sessions/ for the latest session"
	@uv run python src/prometheus_exporter.py --mode live --sessions-dir monitoring_sessions --port 9092

# Remote monitoring with simultaneous live Grafana export
monitor-remote-grafana:
	@if [ -z "$(REMOTE_IP)" ]; then \
		echo "Error: Please specify REMOTE_IP=<ip_address>"; \
		echo "Example: make monitor-remote-grafana REMOTE_IP=192.168.1.100"; \
		exit 1; \
	fi
	@echo "🚀 Starting remote monitoring + live Grafana export..."
	@echo "   Remote host : $(REMOTE_IP)"
	@echo "   Metrics     : http://localhost:9092/metrics"
	@echo "   Grafana      : http://localhost:30000"
	@echo ""
	@fuser -k 9092/tcp 2>/dev/null || true; sleep 0.3; \
	uv run python src/prometheus_exporter.py --mode live --sessions-dir monitoring_sessions --port 9092 > /tmp/grafana-exporter.log 2>&1 & \
	EXPORTER_PID=$$!; \
	echo "Exporter started (PID $$EXPORTER_PID, logs: /tmp/grafana-exporter.log)"; \
	_stop() { \
		echo ""; \
		echo "Stopping exporter (PID $$EXPORTER_PID)..."; \
		kill -- -$$EXPORTER_PID 2>/dev/null || kill $$EXPORTER_PID 2>/dev/null; \
		fuser -k 9092/tcp 2>/dev/null || true; \
		echo "Done."; \
	}; \
	trap _stop INT TERM; \
	uv run python src/monitor_stack.py --remote-ip $(REMOTE_IP) $(if $(REMOTE_USER),--remote-user $(REMOTE_USER)) \
		$(if $(DURATION),--duration $(DURATION)) $(if $(NODE),--node $(NODE)) $(if $(INTERVAL),--interval $(INTERVAL)); \
	_stop; \
	echo ""; \
	echo "✅ Monitoring complete."; \
	echo ""; \
	echo "📁 Session results:"; \
	SESSION_DIR=$$(ls -td monitoring_sessions/[0-9]*/ 2>/dev/null | head -1 | sed 's|/$$||'); \
	if [ -n "$$SESSION_DIR" ]; then \
		echo "   Plots       : $$SESSION_DIR/visualizations/"; \
		echo "   Avg plots   : monitoring_sessions/average_5/"; \
		echo "   Pipeline    : make pipeline-graph"; \
		echo "   Avg review  : make view-average-plot"; \
	fi

# Remote PID-only monitoring + live Grafana export
monitor-remote-pid-grafana:
	@if [ -z "$(REMOTE_IP)" ]; then \
		echo "Error: Please specify REMOTE_IP=<ip_address>"; \
		echo "Example: make monitor-remote-pid-grafana REMOTE_IP=192.168.1.100"; \
		exit 1; \
	fi
	@echo "🚀 Starting remote PID monitoring + live Grafana export..."
	@echo "   Remote host : $(REMOTE_IP)"
	@echo "   Metrics     : http://localhost:9092/metrics"
	@echo "   Grafana      : http://localhost:30000"
	@echo ""
	@fuser -k 9092/tcp 2>/dev/null || true; sleep 0.3; \
	uv run python src/prometheus_exporter.py --mode live --sessions-dir monitoring_sessions --port 9092 > /tmp/grafana-exporter.log 2>&1 & \
	EXPORTER_PID=$$!; \
	echo "Exporter started (PID $$EXPORTER_PID, logs: /tmp/grafana-exporter.log)"; \
	_stop() { \
		echo ""; \
		echo "Stopping exporter (PID $$EXPORTER_PID)..."; \
		kill -- -$$EXPORTER_PID 2>/dev/null || kill $$EXPORTER_PID 2>/dev/null; \
		fuser -k 9092/tcp 2>/dev/null || true; \
		echo "Done."; \
	}; \
	trap _stop INT TERM; \
	uv run python src/monitor_stack.py --remote-ip $(REMOTE_IP) $(if $(REMOTE_USER),--remote-user $(REMOTE_USER)) \
		--pid-only \
		$(if $(DURATION),--duration $(DURATION)) $(if $(NODE),--node $(NODE)) $(if $(INTERVAL),--interval $(INTERVAL)) \
		$(if $(ALGORITHM),--algorithm '$(ALGORITHM)') $(if $(DOMAIN_ID),--ros-domain-id $(DOMAIN_ID)); \
	_stop; \
	echo ""; \
	echo "✅ Monitoring complete."; \
	echo ""; \
	echo "📁 Session results:"; \
	SESSION_DIR=$$(ls -td monitoring_sessions/[0-9]*/ 2>/dev/null | head -1 | sed 's|/$$||'); \
	if [ -n "$$SESSION_DIR" ]; then \
		echo "   Plots       : $$SESSION_DIR/visualizations/"; \
		echo "   Pipeline    : make pipeline-graph"; \
	fi

# Run remote monitoring N times back-to-back (e.g. once per algorithm run)
#
#   make monitor-remote-repeat REMOTE_IP=<ip> REMOTE_USER=intel REPEAT=3
#   make monitor-remote-repeat REMOTE_IP=<ip> REMOTE_USER=intel REPEAT=5 DURATION=120 PAUSE=10
#   make monitor-remote-repeat REMOTE_IP=<ip> REMOTE_USER=intel REPEAT=3 GPU=1 ALGORITHM=wandering DOMAIN_ID=46
#   make monitor-remote-repeat REMOTE_IP=<ip> REMOTE_USER=intel REPEAT=3 NPU=1 ALGORITHM=wandering DOMAIN_ID=46
#   make monitor-remote-repeat REMOTE_IP=<ip> REMOTE_USER=intel REPEAT=3 GPU=1 NPU=1 ALGORITHM=wandering DOMAIN_ID=46
#
#   REPEAT  : number of monitoring runs (default: 3)
#   DURATION: seconds per run (default: 60)
#   PAUSE   : seconds to wait between runs (default: 5)
# ─────────────────────────────────────────────────────────────────────────────
monitor-remote-repeat:
	@if [ -z "$(REMOTE_IP)" ]; then \
		echo "Error: Please specify REMOTE_IP=<ip_address>"; \
		echo "Example: make monitor-remote-repeat REMOTE_IP=192.168.1.100 REMOTE_USER=intel REPEAT=3"; \
		exit 1; \
	fi
	@REPEAT=$(if $(REPEAT),$(REPEAT),3); \
	DURATION=$(if $(DURATION),$(DURATION),60); \
	PAUSE=$(if $(PAUSE),$(PAUSE),5); \
	fuser -k 9092/tcp 2>/dev/null || true; sleep 0.3; \
	uv run python src/prometheus_exporter.py --mode live --sessions-dir monitoring_sessions --port 9092 \
		> /tmp/grafana-exporter.log 2>&1 & \
	EXPORTER_PID=$$!; \
	echo "📊 Exporter started (PID $$EXPORTER_PID)"; \
	_stop() { \
		echo ""; \
		echo "Stopping exporter..."; \
		kill -- -$$EXPORTER_PID 2>/dev/null || kill $$EXPORTER_PID 2>/dev/null; \
		fuser -k 9092/tcp 2>/dev/null || true; \
	}; \
	trap _stop INT TERM; \
	echo "🔁 Running $$REPEAT monitoring session(s) × $${DURATION}s each (pause=$${PAUSE}s)"; \
	echo "   Remote: $(if $(REMOTE_USER),$(REMOTE_USER)@,)$(REMOTE_IP)"; \
	echo "   Grafana: http://localhost:30000"; \
	echo ""; \
	for i in $$(seq 1 $$REPEAT); do \
		echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"; \
		echo "▶  Run $$i / $$REPEAT"; \
		echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"; \
		uv run python src/monitor_stack.py \
			--remote-ip $(REMOTE_IP) \
			$(if $(REMOTE_USER),--remote-user $(REMOTE_USER)) \
			$(if $(DOMAIN_ID),--ros-domain-id $(DOMAIN_ID)) \
			--duration $$DURATION \
			$(if $(NODE),--node $(NODE)) \
			$(if $(INTERVAL),--interval $(INTERVAL)) \
			$(if $(GPU),--gpu) \
			$(if $(NPU),--npu) \
			$(if $(ALGORITHM),--algorithm '$(ALGORITHM)'); \
		SESSION_DIR=$$(ls -td monitoring_sessions/[0-9]*/ monitoring_sessions/*/[0-9]*/ 2>/dev/null | head -1 | sed 's|/$$||'); \
		echo "   ✅ Session saved: $$SESSION_DIR"; \
		if [ $$i -lt $$REPEAT ]; then \
			echo "   ⏳ Pausing $${PAUSE}s before next run..."; \
			sleep $$PAUSE; \
		fi; \
	done; \
	_stop; \
	echo ""; \
	echo "✅ All $$REPEAT runs complete."; \
	echo ""; \
	echo "📁 Cross-session average (last $$REPEAT runs):"; \
	uv run python src/view_average.py --plot --runs $$REPEAT --no-show \
		--output-dir monitoring_sessions/average_$${REPEAT} 2>/dev/null || true; \
	echo "   make view-average-plot RUNS=$$REPEAT"; \
	echo "   make pipeline-graph"

# ─────────────────────────────────────────────────────────────────────────────
# Simulation benchmarking — delegate to src/Makefile
#
# Params forwarded: RUNS  TIMEOUT  PN_TIMEOUT  PAUSE  BENCH  NODE
# Full target list: make -f src/Makefile help
# ─────────────────────────────────────────────────────────────────────────────

_SRC_FWD = $(if $(RUNS),RUNS=$(RUNS)) $(if $(TIMEOUT),TIMEOUT=$(TIMEOUT)) \
           $(if $(PN_TIMEOUT),PN_TIMEOUT=$(PN_TIMEOUT)) $(if $(PAUSE),PAUSE=$(PAUSE)) \
           $(if $(BENCH),BENCH=$(BENCH)) $(if $(NODE),NODE=$(NODE))

wandering wandering-record wandering-plot wandering-record-plot wandering-benchmark \
picknplace-run picknplace-record picknplace-plot picknplace-record-plot picknplace-benchmark \
analyze-benchmark:
	$(MAKE) -f src/Makefile $@ $(_SRC_FWD)

# ─────────────────────────────────────────────────────────────────────────────
# Simulation benchmarking — delegate to src/Makefile
	@echo "📊 Grafana Dashboard Stack Status"
	@echo "=================================="
	@if docker compose ps 2>/dev/null | grep -q "Up"; then \
		echo "✅ Services running:"; \
		docker compose ps; \
		echo ""; \
		echo "🌐 Access Points:"; \
		echo "   Grafana:    http://localhost:30000 (admin/admin)"; \
		echo "   Prometheus: http://localhost:9090"; \
		echo ""; \
		if curl -s http://localhost:9092/metrics > /dev/null 2>&1; then \
			echo "✅ Metrics exporter: http://localhost:9092/metrics"; \
		else \
			echo "⚠️  Metrics exporter not running"; \
			echo "   Start with: make grafana-export"; \
		fi; \
	else \
		echo "⚠️  Services not running"; \
		echo "Start with: make grafana-start"; \
	fi

# View Grafana logs
grafana-logs:
	@docker compose logs -f

# Open Grafana in browser
grafana-open:
	@echo "🌐 Opening Grafana dashboard..."
	@if command -v xdg-open >/dev/null 2>&1; then \
		xdg-open http://localhost:30000; \
	elif command -v firefox >/dev/null 2>&1; then \
		firefox http://localhost:30000; \
	else \
		echo "Open http://localhost:30000 in your browser"; \
	fi


