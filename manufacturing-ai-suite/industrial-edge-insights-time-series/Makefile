#
# Apache v2 license
# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
#

DEFAULT_SAMPLE_APP := wind-turbine-anomaly-detection
SAMPLE_APP_LIST := wind-turbine-anomaly-detection weld-anomaly-detection

ifdef app
ifeq ($(filter $(app),$(SAMPLE_APP_LIST)),)
$(error Sample app '$(app)' not found. Valid options: $(SAMPLE_APP_LIST))
endif
SAMPLE_APP := $(app)
else
$(info Using default Sample app: $(DEFAULT_SAMPLE_APP))
SAMPLE_APP := $(DEFAULT_SAMPLE_APP)
endif

app-%:
	@true

export SAMPLE_APP

INCLUDE ?= default_INCLUDE

DOCKER_COMPOSE_FILE = ./docker-compose.yml
DOCKER_COMPOSE_VALIDATION_FILE=./docker-compose-validation.override.yml
DOCKER_COMPOSE = docker compose
SECURE_MODE='false'

# Define the path to the .env file and scripts
ENV_FILE = ./.env

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

# This section generates an SSL certificate for secure communication.
.PHONY: generated_ssl_certs_nginx
generated_ssl_certs_nginx:
	@echo "Generating SSL certificates for Nginx..."
	@if [ -d "./nginx/ssl" ]; then rm -rf ./nginx/ssl; fi
	@mkdir -p ./nginx/ssl
	@openssl req -x509 -nodes -days ${DAYS} -${SHA_ALGO} -newkey rsa:${KEY_LENGTH} -keyout ./nginx/ssl/key.pem -out ./nginx/ssl/cert.pem -subj "/CN=localhost"
	@chmod 644 ./nginx/ssl/key.pem ./nginx/ssl/cert.pem
# Check if multiple particular variables in .env are assigned with values
.PHONY: check_env_variables
check_env_variables:
	@echo "Checking if username/password in .env are matching the rules set..."
	@variables="INFLUXDB_USERNAME INFLUXDB_PASSWORD VISUALIZER_GRAFANA_USER VISUALIZER_GRAFANA_PASSWORD MR_PSQL_PASSWORD MR_MINIO_ACCESS_KEY MR_MINIO_SECRET_KEY"; \
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
			MR_PSQL_PASSWORD) \
				if ! echo "$$value" | grep -Eq "^[A-Za-z0-9]{10,}$$" || ! echo "$$value" | grep -q "[0-9]" || ! echo "$$value" | grep -q "[A-Za-z]"; then \
					echo "MR_PSQL_PASSWORD length must be a minimum of 10 alphanumeric characters with atleast one digit"; \
					exit 1; \
				fi \
				;; \
			MR_MINIO_ACCESS_KEY) \
				if ! echo "$$value" | grep -Eq "^[A-Za-z0-9]{10,}$$" || ! echo "$$value" | grep -q "[0-9]" || ! echo "$$value" | grep -q "[A-Za-z]"; then \
					echo "MR_MINIO_ACCESS_KEY length must be a minimum of 10 alphanumeric characters with atleast one digit"; \
					exit 1; \
				fi \
				;; \
			MR_MINIO_SECRET_KEY) \
				if ! echo "$$value" | grep -Eq "^[A-Za-z0-9]{10,}$$" || ! echo "$$value" | grep -q "[0-9]" || ! echo "$$value" | grep -q "[A-Za-z]"; then \
					echo "MR_MINIO_SECRET_KEY length must be a minimum of 10 alphanumeric characters with atleast one digit"; \
					exit 1; \
				fi \
				;; \
		esac; \
	done

.PHONY: up_mqtt_ingestion
up_mqtt_ingestion: check_env_variables down generated_ssl_certs_nginx
	@export TELEGRAF_INPUT_PLUGIN=$$(if [ $(INCLUDE) = 'validation' ]; then echo "mqtt_consumer:net:cpu:disk:docker:diskio:kernel:mem:processes:swap:system"; else echo "mqtt_consumer"; fi); \
	echo "Starting Docker containers..."; \
	if [ $(INCLUDE) = 'validation' ]; then \
		$(DOCKER_COMPOSE) -f $(DOCKER_COMPOSE_FILE) -f $(DOCKER_COMPOSE_VALIDATION_FILE) up --scale ia-opcua-server=0 -d; \
	else \
		$(DOCKER_COMPOSE) up --scale ia-opcua-server=0 -d; \
	fi;

# Run Docker containers
.PHONY: up_opcua_ingestion
up_opcua_ingestion: check_env_variables down generated_ssl_certs_nginx
	@export TELEGRAF_INPUT_PLUGIN=$$(if [ $(INCLUDE) = 'validation' ]; then echo "opcua:net:cpu:disk:docker:diskio:kernel:mem:processes:swap:system"; else echo "opcua"; fi); \
	echo "Starting Docker containers..."; \
	if [ $(INCLUDE) = 'validation' ]; then \
		$(DOCKER_COMPOSE) -f $(DOCKER_COMPOSE_FILE) -f $(DOCKER_COMPOSE_VALIDATION_FILE) up --scale ia-mqtt-publisher=0 -d ;\
	else \
		$(DOCKER_COMPOSE) up --scale ia-mqtt-publisher=0 -d; \
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

# Generate helm packages
.PHONY: gen_helm_charts
gen_helm_charts:
	@echo "Generating Helm packages"
	@echo "Packaging Helm chart for ${SAMPLE_APP}"
	@cp -f grafana/dashboards/*.yml helm/
	@cp -f apps/${SAMPLE_APP}/grafana-dashboard/dashboard.json helm/
	@cp -f influxdb/config/*.conf helm/
	@cp -f influxdb/init-influxdb.sh helm/
	@cp -f mqtt-broker/*.conf helm/
	@cp -f apps/${SAMPLE_APP}/ingestor-data/${SAMPLE_APP}.csv helm/
	@cp -f apps/${SAMPLE_APP}/telegraf-config/*.conf helm
	@cp -f grafana/entrypoint.sh helm/grafana_entrypoint.sh
	@cp -f apps/${SAMPLE_APP}/time-series-analytics-config/config.json helm/
	@cp -f telegraf/entrypoint.sh helm/telegraf_entrypoint.sh
	@sed -i "s/name: .*/name: ${SAMPLE_APP}-sample-app/" "helm/Chart.yaml"
	@sed -i "s/SAMPLE_APP: .*/SAMPLE_APP: ${SAMPLE_APP}/" "helm/values.yaml"
	@echo "Helm packages generated"

# Help
.PHONY: help
help:
	@echo "Makefile commands:"
	@echo "  make build    - Build Docker containers"
	@echo "  make build_copyleft_sources - Build Docker containers including copyleft licensed sources"
	@echo "  make up_mqtt_ingestion     - Start Docker containers using mqtt ingestion"
	@echo "  make up_opcua_ingestion    - Start Docker containers using opcua ingestion"
	@echo "  make down     - Stop Docker containers"
	@echo "  make restart  - Restart Docker containers"
	@echo "  make clean    - Remove all stopped containers and unused images"
	@echo "  make push_images     - Push the images to docker registry"
	@echo "  make gen_helm_charts	- Generate helm packages"
	@echo "  make help     - Display this help message"
