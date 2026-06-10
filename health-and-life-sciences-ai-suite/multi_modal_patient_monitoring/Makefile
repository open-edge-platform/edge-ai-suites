# Copyright © 2026 Intel Corporation. All rights reserved.
# SPDX-License-Identifier: Apache-2.0


.PHONY: init-mdpnp build-mdpnp build-dds-bridge precheck-models run down download-rppg-assets

HTTP_PROXY := $(or $(HTTP_PROXY),$(http_proxy))
HTTPS_PROXY := $(or $(HTTPS_PROXY),$(https_proxy))
NO_PROXY := $(or $(NO_PROXY),$(no_proxy))
export HTTP_PROXY
export HTTPS_PROXY
export NO_PROXY

MDPNP_PATH := services/mdpnp/mdpnp
DDS_BRIDGE_PATH := services/dds-bridge
DOCKER_COMPOSE := docker-compose.yaml
REGISTRY ?= true

# Detect host IP for UI/backend communication (first non-loopback address)
HOST_IP ?= $(shell ip route get 1 2>/dev/null | awk '{print $$7}' | head -1)
export HOST_IP

TAG ?= 2026.1.0-rc2
export TAG

MODEL_STAGING_DIR ?= $(CURDIR)/models/downloads
RPPG_SOURCE_MODEL := $(MODEL_STAGING_DIR)/rppg/mtts_can.hdf5
POSE_SOURCE_ARCHIVE := $(MODEL_STAGING_DIR)/3d-pose/human-pose-estimation-3d.tar.gz
ECG_SOURCE_DIR := $(MODEL_STAGING_DIR)/ai-ecg/hubert-ecg-small

init-mdpnp:
	@echo "Initializing mdpnp submodule..."
	git submodule update --init $(MDPNP_PATH)

build-mdpnp: init-mdpnp
	@echo "Running mdpnp Gradle makeFlatRuntime..."
	cd $(MDPNP_PATH) && ./gradlew :interop-lab:demo-apps:makeFlatRuntime

build-dds-bridge: 
	@echo "Running dds-bridge build..."
	cd $(DDS_BRIDGE_PATH) && ./gradlew clean build

precheck-models:
	@echo "Checking manually staged model artifacts..."
	@test -f "$(RPPG_SOURCE_MODEL)" || (echo "[ERROR] Missing rPPG source model: $(RPPG_SOURCE_MODEL)" && exit 1)
	@test -f "$(POSE_SOURCE_ARCHIVE)" || (echo "[ERROR] Missing 3D pose source archive: $(POSE_SOURCE_ARCHIVE)" && exit 1)
	@test -d "$(ECG_SOURCE_DIR)" || (echo "[ERROR] Missing AI-ECG source directory: $(ECG_SOURCE_DIR)" && exit 1)
	@echo "All required model artifacts are present under $(MODEL_STAGING_DIR)."

run: precheck-models
	@if [ "$(REGISTRY)" = "true" ]; then \
		echo "##############Using registry mode - fetching all images..."; \
		echo "Using HOST_IP=$(HOST_IP) for UI backend"; \
		./run_compose.sh -d; \
	else \
		echo "Using HOST_IP=$(HOST_IP) for UI backend"; \
		./run_compose.sh --build -d; \
	fi
	@echo "==============================================="
	@echo "Multi-modal patient monitoring application is starting up."
	@echo "Please access the UI at:       http://$(HOST_IP):3000"
	@echo "==============================================="

down:
	@echo "Tearing down the services..."
	docker compose -f $(DOCKER_COMPOSE) down

download-rppg-assets:
	@echo "Downloading RPPG model and sample video assets..."
	cd services/rppg-service && python3 scripts/download_assets.py
	@echo "RPPG assets download complete."

