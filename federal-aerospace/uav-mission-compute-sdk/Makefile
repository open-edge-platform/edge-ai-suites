# SPDX-FileCopyrightText: (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

SHELL := bash -eu -o pipefail
.PHONY: init up up-ethernet down down-ethernet build build-nc logs ps apps apps-down apps-logs clean deps clean-venv bench bench-sweep bench-bridge-sweep help

# ── Deployment mode flag ───────────────────────────────────────────────────
# FC_IP must be set for ethernet mode (IP of FC machine running mavlink-router)
FC_IP ?=

COMPOSE_LOCAL   := docker compose -f docker-compose.yml
COMPOSE_ETH     := docker compose -f docker-compose.yml -f docker-compose.ethernet.yml
COMPOSE_APPS    := docker compose -f sample-apps/docker-compose.yml

# ── Environment file ──────────────────────────────────────────────────────
init:
	@# Help: Create .env from .env.example if it does not already exist
	@test -f .env && echo ".env already exists — skipping" || (cp .env.example .env && echo ".env created — edit it to set your own credentials before starting the stack")

# ── Local simulation mode (default) ───────────────────────────────────────
# Camera mode is controlled via .env (multi-cam default, single-cam by switching vars)
up:
	@# Help: Start core infra (PX4 Gazebo sim + bridges + MQTT + RTSP + observability)
	$(COMPOSE_LOCAL) up -d --build

build:
	@# Help: Build all images (core infra + apps), using Docker layer cache
	$(COMPOSE_LOCAL) build
	$(COMPOSE_APPS) build

build-nc:
	@# Help: Build all images (core infra + apps) with NO cache — full rebuild
	$(COMPOSE_LOCAL) build --no-cache
	$(COMPOSE_APPS) build --no-cache

down:
	@# Help: Stop core infra
	$(COMPOSE_LOCAL) down

logs:
	@# Help: Tail logs for core infra
	$(COMPOSE_LOCAL) logs -f

ps:
	@# Help: Show service status (core infra)
	$(COMPOSE_LOCAL) ps

# ── Sample apps + AI helpers ──────────────────────────────────────────────
apps:
	@# Help: Start AI helpers + sample apps (requires core infra running)
	$(COMPOSE_APPS) up -d --build

apps-down:
	@# Help: Stop AI helpers + sample apps
	$(COMPOSE_APPS) down

apps-logs:
	@# Help: Tail logs for AI helpers + sample apps
	$(COMPOSE_APPS) logs -f

# ── Ethernet / real hardware mode ─────────────────────────────────────────
up-ethernet:
	@# Help: Start stack in ethernet mode — requires FC_IP=<IP>
	@if [[ -z "$(FC_IP)" ]]; then \
		echo "Error: FC_IP is required.  Usage: make up-ethernet FC_IP=192.168.1.100"; \
		exit 1; \
	fi
	FC_IP=$(FC_IP) $(COMPOSE_ETH) up -d --build

down-ethernet:
	@# Help: Stop ethernet stack
	FC_IP=$(FC_IP) $(COMPOSE_ETH) down

# ── Deploy FC machine (remote PX4 SITL + mavlink-router) ──────────────────
deploy-remote:
	@# Help: Copy infra/px4-remote/ to FC machine and start it — requires FC_IP=<IP>
	@if [[ -z "$(FC_IP)" ]]; then \
		echo "Error: FC_IP is required.  Usage: make deploy-remote FC_IP=192.168.1.100"; \
		exit 1; \
	fi
	bash infra/scripts/deploy_remote.sh $(FC_IP)

# ── Misc ──────────────────────────────────────────────────────────────────
clean:
	@# Help: Remove stopped containers and dangling images
	docker compose -f docker-compose.yml down --remove-orphans
	docker image prune -f

help:
	@printf "%-20s %s\n" "Target" "Description"
	@printf "%-20s %s\n" "------" "-----------"
	@make -pqR : 2>/dev/null \
	  | awk -v RS= -F: '/^# File/,/^# Finished Make data base/ \
	    {if ($$1 !~ "^[#.]") {print $$1}}' \
	  | sort \
	  | grep -Ev -e '^[^[:alnum:]]' -e '^$$' \
	  | xargs -I _ sh -c 'printf "%-20s " _; make _ -nB 2>/dev/null \
	    | (grep -i "^# Help:" || echo "") | tail -1 | sed "s/^# Help: //g"'

# Python env for host-side scripts (benchmarks, missions)
VENV := .venv
PY   := $(VENV)/bin/python
PIP  := $(VENV)/bin/pip
REQ  := requirements.txt

deps: $(VENV)/.installed  ## Install Python deps into a local .venv (uv if present, else python3-venv)
	@echo ""
	@echo "Deps installed in $(VENV)."

$(VENV)/.installed: $(REQ)
	@if command -v uv >/dev/null 2>&1; then \
		echo ">>> using uv"; \
		uv venv $(VENV); \
		uv pip install --python $(PY) -r $(REQ); \
	elif python3 -c "import ensurepip" >/dev/null 2>&1; then \
		echo ">>> using python3 -m venv"; \
		test -d $(VENV) || python3 -m venv $(VENV); \
		$(PIP) install --upgrade pip; \
		$(PIP) install -r $(REQ); \
	else \
		echo "ERROR: neither 'uv' nor python3 'ensurepip' is available."; \
		echo "Fix with ONE of:"; \
		echo "  sudo apt install python3-venv           # then re-run 'make deps'"; \
		echo "  curl -LsSf https://astral.sh/uv/install.sh | sh   # install uv, then re-run"; \
		echo "  make deps-break                         # last resort: system-wide install"; \
		exit 1; \
	fi
	@touch $@

bench:  ## Run the MAVLink->MQTT telemetry benchmark (stack must be running); pass args with ARGS="--duration 30 --clients 4"
	$(PY) benchmarks/benchmark_mavlink_mqtt.py $(ARGS)

# SWEEP_RATES: comma-separated Hz tiers to stress-test (default covers a wide range)
SWEEP_RATES    ?= 10,25,50,100,200,500
# SWEEP_DURATION: measurement window per tier in seconds
SWEEP_DURATION ?= 10
bench-sweep:  ## Broker-only stress: synthetic publisher at increasing Hz measures drop/latency; tune with SWEEP_RATES="10,25,50,100,200,500" SWEEP_DURATION=10
	$(PY) benchmarks/benchmark_mavlink_mqtt.py --sweep --sweep-rates $(SWEEP_RATES) --sweep-duration $(SWEEP_DURATION) $(ARGS)

# BRIDGE_SWEEP_RATES: caps applied to attitude/velocity/position on each tier
BRIDGE_SWEEP_RATES ?= 20,50,100,200
bench-bridge-sweep:  ## End-to-end stress: recreates companion-bridge with escalating RATE_*_HZ caps and measures observed rate/latency. Requires `make up` and uav armed. Tune with BRIDGE_SWEEP_RATES="20,50,100,200" SWEEP_DURATION=15
	$(PY) benchmarks/benchmark_mavlink_mqtt.py --bridge-sweep --sweep-rates $(BRIDGE_SWEEP_RATES) --sweep-duration $(SWEEP_DURATION) $(ARGS)

clean-venv:  ## Remove the local .venv
	rm -rf $(VENV)

.DEFAULT_GOAL := help
