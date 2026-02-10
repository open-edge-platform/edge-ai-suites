# Copyright © 2026 Intel Corporation. All rights reserved.
# SPDX-License-Identifier: Apache-2.0


.PHONY: init-mdpnp build-mdpnp build-dds-bridge run down download-rppg-assets

MDPNP_PATH := services/mdpnp/mdpnp
DDS_BRIDGE_PATH := services/dds-bridge
DOCKER_COMPOSE := docker-compose.yaml
REGISTRY ?= true

# Detect host IP for UI/backend communication (first non-loopback address)
HOST_IP ?= $(shell hostname -I | awk '{print $$1}')
export HOST_IP


init-mdpnp:
	@echo "Initializing mdpnp submodule..."
	git submodule update --init $(MDPNP_PATH)

build-mdpnp: init-mdpnp
	@echo "Running mdpnp Gradle makeFlatRuntime..."
	cd $(MDPNP_PATH) && ./gradlew :interop-lab:demo-apps:makeFlatRuntime

build-dds-bridge: 
	@echo "Running dds-bridge build..."
	cd $(DDS_BRIDGE_PATH) && ./gradlew clean build

run:
	@if [ "$(REGISTRY)" = "true" ]; then \
		echo "##############Using registry mode - fetching all images..."; \
		echo "Using HOST_IP=$(HOST_IP) for UI backend"; \
		docker compose -f $(DOCKER_COMPOSE) --env-file configs/device.env up -d; \
	else \
		echo "Using HOST_IP=$(HOST_IP) for UI backend"; \
		docker compose -f $(DOCKER_COMPOSE) --env-file configs/device.env up --build -d; \
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

