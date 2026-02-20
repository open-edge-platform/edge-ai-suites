# SPDX-FileCopyrightText: Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

# ==============================================================================
# Smart Traffic Intersection Agent - Makefile
# ==============================================================================
#
# Build, test, deploy, and manage the Smart Traffic Intersection Agent.
# Python application with FastAPI backend and Gradio UI for real-time
# traffic intersection analytics powered by VLM inference.
#
# Quick Start:
#   make help              - Show all available commands
#   make build             - Build the Docker image
#   make deploy            - Deploy the application
#   make deploy-build      - Build and deploy
#   make undeploy          - Stop the application
#
# Configuration:
#   TAG                         - Image tag (default: latest)
#   REGISTRY                    - Image registry (default: empty)
#   LOG_LEVEL                   - Logging level (default: INFO)
#   VLM_MODEL_NAME              - VLM model (default: microsoft/Phi-3.5-vision-instruct)
#   VLM_DEVICE                  - Inference device (default: CPU)
#
# ==============================================================================

SHELL := bash -eu -o pipefail
.DEFAULT_GOAL := help

# ==============================================================================
# Project Configuration
# ==============================================================================

SERVICE_NAME := smart-traffic-intersection-agent
VERSION ?= latest
PYTHON_VERSION := 3.11

# ==============================================================================
# Pre-built Image Configuration
# ==============================================================================

DEFAULT_REGISTRY :=
DEFAULT_TAG := latest

# ==============================================================================
# Component Configuration
# ==============================================================================

COMPONENTS := traffic-agent
TEST_COMPONENTS := traffic-agent

# Build context and Dockerfile
traffic-agent_CONTEXT_DIR := ./src
traffic-agent_DOCKERFILE := ./src/Dockerfile
traffic-agent_LANG := python

# VLM dependency (pre-built, not built by this Makefile)
VLM_IMAGE := intel/vlm-openvino-serving:1.3.2

# ==============================================================================
# Deployment Configuration
# ==============================================================================

REGISTRY ?= $(DEFAULT_REGISTRY)
TAG ?= $(DEFAULT_TAG)
LOG_LEVEL ?= INFO

# Docker Compose
COMPOSE_FILE := docker/agent-compose.yaml
PROJECT_NAME ?= trafficagent

# VLM Configuration
VLM_MODEL_NAME ?= microsoft/Phi-3.5-vision-instruct
VLM_DEVICE ?= CPU
VLM_COMPRESSION_WEIGHT_FORMAT ?= int8
VLM_SEED ?= 42
VLM_WORKERS ?= 1
VLM_LOG_LEVEL ?= info
VLM_MAX_COMPLETION_TOKENS ?= 1500

# Traffic Agent Configuration
REFRESH_INTERVAL ?= 15
HIGH_DENSITY_THRESHOLD ?= 10
WEATHER_MOCK ?= false

# MQTT Configuration
MQTT_HOST ?= broker.scenescape.intel.com
MQTT_PORT ?= 1883

# ==============================================================================
# Internal Variables
# ==============================================================================

TEST_TARGETS := $(addprefix test-,$(TEST_COMPONENTS))

.PHONY: all build test clean help list \
        deploy deploy-build undeploy restart restart-agent restart-deps \
        clean-all clean-all-keep-models \
        shellcheck pylint ruff \
        trivy-scan trivy-scan-fs trivy-scan-image trivy-scan-config \
        clamav-scan bandit-scan gitleaks-scan codeql-scan \
        $(TEST_TARGETS) \
        get-service-name get-component-names get-image-tags get-context-dirs \
        get-python-version get-scan-matrix-json

# ==============================================================================
# Build Targets
# ==============================================================================

build:
	@echo "📦 Building $(SERVICE_NAME)..."
	@docker build \
		-t $(SERVICE_NAME):$(VERSION) \
		-f $(traffic-agent_DOCKERFILE) $(traffic-agent_CONTEXT_DIR)
	@echo "✅ Build complete: $(SERVICE_NAME):$(VERSION)"

# ==============================================================================
# Test Targets
# ==============================================================================

test: $(TEST_TARGETS)

test-traffic-agent:
	@echo "🧪 Running tests for traffic-agent..."
	@cd src && \
	python3 -m venv .test-venv && \
	source .test-venv/bin/activate && \
	pip install uv && \
	uv sync && \
	uv run pytest ../tests/ -v \
		--tb=short \
		--junitxml=../test-results/pytest-traffic-agent.xml || true && \
	deactivate && \
	rm -rf .test-venv
	@echo "✅ traffic-agent tests complete."

# ==============================================================================
# Deployment Targets
# ==============================================================================

define DEPLOY_BANNER
	@echo "══════════════════════════════════════════════════"
	@echo "🚀 $(1) - $(SERVICE_NAME)"
	@echo "══════════════════════════════════════════════════"
	@echo ""
	@echo "Configuration:"
	@echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
	@echo "  REGISTRY:                  $${REGISTRY:-$(DEFAULT_REGISTRY)}"
	@echo "  TAG:                       $${TAG:-$(DEFAULT_TAG)}"
	@echo "  LOG_LEVEL:                 $${LOG_LEVEL:-$(LOG_LEVEL)}"
	@echo "  PROJECT_NAME:              $${PROJECT_NAME:-$(PROJECT_NAME)}"
	@echo ""
	@echo "  VLM Configuration:"
	@echo "  VLM_MODEL_NAME:            $${VLM_MODEL_NAME:-$(VLM_MODEL_NAME)}"
	@echo "  VLM_DEVICE:                $${VLM_DEVICE:-$(VLM_DEVICE)}"
	@echo "  VLM_COMPRESSION_FORMAT:    $${VLM_COMPRESSION_WEIGHT_FORMAT:-$(VLM_COMPRESSION_WEIGHT_FORMAT)}"
	@echo "  VLM_MAX_COMPLETION_TOKENS: $${VLM_MAX_COMPLETION_TOKENS:-$(VLM_MAX_COMPLETION_TOKENS)}"
	@echo ""
	@echo "  Traffic Agent:"
	@echo "  REFRESH_INTERVAL:          $${REFRESH_INTERVAL:-$(REFRESH_INTERVAL)}"
	@echo "  HIGH_DENSITY_THRESHOLD:    $${HIGH_DENSITY_THRESHOLD:-$(HIGH_DENSITY_THRESHOLD)}"
	@echo "  WEATHER_MOCK:              $${WEATHER_MOCK:-$(WEATHER_MOCK)}"
	@echo "  MQTT_HOST:                 $${MQTT_HOST:-$(MQTT_HOST)}"
	@echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
	@echo ""
endef

define SETUP_EXPORTS
	export TAG="$${TAG:-$(DEFAULT_TAG)}" && \
	export REGISTRY="$${REGISTRY:-$(DEFAULT_REGISTRY)}" && \
	export LOG_LEVEL="$${LOG_LEVEL:-$(LOG_LEVEL)}" && \
	export VLM_MODEL_NAME="$${VLM_MODEL_NAME:-$(VLM_MODEL_NAME)}" && \
	export VLM_DEVICE="$${VLM_DEVICE:-$(VLM_DEVICE)}" && \
	export VLM_COMPRESSION_WEIGHT_FORMAT="$${VLM_COMPRESSION_WEIGHT_FORMAT:-$(VLM_COMPRESSION_WEIGHT_FORMAT)}" && \
	export VLM_SEED="$${VLM_SEED:-$(VLM_SEED)}" && \
	export VLM_WORKERS="$${VLM_WORKERS:-$(VLM_WORKERS)}" && \
	export VLM_LOG_LEVEL="$${VLM_LOG_LEVEL:-$(VLM_LOG_LEVEL)}" && \
	export VLM_MAX_COMPLETION_TOKENS="$${VLM_MAX_COMPLETION_TOKENS:-$(VLM_MAX_COMPLETION_TOKENS)}" && \
	export REFRESH_INTERVAL="$${REFRESH_INTERVAL:-$(REFRESH_INTERVAL)}" && \
	export HIGH_DENSITY_THRESHOLD="$${HIGH_DENSITY_THRESHOLD:-$(HIGH_DENSITY_THRESHOLD)}" && \
	export WEATHER_MOCK="$${WEATHER_MOCK:-$(WEATHER_MOCK)}" && \
	export MQTT_HOST="$${MQTT_HOST:-$(MQTT_HOST)}" && \
	export MQTT_PORT="$${MQTT_PORT:-$(MQTT_PORT)}"
endef

deploy:
	$(call DEPLOY_BANNER,Deploy)
	@read -p "Proceed with deployment? [y/N]: " confirm; \
	if [ "$$confirm" != "y" ] && [ "$$confirm" != "Y" ]; then \
		echo ""; \
		echo "Deployment cancelled."; \
		echo ""; \
	else \
		echo ""; \
		echo "→ Deploying..."; \
		$(SETUP_EXPORTS) && \
		bash -c "source setup.sh --run"; \
		echo ""; \
		echo "✅ Deployment complete!"; \
	fi

deploy-build:
	$(call DEPLOY_BANNER,Deploy Build)
	@echo "This will BUILD images and then deploy."
	@echo ""
	@read -p "Proceed with build and deployment? [y/N]: " confirm; \
	if [ "$$confirm" != "y" ] && [ "$$confirm" != "Y" ]; then \
		echo ""; \
		echo "Deployment cancelled."; \
		echo ""; \
	else \
		echo ""; \
		echo "→ Building and deploying..."; \
		$(SETUP_EXPORTS) && \
		bash -c "source setup.sh --setup"; \
		echo ""; \
		echo "✅ Build and deployment complete!"; \
	fi

undeploy:
	@echo "══════════════════════════════════════════════════"
	@echo "🛑 Stopping $(SERVICE_NAME)"
	@echo "══════════════════════════════════════════════════"
	@bash -c "source setup.sh --stop"
	@echo "✅ Application stopped."

restart:
	@echo "══════════════════════════════════════════════════"
	@echo "🔄 Restarting all services (agent + dependencies)"
	@echo "══════════════════════════════════════════════════"
	@$(SETUP_EXPORTS) && \
	bash -c "source setup.sh --restart all"
	@echo "✅ All services restarted."

restart-agent:
	@echo "══════════════════════════════════════════════════"
	@echo "🔄 Restarting traffic agent (Backend/UI only)"
	@echo "══════════════════════════════════════════════════"
	@$(SETUP_EXPORTS) && \
	bash -c "source setup.sh --restart agent"
	@echo "✅ Traffic agent restarted."

restart-deps:
	@echo "══════════════════════════════════════════════════"
	@echo "🔄 Restarting dependencies (Smart Intersection RI)"
	@echo "══════════════════════════════════════════════════"
	@$(SETUP_EXPORTS) && \
	bash -c "source setup.sh --restart deps"
	@echo "✅ Dependencies restarted."

clean-all:
	@echo "══════════════════════════════════════════════════"
	@echo "🧹 Cleaning $(SERVICE_NAME) (containers + volumes)"
	@echo "══════════════════════════════════════════════════"
	@bash -c "source setup.sh --clean"
	@echo "✅ Full cleanup complete."

clean-all-keep-models:
	@echo "══════════════════════════════════════════════════"
	@echo "🧹 Cleaning $(SERVICE_NAME) (keeping VLM models)"
	@echo "══════════════════════════════════════════════════"
	@bash -c "source setup.sh --clean --keep-models"
	@echo "✅ Cleanup complete (VLM model cache preserved)."

# ==============================================================================
# Code Quality Targets
# ==============================================================================

shellcheck:
	@echo "🔍 Running ShellCheck..."
	@mkdir -p security-results
	@find . -type f \( -name "*.sh" -o -name "*.bash" \) -print0 | xargs -0 \
		shellcheck --format=json > security-results/shellcheck-report-$(SERVICE_NAME).json 2>/dev/null || true
	@echo "✅ Report: security-results/shellcheck-report-$(SERVICE_NAME).json"

pylint:
	@echo "🔍 Running Pylint..."
	@mkdir -p security-results
	@cd src && \
	python3 -m venv .pylint-venv && \
	source .pylint-venv/bin/activate && \
	pip install uv && \
	uv sync && \
	pip install pylint && \
	( \
		echo "[MESSAGES CONTROL]"; \
		echo "disable=C0111,C0103,R0903,R0913,W0613,W0622,R0801,R0902,R0914,R0915,R0912,C0301,C0302"; \
		echo ""; \
		echo "[FORMAT]"; \
		echo "max-line-length=120"; \
		echo ""; \
		echo "[REPORTS]"; \
		echo "output-format=json"; \
		echo "reports=yes"; \
	) > .pylintrc && \
	find . -type f -name "*.py" -not -path "./.pylint-venv/*" \
		-exec pylint --rcfile=.pylintrc {} + \
		> ../security-results/pylint-report-$(SERVICE_NAME).json 2>/dev/null || true && \
	deactivate && \
	rm -rf .pylint-venv .pylintrc
	@echo "✅ Report: security-results/pylint-report-$(SERVICE_NAME).json"

ruff:
	@echo "🔍 Running Ruff linter..."
	@mkdir -p security-results
	@cd src && \
	python3 -m venv .ruff-venv && \
	source .ruff-venv/bin/activate && \
	pip install ruff && \
	ruff check . --output-format json \
		> ../security-results/ruff-report-$(SERVICE_NAME).json 2>/dev/null || true && \
	deactivate && \
	rm -rf .ruff-venv
	@echo "✅ Report: security-results/ruff-report-$(SERVICE_NAME).json"

# ==============================================================================
# Security Scan Targets
# ==============================================================================

# Trivy HTML template - auto-detect or download
TRIVY_HTML_TPL_URL := https://raw.githubusercontent.com/aquasecurity/trivy/main/pkg/report/templates/html.tpl
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

trivy-scan: trivy-scan-fs trivy-scan-image trivy-scan-config
	@echo "📦 Creating security scan archive..."
	@cd security-results && zip -r trivy-scan-$(SERVICE_NAME)-$$(date +%Y%m%d-%H%M%S).zip trivy-* 2>/dev/null || true
	@echo "✅ All Trivy scans complete. Reports: security-results/trivy-*"

trivy-scan-fs:
	@echo "🔍 Running Trivy Filesystem Scan..."
	@mkdir -p security-results
	@trivy fs --severity HIGH,CRITICAL --ignore-unfixed --format json \
		--output security-results/trivy-fs-$(SERVICE_NAME).json . || true
	@$(ENSURE_TRIVY_HTML_TPL); \
	if [ -n "$$TRIVY_HTML_TPL" ] && [ -f "$$TRIVY_HTML_TPL" ]; then \
		trivy fs --severity HIGH,CRITICAL --ignore-unfixed --format template \
			--template "@$$TRIVY_HTML_TPL" \
			--output security-results/trivy-fs-$(SERVICE_NAME).html . || true; \
		echo "✅ Filesystem scan complete: security-results/trivy-fs-$(SERVICE_NAME).{json,html}"; \
	else \
		echo "✅ Filesystem scan complete: security-results/trivy-fs-$(SERVICE_NAME).json"; \
	fi

trivy-scan-image:
	@echo "🔍 Running Trivy Image Scan..."
	@mkdir -p security-results
	@$(ENSURE_TRIVY_HTML_TPL); \
	echo "  → Scanning $(SERVICE_NAME) image..."; \
	if [ -z "$$(docker images -q $(SERVICE_NAME):$(VERSION) 2>/dev/null)" ]; then \
		echo "  ⚠️  Image '$(SERVICE_NAME):$(VERSION)' not found. Run 'make build' first."; \
	else \
		trivy image --severity HIGH,CRITICAL --ignore-unfixed --format json \
			--output security-results/trivy-image-$(SERVICE_NAME).json \
			$(SERVICE_NAME):$(VERSION) || true; \
		if [ -n "$$TRIVY_HTML_TPL" ] && [ -f "$$TRIVY_HTML_TPL" ]; then \
			trivy image --severity HIGH,CRITICAL --ignore-unfixed --format template \
				--template "@$$TRIVY_HTML_TPL" \
				--output security-results/trivy-image-$(SERVICE_NAME).html \
				$(SERVICE_NAME):$(VERSION) || true; \
		fi; \
	fi
	@echo "✅ Image scan complete: security-results/trivy-image-$(SERVICE_NAME).{json,html}"

trivy-scan-config:
	@echo "🔍 Running Trivy Config Scan..."
	@mkdir -p security-results
	@$(ENSURE_TRIVY_HTML_TPL); \
	trivy config --severity HIGH,CRITICAL --format json \
		--output security-results/trivy-config-$(SERVICE_NAME).json \
		--file-patterns "dockerfile:Dockerfile" src/ || true; \
	if [ -n "$$TRIVY_HTML_TPL" ] && [ -f "$$TRIVY_HTML_TPL" ]; then \
		trivy config --severity HIGH,CRITICAL --format template \
			--template "@$$TRIVY_HTML_TPL" \
			--output security-results/trivy-config-$(SERVICE_NAME).html \
			--file-patterns "dockerfile:Dockerfile" src/ || true; \
	fi
	@echo "✅ Config scan complete: security-results/trivy-config-$(SERVICE_NAME).{json,html}"

clamav-scan:
	@echo "🦠 Running ClamAV Antivirus Scan..."
	@mkdir -p security-results
	@clamscan -r . \
		--exclude-dir=.git \
		--exclude-dir=node_modules \
		--exclude-dir=venv \
		--exclude-dir=.venv \
		> security-results/clamav-$(SERVICE_NAME)-$$(date +%Y%m%d-%H%M%S).txt 2>&1 || true
	@echo "✅ ClamAV scan complete: security-results/clamav-*"

bandit-scan:
	@echo "🔐 Running Bandit Security Scan..."
	@mkdir -p security-results
	@python3 -m venv bandit-venv && \
	source bandit-venv/bin/activate && \
	pip install bandit && \
	bandit -r src/ tests/ \
		--exclude .git,node_modules,venv,.venv \
		-f json \
		-o security-results/bandit-report-$(SERVICE_NAME).json || true && \
	bandit -r src/ tests/ \
		--exclude .git,node_modules,venv,.venv \
		-f html \
		-o security-results/bandit-report-$(SERVICE_NAME).html || true && \
	deactivate && \
	rm -rf bandit-venv
	@echo "✅ Bandit scan complete: security-results/bandit-report-$(SERVICE_NAME).{json,html}"

gitleaks-scan:
	@echo "🔑 Running Gitleaks Secrets Scan..."
	@mkdir -p security-results
	@gitleaks dir . -v \
		-r security-results/gitleaks-$(SERVICE_NAME)-$$(date +%Y%m%d-%H%M%S).json || true
	@echo "✅ Gitleaks scan complete: security-results/gitleaks-*"

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

	@# --- Python: src + tests ---
	@echo "→ Creating CodeQL database for Python..."
	@codeql database create security-results/codeql-db-python-$(SERVICE_NAME) \
		--language=python \
		--source-root=. \
		--build-mode=none \
		--overwrite 2>&1 | tail -5

	@echo "→ Running CodeQL analysis..."
	@codeql database analyze security-results/codeql-db-python-$(SERVICE_NAME) \
		codeql/python-queries \
		--format=csv \
		--output=security-results/codeql-python-$(SERVICE_NAME).csv || true
	@echo "→ Converting results to JSON..."
	@python3 -c "import csv,json; h=['name','description','severity','message','path','start_line','start_col','end_line','end_col']; rows=[dict(zip(h,r)) for r in csv.reader(open('security-results/codeql-python-$(SERVICE_NAME).csv')) if r]; json.dump(rows,open('security-results/codeql-python-$(SERVICE_NAME).json','w'),indent=2); print('  Converted '+str(len(rows))+' finding(s) to JSON')" || true

	@echo "✅ Python analysis complete."
	@echo ""
	@echo "✅ CodeQL scan complete: security-results/codeql-*"

# ==============================================================================
# Info & Utility Targets
# ==============================================================================

list:
	@echo "══════════════════════════════════════════════════"
	@echo "📋 Build Configuration: $(SERVICE_NAME)"
	@echo "══════════════════════════════════════════════════"
	@echo ""
	@echo "Version: $(VERSION)"
	@echo ""
	@echo "Components:"
	@$(foreach component,$(COMPONENTS), echo "  • $(component) → $(SERVICE_NAME):$(VERSION)";)
	@echo ""
	@echo "Dependencies (pre-built):"
	@echo "  • vlm-openvino-serving → $(VLM_IMAGE)"
	@echo ""
	@echo "Test Components:"
	@$(foreach component,$(TEST_COMPONENTS), echo "  • $(component)";)

clean:
	@echo "🧹 Removing Docker images..."
	@docker rmi -f $(SERVICE_NAME):$(VERSION) 2>/dev/null || true
	@echo "✅ Cleanup complete."

# ==============================================================================
# CI/CD Getter Targets
# ==============================================================================

get-service-name:
	@echo $(SERVICE_NAME)

get-component-names:
	@echo "$(COMPONENTS)"

get-image-tags:
	@echo "$(SERVICE_NAME):$(VERSION)"

get-context-dirs:
	@$(foreach component,$(COMPONENTS), echo "$($(component)_CONTEXT_DIR)";)

get-python-version:
	@echo $(PYTHON_VERSION)

get-scan-matrix-json:
	@printf '{"include":['
	@$(foreach component,$(COMPONENTS), \
		$(eval COMMA := $(if $(findstring $(component),$(firstword $(COMPONENTS))),,',')) \
		printf '%s' '$(COMMA){"name":"$(component)","image":"$(SERVICE_NAME):$(VERSION)","context":"$($(component)_CONTEXT_DIR)","dockerfile":"$($(component)_DOCKERFILE)"}'; \
	)
	@printf ']}\n'

# ==============================================================================
# Help
# ==============================================================================

help:
	@echo ""
	@echo "╔══════════════════════════════════════════════════════════════════╗"
	@echo "║       Smart Traffic Intersection Agent - Makefile               ║"
	@echo "╚══════════════════════════════════════════════════════════════════╝"
	@echo ""
	@echo "Usage: make <target>"
	@echo ""
	@echo "BUILD & TEST"
	@echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
	@echo "  build            Build the Docker image"
	@echo "  test             Run all unit tests (pytest)"
	@echo ""
	@echo "DEPLOYMENT"
	@echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
	@echo "  deploy           Deploy using pre-built image"
	@echo "  deploy-build     Build and deploy (includes dependency setup)"
	@echo "  undeploy         Stop and remove containers"
	@echo "  restart          Restart all services (agent + dependencies)"
	@echo "  restart-agent    Restart only the traffic agent (Backend/UI)"
	@echo "  restart-deps     Restart only dependencies (Smart Intersection RI)"
	@echo "  clean-all        Stop, remove containers, and delete volumes"
	@echo "  clean-all-keep-models  Same as clean-all but keep VLM model cache"
	@echo ""
	@echo "  Environment Variables:"
	@echo "    TAG                          Image tag (default: $(DEFAULT_TAG))"
	@echo "    REGISTRY                     Image registry (default: empty)"
	@echo "    LOG_LEVEL                    DEBUG, INFO, WARNING, ERROR (default: INFO)"
	@echo "    PROJECT_NAME                 Docker compose project name (default: trafficagent)"
	@echo ""
	@echo "    VLM Configuration:"
	@echo "    VLM_MODEL_NAME               VLM model (default: microsoft/Phi-3.5-vision-instruct)"
	@echo "    VLM_DEVICE                   CPU or GPU (default: CPU)"
	@echo "    VLM_COMPRESSION_WEIGHT_FORMAT int4 or int8 (default: int8)"
	@echo "    VLM_MAX_COMPLETION_TOKENS    Max tokens (default: 1500)"
	@echo "    HUGGINGFACE_TOKEN            HuggingFace API token (required)"
	@echo ""
	@echo "    Traffic Agent:"
	@echo "    REFRESH_INTERVAL             Data refresh in seconds (default: 15)"
	@echo "    HIGH_DENSITY_THRESHOLD       High density vehicle count (default: 10)"
	@echo "    WEATHER_MOCK                 Mock weather data (default: false)"
	@echo "    MQTT_HOST                    MQTT broker host (default: broker.scenescape.intel.com)"
	@echo "    MQTT_PORT                    MQTT broker port (default: 1883)"
	@echo ""
	@echo "CODE QUALITY & SECURITY"
	@echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
	@echo "  shellcheck       Run ShellCheck on shell scripts"
	@echo "  pylint           Run Pylint on Python code"
	@echo "  ruff             Run Ruff linter on Python code"
	@echo "  trivy-scan       Run all Trivy scans"
	@echo "  trivy-scan-fs    Run Trivy filesystem scan"
	@echo "  trivy-scan-image Run Trivy image scan"
	@echo "  trivy-scan-config Run Trivy Dockerfile scan"
	@echo "  clamav-scan      Run ClamAV antivirus scan"
	@echo "  bandit-scan      Run Bandit security scan"
	@echo "  gitleaks-scan    Run Gitleaks secrets scan"
	@echo "  codeql-scan      Run CodeQL security analysis (Python)"
	@echo ""
	@echo "UTILITIES"
	@echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
	@echo "  list             Show build configuration"
	@echo "  clean            Remove built Docker images"
	@echo "  help             Show this help message"
	@echo ""
	@echo "EXAMPLES"
	@echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
	@echo "  # Build and deploy with default settings"
	@echo "  HUGGINGFACE_TOKEN=hf_xxx make deploy-build"
	@echo ""
	@echo "  # Deploy with GPU acceleration"
	@echo "  VLM_DEVICE=GPU HUGGINGFACE_TOKEN=hf_xxx make deploy-build"
	@echo ""
	@echo "  # Deploy with custom VLM model"
	@echo "  VLM_MODEL_NAME=Qwen/Qwen2.5-VL-3B-Instruct make deploy"
	@echo ""
	@echo "  # Run all security scans"
	@echo "  make trivy-scan bandit-scan gitleaks-scan codeql-scan"
	@echo ""
