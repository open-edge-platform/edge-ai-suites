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

MODELS_RETRIES  ?= 20
MODELS_STATUS_INTERVAL ?= 30
MODELS_LICENSE_FILE ?= .license-accepted
MODELS_SUPPORTED_FILE ?= $(VIPPET_CWD)/shared/models/supported_models.yaml

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
	stage vippet \
	restler-build restler-stt restler-package \
	models-license models-download models-status

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
	python3 $(SELF_DIR)/scripts/filter_models.py \
		"$(VIPPET_CWD)/shared/models/supported_models.yaml" \
		"$(VIPPET_CWD)/vippet/pipelines"; \
	if ! grep -q 'METRICS_MANAGER_HOSTNAME' $(VIPPET_CWD)/compose.yml; then \
		sed -i 's|METRICS_RETENTION_SECONDS:.*|&\n      METRICS_MANAGER_HOSTNAME: $${METRICS_MANAGER_HOSTNAME:-ptl}|' $(VIPPET_CWD)/compose.yml; \
		echo "✓ compose.yml patched (METRICS_MANAGER_HOSTNAME added)"; \
	fi; \
	if ! grep -q 'vippet/pipelines' $(VIPPET_CWD)/compose.yml; then \
		sed -i '/    - \.\/shared\/metadata\/:\/metadata/a\    - .\/vippet\/pipelines:\/home\/dlstreamer\/vippet\/pipelines:ro' \
			$(VIPPET_CWD)/compose.yml; \
		echo "✓ compose.yml patched (pipelines volume added)"; \
	fi; \
    if grep -q '80:80' $(VIPPET_CWD)/compose.yml; then \
		yq -i -y '(.services[] | select(.ports[]? == "80:80") | .ports) = []' $(VIPPET_CWD)/compose.yml; \
		echo "✓ compose.yml patched (80:80 port mapping removed)"; \
    fi; \
	if ! grep -q 'frame-ancestors' $(VIPPET_CWD)/ui/nginx.conf; then \
		sed -i 's|SAMEORIGIN|frame-ancestors|' $(VIPPET_CWD)/ui/nginx.conf; \
		echo "✓ nginx.conf patched (frame-ancestors added)"; \
	fi; \
	# pallet_defect_detection needs updated model server (higher than 2026.1.0), otherwise it will fail to download
	yq -i -y 'del(.[] | select(.name == "pallet_defect_detection"))' $(VIPPET_CWD)/shared/models/supported_models.yaml; \
	# disable HTTP port with metrics
	yq -i -y '.services."metrics-manager".ports = ["9090:9090"]' $(VIPPET_CWD)/compose.yml; \
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
	$(MAKE) build-onvif-discovery run && \
	echo "✓ vippet running"
	# fedaero makefile
	$(MAKE) models-license models-download models-status 

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

test: ## Test service connectivity
	@echo "Testing services..."
	@curl -sfk https://localhost:443             > /dev/null && echo "✓ Single pane page"  || echo "✗ Single pane page"
	@curl -sfk https://localhost:1443            > /dev/null && echo "✓ ViPPET"            || echo "✗ ViPPET"
	@curl -sfk https://localhost:5443/health     > /dev/null && echo "✓ Whisper STT"       || echo "✗ Whisper STT"
	@curl -sfk https://localhost:6443/metrics    > /dev/null && echo "✓ OVMS"              || echo "✗ OVMS"
	@curl -sfk https://localhost:7443/api/health > /dev/null && echo "✓ Grafana"           || echo "✗ Grafana"
	@curl -sfk https://localhost:8443            > /dev/null && echo "✓ Open WebUI"        || echo "✗ Open WebUI"

urls: ## Print service endpoints
	@echo ""
	@echo "  Single pane page        https://localhost:443    (via nginx)"
	@echo "  VIPPET UI               https://localhost:1443   (via nginx)"
	@echo "  Whisper STT             https://localhost:5443   (via nginx)"
	@echo "  OVMS metrics            https://localhost:6443   (via nginx)"
	@echo "  Grafana                 https://localhost:7443   (via nginx)"
	@echo "  Open WebUI              https://localhost:8443   (via nginx)"
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

RESTLER_EVIDENCE_ZIP ?= $(WORK_DIR)/restler-evidence.zip

STT_HOST         ?= https://localhost:5443
RESTLER_VERSION  ?= v9.3.1
RESTLER_IMAGE    ?= restler-fuzzer:$(RESTLER_VERSION)
RESTLER_DIR      := $(WORK_DIR)/restler
STT_RESTLER_IP   ?= localhost
STT_RESTLER_PORT ?= 5443
RESTLER_BUDGET   ?= 0.5

fuzz-stt: ## Fuzz / robustness test the Whisper STT API (override with STT_HOST=https://…)
	@command -v python3 >/dev/null 2>&1 || { echo "python3 not found"; exit 1; }
	@python3 -c "import requests" 2>/dev/null || { echo "Missing dependency — run: pip install requests"; exit 1; }
	python3 tests/fuzz_stt_api.py --host "$(STT_HOST)"

restler-build: ## Build the RESTler Docker image from source (once; RESTLER_VERSION overridable)
	@if docker image inspect "$(RESTLER_IMAGE)" > /dev/null 2>&1; then \
		echo "✓ $(RESTLER_IMAGE) already present"; \
	else \
		echo "Building RESTler $(RESTLER_VERSION) — this takes a few minutes (no binary releases exist)..."; \
		docker build \
			-t "$(RESTLER_IMAGE)" \
			"https://github.com/microsoft/restler-fuzzer.git#$(RESTLER_VERSION)"; \
	fi

restler-stt: restler-build ## RESTler fuzz the Whisper STT API for RESTLER_BUDGET hours (default 0.5h)
	@echo ">> RESTler fuzz: https://$(STT_RESTLER_IP):$(STT_RESTLER_PORT) budget=$(RESTLER_BUDGET)h"
	@mkdir -p "$(RESTLER_DIR)"
	@echo "  Step 1: compile grammar from tests/stt-openapi.yaml"
	docker run --rm \
		--workdir /work \
		-v "$(SELF_DIR)/tests/stt-openapi.yaml:/work/stt-openapi.yaml:ro" \
		-v "$(RESTLER_DIR):/work" \
		"$(RESTLER_IMAGE)" \
		/RESTler/restler/Restler compile --api_spec /work/stt-openapi.yaml
	@echo "  Step 2: fuzz (budget=$(RESTLER_BUDGET)h)"
	docker run --rm \
		--workdir /work \
		--network host \
		-v "$(RESTLER_DIR):/work" \
		-v "$(SELF_DIR)/tests/restler-settings.json:/work/restler-settings.json:ro" \
		"$(RESTLER_IMAGE)" \
		/RESTler/restler/Restler fuzz \
			--grammar_file /work/Compile/grammar.py \
			--dictionary_file /work/Compile/dict.json \
			--settings /work/restler-settings.json \
			--target_ip $(STT_RESTLER_IP) \
			--target_port $(STT_RESTLER_PORT) \
			--time_budget $(RESTLER_BUDGET)
	@LATEST=$$(ls -td "$(RESTLER_DIR)/Fuzz/RestlerResults/experiment"*/ 2>/dev/null | head -1); \
	echo ">> RESTler results: $${LATEST:-$(RESTLER_DIR)/Fuzz/RestlerResults/}"

restler-package: ## Assemble RESTler evidence ZIP for submission (run after restler-stt)
	@set -eu; \
	LATEST=$$(ls -td "$(RESTLER_DIR)/Fuzz/RestlerResults/experiment"*/ 2>/dev/null | head -1); \
	[ -n "$$LATEST" ] || { echo "ERROR: No RESTler results found. Run 'make restler-stt' first." >&2; exit 1; }; \
	EXP_ID=$$(basename "$${LATEST%/}"); \
	echo ">> Packaging $$EXP_ID into evidence ZIP..."; \
	OUT="$(WORK_DIR)/restler-evidence"; \
	LOGS="$$OUT/Fuzz/RestlerResults/$$EXP_ID/logs"; \
	RESPONSE_BUCKETS="$(RESTLER_DIR)/Fuzz/ResponseBuckets"; \
	rm -rf "$$OUT"; \
	mkdir -p "$$LOGS/bug_buckets" "$$LOGS/ResponseBuckets"; \
	cp "$$LATEST/logs/main.txt" "$$LOGS/main.txt"; \
	if [ -f "$$LATEST/logs/bug_buckets/bug_buckets.txt" ]; then \
		cp "$$LATEST/logs/bug_buckets/bug_buckets.txt" "$$LOGS/bug_buckets/bug_buckets.txt"; \
	else \
		printf 'Bug buckets summary\n===================\n\nNo bugs detected (0 bug buckets).\n' \
			> "$$LOGS/bug_buckets/bug_buckets.txt"; \
	fi; \
	TS="$$LATEST/logs/testing_summary.json"; \
	if [ -f "$$RESPONSE_BUCKETS/errorBuckets.json" ]; then \
		cp "$$RESPONSE_BUCKETS/errorBuckets.json" "$$LOGS/ResponseBuckets/errorBuckets.json"; \
	fi; \
	if [ -f "$$RESPONSE_BUCKETS/runSummary.json" ]; then \
		cp "$$RESPONSE_BUCKETS/runSummary.json" "$$LOGS/ResponseBuckets/runSummary.json"; \
	else \
		python3 -c "import json,sys; ts=json.load(open(sys.argv[1])); sent=ts.get('total_requests_sent',{}); total=sum(v for v in sent.values() if isinstance(v,int)); bugs=sum(ts.get('bug_buckets',{}).values()); print(json.dumps({'requestsCount':total,'sequencesCount':0,'bugCount':bugs,'codeCounts':{},'errorBuckets':ts.get('bug_buckets',{})},indent=4))" "$$TS" \
			> "$$LOGS/ResponseBuckets/runSummary.json"; \
	fi; \
	cp "$(SELF_DIR)/tests/stt-openapi.yaml" "$$OUT/stt-openapi.yaml"; \
	printf 'RESTler Evidence Package\n========================\nTool:     RESTler $(RESTLER_VERSION)\nDate:     %s\nTarget:   https://$(STT_RESTLER_IP):$(STT_RESTLER_PORT)\nBudget:   $(RESTLER_BUDGET) hours\n\nCommand:\n  make restler-stt STT_RESTLER_IP=$(STT_RESTLER_IP) STT_RESTLER_PORT=$(STT_RESTLER_PORT) RESTLER_BUDGET=$(RESTLER_BUDGET)\n\nSettings (tests/restler-settings.json):\n  no_ssl: false                    TLS enabled\n  disable_cert_validation: true    self-signed cert accepted\n  time_budget: $(RESTLER_BUDGET)h, max_combinations: 20, request_throttle_ms: 200\n\nGrammar:    auto-compiled from stt-openapi.yaml (no manual edits)\nDictionary: auto-generated (no manual edits)\nCheckers:   default (PayloadBodyChecker, InvalidValueChecker)\n' \
		"$$(date -u '+%Y-%m-%d %H:%M UTC')" > "$$OUT/README.txt"; \
	rm -f "$(RESTLER_EVIDENCE_ZIP)"; \
	cd "$(WORK_DIR)" && zip -r "restler-evidence.zip" "restler-evidence/"; \
	echo ""; \
	echo ">> ZIP ready: $(RESTLER_EVIDENCE_ZIP)"; \
	unzip -l "$(RESTLER_EVIDENCE_ZIP)" | awk '/---/{found=1; next} found && /---/{exit} found{print "  " $$4}'


models-download:
	echo "Downloading all supported models (this may take a while)..."; \
	MODELS=$$(cat $(MODELS_SUPPORTED_FILE)|yq --compact-output '[.[].name]'); \
	for i in $$(seq 1 $(MODELS_RETRIES)); do \
		CODE=$$(curl -s -o /dev/null -w '%{http_code}' \
			'http://localhost:7860/api/v1/models/download' -X POST \
			-H 'Content-Type: application/json' \
			--data-raw "{\"names\":$$MODELS}"); \
		case "$$CODE" in \
			2[0-9][0-9]) exit 0;; \
			409)         exit 0;;  # 409 Conflict is expected if request is executed while models are already being downloaded \
			*)           echo "  [$$i/$(MODELS_RETRIES)] HTTP $$CODE — retrying...";; \
		esac; \
		[ $$i -eq $(MODELS_RETRIES) ] && break; \
		sleep 5; \
    done; \

models-status:
	@for i in $$(seq 1 $(MODELS_RETRIES)); do \
		STATUS=$$(curl -sf http://localhost:7860/api/v1/models | jq -c '[.[] | {display_name, install_status}]'); \
		if [ -z "$$STATUS" ]; then \
			echo "  [$$i/$(MODELS_RETRIES)] API not reachable yet..."; \
		else \
			echo "$$STATUS" | jq -r '.[] | "  \(.display_name)\t\(.install_status)"' | column -t -s "$$(printf '\t')"; \
			if echo "$$STATUS" | jq -e 'length > 0 and all(.[]; .install_status == "installed")' >/dev/null; then \
				echo "✓ All models installed"; \
				exit 0; \
			fi; \
		fi; \
		[ $$i -eq $(MODELS_RETRIES) ] && break; \
		echo "  [$$i/$(MODELS_RETRIES)] not all installed yet, retrying in $(MODELS_STATUS_INTERVAL)s..."; \
		sleep $(MODELS_STATUS_INTERVAL); \
	done; \
	echo "✗ Timeout: not all models installed after $$(( $(MODELS_RETRIES) * $(MODELS_STATUS_INTERVAL) ))s"; \
	exit 1

models-license:
	@if [ -f $(MODELS_LICENSE_FILE) ]; then \
		echo "✓ License already accepted ($(MODELS_LICENSE_FILE))"; \
		exit 0; \
	fi; \
	echo "  By proceeding, you agree to license agreements for following models:  $$(cat $(MODELS_SUPPORTED_FILE)|yq '[.[].display_name] |join (",")')"; \
	printf "  Do you accept the license agreements? [y/N] "; \
	read ans; \
	case "$$ans" in \
		[Yy]|[Yy][Ee][Ss]) \
			touch $(MODELS_LICENSE_FILE); \
			;; \
		*) \
			echo "✗ License not accepted — aborting."; \
			exit 1; \
			;; \
	esac
