# SPDX-FileCopyrightText: (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

SHELL := bash -eu -o pipefail
.PHONY: init up-sim-camera up-sim-camera-lean up-sim-camera-mono up-sim-camera-mono-lean up-usb-camera-lean up-ethernet down down-ethernet build build-nc logs ps apps apps-down apps-logs clean clean-all deps clean-venv bench bench-bridge-sweep help

# ── Deployment mode flag ───────────────────────────────────────────────────
# FC_IP must be set for ethernet mode (IP of FC machine running mavlink-router)
FC_IP ?=

COMPOSE_LOCAL   := docker compose -f docker-compose.yml
COMPOSE_ETH     := docker compose -f docker-compose.yml -f docker-compose.ethernet.yml
COMPOSE_APPS    := docker compose --env-file .env -f sample-apps/docker-compose.yml

# ── Environment file ──────────────────────────────────────────────────────
init:
	@# Help: Create .env from .env.example, populate required credentials, and auto-detect GPU devices
	@if [ ! -f .env ]; then \
		cp .env.example .env; \
		echo ".env created"; \
	fi; \
	set_if_empty() { \
		key="$$1"; value="$$2"; \
		if ! grep -qE "^$$key=.+$$" .env 2>/dev/null; then \
			sed -i "/^$$key=/d" .env; \
			echo "$$key=$$value" >> .env; \
		fi; \
	}; \
	uav_id="uav-1"; \
	influxdb_password="$$(openssl rand -hex 16)"; \
	influxdb_token="$$(openssl rand -hex 32)"; \
	influxdb_org="uav-sdk"; \
	grafana_password="$$(openssl rand -hex 12)"; \
	set_if_empty "UAV_ID" "$$uav_id"; \
	set_if_empty "INFLUXDB_PASSWORD" "$$influxdb_password"; \
	set_if_empty "INFLUXDB_TOKEN" "$$influxdb_token"; \
	set_if_empty "INFLUXDB_ORG" "$$influxdb_org"; \
	set_if_empty "GRAFANA_PASSWORD" "$$grafana_password"; \
	echo "Generated default credentials in .env"; \
	if GPU_CARD=$$(ls -1 /dev/dri/card* 2>/dev/null | head -1); then \
		GPU_RENDER=$$(ls -1 /dev/dri/renderD* 2>/dev/null | head -1); \
		if [ -n "$$GPU_RENDER" ]; then \
			GPU_RENDER_GID=$$(stat -c "%g" "$$GPU_RENDER" 2>/dev/null); \
			echo "✅ GPU devices detected. Adding to .env:"; \
			echo "   GPU_DEVICE=$$GPU_CARD"; \
			echo "   GPU_RENDER_DEVICE=$$GPU_RENDER"; \
			echo "   GPU_RENDER_GID=$$GPU_RENDER_GID"; \
			sed -i '/^GPU_DEVICE=/d' .env; \
			sed -i '/^GPU_RENDER_DEVICE=/d' .env; \
			sed -i '/^GPU_RENDER_GID=/d' .env; \
			echo "GPU_DEVICE=$$GPU_CARD" >> .env; \
			echo "GPU_RENDER_DEVICE=$$GPU_RENDER" >> .env; \
			echo "GPU_RENDER_GID=$$GPU_RENDER_GID" >> .env; \
		fi; \
	fi

# ── Local simulation mode (default) ───────────────────────────────────────
# Camera mode is controlled via .env. Each target below sets every relevant
# var on every run, so switching between multi-cam and mono-cam is clean
# regardless of what a previous `make up-sim-camera*` run left behind.
SIM_CAMERA_VARS_MULTI = PX4_START_SCRIPT=start_px4_multicam.sh PX4_MODEL_DIR=multi_cam PX4_WORLD_FILE=baylands_multicam.sdf GZ_WORLD=baylands_multicam CAMERA_IDS=nadir,forward,rear VISION_CAMERA_IDS=nadir,forward,rear COMPANION_BRIDGE_URL=http://px4-gazebo:8080
SIM_CAMERA_VARS_MONO = PX4_START_SCRIPT=start_px4.sh PX4_MODEL_DIR=mono_cam PX4_WORLD_FILE=baylands_detection.sdf GZ_WORLD=baylands_detection CAMERA_IDS=nadir VISION_CAMERA_IDS=nadir COMPANION_BRIDGE_URL=http://px4-gazebo:8080

define set_env_vars
	@touch .env
	@for kv in $(1); do \
		key=$${kv%%=*}; \
		sed -i "/^$${key}=/d" .env; \
		echo "$$kv" >> .env; \
	done
endef

up-sim-camera:
	@# Help: Start core infra with PX4 Gazebo sim cameras — 3 cameras: nadir, forward, rear (sim-camera profile)
	$(call set_env_vars,$(SIM_CAMERA_VARS_MULTI))
	PX4_NETWORK_SERVICE=px4 $(COMPOSE_LOCAL) --profile sim-camera --profile observability up -d --build

up-sim-camera-lean:
	@# Help: Start sim-camera without observability stack (saves ~300 MB RAM)
	$(call set_env_vars,$(SIM_CAMERA_VARS_MULTI))
	PX4_NETWORK_SERVICE=px4 $(COMPOSE_LOCAL) --profile sim-camera up -d --build

up-sim-camera-mono:
	@# Help: Start core infra with PX4 Gazebo sim cameras — 1 camera: nadir only (sim-camera profile)
	$(call set_env_vars,$(SIM_CAMERA_VARS_MONO))
	PX4_NETWORK_SERVICE=px4 $(COMPOSE_LOCAL) --profile sim-camera --profile observability up -d --build

up-sim-camera-mono-lean:
	@# Help: Start mono sim-camera without observability stack (saves ~300 MB RAM)
	$(call set_env_vars,$(SIM_CAMERA_VARS_MONO))
	PX4_NETWORK_SERVICE=px4 $(COMPOSE_LOCAL) --profile sim-camera up -d --build

up-usb-camera:
	@# Help: Start core infra with real USB camera + lightweight PX4 SIH + companion telemetry services
	@touch .env \
		&& sed -i '/^COMPANION_BRIDGE_URL=/d' .env && echo 'COMPANION_BRIDGE_URL=http://px4-sitl:8080' >> .env \
		&& sed -i '/^VISION_CAMERA_IDS=/d' .env && echo 'VISION_CAMERA_IDS=nadir' >> .env
	PX4_NETWORK_SERVICE=px4-sih $(COMPOSE_LOCAL) --profile usb-camera --profile observability up -d --build

up-usb-camera-lean:
	@# Help: Start usb-camera without observability stack (saves ~300 MB RAM)
	@touch .env \
		&& sed -i '/^COMPANION_BRIDGE_URL=/d' .env && echo 'COMPANION_BRIDGE_URL=http://px4-sitl:8080' >> .env \
		&& sed -i '/^VISION_CAMERA_IDS=/d' .env && echo 'VISION_CAMERA_IDS=nadir' >> .env
	PX4_NETWORK_SERVICE=px4-sih $(COMPOSE_LOCAL) --profile usb-camera up -d --build

build:
	@# Help: Build all images (core infra + apps), using Docker layer cache
	$(COMPOSE_LOCAL) build
	$(COMPOSE_APPS) build

build-nc:
	@# Help: Build all images (core infra + apps) with NO cache — full rebuild
	$(COMPOSE_LOCAL) build --no-cache
	$(COMPOSE_APPS) build --no-cache

down:
	@# Help: Stop all containers — core infra (sim-camera/usb-camera) + apps
	$(COMPOSE_APPS) down --remove-orphans
	$(COMPOSE_LOCAL) --profile sim-camera --profile usb-camera --profile observability down --remove-orphans

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
	FC_IP=$(FC_IP) $(COMPOSE_ETH) --profile ethernet --profile observability up -d --build

down-ethernet:
	@# Help: Stop ethernet stack (FC_IP not required — value is irrelevant for teardown)
	FC_IP=$(if $(FC_IP),$(FC_IP),0.0.0.0) $(COMPOSE_ETH) --profile ethernet --profile observability down

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
	$(COMPOSE_LOCAL) --profile sim-camera --profile usb-camera --profile observability down --remove-orphans
	docker image prune -f

clean-all:
	@# Help: Remove containers, compose volumes, and all unused images
	$(COMPOSE_LOCAL) --profile sim-camera --profile usb-camera --profile observability down --remove-orphans --volumes
	docker image prune -a -f

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
		exit 1; \
	fi
	@touch $@

bench:  ## Run the MAVLink->MQTT telemetry benchmark (stack must be running); pass args with ARGS="--duration 30 --clients 4"
	$(PY) benchmarks/benchmark_mavlink_mqtt.py $(ARGS)

# SWEEP_DURATION: measurement window per tier in seconds
SWEEP_DURATION ?= 10

# BRIDGE_SWEEP_RATES: caps applied to attitude/velocity/position on each tier
BRIDGE_SWEEP_RATES ?= 20,50,100,200
bench-bridge-sweep:  ## End-to-end stress: recreates companion-bridge with escalating RATE_*_HZ caps and measures observed rate/latency. Requires `make up-sim-camera` and uav armed. Tune with BRIDGE_SWEEP_RATES="20,50,100,200" SWEEP_DURATION=15
	$(PY) benchmarks/benchmark_mavlink_mqtt.py --bridge-sweep --sweep-rates $(BRIDGE_SWEEP_RATES) --sweep-duration $(SWEEP_DURATION) $(ARGS)

clean-venv:  ## Remove the local .venv
	rm -rf $(VENV)

.DEFAULT_GOAL := help
