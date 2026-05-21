# SPDX-FileCopyrightText: (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
#
# handheld-multi-modal — operational and packaging Makefile.
#
# Operational targets (deploy, up, down, ...) run the stack locally.
# Packaging targets (stage, vippet) are called by the parent
# federal-aerospace/Makefile to build the distribution ZIP.

SHELL        := /bin/bash
.SHELLFLAGS  := -eu -o pipefail -c
.DEFAULT_GOAL := help

# Directory of this Makefile — all paths are anchored here.
SELF_DIR := $(abspath $(dir $(lastword $(MAKEFILE_LIST))))

# ---------------------------------------------------------------------------
# Compose helpers
# ---------------------------------------------------------------------------
# Explicit -f keeps docker compose's project directory as SELF_DIR regardless
# of the caller's CWD.
COMPOSE            := docker compose -f $(SELF_DIR)/docker-compose.yml
COMPOSE_CDI        := docker compose -f $(SELF_DIR)/docker-compose-cdi.yml
COMPOSE_STANDALONE := docker compose -f $(SELF_DIR)/docker-compose-standalone.yml

VIPPET_NETWORK := visual-pipeline-and-platform-evaluation-tool_default

# ---------------------------------------------------------------------------
# vippet config
# ---------------------------------------------------------------------------
VIPPET_REPO ?= https://github.com/open-edge-platform/edge-ai-libraries.git
VIPPET_REF  ?= $(strip $(file < $(SELF_DIR)/VIPPET_REF))
VIPPET_PATH ?= tools/visual-pipeline-and-platform-evaluation-tool

# Derive docker image tag from ref: "2026.1-20260512" → "2026.1.0-20260512-weekly"
_VIPPET_VER       := $(firstword $(subst -, ,$(VIPPET_REF)))
_VIPPET_DATE      := $(lastword  $(subst -, ,$(VIPPET_REF)))
VIPPET_DOCKER_TAG ?= $(_VIPPET_VER).0-$(_VIPPET_DATE)-weekly

# vippet-fedaero sits next to this app directory (operational runtime checkout)
VIPPET_DIR := $(SELF_DIR)/../vippet-fedaero
VIPPET_CWD := $(VIPPET_DIR)/$(VIPPET_PATH)

# ---------------------------------------------------------------------------
# Packaging config (used by 'stage' / 'vippet' targets)
# ---------------------------------------------------------------------------
STAGE_DIR    ?=
WORK_DIR     ?= $(SELF_DIR)/.work
TEMPLATE_DIR := $(SELF_DIR)/templates

# ---------------------------------------------------------------------------
.PHONY: help setup \
	vippet-get vippet-configure vippet-up vippet-down \
	deploy deploy-cdi \
	up up-cdi up-standalone down down-cdi down-standalone restart restart-cdi \
	build rebuild clean health test urls build-whisper \
	stage vippet

help: ## Show this help
	@awk ' \
		/^# [A-Za-z]/ { \
			gsub(/^# /,""); printf "\n\033[1m%s\033[0m\n", $$0; next \
		} \
		/^[a-zA-Z_-]+:.*?## / { \
			split($$0, a, ":.*?## "); printf "  %-22s %s\n", a[1], a[2] \
		} \
	' $(MAKEFILE_LIST)

# Environment

setup: ## Detect render group and write missing vars to .env (safe to re-run)
	@touch $(SELF_DIR)/.env; \
	RENDER_GID=$$(getent group render | cut -d: -f3); \
	if [ -z "$$RENDER_GID" ]; then \
		echo "WARNING: 'render' group not found — using default 109"; \
		RENDER_GID=109; \
	fi; \
	if grep -q "^RENDER_GID=" $(SELF_DIR)/.env; then \
		sed -i "s|^RENDER_GID=.*|RENDER_GID=$$RENDER_GID|" $(SELF_DIR)/.env; \
	else \
		echo "RENDER_GID=$$RENDER_GID" >> $(SELF_DIR)/.env; \
	fi; \
	echo "✓ .env updated  (RENDER_GID=$$RENDER_GID)"

# vippet prerequisite

vippet-get: ## Sparse-checkout vippet into ../vippet-fedaero (excludes docs, drops .git)
	@if [ -d "$(VIPPET_CWD)" ]; then \
		echo "✓ vippet already at $(VIPPET_CWD)"; \
	else \
		echo "Cloning vippet @ $(VIPPET_REF) (sparse, docs excluded)..."; \
		git clone --filter=blob:none --no-checkout --depth 1 \
			--branch $(VIPPET_REF) $(VIPPET_REPO) $(VIPPET_DIR) && \
		cd $(VIPPET_DIR) && \
		git sparse-checkout init --no-cone && \
		printf '$(VIPPET_PATH)/**\n!$(VIPPET_PATH)/docs/**\n' | \
			git sparse-checkout set --stdin && \
		git checkout && \
		rm -rf .git && \
		echo "✓ vippet cloned to $(VIPPET_CWD)"; \
	fi

vippet-configure: vippet-get ## Copy telegraf config and inject env vars into vippet
	@echo "Configuring vippet metrics-manager..."; \
	cp $(SELF_DIR)/collector/telegraf.conf $(VIPPET_CWD)/vippet-telegraf.conf; \
	python3 -c 'import yaml; src="$(VIPPET_CWD)/shared/models/supported_models.yaml"; models=yaml.safe_load(open(src)); filtered=[m for m in models if m.get("source")!="huggingface"]; yaml.dump(filtered,open(src,"w"),default_flow_style=False,allow_unicode=True); print(f"✓ supported_models.yaml filtered ({len(filtered)}/{len(models)} models, huggingface excluded)")'; \
	if ! grep -q 'METRICS_MANAGER_HOSTNAME' $(VIPPET_CWD)/compose.yml; then \
		sed -i 's|METRICS_RETENTION_SECONDS:.*|&\n      METRICS_MANAGER_HOSTNAME: $${METRICS_MANAGER_HOSTNAME:-ptl}|' $(VIPPET_CWD)/compose.yml; \
		echo "✓ compose.yml patched (METRICS_MANAGER_HOSTNAME added)"; \
	fi; \
	echo "✓ vippet configured (telegraf.conf copied)"

vippet-up: vippet-configure ## Start vippet (builds images, installs all models, starts stack)
	@cd $(VIPPET_CWD) && \
	sed -i 's|^VERSION=.*|VERSION=$(VIPPET_DOCKER_TAG)|' setup_env.sh && \
	{ [ -f .env ] || bash setup_env.sh; } && \
	if grep -q '^DOCKER_TAG=' .env 2>/dev/null; then \
		sed -i 's|^DOCKER_TAG=.*|DOCKER_TAG=$(VIPPET_DOCKER_TAG)|' .env; \
	else \
		echo 'DOCKER_TAG=$(VIPPET_DOCKER_TAG)' >> .env; \
	fi && \
	if grep -q '^METRICS_MANAGER_HOSTNAME=' .env 2>/dev/null; then \
		sed -i 's|^METRICS_MANAGER_HOSTNAME=.*|METRICS_MANAGER_HOSTNAME=ptl|' .env; \
	else \
		echo 'METRICS_MANAGER_HOSTNAME=ptl' >> .env; \
	fi && \
	$(MAKE) build-onvif-discovery build-models install-models-all run && \
	echo "✓ vippet running"

vippet-down: ## Stop vippet
	@cd $(VIPPET_CWD) && docker compose down

# Full one-shot deployment

define _wait_for_network
	@echo "Waiting for vippet network to appear..."; \
	for i in $$(seq 1 30); do \
		docker network ls --format '{{.Name}}' | \
			grep -q '$(VIPPET_NETWORK)' && { echo "✓ Network ready"; break; }; \
		if [ $$i -eq 30 ]; then \
			echo "ERROR: vippet network '$(VIPPET_NETWORK)' not found after 60s"; \
			echo "       Is vippet running? Try: make vippet-up"; \
			exit 1; \
		fi; \
		echo "  [$$i/30] not ready yet, retrying in 2s..."; \
		sleep 2; \
	done
endef

deploy: setup vippet-up ## Full deploy: setup → start vippet → start this stack
	$(call _wait_for_network)
	@$(MAKE) up

deploy-cdi: setup vippet-up ## Full deploy (CDI/SR-IOV): setup → start vippet → start this stack
	$(call _wait_for_network)
	@$(MAKE) up-cdi

# Stack lifecycle

build-whisper: ## Build whisper-stt image if not already present
	@if docker image inspect whisper-stt:latest > /dev/null 2>&1; then \
		echo "✓ whisper-stt:latest already exists — skipping build"; \
	else \
		echo "Building whisper-stt image..."; \
		$(COMPOSE) build whisper-stt; \
	fi

up: build-whisper ## Start all services (standard)
	@echo "Starting handheld-multi-modal stack (standard)..."
	$(COMPOSE) up -d

up-cdi: build-whisper ## Start all services (CDI / SR-IOV)
	@echo "Starting handheld-multi-modal stack (CDI)..."
	$(COMPOSE_CDI) up -d

down: vippet-down ## Stop all services (standard) and vippet
	$(COMPOSE) down

down-cdi: vippet-down ## Stop all services (CDI) and vippet
	$(COMPOSE_CDI) down

up-standalone: build-whisper ## Start all services (standalone — no VIPPET required, dev/testing only)
	@echo "Starting handheld-multi-modal stack (standalone)..."
	$(COMPOSE_STANDALONE) up -d

down-standalone: ## Stop all services (standalone)
	$(COMPOSE_STANDALONE) down

restart: ## Restart all services (standard)
	$(COMPOSE) restart

restart-cdi: ## Restart all services (CDI)
	$(COMPOSE_CDI) restart

build: ## Build all Docker images
	$(COMPOSE) build

rebuild: ## Rebuild images without touching volumes
	$(COMPOSE) down --rmi local && $(COMPOSE) build

clean: ## Remove staging scratch (.work). Add CONFIRM=yes to also stop containers and wipe data dirs
	rm -rf "$(WORK_DIR)"
	@if [ "$(CONFIRM)" = "yes" ]; then \
		$(COMPOSE) down -v; \
		docker run --rm -v "$(SELF_DIR)/data:/data" alpine \
			sh -c "rm -rf /data/grafana /data/ovms-models /data/open-webui /data/whisper-cache /data/nginx-certs"; \
		echo "✓ Containers stopped and data directories removed"; \
	else \
		echo "  Tip: run  make clean CONFIRM=yes  to also stop containers and remove data dirs"; \
	fi

health: ## Show service health status
	$(COMPOSE) ps --format "table {{.Service}}\t{{.Status}}"

test: ## Test service connectivity (OVMS may need several minutes on first boot)
	@echo "Testing services..."
	@echo "  Note: OVMS downloads the model on first start — allow a few minutes if just deployed."
	@curl -sfk https://localhost:7443/api/health > /dev/null && echo "✓ Grafana"     || echo "✗ Grafana"
	@curl -sf  http://localhost:9000/v3/models   > /dev/null && echo "✓ OVMS"        || echo "✗ OVMS (may still be loading model)"
	@curl -sfk https://localhost:8443            > /dev/null && echo "✓ Open WebUI"  || echo "✗ Open WebUI"
	@curl -sfk https://localhost:5443/health     > /dev/null && echo "✓ Whisper STT" || echo "✗ Whisper STT"

urls: ## Print service endpoints
	@echo ""
	@echo "  Open WebUI       https://localhost:8443   (via nginx)"
	@echo "  Grafana          https://localhost:7443   (via nginx)"
	@echo "  Whisper STT      https://localhost:5443   (via nginx)"
	@echo "  VIPPET UI        https://localhost:443    (via nginx)"
	@echo "  OVMS API         http://localhost:9000/v3"
	@echo "  OVMS metrics     http://localhost:9000/metrics"
	@echo ""

# Packaging — called by the federal-aerospace top-level Makefile

stage: ## Stage the handheld-multi-modal tree at $(STAGE_DIR) (called by parent Makefile)
	@if [[ -z "$(STAGE_DIR)" ]]; then echo "error: STAGE_DIR is required" >&2; exit 2; fi
	@echo ">> Staging handheld-multi-modal at $(STAGE_DIR)"
	@rm -rf "$(STAGE_DIR)"
	@mkdir -p "$(STAGE_DIR)/handheld-multi-modal"
	rsync -a --exclude='templates' --exclude='.work' \
		"$(SELF_DIR)/" "$(STAGE_DIR)/handheld-multi-modal/"
	cp "$(TEMPLATE_DIR)/README.md" "$(STAGE_DIR)/README.md"
	install -m 0755 "$(TEMPLATE_DIR)/run.sh" "$(STAGE_DIR)/run.sh"
	$(MAKE) --no-print-directory vippet VIPPET_DEST="$(STAGE_DIR)/vippet-fedaero"

vippet: ## Sparse-checkout vippet into $(VIPPET_DEST) for packaging (called by stage)
	@if [[ -z "$(VIPPET_DEST)" ]]; then echo "error: VIPPET_DEST is required" >&2; exit 2; fi
	@echo ">> Sparse-checking out vippet @ $(VIPPET_REF) (docs excluded)"
	@rm -rf "$(WORK_DIR)/vippet_src"
	git clone --filter=blob:none --no-checkout --depth 1 \
		--branch "$(VIPPET_REF)" "$(VIPPET_REPO)" "$(WORK_DIR)/vippet_src"
	cd "$(WORK_DIR)/vippet_src" && \
		git sparse-checkout init --no-cone && \
		printf '$(VIPPET_PATH)/**\n!$(VIPPET_PATH)/docs/**\n' | \
			git sparse-checkout set --stdin && \
		git checkout
	@rm -rf "$(VIPPET_DEST)"
	@mkdir -p "$(VIPPET_DEST)/$(VIPPET_PATH)"
	cp -a "$(WORK_DIR)/vippet_src/$(VIPPET_PATH)/." "$(VIPPET_DEST)/$(VIPPET_PATH)/"
	@echo "$(VIPPET_REF)" > "$(VIPPET_DEST)/.vippet-ref"

STT_HOST ?= https://localhost:5443
fuzz-stt: ## Fuzz / robustness test the Whisper STT API (override with STT_HOST=https://…)
	@command -v python3 >/dev/null 2>&1 || { echo "python3 not found"; exit 1; }
	@python3 -c "import requests" 2>/dev/null || { echo "Missing dependency — run: pip install requests"; exit 1; }
	python3 tests/fuzz_stt_api.py --host "$(STT_HOST)"
