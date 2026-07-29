# SPDX-FileCopyrightText: Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

# ==============================================================================
# Live Video Alert Agent - Makefile
# ==============================================================================
#
# Build, deploy, and manage the Live Video Alert Agent Docker stack.
# This application includes:
#   - live-video-alert-agent 
#   - OVMS VLM / LLM inference servers (OpenVINO pre-built images)
#   - metrics-manager (Intel pre-built image)
#
# Quick Start:
#   make help           - Show all available commands
#   make build          - Build the live-video-alert-agent Docker image
#   make deploy         - Pull images and start the stack
#   make deploy-build-from-source   - Build app image then deploy
#   make clean          - Stop all containers
#   make clean-data     - Stop containers and delete all volumes
#
# Configuration:
#   REGISTRY_URL        - Image registry prefix (default: intel)
#   TAG                 - App image tag (default: latest)
#   DEVICE              - GPU (default), CPU, or NPU for VLM/LLM inference
#   PORT                - App port (default: 9000)
#
# Required (must be set before deploy):
#   HF_TOKEN            - HuggingFace token (needed for initial model download)
#
# ==============================================================================

SHELL := bash
.SHELLFLAGS := -eu -o pipefail -c
.ONESHELL:
.DEFAULT_GOAL := help

# ==============================================================================
# Project Configuration
# ==============================================================================

SERVICE_NAME := live-video-alert-agent
VERSION ?= latest

# ==============================================================================
# Image Configuration
# ==============================================================================

# Registry and tag defaults
REGISTRY_URL ?= intel
PROJECT_NAME ?=
TAG ?= latest

# Compute REGISTRY the same way as the compose file: REGISTRY_URL/PROJECT_NAME/
REGISTRY := $(if $(REGISTRY_URL),$(REGISTRY_URL)/)$(if $(PROJECT_NAME),$(PROJECT_NAME)/)

# ==============================================================================
# Component Definitions
# ==============================================================================

# First-party app component (built from local Dockerfile)
COMPONENTS := live-video-alert-agent
DOCKER_DIR := docker

# Intel platform images (pre-built, fixed release tags)
METRICS_MANAGER_IMAGE := intel/metrics-manager:2026.1.0
PLATFORM_IMAGES       := $(METRICS_MANAGER_IMAGE)

# ==============================================================================
# Deployment Configuration
# ==============================================================================

# Target device for VLM / LLM inference (GPU is the recommended default)
DEVICE ?= GPU
NPU_DEVICE_PATH ?= /dev/accel/accel0

# Agentic dispatch (true = ADK + local OVMS LLM, false = rule-based)
USE_ADK ?= true

# RTSP stream URL — optional at deploy time; can be configured in the UI
RTSP_URL ?=

# HuggingFace token (required for initial model download)
HF_TOKEN ?=

# Application ports
PORT         ?= 9000


# VLM / LLM model configuration
OVMS_SOURCE_MODEL ?= OpenVINO/Phi-3.5-vision-instruct-int4-ov
MODEL_NAME        ?= Phi-3.5-vision
LLM_MODEL         ?= OpenVINO/Phi-4-mini-instruct-int4-ov

# Capture and logging
LOG_LEVEL   ?= DEBUG

# Optional action tools
WEBHOOK_URL     ?=
WEBHOOK_SECRET  ?=
MQTT_BROKER     ?= "192.168.1.20"
MQTT_PORT       ?= 1883
MQTT_USERNAME   ?=
MQTT_PASSWORD   ?=
MQTT_BASE_TOPIC ?= alerts/live-video

# MCP (Model Context Protocol)
MCP_ENABLED ?= true

# GPU render device GID — auto-detect from host, fall back to 992 if absent
RENDER_DEVICE_GID ?= $(shell stat -c "%g" /dev/dri/render* 2>/dev/null | head -n 1 || echo 992)

# Build arg — set to true to embed copyleft source packages in image
COPYLEFT_SOURCES ?= false

# ==============================================================================
# Internal Variables
# ==============================================================================

DEVICE_UPPER := $(shell echo $(DEVICE) | tr '[:lower:]' '[:upper:]')

# Compose profile: activate adk-llm when USE_ADK=true to bring up ovms-llm
ifeq ($(USE_ADK),true)
  COMPOSE_PROFILE_FLAGS := --profile adk-llm
else
  COMPOSE_PROFILE_FLAGS :=
endif

COMPOSE_PROJECT_FLAGS :=
COMPOSE_FILE_FLAGS := -f $(DOCKER_DIR)/docker-compose.yml
ifeq ($(DEVICE_UPPER),NPU)
  COMPOSE_FILE_FLAGS += -f $(DOCKER_DIR)/docker-compose.npu.yml
endif

# ==============================================================================
# Environment Export Block
# ==============================================================================

define EXPORT_RUNTIME_ENV
	export REGISTRY="$${REGISTRY:-$(REGISTRY)}"
	export REGISTRY_URL="$${REGISTRY_URL:-$(REGISTRY_URL)}"
	export TAG="$${TAG:-$(TAG)}"
	export DEVICE="$${DEVICE:-$(DEVICE_UPPER)}"
	export VLM_TARGET_DEVICE="$${VLM_TARGET_DEVICE:-$(DEVICE_UPPER)}"
	export LLM_TARGET_DEVICE="$${LLM_TARGET_DEVICE:-$(DEVICE_UPPER)}"
	export OVMS_TARGET_DEVICE="$${OVMS_TARGET_DEVICE:-$(DEVICE_UPPER)}"
	export NPU_DEVICE_PATH="$${NPU_DEVICE_PATH:-$(NPU_DEVICE_PATH)}"
	export RENDER_DEVICE_GID="$${RENDER_DEVICE_GID:-$(RENDER_DEVICE_GID)}"
	export USE_ADK="$${USE_ADK:-$(USE_ADK)}"
	export RTSP_URL="$${RTSP_URL:-$(RTSP_URL)}"
	export HF_TOKEN="$${HF_TOKEN:-$(HF_TOKEN)}"
	export PORT="$${PORT:-$(PORT)}"
	export OVMS_SOURCE_MODEL="$${OVMS_SOURCE_MODEL:-$(OVMS_SOURCE_MODEL)}"
	export MODEL_NAME="$${MODEL_NAME:-$(MODEL_NAME)}"
	export LLM_MODEL="$${LLM_MODEL:-$(LLM_MODEL)}"
	export LOG_LEVEL="$${LOG_LEVEL:-$(LOG_LEVEL)}"
	export WEBHOOK_URL="$${WEBHOOK_URL:-}"
	export WEBHOOK_SECRET="$${WEBHOOK_SECRET:-}"
	export MQTT_BROKER="$${MQTT_BROKER:-}"
	export MQTT_PORT="$${MQTT_PORT:-$(MQTT_PORT)}"
	export MQTT_USERNAME="$${MQTT_USERNAME:-}"
	export MQTT_PASSWORD="$${MQTT_PASSWORD:-}"
	export MQTT_BASE_TOPIC="$${MQTT_BASE_TOPIC:-$(MQTT_BASE_TOPIC)}"
	export MCP_ENABLED="$${MCP_ENABLED:-$(MCP_ENABLED)}"
	export PYTHON_KEYRING_BACKEND="keyring.backends.null.Keyring"
endef


# ==============================================================================
# Phony Targets
# ==============================================================================

.PHONY: help validate inspect validate-env validate-device \
        build \
        deploy deploy-build-from-source \
        clean clean-data \
        ps status logs \
        shellcheck bandit-scan clamav-scan codeql-scan \
        trivy-scan trivy-scan-image trivy-scan-fs trivy-scan-config \
        gitleaks-scan \
        get-service-name get-component-names get-image-tags get-context-dirs \
        get-scan-matrix-json


# ==============================================================================
# Validation Targets
# ==============================================================================

validate: inspect validate-env validate-device

inspect:
	@echo "══════════════════════════════════════════════════"
	@echo "🏥 Inspect - Host Readiness Check"
	@echo "══════════════════════════════════════════════════"
	@echo ""
	@ERRORS=0; \
	echo "Docker:"; \
	echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"; \
	if command -v docker >/dev/null 2>&1; then \
		echo "  ✅ docker:          $$(docker --version | head -1)"; \
	else \
		echo "  ❌ docker:          Not found"; ERRORS=$$((ERRORS+1)); \
	fi; \
	if docker compose version >/dev/null 2>&1; then \
		echo "  ✅ docker compose:  $$(docker compose version --short)"; \
	else \
		echo "  ❌ docker compose:  Not found"; ERRORS=$$((ERRORS+1)); \
	fi; \
	if docker info >/dev/null 2>&1; then \
		echo "  ✅ docker daemon:   Running"; \
	else \
		echo "  ❌ docker daemon:   Not reachable (permission denied or not running)"; ERRORS=$$((ERRORS+1)); \
	fi; \
	echo ""; \
	echo "Host OS:"; \
	echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"; \
	echo "  OS:               $$(uname -s) $$(uname -r)"; \
	echo "  Arch:             $$(uname -m)"; \
	echo ""; \
	echo "Device Nodes:"; \
	echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"; \
	if [ -d /dev/dri ] && [ "$$(ls -A /dev/dri 2>/dev/null)" ]; then \
		echo "  ✅ /dev/dri:        Available (GPU acceleration possible)"; \
	else \
		echo "  ⚠️  /dev/dri:        Not found (CPU-only mode)"; \
	fi; \
	echo ""; \
	echo "Required Environment:"; \
	echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"; \
	for var in HF_TOKEN; do \
		if [ -n "$${!var:-}" ]; then \
			echo "  ✅ $$var: Set"; \
		else \
			echo "  ❌ $$var: Not set"; ERRORS=$$((ERRORS+1)); \
		fi; \
	done; \
	echo ""; \
	if [ $$ERRORS -gt 0 ]; then \
		echo "❌ $$ERRORS issue(s) found. Fix before deploying."; \
		exit 1; \
	else \
		echo "✅ All checks passed. Ready to deploy."; \
	fi


validate-env:
	@ERRORS=0; \
	for var in HF_TOKEN; do \
		if [ -z "$${!var:-}" ]; then \
			echo "❌ Required variable $$var is not set."; ERRORS=$$((ERRORS+1)); \
		fi; \
	done; \
	if [ $$ERRORS -gt 0 ]; then \
		echo ""; \
		echo "Set required variables before deploying:"; \
		echo "  export HF_TOKEN=<your-huggingface-token>"; \
		exit 1; \
	fi

validate-device:
	@if [ "$(DEVICE_UPPER)" != "CPU" ] && [ "$(DEVICE_UPPER)" != "GPU" ] && [ "$(DEVICE_UPPER)" != "NPU" ]; then \
		echo "❌ Invalid DEVICE '$(DEVICE_UPPER)'. Use CPU, GPU, or NPU."; \
		exit 1; \
	fi; \
	if [ "$(DEVICE_UPPER)" = "GPU" ]; then \
		if [ ! -d /dev/dri ] || [ -z "$$(ls -A /dev/dri 2>/dev/null)" ]; then \
			echo "❌ GPU mode requires /dev/dri but it is not available."; \
			exit 1; \
		fi; \
	fi; \
	if [ "$(DEVICE_UPPER)" = "NPU" ]; then \
		if [ ! -c "$(NPU_DEVICE_PATH)" ]; then \
			echo "❌ NPU mode requires device node $(NPU_DEVICE_PATH), but it is not available."; \
			exit 1; \
		fi; \
	fi


# ==============================================================================
# Build Target
# ==============================================================================

build:
	@echo "══════════════════════════════════════════════════"
	@echo "🔨 Build - $(SERVICE_NAME):$(TAG)"
	@echo "══════════════════════════════════════════════════"
	@echo ""
	@echo "  Image:            $(REGISTRY)$(SERVICE_NAME):$(TAG)"
	@echo "  COPYLEFT_SOURCES: $(COPYLEFT_SOURCES)"
	@echo ""
	docker compose $(COMPOSE_PROJECT_FLAGS) $(COMPOSE_FILE_FLAGS) build --build-arg COPYLEFT_SOURCES=$(COPYLEFT_SOURCES)
	@echo ""
	@echo "✅ Build complete: $(REGISTRY)$(SERVICE_NAME):$(TAG)"


# ==============================================================================
# Deployments
# ==============================================================================

deploy: validate
	@echo "══════════════════════════════════════════════════"
	@echo "🚀 Deploy - $(SERVICE_NAME)"
	@echo "══════════════════════════════════════════════════"
	@echo ""
	@echo "Configuration:"
	@echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
	@echo "  DEVICE:             $(DEVICE_UPPER)"
	@echo "  REGISTRY_URL:       $(REGISTRY_URL)"
	@echo "  TAG:                $(TAG)"
	@echo "  PORT:               $(PORT)"
	@echo "  USE_ADK:            $(USE_ADK)"
	@echo "  OVMS_SOURCE_MODEL:  $(OVMS_SOURCE_MODEL)"
	@echo "  LLM_MODEL:          $(LLM_MODEL)"
	@echo "  LOG_LEVEL:          $(LOG_LEVEL)"
	@echo ""
	@echo "→ Starting stack (ADK profile: $(if $(filter true,$(USE_ADK)),active,inactive))..."
	@bash -c '\
		$(EXPORT_RUNTIME_ENV)
		docker compose $(COMPOSE_PROJECT_FLAGS) $(COMPOSE_FILE_FLAGS) $(COMPOSE_PROFILE_FLAGS) up --detach --remove-orphans
	'
	@echo ""
	@echo "✅ Stack is up. Dashboard: http://localhost:$(PORT)"
	@echo "   First run downloads the VLM model (~2 GB; may take 5-10 min)."

deploy-build-from-source: build
	@$(MAKE) -C $(CURDIR) deploy


# ==============================================================================
# Status / Logs Targets
# ==============================================================================

ps:
	@bash -c '\
		$(EXPORT_RUNTIME_ENV)
		docker compose $(COMPOSE_PROJECT_FLAGS) $(COMPOSE_FILE_FLAGS) $(COMPOSE_PROFILE_FLAGS) ps
	'

status: ps

logs:
	@bash -c '\
		$(EXPORT_RUNTIME_ENV)
		docker compose $(COMPOSE_PROJECT_FLAGS) $(COMPOSE_FILE_FLAGS) $(COMPOSE_PROFILE_FLAGS) logs -f $(SERVICE)
	'

SERVICE ?=


# ==============================================================================
# Cleaning
# ==============================================================================

clean:
	@echo "Stopping all containers for the Live Video Alert Agent stack (volumes are preserved)"
	@bash -c '\
		$(EXPORT_RUNTIME_ENV)
		docker compose $(COMPOSE_PROJECT_FLAGS) $(COMPOSE_FILE_FLAGS) $(COMPOSE_PROFILE_FLAGS) down --remove-orphans
	'

clean-data:
	@echo "Stopping all containers and deleting volumes for the Live Video Alert Agent stack"
	@bash -c '\
		$(EXPORT_RUNTIME_ENV)
		docker compose $(COMPOSE_PROJECT_FLAGS) $(COMPOSE_FILE_FLAGS) $(COMPOSE_PROFILE_FLAGS) down --volumes --remove-orphans
	'
	docker system prune -a --volumes -f
	docker compose $(COMPOSE_PROJECT_FLAGS) $(COMPOSE_FILE_FLAGS) down -v


# ==============================================================================
# Code Quality Targets
# ==============================================================================

shellcheck:
	@echo "══════════════════════════════════════════════════"
	@echo "🔍 ShellCheck - Linting Shell Scripts"
	@echo "══════════════════════════════════════════════════"
	@if ! command -v shellcheck >/dev/null 2>&1; then \
		echo "❌ ShellCheck is not installed. Please install it to run this check."; \
		exit 1; \
	fi
	@mkdir -p security-results
	@find . -type f \( -name "*.sh" -o -name "*.bash" \) -print0 | xargs -0 -r \
		shellcheck --format=json > security-results/shellcheck-report-$(SERVICE_NAME).json 2>/dev/null || true
	@echo "✅ Report: security-results/shellcheck-report-$(SERVICE_NAME).json"


bandit-scan:
	@echo "🔐 Running Bandit Security Scan..."
	@mkdir -p security-results
	@python3 -m venv bandit-venv && \
	source bandit-venv/bin/activate && \
	pip install --upgrade pip && \
	pip install bandit[toml] && \
	CONFIG_OPT=""; \
	if [ -f "pyproject.toml" ]; then CONFIG_OPT="-c pyproject.toml"; fi; \
	echo "📝 Generating TXT Report (matches CI)..." && \
	bandit $$CONFIG_OPT --severity-level high --confidence-level high -r . \
		-f txt -o security-results/bandit-report-$(SERVICE_NAME).txt || true && \
	echo "📊 Generating JSON Report..." && \
	bandit $$CONFIG_OPT --severity-level high --confidence-level high -r . \
		-f json -o security-results/bandit-report-$(SERVICE_NAME).json || true && \
	echo "🌐 Generating HTML Report..." && \
	bandit $$CONFIG_OPT --severity-level high --confidence-level high -r . \
		-f html -o security-results/bandit-report-$(SERVICE_NAME).html || true && \
	deactivate && \
	rm -rf bandit-venv
	@echo "✅ Bandit scan complete. Check security-results/ for txt, json, and html reports."


clamav-scan:
	@echo "🦠 Running ClamAV Antivirus Scan..."
	@if ! command -v clamscan >/dev/null 2>&1; then \
		echo "❌ ClamAV is not installed. Please install it to run this check."; \
		exit 1; \
	fi
	@mkdir -p security-results
	@clamscan -r . \
		--exclude-dir=.git \
		--exclude-dir=venv \
		--exclude-dir=.venv \
		> security-results/clamav-$(SERVICE_NAME)-$$(date +%Y%m%d-%H%M%S).txt 2>&1 || true
	@echo "✅ ClamAV scan complete: security-results/clamav-*"


codeql-scan:
	@echo "🛡️  Running CodeQL Security Analysis..."
	@if ! command -v codeql >/dev/null 2>&1; then \
		echo ""; \
		echo "❌ CodeQL CLI is not installed."; \
		echo "Install: https://github.com/github/codeql-cli-binaries/releases"; \
		echo ""; \
		exit 1; \
	fi

	@mkdir -p security-results
	@echo ""

	@# --- Download / verify required query packs ---
	@echo "→ Checking CodeQL Python query pack..."
	@if ! codeql resolve qlpacks 2>/dev/null | grep -q 'codeql/python-queries'; then \
		echo "  ⬇️  Downloading codeql/python-queries..."; \
		codeql pack download codeql/python-queries; \
	else \
		echo "  ✅ codeql/python-queries already available."; \
	fi

	@echo "→ Checking CodeQL JavaScript/TypeScript query pack..."
	@if ! codeql resolve qlpacks 2>/dev/null | grep -q 'codeql/javascript-queries'; then \
		echo "  ⬇️  Downloading codeql/javascript-queries..."; \
		codeql pack download codeql/javascript-queries; \
	else \
		echo "  ✅ codeql/javascript-queries already available."; \
	fi
	@echo ""

	@# --- Python: LVAA ---
	@echo "→ Creating CodeQL database for Python (LVAA)..."
	@codeql database create security-results/codeql-db-python-lvaa \
		--language=python \
		--source-root=src \
		--build-mode=none \
		--overwrite 2>&1 | tail -5

	@echo "→ Running CodeQL analysis on LVAA (SARIF)..."
	@codeql database analyze security-results/codeql-db-python-lvaa \
		codeql/python-queries \
		--format=sarif-latest --sarif-add-snippets \
		--output=security-results/codeql-python-lvaa.sarif || true
	@echo "→ Running CodeQL analysis on LVAA (CSV)..."
	@codeql database analyze security-results/codeql-db-python-lvaa \
		codeql/python-queries \
		--format=csv \
		--output=security-results/codeql-python-lvaa.csv || true
	@echo "✅ Python (LVAA) analysis complete."
	@echo ""

# ==============================================================================
# Security Scanning
# ==============================================================================

trivy-scan: trivy-scan-fs trivy-scan-image trivy-scan-config
	@echo "📦 Creating security scan archive..."
	@cd security-results && zip -r trivy-scan-$(SERVICE_NAME)-$$(date +%Y%m%d-%H%M%S).zip trivy-* 2>/dev/null || true
	@echo "✅ All Trivy scans complete. Reports: security-results/trivy-*"


# Trivy HTML template — auto-detect installed copy or download from upstream
TRIVY_HTML_TPL_URL   := https://raw.githubusercontent.com/aquasecurity/trivy/main/pkg/report/templates/html.tpl
TRIVY_HTML_TPL_LOCAL := security-results/.trivy-html.tpl

define ENSURE_TRIVY_HTML_TPL
	if [ -f "/usr/local/share/trivy/templates/html.tpl" ]; then \
		TRIVY_HTML_TPL="/usr/local/share/trivy/templates/html.tpl"; \
	elif [ -f "/usr/share/trivy/templates/html.tpl" ]; then \
		TRIVY_HTML_TPL="/usr/share/trivy/templates/html.tpl"; \
	else \
		echo "  → Trivy HTML template not found locally, downloading..."; \
		mkdir -p security-results; \
		curl -sSL -o $(TRIVY_HTML_TPL_LOCAL) $(TRIVY_HTML_TPL_URL) || \
			wget -qO $(TRIVY_HTML_TPL_LOCAL) $(TRIVY_HTML_TPL_URL) || \
			{ echo "  ⚠️  Could not download HTML template. HTML reports will be skipped."; TRIVY_HTML_TPL=""; }; \
		TRIVY_HTML_TPL="$(TRIVY_HTML_TPL_LOCAL)"; \
	fi
endef


# trivy-scan-image: pull-and-scan the first-party app image plus Intel platform images.
# Strategy: pull exactly what runs in production, then audit the supply chain.
trivy-scan-image:
	@echo "🔍 Running Trivy Image Scans (pull-and-scan)..."
	@mkdir -p security-results
	@$(ENSURE_TRIVY_HTML_TPL); \
	REGISTRY="$(REGISTRY)"; \
	for comp in $(COMPONENTS); do \
		IMAGE="$${REGISTRY}$${comp}:$(TAG)"; \
		echo ""; \
		echo "→ Pulling $${IMAGE}..."; \
		docker pull "$${IMAGE}" || { echo "⚠️  Pull failed for $${IMAGE}, skipping."; continue; }; \
		echo "→ Scanning $${IMAGE}..."; \
		SAFE="$$(echo "$${comp}" | tr '/' '-')"; \
		trivy image --severity HIGH,CRITICAL --ignore-unfixed --format json \
			--output "security-results/trivy-image-$${SAFE}.json" \
			"$${IMAGE}" || true; \
		trivy image --format spdx-json \
			--output "security-results/trivy-image-$${SAFE}.spdx.json" \
			"$${IMAGE}" || true; \
		if [ -n "$$TRIVY_HTML_TPL" ] && [ -f "$$TRIVY_HTML_TPL" ]; then \
			trivy image --severity HIGH,CRITICAL --ignore-unfixed \
				--format template --template "@$$TRIVY_HTML_TPL" \
				--output "security-results/trivy-image-$${SAFE}.html" \
				"$${IMAGE}" || true; \
		fi; \
	done; \
	for img in $(PLATFORM_IMAGES); do \
		echo ""; \
		echo "→ Pulling $${img}..."; \
		docker pull "$${img}" || { echo "⚠️  Pull failed for $${img}, skipping."; continue; }; \
		echo "→ Scanning $${img}..."; \
		SAFE="$$(echo "$${img}" | tr '/.:' '---')"; \
		trivy image --severity HIGH,CRITICAL --ignore-unfixed --format json \
			--output "security-results/trivy-image-$${SAFE}.json" \
			"$${img}" || true; \
		trivy image --format spdx-json \
			--output "security-results/trivy-image-$${SAFE}.spdx.json" \
			"$${img}" || true; \
		if [ -n "$$TRIVY_HTML_TPL" ] && [ -f "$$TRIVY_HTML_TPL" ]; then \
			trivy image --severity HIGH,CRITICAL --ignore-unfixed \
				--format template --template "@$$TRIVY_HTML_TPL" \
				--output "security-results/trivy-image-$${SAFE}.html" \
				"$${img}" || true; \
		fi; \
	done
	@echo ""
	@echo "✅ Image scans complete: security-results/trivy-image-*.{json,spdx.json,html}"


trivy-scan-fs:
	@echo "🔍 Running Trivy Filesystem Scan (src/, pyproject.toml)..."
	@mkdir -p security-results
	@$(ENSURE_TRIVY_HTML_TPL); \
	trivy fs --severity HIGH,CRITICAL --ignore-unfixed --format json \
		--output "security-results/trivy-fs-$(SERVICE_NAME).json" \
		src/ pyproject.toml || true; \
	trivy fs --format spdx-json \
		--output "security-results/trivy-fs-$(SERVICE_NAME).spdx.json" \
		src/ pyproject.toml || true; \
	if [ -n "$$TRIVY_HTML_TPL" ] && [ -f "$$TRIVY_HTML_TPL" ]; then \
		trivy fs --severity HIGH,CRITICAL --ignore-unfixed \
			--format template --template "@$$TRIVY_HTML_TPL" \
			--output "security-results/trivy-fs-$(SERVICE_NAME).html" \
			src/ pyproject.toml || true; \
	fi
	@echo "✅ Filesystem scan complete: security-results/trivy-fs-*"


trivy-scan-config:
	@echo "🔍 Running Trivy Config Scans..."
	@mkdir -p security-results
	@$(ENSURE_TRIVY_HTML_TPL); \
		echo "  → Scanning Dockerfile..."; \
		trivy config --severity HIGH,CRITICAL --format json \
			--output security-results/trivy-config-$(SERVICE_NAME).json \
			--file-patterns "dockerfile:Dockerfile" . || true; \
		if [ -n "$$TRIVY_HTML_TPL" ] && [ -f "$$TRIVY_HTML_TPL" ]; then \
			trivy config --severity HIGH,CRITICAL --format template \
				--template "@$$TRIVY_HTML_TPL" \
				--output security-results/trivy-config-$(SERVICE_NAME).html \
				--file-patterns "dockerfile:Dockerfile" . || true; \
		fi; 
	@echo "✅ Config scans complete: security-results/trivy-config-*.{json,html}"

gitleaks-scan:
	@echo "🔑 Running Gitleaks Secrets Scan..."
	@mkdir -p security-results
	@gitleaks dir . -v \
		-r security-results/gitleaks-$(SERVICE_NAME)-$$(date +%Y%m%d-%H%M%S).json || true
	@echo "✅ Gitleaks scan complete: security-results/gitleaks-*"


# ==============================================================================
# CI/CD Targets
# ==============================================================================

get-service-name:
	@echo $(SERVICE_NAME)

get-component-names:
	@echo "$(COMPONENTS)"

get-image-tags:
	@$(foreach component,$(COMPONENTS), echo "$(SERVICE_NAME)-$(component):$(VERSION)";)

get-context-dirs:
	@$(foreach component,$(COMPONENTS), echo ". ";)

get-scan-matrix-json:
	@printf '{"include":['
	@$(foreach component,$(COMPONENTS), \
		$(eval COMMA := $(if $(findstring $(component),$(firstword $(COMPONENTS))),,',')) \
		printf '%s' '$(COMMA){"name":"$(component)","image":"$(REGISTRY)$(component):$(TAG)","context":".","dockerfile":"Dockerfile"}'; \
	)
	@printf ']}\n'


# ==============================================================================
# Help
# ==============================================================================

help:
	@echo ""
	@echo "╔══════════════════════════════════════════════════════════════════╗"
	@echo "║          Live Video Alert Agent - Makefile                       ║"
	@echo "╚══════════════════════════════════════════════════════════════════╝"
	@echo ""
	@echo "Usage: make <target> [VAR=value ...]"
	@echo ""
	@echo "PRE-FLIGHT"
	@echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
	@echo "  validate           Run all pre-flight checks"
	@echo ""
	@echo "BUILD"
	@echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
	@echo "  build              Build the live-video-alert-agent Docker image"
	@echo ""
	@echo "DEPLOYMENT"
	@echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
	@echo "  deploy             Pull images and start the stack"
	@echo "  deploy-build-from-source       Build app image then deploy"
	@echo "  clean              Stop containers (volumes preserved)"
	@echo "  clean-data         Stop containers and delete all volumes"
	@echo ""
	@echo "STATUS & LOGS"
	@echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
	@echo "  ps / status        Show running containers"
	@echo "  logs               Follow logs (SERVICE=<name> to filter)"
	@echo ""
	@echo "CODE QUALITY & SECURITY"
	@echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
	@echo "  shellcheck         Lint shell scripts"
	@echo "  bandit-scan        Python security static analysis (src/)"
	@echo "  clamav-scan        Antivirus scan"
	@echo "  trivy-scan         Run all Trivy scans (image + fs + config)"
	@echo "  trivy-scan-image   Pull and scan first-party and platform images"
	@echo "  trivy-scan-fs      Scan Python source + dependencies (src/, pyproject.toml)"
	@echo "  trivy-scan-config  Scan Dockerfile and docker-compose.yml"
	@echo "  gitleaks-scan      Run Gitleaks secrets scan"
	@echo ""
	@echo "CI/CD METADATA"
	@echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
	@echo "  get-service-name       Print service name"
	@echo "  get-component-names    Print component list"
	@echo "  get-image-tags         Print all image:tag references"
	@echo "  get-context-dirs       Print build context directory"
	@echo "  get-scan-matrix-json   Print JSON matrix for CI scanning"
	@echo ""
	@echo "CONFIGURATION VARIABLES"
	@echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
	@echo "  REGISTRY_URL        Image registry prefix (default: intel)"
	@echo "  TAG                 App image tag (default: latest)"
	@echo "  DEVICE              GPU (default) or CPU for VLM/LLM inference"
	@echo "  HF_TOKEN            HuggingFace token (required for model download)"
	@echo "  RTSP_URL            RTSP stream URL (optional; configure in UI)"
	@echo "  PORT                App port (default: 9000)"
	@echo "  USE_ADK             true (default) or false — agentic dispatch mode"
	@echo "  OVMS_SOURCE_MODEL   VLM model repo (default: OpenVINO/Phi-3.5-vision-instruct-int4-ov)"
	@echo "  LLM_MODEL           LLM model repo (default: OpenVINO/Phi-4-mini-instruct-int4-ov)"
	@echo "  LOG_LEVEL           Log verbosity (default: INFO)"
	@echo "  COPYLEFT_SOURCES    Include copyleft sources in image (default: false)"
	@echo ""
	@echo "EXAMPLES"
	@echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
	@echo "  # Deploy with pre-built images (GPU)"
	@echo "  HF_TOKEN=<token> make deploy"
	@echo ""
	@echo "  # Build from source then deploy"
	@echo "  HF_TOKEN=<token> make deploy-build"
	@echo ""
	@echo "  # Deploy on CPU (slower inference)"
	@echo "  DEVICE=CPU HF_TOKEN=<token> make deploy"
	@echo ""
	@echo "  # Deploy with a specific RTSP stream"
	@echo "  HF_TOKEN=<token> RTSP_URL=rtsp://192.168.1.10:554/stream make deploy"
	@echo ""
	@echo "  # Deploy without ADK (rule-based mode, no LLM service)"
	@echo "  HF_TOKEN=<token> USE_ADK=false make deploy"
	@echo ""
	@echo "  # Check host readiness"
	@echo "  make validate"
	@echo ""
