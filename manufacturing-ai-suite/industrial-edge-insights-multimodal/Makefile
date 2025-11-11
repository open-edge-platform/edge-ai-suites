#
# Apache v2 license
# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
#

INCLUDE ?= default_INCLUDE

DOCKER_COMPOSE_FILE = ./docker-compose.yml
DOCKER_COMPOSE_VALIDATION_FILE=./docker-compose-validation.override.yml
DOCKER_COMPOSE = docker compose
SECURE_MODE='false'

# Define the path to the .env file and scripts
ENV_FILE = ./.env
HELM_PACKAGE_SCRIPT = ./package_helm.sh

include $(ENV_FILE)
export $(shell sed 's/=.*//' $(ENV_FILE))

# Default values
KEY_LENGTH=3072
DAYS=365
SHA_ALGO="sha384"

# Build Docker containers
.PHONY: build
build:
	@echo "Building Docker containers..."
	$(DOCKER_COMPOSE) build;

.PHONY: build_copyleft_sources
build_copyleft_sources:
	@echo "Building Docker containers including copyleft licensed sources..."
	$(DOCKER_COMPOSE) build --build-arg COPYLEFT_SOURCES=true;

.PHONY: validate_host_ip
validate_host_ip:
	@echo "Validating HOST_IP in .env..."
	@host_ip=$$(grep -E "^HOST_IP=" $(ENV_FILE) | cut -d'=' -f2); \
	if [ -z "$$host_ip" ]; then \
		echo "HOST_IP is not set in $(ENV_FILE)."; \
		exit 1; \
	fi; \
	if ! echo "$$host_ip" | grep -Eq '^([0-9]{1,3}\.){3}[0-9]{1,3}$$'; then \
		echo "HOST_IP ($$host_ip) is not a valid IPv4 address format."; \
		exit 1; \
	fi; \
	for octet in $$(echo "$$host_ip" | tr '.' ' '); do \
		if [ "$$octet" -lt 0 ] || [ "$$octet" -gt 255 ]; then \
			echo "HOST_IP ($$host_ip) has an invalid octet: $$octet"; \
			exit 1; \
		fi; \
	done; \
	echo "HOST_IP ($$host_ip) is valid."

# Check if multiple particular variables in .env are assigned with values
.PHONY: check_env_variables
check_env_variables:
	@echo "Checking if username/password in .env are matching the rules set..."
	@variables="INFLUXDB_USERNAME INFLUXDB_PASSWORD VISUALIZER_GRAFANA_USER VISUALIZER_GRAFANA_PASSWORD MTX_WEBRTCICESERVERS2_0_USERNAME MTX_WEBRTCICESERVERS2_0_PASSWORD"; \
	for variable_name in $$variables; do \
		value=$$(grep -E "^$$variable_name=" $(ENV_FILE) | cut -d'=' -f2); \
		if [ -z "$$value" ]; then \
			echo "'$$variable_name' in $(ENV_FILE) is unassigned."; \
			exit 1; \
		fi; \
		case "$$variable_name" in \
			INFLUXDB_USERNAME) \
				if [ "$$value" = "admin" ]; then \
					echo "INFLUXDB_USERNAME must not be admin."; \
					exit 1; \
				fi; \
				if ! echo "$$value" | grep -Eq "^[A-Za-z]{5,}$$"; then \
					echo "INFLUXDB_USERNAME must contain only alphabets and be at least 5 characters minimum"; \
					exit 1; \
				fi \
				;; \
			INFLUXDB_PASSWORD) \
				if ! echo "$$value" | grep -Eq "^[A-Za-z0-9]{10,}$$" || ! echo "$$value" | grep -q "[0-9]" || ! echo "$$value" | grep -q "[A-Za-z]"; then \
					echo "The INFLUXDB_PASSWORD length must be a minimum of 10 alphanumeric characters with at least one digit"; \
					exit 1; \
				fi \
				;; \
			VISUALIZER_GRAFANA_USER) \
				if ! echo "$$value" | grep -Eq "^[A-Za-z]{5,}$$"; then \
					echo "VISUALIZER_GRAFANA_USER must contain only alphabets and be at least 5 characters minimum"; \
					exit 1; \
				fi \
				;; \
			VISUALIZER_GRAFANA_PASSWORD) \
				if ! echo "$$value" | grep -Eq "^[A-Za-z0-9]{10,}$$" || ! echo "$$value" | grep -q "[0-9]" || ! echo "$$value" | grep -q "[A-Za-z]"; then \
					echo "VISUALIZER_GRAFANA_PASSWORD length must be a minimum of 10 alphanumeric characters with at least one digit"; \
					exit 1; \
				fi \
				;; \
		esac; \
	done

.PHONY: up
up: check_env_variables validate_host_ip down
	@export TELEGRAF_INPUT_PLUGIN=$$(if [ $(INCLUDE) = 'validation' ]; then echo "mqtt_consumer:net:cpu:disk:docker:diskio:kernel:mem:processes:swap:system"; else echo "mqtt_consumer"; fi); \
	echo "Starting Docker containers..."; \
	if [ $(INCLUDE) = 'validation' ]; then \
		$(DOCKER_COMPOSE) -f $(DOCKER_COMPOSE_FILE) -f $(DOCKER_COMPOSE_VALIDATION_FILE) up -d; \
	else \
		$(DOCKER_COMPOSE) up -d; \
	fi;

# Status of the deployed containers
.PHONY: status
status:
	@echo "Status of the deployed containers..."; \
	docker ps -a --filter "name=^ia-" --filter "name=mr_" --filter "name=model_" --filter "name=wind-turbine" --format "table {{.ID}}\t{{.Names}}\t{{.Status}}\t{{.Ports}}"; \
	echo "Parsing the logs of all containers to catch any error messages..."; \
	sleep 20; \
	containers=$$(docker ps -a --filter "name=^ia-" --filter "name=mr_" --filter "name=model_" --filter "name=wind-turbine" --format "{{.Names}}"); \
	failure_cont_flag=0; \
	for container in $$containers; do \
		errors=$$(docker logs --tail 5 $$container 2>&1 | grep -i "error"); \
		error_count=0; \
		if [ -n "$$errors" ]; then \
			error_count=$$(echo "$$errors" | wc -l); \
		fi; \
		if [ $$error_count -gt 0 ]; then \
			echo ""; \
			echo "=============Found errors in container $$container========"; \
			echo "$$errors"; \
			echo "******************************************************"; \
			echo ""; \
			failure_cont_flag=1; \
		fi; \
	done; \
	if [ $$failure_cont_flag -eq 0 ]; then \
		echo ""; \
		echo "All containers are up and running without errors."; \
		echo ""; \
	else \
		echo ""; \
		echo "Some containers have errors. Please check the logs above."; \
		echo ""; \
	fi;
	
# Removes docker compose containers and volumes
.PHONY: down
down:
	@echo "Stopping Docker containers...";
	$(DOCKER_COMPOSE) -f $(DOCKER_COMPOSE_FILE) down -v --remove-orphans

# Push the docker images to docker registry, ensure to configure DOCKER_REGISTRY in .env
# and have logged into that. Applies mainly when one is dealing with internal docker registry.
# If you are using docker hub, ensure to have logged in with `docker login` command
# before running this command.
.PHONY: push_images
push_images: build
	@echo "Pushing the images to docker registry"
	docker compose -f $(DOCKER_COMPOSE_FILE) push

# Help
.PHONY: help
help:
	@echo "Makefile commands:"
	@echo "  make build    - Build Docker containers"
	@echo "  make build_copyleft_sources - Build Docker containers including copyleft licensed sources"
	@echo "  make up    - Start Docker containers"
	@echo "  make down     - Stop Docker containers"
	@echo "  make restart  - Restart Docker containers"
	@echo "  make clean    - Remove all stopped containers and unused images"
	@echo "  make push_images     - Push the images to docker registry"
	@echo "  make help     - Display this help message"
