# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
#
# These contents may have been developed with support from one or more
# Intel-operated generative artificial intelligence solutions.
ROOT_DIR := $(shell dirname $(realpath $(firstword $(MAKEFILE_LIST))))
ROS_DISTRO ?= humble
RUN_CONFIG ?=   # Optional: path to a YAML run profile (e.g. config/wandering_run.yaml)

ifeq ($(ROS_DISTRO),humble)
	UBUNTU_CODENAME := jammy
else
	UBUNTU_CODENAME := noble
endif

.PHONY: help install install-qmassa enable-power-mon check-deps check-hw check-domain \
        clean clean-last clean-session \
        grafana-start grafana-stop grafana-pull grafana-status grafana-logs grafana-open \
        wandering wandering-record wandering-plot wandering-record-plot wandering-benchmark \
        picknplace-run picknplace-record picknplace-plot picknplace-record-plot picknplace-benchmark \
        bag-replay bag-replay-plot bag-replay-benchmark \
        fastmapping fastmapping-plot fastmapping-benchmark \
        analyze-benchmark analyze-e2e regression-check regression-check-l2 \
        report visualize-kpi results visualize-thermal show-sessions summarize-benchmark \
        test package license-check lint lint-all


# Default target
help:
	@echo "ROS2 KPI Monitoring — Infrastructure Targets"
	@echo ""
	@echo "⚠️  IMPORTANT: Source ROS2 before monitoring:"
	@echo "   source /opt/ros/$(ROS_DISTRO)/setup.bash  (or: source ./setup_ros2_env.sh)"
	@echo "   export ROS_DOMAIN_ID=46"
	@echo ""
	@echo "QUICK START:"
	@echo "  ./quickstart                              - Interactive menu"
	@echo ""
	@echo "MONITORING (run directly with uv):"
	@echo "  uv run python src/monitor_stack.py --help"
	@echo "  uv run python src/monitor_stack.py --duration 60"
	@echo "  uv run python src/monitor_stack.py --remote-ip <ip> --duration 60"
	@echo "  uv run python src/monitor_stack.py --remote-ip <ip> --gpu --npu"
	@echo "  uv run python src/monitor_stack.py --pid-only --duration 300"
	@echo ""
	@echo "VISUALIZATION:"
	@echo "  uv run python src/visualize_timing.py <session>/graph_timing.csv --help"
	@echo "  uv run python src/visualize_resources.py <session>/resource_usage.log --help"
	@echo "  uv run python src/visualize_gpu.py <session>/gpu_usage.log --help"
	@echo "  uv run python src/visualize_npu.py <session>/npu_usage.log --help"
	@echo "  uv run python src/visualize_timing.py <session>/graph_timing.csv --help"
	@echo "  uv run python src/visualize_resources.py <session>/resource_usage.log --help"
	@echo "  uv run python src/visualize_gpu.py <session>/gpu_usage.log --help"
	@echo "  uv run python src/visualize_npu.py <session>/npu_usage.log --help"
	@echo "  uv run python src/visualize_graph.py <session>/graph_timing.csv --topology <session>/graph_topology.json"
	@echo "  uv run python src/visualize_kpi.py --session <session>              - KPI latency histogram"
	@echo "  uv run python src/visualize_kpi.py --kpi a.json b.json --label A B  - Cross-SKU comparison"
	@echo "  make visualize-kpi SESSION=<session>                               - Same via make"
	@echo "  make results [SESSION=<session>]                                   - KPI charts + HTML report for latest (or given) session"
	@echo "  make visualize-thermal [SESSION=<session>]                         - CPU/GPU temperature + throttle + power plot"
	@echo "  uv run python demo_interactive_heatmap.py [SESSION_DIR]"
	@echo ""
	@echo "ANALYSIS:"
	@echo "  uv run python src/view_average.py --help"
	@echo "  uv run python src/analyze_trigger_latency.py --help"
	@echo "  uv run python src/analyze_rosbag.py <path/to/bag.db3>"
	@echo "  uv run python src/gpu_pid_analyzer.py --help"
	@echo ""
	@echo "SIMULATIONS:"
	@echo "  bash src/wandering_run.sh --help"
	@echo "  bash src/picknplace_run.sh --help"
	@echo "  make wandering [RUN_CONFIG=config/wandering_run.yaml] - Override run profile YAML"
	@echo ""
	@echo "BAG REPLAY (offline / CI benchmarking):"
	@echo "  make bag-replay BAG=<bag_dir> [RATE=1.0]  - Single replay + KPI collection"
	@echo "  make bag-replay-plot BAG=<bag_dir>         - Same + trigger-timeline plots"
	@echo "  make bag-replay-benchmark BAG=<bag_dir> [RUNS=10] [RATE=1.0] [PAUSE=10]"
	@echo "                                             - N independent runs → aggregate KPI"
	@echo ""
	@echo "FAST MAPPING (bag-replay pipeline):"
	@echo "  make fastmapping [BAG=<dir>] [RATE=1.0]   - fast_mapping_node + bag replay"
	@echo "  make fastmapping-plot [BAG=<dir>]          - Same + trigger-timeline plots"
	@echo "  make fastmapping-benchmark [RUNS=10] [RATE=1.0] [PAUSE=10]"
	@echo "                                             - N runs using bundled spinning bag"
	@echo ""
	@echo "GRAFANA + PROMETHEUS:"
	@echo "  ./start_grafana.sh                        - Start stack"
	@echo "  ./stop_grafana.sh                         - Stop stack"
	@echo "  uv run python src/prometheus_exporter.py --help"
	@echo "  ./grafana-monitor.sh --remote-ip <ip>     - Monitor + live Grafana export"
	@echo "  ./grafana-monitor.sh --help"
	@echo ""
	@echo "INFRASTRUCTURE (make targets):"
	@echo "  make install                              - Install all dependencies"
	@echo "  make install-qmassa                       - Compile and install qmassa/qmmd (xe GPU monitoring)"
	@echo "  make enable-power-mon                     - Install udev rule to allow RAPL power reading without root"
	@echo "  make check-deps                           - Check all dependencies"
	@echo "  make check-hw                             - Probe GPU and NPU tool availability"
	@echo "  make check-domain [REMOTE_IP=<ip>]        - Verify ROS_DOMAIN_ID matches"
	@echo "  make clean                                - Remove all monitoring sessions"
	@echo "  make clean-last                           - Remove most recent session"
	@echo "  make clean-session SESSION=<name>         - Remove specific session"
	@echo "  make show-sessions                        - Tree view of all sessions with metrics"
	@echo "  make summarize-benchmark BENCH=<bench_dir> - Cross-run aggregate table for one benchmark"
	@echo "  make analyze-e2e BENCH=<bench_dir>         - Level 2 traced e2e analysis + summary table"
	@echo "  make grafana-start / grafana-stop         - Grafana stack lifecycle"
	@echo "  make grafana-status                       - Check Grafana stack status"
	@echo "  make package [ROS_DISTRO=jazzy]           - Build Debian package"
	@echo "  make regression-check BASELINE=<b> CURRENT=<c> [THRESHOLD=5.0] [REPORT=<r>]"
	@echo "  make test                                 - Run unit tests (pytest via uv)"
	@echo "  make lint / license-check                 - Code quality checks"

# Show all monitoring session data
show-sessions:
	uv run python src/show_sessions.py $(if $(ROOT),--root $(ROOT))

# Clean all monitoring data
clean:
	@echo "Removing all monitoring session data..."
	@rm -rf monitoring_sessions/
	@echo "Done."

# Clean the most recent session
clean-last:
	@echo "Removing the most recent monitoring session or bench directory..."
	@LAST=$$(find monitoring_sessions -mindepth 2 -maxdepth 2 -type d \
		-printf '%T@ %p\n' 2>/dev/null | sort -rn | head -1 | awk '{print $$2}'); \
	if [ -z "$$LAST" ]; then \
		echo "No monitoring sessions found."; \
	else \
		echo "Removing: $$LAST"; \
		rm -rf "$$LAST"; \
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

# Compile and install qmassa + qmmd from crates.io.
# Installs Rust via rustup (minimal profile) if cargo is not already present.
# Binaries land in ~/.cargo/bin/ which is already on PATH after rustup setup.
install-qmassa:
	@echo "[1/2] Checking for Rust/Cargo..."
	@if ! command -v cargo >/dev/null 2>&1; then \
		echo "  cargo not found — installing Rust toolchain via rustup (minimal profile)..."; \
		curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs \
			| sh -s -- -y --no-modify-path --profile minimal --quiet; \
		echo "  Rust installed. Add ~/.cargo/bin to PATH if not already done:"; \
		echo "    echo 'export PATH=\$$HOME/.cargo/bin:\$$PATH' >> ~/.bashrc && source ~/.bashrc"; \
		export PATH="$$HOME/.cargo/bin:$$PATH"; \
	else \
		echo "  ✅ cargo found: $$(cargo --version)"; \
	fi
	@echo "[2/2] Installing qmassa and qmmd from crates.io..."
	@PATH="$$HOME/.cargo/bin:$$PATH" cargo install --locked qmassa qmmd
	@echo ""
	@echo "✅ qmassa and qmmd installed to ~/.cargo/bin/"
	@echo "   Run: qmassa --help"
	@echo "   Run: qmmd   --help"

enable-power-mon:
	@# Help: Install udev rule granting read access to Intel RAPL energy counter (no root required at runtime)
	@echo "Installing RAPL udev rule..."
	@echo 'SUBSYSTEM=="powercap", KERNEL=="intel-rapl:0", ACTION=="add", RUN+="/bin/chmod o+r /sys/class/powercap/intel-rapl/%k/energy_uj"' \
		| sudo tee /etc/udev/rules.d/51-rapl.rules > /dev/null
	@sudo udevadm control --reload-rules
	@sudo udevadm trigger --subsystem-match=powercap
	@echo "✅ udev rule installed → /etc/udev/rules.d/51-rapl.rules"
	@echo "   RAPL will be readable without root after next reboot (or udev trigger above)."
	@echo "   Re-run: make check-hw"

# Install dependencies
install:
	@echo "Installing required dependencies..."
	@echo ""
	@echo "[1/4] Installing system packages (sysstat, python3-tk, curl)..."
	@sudo apt-get update -qq && sudo apt-get install -y sysstat python3-tk curl
	@echo ""
	@echo "[2/4] Installing uv (Astral)..."
	@if command -v uv >/dev/null 2>&1; then \
		echo "  ✅ uv already installed: $$(uv --version)"; \
	else \
		echo "  Downloading and installing uv..."; \
		curl -LsSf https://astral.sh/uv/install.sh | sh; \
		export PATH="$$HOME/.local/bin:$$PATH"; \
		echo "  ✅ uv installed: $$(uv --version)"; \
		echo "  ℹ️  Add to PATH permanently: export PATH=\"\$$HOME/.local/bin:\$$PATH\""; \
	fi
	@echo ""
	@echo "[3/4] Installing Python dependencies with uv..."
	@PATH="$$HOME/.local/bin:$$PATH" uv sync
	@sed -i 's/include-system-site-packages = false/include-system-site-packages = true/' .venv/pyvenv.cfg 2>/dev/null || true
	@echo ""
	@echo "[4/4] Checking Docker (needed for Grafana dashboard)..."
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
	@if command -v ros2 >/dev/null 2>&1; then \
		echo "✅ ROS 2 detected: $${ROS_DISTRO:-unknown distro} (ros2 binary at $$(command -v ros2))"; \
	elif [ -d /opt/ros ]; then \
		_distro=$$(ls /opt/ros/ 2>/dev/null | tail -1); \
		echo "⚠️  ROS 2 is installed (/opt/ros/$$_distro) but not sourced."; \
		echo "   Run: source /opt/ros/$$_distro/setup.bash"; \
		echo "   Or add it to your ~/.bashrc"; \
	else \
		echo "⚠️  ROS 2 not found — required to monitor ROS 2 systems."; \
		echo "   Install: sudo apt install -y ros-jazzy-ros-base  (or ros-humble-ros-base)"; \
		echo "   See INSTALL.md for full instructions."; \
	fi
	@echo "   Tip: export ROS_DOMAIN_ID=0  (must match your robot/sim)"

# ============================================================================
# INTEL GPU PID ANALYSIS
# Requires: make install-qmassa
#
# Collected per sample:
#   GPU-level  : Engine-class busy % (Render/3D, Blitter, Compute, Video, VE)
#                Freq actual (MHz), GPU Temp (°C), GPU/Pkg Power (W)
#                VRAM / shared-mem MB, throttle status
#   Per-PID    : GPU busy % broken down by engine class (via DRM fdinfo)
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

# Probe GPU and NPU tool availability
check-hw:
	@uv run python src/monitor_resources.py --check-hw; exit 0

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
	@echo "  • uv run python src/monitor_stack.py --duration 30       # Quick local test"
	@echo "  • uv run python src/monitor_stack.py --node /my_node     # Monitor specific node"
	@if [ -n "$(REMOTE_IP)" ]; then \
		echo "  • uv run python src/monitor_stack.py --remote-ip $(REMOTE_IP)   # Monitor remote system"; \
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
			echo "Run 'uv run python src/monitor_stack.py' first to create a session"; \
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
		echo "Example: ./grafana-monitor.sh --remote-ip 192.168.1.100"; \
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
		echo "   Pipeline    : uv run python src/visualize_graph.py <session>/graph_timing.csv --show"; \
			echo "   Avg review  : uv run python src/view_average.py --runs 5"; \
	fi

# Remote PID-only monitoring + live Grafana export
monitor-remote-pid-grafana:
	@if [ -z "$(REMOTE_IP)" ]; then \
		echo "Error: Please specify REMOTE_IP=<ip_address>"; \
		echo "Example: ./grafana-monitor.sh --remote-ip 192.168.1.100 --pid-only"; \
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
		echo "   Pipeline    : uv run python src/visualize_graph.py $$SESSION_DIR/graph_timing.csv --show"; \
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
	echo "   uv run python src/view_average.py --runs $$REPEAT"; \
	echo "   uv run python src/visualize_graph.py <session>/graph_timing.csv --show"

# ─────────────────────────────────────────────────────────────────────────────
# Simulation benchmarking
#
# Optional params: RUNS TIMEOUT PN_TIMEOUT PAUSE BENCH NODE RUN_CONFIG
#   RUN_CONFIG : path to YAML run profile (default: config/<scenario>_run.yaml)
#                Example: make wandering RUN_CONFIG=config/my_custom_run.yaml
# ─────────────────────────────────────────────────────────────────────────────

wandering:
	bash src/wandering_run.sh $(if $(RUN_CONFIG),--run-config $(RUN_CONFIG)) $(if $(TIMEOUT),--timeout $(TIMEOUT)) $(if $(SIDE_TERMINALS),--side-terminals)

wandering-record:
	bash src/wandering_run.sh $(if $(RUN_CONFIG),--run-config $(RUN_CONFIG)) --record $(if $(TIMEOUT),--timeout $(TIMEOUT)) $(if $(SIDE_TERMINALS),--side-terminals)

wandering-plot:
	bash src/wandering_run.sh $(if $(RUN_CONFIG),--run-config $(RUN_CONFIG)) --plot $(if $(TIMEOUT),--timeout $(TIMEOUT)) $(if $(SIDE_TERMINALS),--side-terminals)

wandering-record-plot:
	bash src/wandering_run.sh $(if $(RUN_CONFIG),--run-config $(RUN_CONFIG)) --record --plot $(if $(TIMEOUT),--timeout $(TIMEOUT)) $(if $(SIDE_TERMINALS),--side-terminals)

wandering-benchmark:
	@RUNS=$(if $(RUNS),$(RUNS),25); \
	TIMEOUT=$(if $(TIMEOUT),$(TIMEOUT),300); \
	PAUSE=$(if $(PAUSE),$(PAUSE),30); \
	GOALS=$(if $(GOALS),$(GOALS),0); \
	BENCH_DIR=monitoring_sessions/wandering/bench_$$(date +%Y%m%d_%H%M%S); \
	mkdir -p "$$BENCH_DIR"; \
	echo "▶  Wandering benchmark: $$RUNS runs x $${TIMEOUT}s  →  $$BENCH_DIR"; \
	[ "$$GOALS" -gt 0 ] && echo "   Stop condition    : $$GOALS goals per run" || echo "   Stop condition    : timeout only"; \
	echo "   Hardware monitoring : GPU/NPU auto-detected per run"; \
	if [ -n "$(SIDE_TERMINALS)" ]; then \
		if command -v terminator >/dev/null 2>&1; then \
			echo "   Side terminals     : opening htop + qmassa..."; \
			terminator -e "htop" --title="htop — benchmark" & \
			_QM=$$(command -v qmassa 2>/dev/null || ls ~/.cargo/bin/qmassa ~/.local/bin/qmassa /usr/bin/qmassa 2>/dev/null | head -1 || true); \
			[ -n "$$_QM" ] && terminator -e "$$_QM" --title="qmassa — GPU monitor" & \
		else \
			echo "   WARNING: SIDE_TERMINALS set but terminator not found" >&2; \
		fi; \
	fi; \
	for i in $$(seq 1 $$RUNS); do \
		echo "--- Run $$i / $$RUNS ---"; \
		bash src/wandering_run.sh $(if $(RUN_CONFIG),--run-config $(RUN_CONFIG)) --timeout $$TIMEOUT --record --output-parent "$$BENCH_DIR" \
			$(if $(GOALS), --goals $$GOALS); \
		[ $$i -lt $$RUNS ] && sleep $$PAUSE; \
	done; \
	uv run python src/aggregate_kpi.py "$$BENCH_DIR" $(if $(NODE),--node $(NODE)); \
	echo ""; \
	echo "▶  Level 2 e2e analysis ready to run:"; \
	echo "   make analyze-e2e BENCH=$$BENCH_DIR"

picknplace-run:
	bash src/picknplace_run.sh $(if $(RUN_CONFIG),--run-config $(RUN_CONFIG)) $(if $(PN_TIMEOUT),--timeout $(PN_TIMEOUT),--timeout 300)

picknplace-record:
	bash src/picknplace_run.sh $(if $(RUN_CONFIG),--run-config $(RUN_CONFIG)) --record $(if $(PN_TIMEOUT),--timeout $(PN_TIMEOUT),--timeout 300)

picknplace-plot:
	bash src/picknplace_run.sh $(if $(RUN_CONFIG),--run-config $(RUN_CONFIG)) --plot $(if $(PN_TIMEOUT),--timeout $(PN_TIMEOUT),--timeout 300)

picknplace-record-plot:
	bash src/picknplace_run.sh $(if $(RUN_CONFIG),--run-config $(RUN_CONFIG)) --record --plot $(if $(PN_TIMEOUT),--timeout $(PN_TIMEOUT),--timeout 300)

picknplace-benchmark:
	@RUNS=$(if $(RUNS),$(RUNS),25); \
	TIMEOUT=$(if $(PN_TIMEOUT),$(PN_TIMEOUT),300); \
	PAUSE=$(if $(PAUSE),$(PAUSE),30); \
	BENCH_DIR=monitoring_sessions/picknplace/bench_$$(date +%Y%m%d_%H%M%S); \
	mkdir -p "$$BENCH_DIR"; \
	echo "▶  Pick-n-place benchmark: $$RUNS runs x $${TIMEOUT}s  →  $$BENCH_DIR"; \
	if [ -n "$(SIDE_TERMINALS)" ]; then \
		if command -v terminator >/dev/null 2>&1; then \
			echo "   Side terminals     : opening htop + qmassa..."; \
			terminator -e "htop" --title="htop — benchmark" & \
			_QM=$$(command -v qmassa 2>/dev/null || ls ~/.cargo/bin/qmassa ~/.local/bin/qmassa /usr/bin/qmassa 2>/dev/null | head -1 || true); \
			[ -n "$$_QM" ] && terminator -e "$$_QM" --title="qmassa — GPU monitor" & \
		else \
			echo "   WARNING: SIDE_TERMINALS set but terminator not found" >&2; \
		fi; \
	fi; \
	for i in $$(seq 1 $$RUNS); do \
		echo "--- Run $$i / $$RUNS ---"; \
		bash src/picknplace_run.sh $(if $(RUN_CONFIG),--run-config $(RUN_CONFIG)) --timeout $$TIMEOUT --record --output-parent "$$BENCH_DIR"; \
		[ $$i -lt $$RUNS ] && sleep $$PAUSE; \
	done; \
	uv run python src/aggregate_kpi.py "$$BENCH_DIR" $(if $(NODE),--node $(NODE)); \
	echo ""; \
	echo "▶  Level 2 e2e analysis ready to run:"; \
	echo "   make analyze-e2e BENCH=$$BENCH_DIR"

# ─────────────────────────────────────────────────────────────────────────────
# Bag-replay benchmarking
# Replay a pre-recorded ROS 2 bag through the monitor stack without a live
# robot or simulator.  Produces deterministic, reproducible KPI results.
#
# Required: BAG=<path>   — path to bag directory (contains metadata.yaml)
# Optional: RATE=1.0     — replay speed multiplier (e.g. 2.0 = 2x)
#           LOOP=1        — number of replay passes (0 = infinite until Ctrl-C)
#           RUNS=10       — number of independent benchmark runs (bag-replay-benchmark)
#           PAUSE=10      — seconds to pause between runs (bag-replay-benchmark)
# ─────────────────────────────────────────────────────────────────────────────

bag-replay:
	@if [ -z "$(BAG)" ]; then \
		echo "Error: Please specify BAG=<bag_directory>"; \
		echo "Example: make bag-replay BAG=monitoring_sessions/wandering/20260430_145256/bag"; \
		exit 1; \
	fi
	bash src/bag_replay_run.sh --bag "$(BAG)" \
		$(if $(RATE),--rate $(RATE)) \
		$(if $(LOOP),--loop $(LOOP))

bag-replay-plot:
	@if [ -z "$(BAG)" ]; then \
		echo "Error: Please specify BAG=<bag_directory>"; \
		echo "Example: make bag-replay-plot BAG=monitoring_sessions/wandering/20260430_145256/bag"; \
		exit 1; \
	fi
	bash src/bag_replay_run.sh --bag "$(BAG)" --plot \
		$(if $(RATE),--rate $(RATE)) \
		$(if $(LOOP),--loop $(LOOP))

bag-replay-benchmark:
	@if [ -z "$(BAG)" ]; then \
		echo "Error: Please specify BAG=<bag_directory>"; \
		echo "Example: make bag-replay-benchmark BAG=monitoring_sessions/wandering/20260430_145256/bag RUNS=10"; \
		exit 1; \
	fi
	@RUNS=$(if $(RUNS),$(RUNS),10); \
	RATE=$(if $(RATE),$(RATE),1.0); \
	PAUSE=$(if $(PAUSE),$(PAUSE),10); \
	BENCH_DIR=monitoring_sessions/bag_replay/bench_$$(date +%Y%m%d_%H%M%S); \
	mkdir -p "$$BENCH_DIR"; \
	echo "▶  Bag-replay benchmark: $$RUNS runs  →  $$BENCH_DIR"; \
	echo "   Bag  : $(BAG)"; \
	echo "   Rate : $${RATE}x"; \
	for i in $$(seq 1 $$RUNS); do \
		echo "--- Run $$i / $$RUNS ---"; \
		bash src/bag_replay_run.sh --bag "$(BAG)" --rate "$$RATE" \
			--output-parent "$$BENCH_DIR"; \
		[ $$i -lt $$RUNS ] && sleep $$PAUSE; \
	done; \
	uv run python src/aggregate_kpi.py "$$BENCH_DIR" $(if $(NODE),--node $(NODE))

# ─────────────────────────────────────────────────────────────────────────────
# Fast Mapping benchmarking
# Uses: ros2 launch fast_mapping fast_mapping.launch.py
# (starts fast_mapping_node + rviz2 + bundled spinning bag replay)
#
# Optional: RUNS=10  — independent benchmark runs (fastmapping-benchmark)
#           PAUSE=10 — seconds between runs (fastmapping-benchmark)
#           RUN_CONFIG — path to YAML run profile (default: config/fastmapping_run.yaml)
# ─────────────────────────────────────────────────────────────────────────────

fastmapping:
	bash src/fastmapping_run.sh $(if $(RUN_CONFIG),--run-config $(RUN_CONFIG))

fastmapping-plot:
	bash src/fastmapping_run.sh --plot $(if $(RUN_CONFIG),--run-config $(RUN_CONFIG))

fastmapping-benchmark:
	@RUNS=$(if $(RUNS),$(RUNS),10); \
	PAUSE=$(if $(PAUSE),$(PAUSE),10); \
	BENCH_DIR=monitoring_sessions/fastmapping/bench_$$(date +%Y%m%d_%H%M%S); \
	mkdir -p "$$BENCH_DIR"; \
	echo "▶  Fast Mapping benchmark: $$RUNS runs  →  $$BENCH_DIR"; \
	for i in $$(seq 1 $$RUNS); do \
		echo "--- Run $$i / $$RUNS ---"; \
		bash src/fastmapping_run.sh \
			$(if $(RUN_CONFIG),--run-config $(RUN_CONFIG)) \
			--output-parent "$$BENCH_DIR"; \
		[ $$i -lt $$RUNS ] && sleep $$PAUSE; \
	done; \
	echo ""; \
	echo "▶  Analysing fast_mapping_node logs..."; \
	for sess in "$$BENCH_DIR"/*/; do \
		[ -d "$$sess" ] && uv run python src/analyze_fastmapping_log.py --session "$$sess" || true; \
	done; \
	uv run python src/aggregate_kpi.py "$$BENCH_DIR" $(if $(NODE),--node $(NODE))

# ═══════════════════════════════════════════════════════════════
# HTML REPORT
# Generate a self-contained HTML benchmark report from a session dir.
# Usage: make report SESSION=<session_dir>
#        make report SESSION=<dir> OUTPUT=<file.html>
# ═══════════════════════════════════════════════════════════════

report:
	@# Help: Generate self-contained HTML report from SESSION=<dir> (writes <session>/report.html)
	@if [ -z "$(SESSION)" ]; then \
		echo "Error: Please specify SESSION=<session_directory>"; \
		echo "Example: make report SESSION=monitoring_sessions/fastmapping/20260513_130427"; \
		exit 1; \
	fi
	uv run python src/generate_report.py --session "$(SESSION)" $(if $(OUTPUT),--output $(OUTPUT))

# Generate KPI charts (latency histogram + more) from a session directory.
# Usage: make visualize-kpi SESSION=<session_dir> [FORMAT=svg]
visualize-kpi:
	@if [ -z "$(SESSION)" ]; then \
		echo "Error: Please specify SESSION=<session_directory>"; \
		echo "Example: make visualize-kpi SESSION=monitoring_sessions/fastmapping/20260513_130427"; \
		exit 1; \
	fi
	uv run python src/visualize_kpi.py \
		--session "$(SESSION)" \
		$(if $(FORMAT),--format $(FORMAT))

# Show results for the most recent (or given) session: KPI charts + HTML report.
# Usage: make results                        (auto-detects latest session)
#        make results SESSION=monitoring_sessions/wandering/bench_X/Y
results:
	@SESSION="$(SESSION)"; \
	if [ -z "$$SESSION" ]; then \
		SESSION=$$(find monitoring_sessions -mindepth 2 -maxdepth 3 -name 'kpi.json' \
			-printf '%T@ %h\n' 2>/dev/null | sort -n | tail -1 | awk '{print $$2}'); \
	fi; \
	if [ -z "$$SESSION" ]; then \
		echo "Error: no sessions found. Run a benchmark first or specify SESSION=<path>"; \
		exit 1; \
	fi; \
	echo "📊  Session: $$SESSION"; \
	echo ""; \
	echo "[1/2] Generating KPI charts..."; \
	uv run python src/visualize_kpi.py --session "$$SESSION" && \
	echo ""; \
	echo "[2/2] Generating HTML report..."; \
	uv run python src/generate_report.py --session "$$SESSION"; \
	REPORT="$$SESSION/report.html"; \
	echo ""; \
	echo "✅  Done.  Open report:"; \
	echo "      file://$$PWD/$$REPORT"; \
	if [ -n "$$DISPLAY" ]; then \
		xdg-open "$$REPORT" 2>/dev/null & \
	fi

# Generate CPU/GPU thermal + throttle time-series plot from a session.
# Usage: make visualize-thermal                  (auto-detects latest session)
#        make visualize-thermal SESSION=<path>
visualize-thermal:
	uv run python src/visualize_thermal.py \
		$(if $(SESSION),"$(SESSION)") \
		--save $(if $(SHOW),--show) $(if $(NO_SHOW),--no-show)

analyze-benchmark:
	@if [ -z "$(BENCH)" ]; then \
		echo "Error: Please specify BENCH=<bench_directory>"; \
		echo "Example: make analyze-benchmark BENCH=monitoring_sessions/wandering/bench_20260421_120000"; \
		exit 1; \
	fi
	uv run python src/aggregate_kpi.py "$(BENCH)" $(if $(NODE),--node $(NODE))

summarize-benchmark:
	@if [ -z "$(BENCH)" ]; then \
		echo "Error: Please specify BENCH=<bench_directory>"; \
		echo "Example: make summarize-benchmark BENCH=monitoring_sessions/wandering/bench_20260521_123522"; \
		exit 1; \
	fi
	uv run python src/summarize_benchmark.py "$(BENCH)"

analyze-e2e:
	@if [ -z "$(BENCH)" ]; then \
		echo "Error: Please specify BENCH=<bench_directory>"; \
		echo "Example: make analyze-e2e BENCH=monitoring_sessions/wandering/bench_20260521_123522"; \
		exit 1; \
	fi
	@for sess_dir in "$(BENCH)"/*/; do \
		kpi="$$sess_dir/kpi.json"; \
		bag="$$sess_dir/bag"; \
		if [ -f "$$kpi" ] && [ -f "$$bag/metadata.yaml" ]; then \
			echo "  → $$(basename $$sess_dir)"; \
			uv run python src/analyze_bag_e2e.py \
				--bag "$$bag" \
				--kpi "$$kpi" \
				--json-out "$$sess_dir/kpi_level2_traced.json" || true; \
		fi; \
	done
	uv run python src/summarize_benchmark.py "$(BENCH)"

regression-check:
	@# Help: Compare two Level 1 KPI JSON files for regressions (exit 1 if any KPI exceeds threshold)
	@# Usage: make regression-check BASELINE=<path> CURRENT=<path> [THRESHOLD=5.0] [REPORT=<path>]
	@if [ -z "$(BASELINE)" ] || [ -z "$(CURRENT)" ]; then \
		echo "Error: Please specify BASELINE=<path> and CURRENT=<path>"; \
		echo "Example: make regression-check BASELINE=tests/fixtures/baseline/kpi.json CURRENT=monitoring_sessions/wandering/20260430_145545/kpi.json"; \
		exit 1; \
	fi
	python3 src/compare_kpi.py \
		--baseline "$(BASELINE)" \
		--current  "$(CURRENT)" \
		$(if $(THRESHOLD),--threshold $(THRESHOLD)) \
		$(if $(REPORT),--report $(REPORT))

regression-check-l2:
	@# Help: Compare two Level 2 KPI JSON files for regressions (exit 1 if any KPI exceeds threshold)
	@# Usage: make regression-check-l2 BASELINE=<path> CURRENT=<path> [THRESHOLD=5.0] [REPORT=<path>]
	@if [ -z "$(BASELINE)" ] || [ -z "$(CURRENT)" ]; then \
		echo "Error: Please specify BASELINE=<path> and CURRENT=<path>"; \
		echo "Example: make regression-check-l2 BASELINE=tests/fixtures/baseline/kpi_level2.json CURRENT=monitoring_sessions/wandering/20260430_145545/kpi_level2.json"; \
		exit 1; \
	fi
	python3 src/compare_kpi.py \
		--baseline "$(BASELINE)" \
		--current  "$(CURRENT)" \
		$(if $(THRESHOLD),--threshold $(THRESHOLD)) \
		$(if $(REPORT),--report $(REPORT))

# Check Grafana stack status
grafana-status:
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
			echo "   Start with: uv run python src/prometheus_exporter.py --session-dir monitoring_sessions/$$(ls -t monitoring_sessions | head -1)"; \
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

# ═══════════════════════════════════════════════════════════════
# PACKAGING
# Build Debian packages matching sibling-repo convention.
# Usage: ROS_DISTRO=humble make package
#        ROS_DISTRO=jazzy  make package
# ═══════════════════════════════════════════════════════════════

package:
	@# Help: Build Debian package inside Docker (produces ros-<distro>-benchmark-framework_*.deb)
	docker run --rm -t --platform linux/amd64 \
		-v $(ROOT_DIR):/src \
		-w /src \
		-e DEBIAN_FRONTEND=noninteractive \
		amd64/ros:$(ROS_DISTRO)-ros-base \
		bash -c " \
			apt-get -qq update && apt-get install -qq -y equivs devscripts python3-hatchling && \
			rm -rf debian && cp -r $(ROS_DISTRO)/debian ./debian && \
			chmod +x debian/rules && \
			mk-build-deps -i --host-arch amd64 --build-arch amd64 \
				-t 'apt-get -y -q -o Debug::pkgProblemResolver=yes --no-install-recommends --allow-downgrades' debian/control && \
			DEB_BUILD_OPTIONS='nocheck' dpkg-buildpackage -us -uc && \
			rm -rf debian && \
			mkdir -p /src/output && mv ../*.deb /src/output/"

test:
	@# Help: Run unit tests with pytest via uv
	uv run pytest tests/ -v

license-check:
	@# Help: Perform a REUSE license check
	docker run --rm --volume $(ROOT_DIR):/data fsfe/reuse:5.0.2 lint

lint:
	@# Help: Run linters (YAML, JSON, Python, Bash, Markdown, GitHub Actions)
	$(MAKE) lint-all

lint-all:
	@# Help: Run super-linter over entire repository
	docker run --rm --platform linux/amd64 \
		-e SHELL=/bin/bash \
		-e RUN_LOCAL=true \
		--env-file ".github/linters/super-linter.env" \
		-v $(ROOT_DIR):/tmp/lint \
		ghcr.io/super-linter/super-linter:slim-v7

