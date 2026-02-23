# SPDX-FileCopyrightText: Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

# ==============================================================================
# Smart Route Planning Agent - Makefile
# ==============================================================================
#
# Build, test, deploy, and manage the Smart Route Planning Agent.
# Single-service Python application with Gradio UI for agentic AI-based
# commuter route optimization using LangGraph.
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
#   AI_ROUTE_PLANNER_PORT       - UI port (default: 7864)
#   LOG_LEVEL                   - Logging level (default: INFO)
#
# ==============================================================================

SHELL := bash -eu -o pipefail
.DEFAULT_GOAL := help

# ==============================================================================
# Project Configuration
# ==============================================================================

SERVICE_NAME := smart-route-planning-agent
VERSION ?= latest
PYTHON_VERSION := 3.12

# ==============================================================================
# Pre-built Image Configuration
# ==============================================================================

DEFAULT_REGISTRY :=
DEFAULT_TAG := latest

# ==============================================================================
# Component Configuration
# ==============================================================================

COMPONENTS := route-planner-agent
TEST_COMPONENTS := route-planner-agent

# Build context and Dockerfile
route-planner-agent_CONTEXT_DIR := ./src
route-planner-agent_DOCKERFILE := ./src/Dockerfile
route-planner-agent_LANG := python

# ==============================================================================
# Deployment Configuration
# ==============================================================================

REGISTRY ?= $(DEFAULT_REGISTRY)
TAG ?= $(DEFAULT_TAG)
AI_ROUTE_PLANNER_PORT ?= 7864
LOG_LEVEL ?= INFO
TRAFFIC_BUFFER_DURATION ?= 60
DATA_RETENTION_HOURS ?= 24

# Docker Compose
COMPOSE_FILE := src/compose.yaml
PROJECT_NAME := routeplanner

# ==============================================================================
# Internal Variables
# ==============================================================================

TEST_TARGETS := $(addprefix test-,$(TEST_COMPONENTS))

.PHONY: all build test clean help list \
        deploy deploy-build undeploy restart clean-all \
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
		-f $(route-planner-agent_DOCKERFILE) $(route-planner-agent_CONTEXT_DIR)
	@echo "✅ Build complete: $(SERVICE_NAME):$(VERSION)"

# ==============================================================================
# Test Targets
# ==============================================================================

test: $(TEST_TARGETS)

test-route-planner-agent:
	@echo "🧪 Running tests for route-planner-agent..."
	@cd src && \
	python3 -m venv .test-venv && \
	source .test-venv/bin/activate && \
	pip install uv && \
	uv sync && \
	uv run pytest ../tests/ -v \
		--tb=short \
		--junitxml=../test-results/pytest-route-planner-agent.xml || true && \
	deactivate && \
	rm -rf .test-venv
	@echo "✅ route-planner-agent tests complete."

# ==============================================================================
# Deployment Targets
# ==============================================================================

deploy:
	@echo "══════════════════════════════════════════════════"
	@echo "🚀 Deploy - $(SERVICE_NAME)"
	@echo "══════════════════════════════════════════════════"
	@echo ""
	@echo "Configuration:"
	@echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
	@echo "  REGISTRY:                  $${REGISTRY:-$(DEFAULT_REGISTRY)}"
	@echo "  TAG:                       $${TAG:-$(DEFAULT_TAG)}"
	@echo "  AI_ROUTE_PLANNER_PORT:     $${AI_ROUTE_PLANNER_PORT:-$(AI_ROUTE_PLANNER_PORT)}"
	@echo "  LOG_LEVEL:                 $${LOG_LEVEL:-$(LOG_LEVEL)}"
	@echo "  TRAFFIC_BUFFER_DURATION:   $${TRAFFIC_BUFFER_DURATION:-$(TRAFFIC_BUFFER_DURATION)}"
	@echo "  DATA_RETENTION_HOURS:      $${DATA_RETENTION_HOURS:-$(DATA_RETENTION_HOURS)}"
	@echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
	@echo ""
	@read -p "Proceed with deployment? [y/N]: " confirm; \
	if [ "$$confirm" != "y" ] && [ "$$confirm" != "Y" ]; then \
		echo ""; \
		echo "Deployment cancelled."; \
		echo ""; \
	else \
		echo ""; \
		echo "→ Deploying..."; \
		export TAG="$${TAG:-$(DEFAULT_TAG)}" && \
		export REGISTRY="$${REGISTRY:-$(DEFAULT_REGISTRY)}" && \
		export AI_ROUTE_PLANNER_PORT="$${AI_ROUTE_PLANNER_PORT:-$(AI_ROUTE_PLANNER_PORT)}" && \
		export LOG_LEVEL="$${LOG_LEVEL:-$(LOG_LEVEL)}" && \
		export TRAFFIC_BUFFER_DURATION="$${TRAFFIC_BUFFER_DURATION:-$(TRAFFIC_BUFFER_DURATION)}" && \
		export DATA_RETENTION_HOURS="$${DATA_RETENTION_HOURS:-$(DATA_RETENTION_HOURS)}" && \
		bash -c "source setup.sh --run"; \
		echo ""; \
		echo "✅ Deployment complete! Access the UI at http://<host-ip>:$${AI_ROUTE_PLANNER_PORT:-$(AI_ROUTE_PLANNER_PORT)}"; \
	fi

deploy-build:
	@echo "══════════════════════════════════════════════════"
	@echo "🚀 Deploy Build - $(SERVICE_NAME)"
	@echo "══════════════════════════════════════════════════"
	@echo ""
	@echo "This will BUILD the image and then deploy."
	@echo ""
	@echo "Configuration:"
	@echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
	@echo "  REGISTRY:                  $${REGISTRY:-$(DEFAULT_REGISTRY)}"
	@echo "  TAG:                       $${TAG:-$(DEFAULT_TAG)}"
	@echo "  AI_ROUTE_PLANNER_PORT:     $${AI_ROUTE_PLANNER_PORT:-$(AI_ROUTE_PLANNER_PORT)}"
	@echo "  LOG_LEVEL:                 $${LOG_LEVEL:-$(LOG_LEVEL)}"
	@echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
	@echo ""
	@read -p "Proceed with build and deployment? [y/N]: " confirm; \
	if [ "$$confirm" != "y" ] && [ "$$confirm" != "Y" ]; then \
		echo ""; \
		echo "Deployment cancelled."; \
		echo ""; \
	else \
		echo ""; \
		echo "→ Building and deploying..."; \
		export TAG="$${TAG:-$(DEFAULT_TAG)}" && \
		export REGISTRY="$${REGISTRY:-$(DEFAULT_REGISTRY)}" && \
		export AI_ROUTE_PLANNER_PORT="$${AI_ROUTE_PLANNER_PORT:-$(AI_ROUTE_PLANNER_PORT)}" && \
		export LOG_LEVEL="$${LOG_LEVEL:-$(LOG_LEVEL)}" && \
		export TRAFFIC_BUFFER_DURATION="$${TRAFFIC_BUFFER_DURATION:-$(TRAFFIC_BUFFER_DURATION)}" && \
		export DATA_RETENTION_HOURS="$${DATA_RETENTION_HOURS:-$(DATA_RETENTION_HOURS)}" && \
		bash -c "source setup.sh --setup"; \
		echo ""; \
		echo "✅ Build and deployment complete! Access the UI at http://<host-ip>:$${AI_ROUTE_PLANNER_PORT:-$(AI_ROUTE_PLANNER_PORT)}"; \
	fi

undeploy:
	@echo "══════════════════════════════════════════════════"
	@echo "🛑 Stopping $(SERVICE_NAME)"
	@echo "══════════════════════════════════════════════════"
	@bash -c "source setup.sh --stop"
	@echo "✅ Application stopped."

restart:
	@echo "══════════════════════════════════════════════════"
	@echo "🔄 Restarting $(SERVICE_NAME)"
	@echo "══════════════════════════════════════════════════"
	@export TAG="$${TAG:-$(DEFAULT_TAG)}" && \
	export REGISTRY="$${REGISTRY:-$(DEFAULT_REGISTRY)}" && \
	export AI_ROUTE_PLANNER_PORT="$${AI_ROUTE_PLANNER_PORT:-$(AI_ROUTE_PLANNER_PORT)}" && \
	export LOG_LEVEL="$${LOG_LEVEL:-$(LOG_LEVEL)}" && \
	export TRAFFIC_BUFFER_DURATION="$${TRAFFIC_BUFFER_DURATION:-$(TRAFFIC_BUFFER_DURATION)}" && \
	export DATA_RETENTION_HOURS="$${DATA_RETENTION_HOURS:-$(DATA_RETENTION_HOURS)}" && \
	bash -c "source setup.sh --restart"
	@echo "✅ Application restarted."

clean-all:
	@echo "══════════════════════════════════════════════════"
	@echo "🧹 Cleaning $(SERVICE_NAME) (containers + images)"
	@echo "══════════════════════════════════════════════════"
	@bash -c "source setup.sh --clean"
	@echo "✅ Full cleanup complete."

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
	@echo "║         Smart Route Planning Agent - Makefile                   ║"
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
	@echo "  deploy-build     Build and deploy"
	@echo "  undeploy         Stop and remove containers"
	@echo "  restart          Restart the application"
	@echo "  clean-all        Stop, remove containers, and delete images"
	@echo ""
	@echo "  Environment Variables:"
	@echo "    TAG                          Image tag (default: $(DEFAULT_TAG))"
	@echo "    REGISTRY                     Image registry (default: empty)"
	@echo "    AI_ROUTE_PLANNER_PORT        UI port (default: 7864)"
	@echo "    LOG_LEVEL                    DEBUG, INFO, WARNING, ERROR (default: INFO)"
	@echo "    TRAFFIC_BUFFER_DURATION      Traffic buffer in seconds (default: 60)"
	@echo "    DATA_RETENTION_HOURS         Data retention in hours (default: 24)"
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
	@echo "  # Build and deploy"
	@echo "  make deploy-build"
	@echo ""
	@echo "  # Deploy with custom port"
	@echo "  AI_ROUTE_PLANNER_PORT=8080 make deploy"
	@echo ""
	@echo "  # Run all security scans"
	@echo "  make trivy-scan bandit-scan gitleaks-scan codeql-scan"
	@echo ""
