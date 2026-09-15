# SPDX-FileCopyrightText: Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

# ==============================================================================
# Live Video Search - Makefile
# ==============================================================================
#
# Deploy and manage the Live Video Search composed Docker stack.
# This application consumes pre-built images and also images build from source from upstream projects:
#   - VSS Search (Video Search and Summarization)
#   - Smart NVR (Frigate-based network video recorder)
#   - Metrics Manager
# 
#
# Quick Start:
#   make help          - Show all available commands
#   make build         - Build all Docker images
#   make deploy        - Deploy using pre-built images
#   make deploy-build  - Build and deploy
#   make undeploy      - Stop the application
#
# Configuration:
#   REGISTRY_URL              - Image registry prefix (default: intel)
#   TAG                       - Shared image tag (default: latest)
#   MULTIMODAL_EMBEDDING_MODEL - Embedding model (default: CLIP/clip-vit-b-32)
#   DATAPREP_EMBEDDING_DEVICE - Indexing embedding device (default: CPU)
#   DATAPREP_DETECTION_DEVICE - Object detection device (default: CPU)
#   MME_EMBEDDING_DEVICE      - Query embedding device (default: CPU)
#   APP_HOST_PORT             - Main app port (default: 12345)
#   ENABLE_METRICS_MANAGER    - Live system/DataPrep metrics (default: true)
#
# Required Secrets (must be set before deploy):
#   MINIO_ROOT_USER, MINIO_ROOT_PASSWORD
#   POSTGRES_USER, POSTGRES_PASSWORD
#   MQTT_USER, MQTT_PASSWORD
#
# ==============================================================================

SHELL := bash
.SHELLFLAGS := -eu -o pipefail -c
.ONESHELL:
.DEFAULT_GOAL := help

# ==============================================================================
# Project Configuration
# ==============================================================================

SERVICE_NAME := live-video-search
VERSION ?= latest

# ==============================================================================
# Image Configuration
# ==============================================================================

# Registry and tag defaults
REGISTRY_URL ?= intel
PROJECT_NAME ?=
TAG ?= latest
VSS_STACK_TAG ?= $(TAG)
SMART_NVR_STACK_TAG ?= $(TAG)

# Compute REGISTRY the same way setup.sh does: REGISTRY_URL/PROJECT_NAME/
REGISTRY := $(if $(REGISTRY_URL),$(REGISTRY_URL)/)$(if $(PROJECT_NAME),$(PROJECT_NAME)/)

# ==============================================================================
# Component Definitions
# ==============================================================================

# VSS Search stack components. Both retriever backend images are distributed
# with LVS; VECTORDB_BACKEND selects which one runs.
VSS_COMPONENTS := vss-ui pipeline-manager video-search multimodal-dataprep multimodal-embedding-serving vector-retriever-vdms vector-retriever-milvus

# Smart NVR stack components
SMART_NVR_COMPONENTS := nvr-event-router

# All first-party components
COMPONENTS := $(VSS_COMPONENTS) $(SMART_NVR_COMPONENTS)

# ==============================================================================
# Deployment Configuration
# ==============================================================================

MULTIMODAL_EMBEDDING_MODEL ?= CLIP/clip-vit-b-32
FRAME_INTERVAL ?= 15
ROI_CONSOLIDATION_ENABLED ?= false
ROI_CONSOLIDATION_IOU_THRESHOLD ?= 0.2
ROI_CONSOLIDATION_CLASS_AWARE ?= true
ROI_CONSOLIDATION_CONTEXT_SCALE ?= 0.2
DATAPREP_EMBEDDING_DEVICE ?= CPU
DATAPREP_DETECTION_DEVICE ?= CPU
MME_EMBEDDING_DEVICE ?= CPU
VECTORDB_BACKEND ?= vdms
ENABLE_METRICS_MANAGER ?= true
VS_WATCH_BATCH_SIZE ?= 10
VS_BATCH_JOB_POLL_INTERVAL_SECONDS ?= 0.5
VS_BATCH_JOB_TIMEOUT_SECONDS ?= 3600

# Deployment mode: default | rtsp-test | usb-camera
START_MODE ?= default

# ==============================================================================
# Internal Variables
# ==============================================================================

# Map START_MODE to setup.sh argument
ifeq ($(START_MODE),rtsp-test)
  SETUP_ARG := --start-rtsp-test
else ifeq ($(START_MODE),usb-camera)
  SETUP_ARG := --start-usb-camera
else
  SETUP_ARG := --start
endif

# Compose file set based on mode
COMPOSE_BASE := -f docker/compose.search.yaml -f docker/compose.smart-nvr.yaml
ifeq ($(ENABLE_METRICS_MANAGER),true)
  COMPOSE_BASE += -f docker/compose.metrics-manager.yaml
endif
ifeq ($(VECTORDB_BACKEND),milvus)
  COMPOSE_BASE += -f docker/compose.search.milvus.yaml
endif
ifeq ($(START_MODE),rtsp-test)
  COMPOSE_FILES := $(COMPOSE_BASE) -f docker/compose.rtsp-test.yaml
else ifeq ($(START_MODE),usb-camera)
  COMPOSE_FILES := $(COMPOSE_BASE) -f docker/compose.usb-camera.yaml
else
  COMPOSE_FILES := $(COMPOSE_BASE)
endif

# ==============================================================================
# Environment Export Block
# ==============================================================================

define EXPORT_RUNTIME_ENV
	export REGISTRY_URL="$${REGISTRY_URL:-$(REGISTRY_URL)}"
	export TAG="$${TAG:-$(TAG)}"
	export VSS_STACK_TAG="$${VSS_STACK_TAG:-$(VSS_STACK_TAG)}"
	export SMART_NVR_STACK_TAG="$${SMART_NVR_STACK_TAG:-$(SMART_NVR_STACK_TAG)}"
	export MULTIMODAL_EMBEDDING_MODEL="$${MULTIMODAL_EMBEDDING_MODEL:-$(MULTIMODAL_EMBEDDING_MODEL)}"
	export FRAME_INTERVAL="$${FRAME_INTERVAL:-$(FRAME_INTERVAL)}"
	export ROI_CONSOLIDATION_ENABLED="$${ROI_CONSOLIDATION_ENABLED:-$(ROI_CONSOLIDATION_ENABLED)}"
	export ROI_CONSOLIDATION_IOU_THRESHOLD="$${ROI_CONSOLIDATION_IOU_THRESHOLD:-$(ROI_CONSOLIDATION_IOU_THRESHOLD)}"
	export ROI_CONSOLIDATION_CLASS_AWARE="$${ROI_CONSOLIDATION_CLASS_AWARE:-$(ROI_CONSOLIDATION_CLASS_AWARE)}"
	export ROI_CONSOLIDATION_CONTEXT_SCALE="$${ROI_CONSOLIDATION_CONTEXT_SCALE:-$(ROI_CONSOLIDATION_CONTEXT_SCALE)}"
	export DATAPREP_EMBEDDING_DEVICE="$${DATAPREP_EMBEDDING_DEVICE:-$(DATAPREP_EMBEDDING_DEVICE)}"
	export DATAPREP_DETECTION_DEVICE="$${DATAPREP_DETECTION_DEVICE:-$(DATAPREP_DETECTION_DEVICE)}"
	export MME_EMBEDDING_DEVICE="$${MME_EMBEDDING_DEVICE:-$(MME_EMBEDDING_DEVICE)}"
	export VECTORDB_BACKEND="$${VECTORDB_BACKEND:-$(VECTORDB_BACKEND)}"
	export ENABLE_METRICS_MANAGER="$${ENABLE_METRICS_MANAGER:-$(ENABLE_METRICS_MANAGER)}"
	export VS_WATCH_BATCH_SIZE="$${VS_WATCH_BATCH_SIZE:-$(VS_WATCH_BATCH_SIZE)}"
	export VS_BATCH_JOB_POLL_INTERVAL_SECONDS="$${VS_BATCH_JOB_POLL_INTERVAL_SECONDS:-$(VS_BATCH_JOB_POLL_INTERVAL_SECONDS)}"
	export VS_BATCH_JOB_TIMEOUT_SECONDS="$${VS_BATCH_JOB_TIMEOUT_SECONDS:-$(VS_BATCH_JOB_TIMEOUT_SECONDS)}"
	export MINIO_ROOT_USER="$${MINIO_ROOT_USER:-}"
	export MINIO_ROOT_PASSWORD="$${MINIO_ROOT_PASSWORD:-}"
	export POSTGRES_USER="$${POSTGRES_USER:-}"
	export POSTGRES_PASSWORD="$${POSTGRES_PASSWORD:-}"
	export MQTT_USER="$${MQTT_USER:-}"
	export MQTT_PASSWORD="$${MQTT_PASSWORD:-}"
	export PYTHON_KEYRING_BACKEND="keyring.backends.null.Keyring"
endef



# ==============================================================================
# Phony Targets
# ==============================================================================

.PHONY: help validate inspect \
        build-from-source \
        deploy deploy-rtsp-test deploy-usb-camera deploy-build-from-source \
        clean clean-data \
        ps status logs \
        shellcheck \
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
	if [ -c "$(USB_CAMERA_DEVICE)" ]; then \
		echo "  ✅ $(USB_CAMERA_DEVICE):   Available"; \
	else \
		echo "  ⚠️  $(USB_CAMERA_DEVICE):   Not found (USB camera mode unavailable)"; \
	fi; \
	echo ""; \
	echo "Required Environment:"; \
	echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"; \
	for var in MINIO_ROOT_USER MINIO_ROOT_PASSWORD POSTGRES_USER POSTGRES_PASSWORD MQTT_USER MQTT_PASSWORD; do \
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
	for var in MINIO_ROOT_USER MINIO_ROOT_PASSWORD POSTGRES_USER POSTGRES_PASSWORD MQTT_USER MQTT_PASSWORD; do \
		if [ -z "$${!var:-}" ]; then \
			echo "❌ Required variable $$var is not set."; ERRORS=$$((ERRORS+1)); \
		fi; \
	done; \
	if [ $$ERRORS -gt 0 ]; then \
		echo ""; \
		echo "Set required secrets before deploying:"; \
		echo "  export MINIO_ROOT_USER=<user> MINIO_ROOT_PASSWORD=<pass>"; \
		echo "  export POSTGRES_USER=<user> POSTGRES_PASSWORD=<pass>"; \
		echo "  export MQTT_USER=<user> MQTT_PASSWORD=<pass>"; \
		exit 1; \
	fi

validate-device:
	@for value in "$(DATAPREP_EMBEDDING_DEVICE)" "$(DATAPREP_DETECTION_DEVICE)" "$(MME_EMBEDDING_DEVICE)"; do \
		case "$$value" in CPU|GPU|NPU) ;; \
			*) echo "❌ Invalid component device '$$value'. Use CPU, GPU, or NPU."; exit 1 ;; \
		esac; \
	done; \
	if [ "$(DATAPREP_EMBEDDING_DEVICE)" = "GPU" ] || [ "$(DATAPREP_DETECTION_DEVICE)" = "GPU" ] || [ "$(MME_EMBEDDING_DEVICE)" = "GPU" ]; then \
		if [ ! -d /dev/dri ] || [ -z "$$(ls -A /dev/dri 2>/dev/null)" ]; then \
			echo "❌ A GPU component device requires /dev/dri but it is not available."; \
			exit 1; \
		fi; \
	fi; \
	if [ "$(DATAPREP_EMBEDDING_DEVICE)" = "NPU" ] || [ "$(DATAPREP_DETECTION_DEVICE)" = "NPU" ] || [ "$(MME_EMBEDDING_DEVICE)" = "NPU" ]; then \
		if [ ! -c /dev/accel/accel0 ]; then \
			echo "❌ An NPU component device requires /dev/accel/accel0 but it is not available."; \
			exit 1; \
		fi; \
	fi; \
	if [ "$(START_MODE)" = "usb-camera" ]; then \
		if [ ! -c "$(USB_CAMERA_DEVICE)" ]; then \
			echo "❌ USB camera mode requires $(USB_CAMERA_DEVICE) but device not found."; \
			exit 1; \
		fi; \
	fi


# ==============================================================================
# Deployments
# ==============================================================================

deploy: validate
	@echo "══════════════════════════════════════════════════"
	@echo "🚀 Deploy - $(SERVICE_NAME) [mode: $(START_MODE)]"
	@echo "══════════════════════════════════════════════════"
	@echo ""
	@echo "Configuration:"
	@echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
	@echo "  START_MODE:         $(START_MODE)"
	@echo "  REGISTRY_URL:       $(REGISTRY_URL)"
	@echo "  TAG:                $(TAG)"
	@echo "  VSS_STACK_TAG:      $(VSS_STACK_TAG)"
	@echo "  SMART_NVR_STACK_TAG: $(SMART_NVR_STACK_TAG)"
	@echo "  APP_HOST_PORT:      $(APP_HOST_PORT)"
	@echo "  MULTIMODAL_EMBEDDING_MODEL: $(MULTIMODAL_EMBEDDING_MODEL)"
	@echo "  DATAPREP_EMBEDDING_DEVICE: $(DATAPREP_EMBEDDING_DEVICE)"
	@echo "  DATAPREP_DETECTION_DEVICE: $(DATAPREP_DETECTION_DEVICE)"
	@echo "  MME_EMBEDDING_DEVICE: $(MME_EMBEDDING_DEVICE)"
	@echo ""
	@echo "Secrets:"
	@echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
	@for var in MINIO_ROOT_USER POSTGRES_USER MQTT_USER; do \
		echo "  ✅ $$var: Set"; \
	done
	@echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
	@echo ""
	@echo "→ Deploying..."
	@bash -c '$(EXPORT_RUNTIME_ENV); source setup.sh $(SETUP_ARG)'
	@echo ""

deploy-rtsp-test:
	@$(MAKE) deploy START_MODE=rtsp-test

deploy-usb-camera:
	@$(MAKE) deploy START_MODE=usb-camera

deploy-build-from-source:
	@echo "Building all images from source before deploying..."
	if [ -d "edge-ai-libraries" ]; then \
		echo "Folder exists, pulling latest changes..."; \
		git -C edge-ai-libraries pull; \
	else \
		git clone https://github.com/open-edge-platform/edge-ai-libraries.git edge-ai-libraries; \
	fi
	echo "Building VSS Search stack from source..."
	cd $(CURDIR)/edge-ai-libraries/sample-applications/video-search-and-summarization
	$(EXPORT_RUNTIME_ENV) 
	./build.sh
	./build.sh --dependencies
	echo "Building Smart-NVR from source..."
	cd ../../../../../smart-nvr
	./build.sh
	echo "STARTING THE APPLICATION..."
	$(MAKE) -C $(CURDIR) deploy START_MODE=$(START_MODE)

# ==============================================================================
# Status / Logs Targets
# ==============================================================================

ps:
	@bash -c '\
		$(EXPORT_RUNTIME_ENV)
		source setup.sh --setenv
		docker compose $(COMPOSE_BASE) ps
	'

status: ps

logs:
	@bash -c '\
		$(EXPORT_RUNTIME_ENV)
		source setup.sh --setenv
		docker compose $(COMPOSE_BASE) logs -f $(SERVICE)
	'

SERVICE ?=


# ==============================================================================
# Cleaning
# ==============================================================================
clean-data:
	@echo "Cleaning all the containers and delete the data(Volumes and networks) for the Live Video Search stack"
	@bash -c 'source setup.sh --clean-data; docker network rm docker_live-video-network live-video-network || true'
	docker ps -aq | xargs -r docker rm -fv && docker system prune -a --volumes -f

clean:
	@echo "Stopping all containers for the Live Video Search stack (data volumes and networks are preserved)"
	@bash -c 'source setup.sh --down'

# ==============================================================================
# Code Quality Targets
# ==============================================================================

shellcheck:
	@echo "══════════════════════════════════════════════════"
	@echo "🔍 ShellCheck - Linting Shell Scripts"
	@echo "══════════════════════════════════════════════════"
	@echo "Checking if ShellCheck is installed..."
	@if ! command -v shellcheck >/dev/null 2>&1; then \
		echo "❌ ShellCheck is not installed. Please install it to run this check."; \
		exit 1; \
	fi
	@mkdir -p security-results
	@find . -type f \( -name "*.sh" -o -name "*.bash" \) -not -path "*/edge-ai-libraries/*" -print0 | xargs -0 -r \
		shellcheck --format=json > security-results/shellcheck-report-$(SERVICE_NAME).json 2>/dev/null || true
	@echo "✅ Report: security-results/shellcheck-report-$(SERVICE_NAME).json"


clamav-scan:
	@echo "🦠 Running ClamAV Antivirus Scan..."
		@echo "Checking if ClamAV is installed..."
	@if ! command -v clamscan >/dev/null 2>&1; then \
		echo "❌ ClamAV is not installed. Please install it to run this check."; \
		exit 1; \
	fi
	@mkdir -p security-results
	@clamscan -r . \
		--exclude-dir=.git \
		--exclude-dir=node_modules \
		--exclude-dir=venv \
		--exclude-dir=ui/test \
		--exclude-dir=tests \
		--exclude-dir=edge-ai-libraries \
		> security-results/clamav-$(SERVICE_NAME)-$$(date +%Y%m%d-%H%M%S).txt 2>&1 || true
	@echo "✅ ClamAV scan complete: security-results/clamav-*"

bandit-scan:
	@echo "🔐 Running Bandit Security Scan..."
	@echo "No Python source files to scan - skipping Bandit scan"


codeql-scan:
	@echo "🛡️  Running CodeQL Security Analysis..."
	@echo "NO SOURCE CODE TO ANALYZE - skipping CodeQL scan"
# ==============================================================================
# Security Scanning
# ==============================================================================

trivy-scan: trivy-scan-fs trivy-scan-image trivy-scan-config
	@echo "📦 Creating security scan archive..."
	@cd security-results && zip -r trivy-scan-$(SERVICE_NAME)-$$(date +%Y%m%d-%H%M%S).zip trivy-* 2>/dev/null || true
	@echo "✅ All Trivy scans complete. Reports: security-results/trivy-*"


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

# trivy-scan-image: pull each first-party image from the registry then scan it.
# No local Dockerfiles exist in this project — images are consumed pre-built.
# Strategy: pull → scan (supply-chain security: audit exactly what will run in production).
trivy-scan-image:
	@echo "🔍 Running Trivy Image Scans (pull-and-scan)..."
	@mkdir -p security-results
	@$(ENSURE_TRIVY_HTML_TPL); \
	REGISTRY="$(REGISTRY)"; \
	for comp in $(VSS_COMPONENTS); do \
		IMAGE="$${REGISTRY}$${comp}:$(VSS_STACK_TAG)"; \
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
	for comp in $(SMART_NVR_COMPONENTS); do \
		IMAGE="$${REGISTRY}$${comp}:$(SMART_NVR_STACK_TAG)"; \
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
	done
	@echo ""
	@echo "✅ Image scans complete: security-results/trivy-image-*.{json,spdx.json,html}"


trivy-scan-fs:
	@echo "🔍 Running Trivy Filesystem Scan..."
	@echo "NO SOURCE CODE FILES TO SCAN - skipping filesystem scan"


trivy-scan-config:
	@echo "🔍 Running Trivy Config Scan..."
	@echo "NO CONFIG FILES TO SCAN - skipping config scan"

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
	@$(foreach component,$(COMPONENTS), echo "$($(component)_CONTEXT_DIR)";)

get-python-version:
	@echo $(PYTHON_VERSION)

get-node-version:
	@echo $(NODE_VERSION)

get-scan-matrix-json:
	@printf '{"include":['
	@$(foreach component,$(COMPONENTS), \
		$(eval COMMA := $(if $(findstring $(component),$(firstword $(COMPONENTS))),,',')) \
		printf '%s' '$(COMMA){"name":"$(component)","image":"$(SERVICE_NAME)-$(component):$(VERSION)","context":"$($(component)_CONTEXT_DIR)","dockerfile":"$($(component)_DOCKERFILE)"}'; \
	)
	@printf ']}\n'

# ==============================================================================
# Help
# ==============================================================================

help:
	@echo ""
	@echo "╔══════════════════════════════════════════════════════════════════╗"
	@echo "║              Live Video Search - Makefile                        ║"
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
	@echo "  build-from-source  Print guidance (no local Dockerfiles)"
	@echo ""
	@echo "DEPLOYMENT"
	@echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
	@echo "  deploy             Deploy default camera workflow"
	@echo "  deploy-rtsp-test   Deploy with bundled RTSP looped sample video"
	@echo "  deploy-usb-camera  Deploy with USB camera input"
	@echo "  deploy-build-from-source       Build images then deploy"
	@echo "  clean              Stop containers (alias for undeploy)"
	@echo "  clean-data         Stop + remove volumes/networks"
	@echo ""
	@echo "STATUS & LOGS"
	@echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
	@echo "  ps / status        Show running containers"
	@echo "  logs               Follow logs (SERVICE=<name> to filter)"
	@echo ""
	@echo "CODE QUALITY & SECURITY"
	@echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
	@echo "  shellcheck         Lint shell scripts"
	@echo "  trivy-scan         Run all Trivy scans (image + fs + config)"
	@echo "  trivy-scan-image   Pull and scan all first-party images from registry"
	@echo "  trivy-scan-fs      Run Trivy filesystem scan"
	@echo "  trivy-scan-config  Run Trivy compose/config scan"
	@echo "  gitleaks-scan      Run Gitleaks secrets scan"
	@echo ""
	@echo "CI/CD METADATA"
	@echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
	@echo "  get-service-name       Print service name"
	@echo "  get-component-names    Print component list"
	@echo "  get-image-tags         Print all image:tag references"
	@echo "  get-context-dirs       Print context directories (N/A for this project)"
	@echo "  get-scan-matrix-json   Print JSON matrix for CI scanning"
	@echo ""
	@echo "CONFIGURATION VARIABLES"
	@echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
	@echo "  REGISTRY_URL            Image registry prefix (default: intel)"
	@echo "  TAG                     Shared image tag (default: latest)"
	@echo "  VSS_STACK_TAG           Override tag for VSS services (default: TAG)"
	@echo "  SMART_NVR_STACK_TAG     Override tag for Smart NVR services (default: TAG)"
	@echo "  MULTIMODAL_EMBEDDING_MODEL  Embedding model (default: CLIP/clip-vit-b-32)"
	@echo "  APP_HOST_PORT           Main app port (default: 12345)"
	@echo "  DATAPREP_EMBEDDING_DEVICE  Indexing embedding device: CPU, GPU, or NPU"
	@echo "  DATAPREP_DETECTION_DEVICE  Object detection device: CPU, GPU, or NPU"
	@echo "  MME_EMBEDDING_DEVICE       Query embedding device: CPU, GPU, or NPU"
	@echo "  VECTORDB_BACKEND        vdms (default) or milvus"
	@echo "  VS_WATCH_BATCH_SIZE     Continuous-ingestion watcher batch size (default: 10; max: 100)"
	@echo "  VS_BATCH_JOB_POLL_INTERVAL_SECONDS  Batch poll interval (default: 0.5)"
	@echo "  VS_BATCH_JOB_TIMEOUT_SECONDS  Batch completion timeout (default: 3600)"
	@echo "  USB_CAMERA_DEVICE       USB camera path (default: /dev/video0)"
	@echo "  START_MODE              default | rtsp-test | usb-camera"
	@echo ""
	@echo "EXAMPLES"
	@echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
	@echo "  # Deploy with default camera (requires secrets to be set)"
	@echo "  make deploy"
	@echo ""
	@echo "  # Deploy with RTSP test stream"
	@echo "  make deploy-rtsp-test"
	@echo ""
	@echo "  # Run indexing and query embeddings on GPU"
	@echo "  DATAPREP_EMBEDDING_DEVICE=GPU MME_EMBEDDING_DEVICE=GPU make deploy"
	@echo ""
	@echo "  # Pull a specific version and deploy"
	@echo "  TAG=<version> make deploy-build"
	@echo ""
	@echo "  # Preview resolved compose config"
	@echo "  make config"
	@echo ""
	@echo "  # Deploy with Milvus and vector-retriever-milvus"
	@echo "  VECTORDB_BACKEND=milvus make deploy"
	@echo ""
	@echo "  # Check host readiness"
	@echo "  make validate"
	@echo ""
