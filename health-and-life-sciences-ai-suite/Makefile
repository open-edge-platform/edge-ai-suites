# Copyright © 2026 Intel Corporation. All rights reserved.
# SPDX-License-Identifier: Apache-2.0


.PHONY: init-mdpnp build-mdpnp run

MDPNP_PATH := services/mdpnp-service/mdpnp
DDS_BRIDGE_PATH := services/dds-bridge
DOCKER_COMPOSE := docker-compose.yaml
REGISTRY ?= true


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
		echo "##############Using registry mode - fetching pipeline runner..."; \
		docker compose -f $(DOCKER_COMPOSE) up -d; \
	else \
		docker compose -f $(DOCKER_COMPOSE) up --build -d; \
	fi

down:
	@echo "Tearing down the services..."
	docker compose -f $(DOCKER_COMPOSE) down

