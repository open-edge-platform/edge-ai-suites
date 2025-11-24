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

# Assign default value to num_of_streams if not provided
ifeq ($(origin num_of_streams), undefined)
num_of_streams := 1
endif

ifdef number_of_data_points_per_stream
export ENABLE_BENCHMARKING=true
export BENCHMARK_TOTAL_PTS=$(number_of_data_points_per_stream)
endif

ifeq ($(origin ingestion_interval), undefined)
ingestion_interval := "1s"
endif

# Assign default value to version and appVersion if not provided for helm deployment
ifeq ($(origin version), undefined)
version := "1.1.0-weekly"
endif

export SAMPLE_APP

# Example: Run a shell if-else block before starting containers
define multi_stream_check
	@if [ "$(num_of_streams)" -gt 1 ]; then \
		TELEGRAF_METRIC_BATCH_SIZE=$$(grep -m1 TELEGRAF_METRIC_BATCH_SIZE $(DOCKER_COMPOSE_FILE) | awk -F ': ' '{print $$2}' | xargs); \
		LOG_LEVEL=$$(grep -E "^LOG_LEVEL=" $(ENV_FILE) | cut -d'=' -f2); \
		python3 -m venv ./venv; \
		. ./venv/bin/activate; \
		python3 -m pip install -r requirements.txt; \
		python generate-telegraf-config.py --no_of_streams $(num_of_streams) --log_level $$LOG_LEVEL --telegraf_metric_batch_size $$TELEGRAF_METRIC_BATCH_SIZE --ingestion_interval $(ingestion_interval) --ingestion_type $(1) --app_name $(SAMPLE_APP); \
		deactivate; \
	fi
endef

INCLUDE ?= default_INCLUDE

DOCKER_COMPOSE_FILE = ./docker-compose.yml
DOCKER_COMPOSE_VALIDATION_FILE=./docker-compose-validation.override.yml
DOCKER_COMPOSE = docker compose
SECURE_MODE='false'

# Define the path to the .env file and scripts
ENV_FILE = ./.env

include $(ENV_FILE)
export $(shell sed 's/=.*//' $(ENV_FILE))


# Build Docker containers
.PHONY: build
build:
	@echo "Building Docker containers..."
	$(DOCKER_COMPOSE) build;

.PHONY: build_copyleft_sources
build_copyleft_sources:
	@echo "Building Docker containers including copyleft licensed sources..."
	$(DOCKER_COMPOSE) build --build-arg COPYLEFT_SOURCES=true;

# Check if multiple particular variables in .env are assigned with values
.PHONY: check_env_variables
check_env_variables:
	@echo "Checking if username/password in .env are matching the rules set..."
	@variables="INFLUXDB_USERNAME INFLUXDB_PASSWORD VISUALIZER_GRAFANA_USER VISUALIZER_GRAFANA_PASSWORD"; \
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

.PHONY: up_mqtt_ingestion
up_mqtt_ingestion: check_env_variables down
	$(call multi_stream_check,mqtt)
	@export TELEGRAF_INPUT_PLUGIN=$$(if [ $(INCLUDE) = 'validation' ]; then echo "mqtt_consumer:net:cpu:disk:docker:diskio:kernel:mem:processes:swap:system"; else echo "mqtt_consumer"; fi); \
	if [ "$(ENABLE_BENCHMARKING)" = "true" ]; then \
		export BENCHMARK_TOTAL_PTS=$$(($(number_of_data_points_per_stream) * $(num_of_streams))); \
	fi; \
	if [ $(num_of_streams) -gt 1 ]; then \
		export TELEGRAF_CONFIG_PATH=/etc/telegraf/Telegraf_multi_stream.conf; \
    fi; \
	echo "Starting Docker containers..."; \
	if [ $(INCLUDE) = 'validation' ]; then \
		$(DOCKER_COMPOSE) -f $(DOCKER_COMPOSE_FILE) -f $(DOCKER_COMPOSE_VALIDATION_FILE) up --scale ia-opcua-server=0 -d; \
	else \
		for i in $$(seq 1 $(num_of_streams)); do \
			echo "Starting ia-mqtt-publisher instance $$i for SAMPLE_APP: $$SAMPLE_APP";\
			$(DOCKER_COMPOSE) run -d --name ia-mqtt-publisher-$$i -e INSTANCE_ID=$$i ia-mqtt-publisher; \
		done; \
		$(DOCKER_COMPOSE) up --scale ia-opcua-server=0 -d $(shell $(DOCKER_COMPOSE) config --services | grep -v ia-mqtt-publisher); \
	fi;

# Run Docker containers
.PHONY: up_opcua_ingestion
up_opcua_ingestion: check_env_variables down
	$(call multi_stream_check,opcua)
	@if [ "$(app)" = "weld-anomaly-detection" ]; then \
		echo "The weld-anomaly-detection sample app supports only MQTT ingestion. Please use 'make up_mqtt_ingestion' command to start the services."; \
		exit 1; \
	fi; \
	if [ $(num_of_streams) -gt 1 ]; then \
		export TELEGRAF_CONFIG_PATH=/etc/telegraf/Telegraf_multi_stream.conf; \
    fi; \
	export TELEGRAF_INPUT_PLUGIN=$$(if [ $(INCLUDE) = 'validation' ]; then echo "opcua:net:cpu:disk:docker:diskio:kernel:mem:processes:swap:system"; else echo "opcua"; fi); \
	echo "Starting Docker containers..."; \
	if [ $(INCLUDE) = 'validation' ]; then \
		$(DOCKER_COMPOSE) -f $(DOCKER_COMPOSE_FILE) -f $(DOCKER_COMPOSE_VALIDATION_FILE) up --scale ia-mqtt-publisher=0 -d ;\
	else \
		$(DOCKER_COMPOSE) up --scale ia-opcua-server=$(num_of_streams) --scale ia-mqtt-publisher=0 -d; \
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
	@cp -f configs/grafana/dashboards/*.yml helm/
	@cp -f apps/${SAMPLE_APP}/grafana-dashboard.json helm/
	@cp -f configs/influxdb/config/*.conf helm/
	@cp -f configs/influxdb/init-influxdb.sh helm/
	@cp -f configs/mqtt-broker/*.conf helm/
	@rm -rf helm/simulation-data
	@cp -rf apps/${SAMPLE_APP}/simulation-data helm/
	@cp -f apps/${SAMPLE_APP}/telegraf-config/*.conf helm
	@cp -f apps/${SAMPLE_APP}/time-series-analytics-config/config.json helm/
	@cp -f configs/telegraf/entrypoint.sh helm/telegraf_entrypoint.sh
	@cp -f configs/nginx/nginx-cert-gen.sh helm/nginx-cert-gen.sh
	@cp -f configs/nginx/nginx.conf helm/nginx.conf
	@sed -i "s/name: .*/name: ${SAMPLE_APP}-sample-app/" "helm/Chart.yaml"
	@sed -i "s/description: .*/description: Helm charts for ${SAMPLE_APP} sample app/" "helm/Chart.yaml"
	@sed -i "s/version: .*/version: ${version}/" "helm/Chart.yaml"
	@sed -i "s/appVersion: .*/appVersion: \"${version}\"/" "helm/Chart.yaml"
	@sed -i "s/SAMPLE_APP: .*/SAMPLE_APP: ${SAMPLE_APP}/" "helm/values.yaml"
	@echo "Helm packages generated"

# Help
.PHONY: help
help:
	@echo "Makefile commands:"
	@echo "  make build                        - Build Docker containers"
	@echo "      No parameters required."
	@echo "  make build_copyleft_sources       - Build Docker containers including copyleft licensed sources"
	@echo "      No parameters required."
	@echo "  make up_mqtt_ingestion            - Start Docker containers using MQTT ingestion"
	@echo "      Mandatory: app (default: wind-turbine-anomaly-detection)"
	@echo "      Optional: num_of_streams (default: 1), number_of_data_points_per_stream, ingestion_interval"
	@echo "      Example: make up_mqtt_ingestion app=wind-turbine-anomaly-detection num_of_streams=2"
	@echo "  make up_opcua_ingestion           - Start Docker containers using OPC UA ingestion"
	@echo "      Mandatory: app (default: wind-turbine-anomaly-detection)"
	@echo "      Optional: num_of_streams (default: 1), number_of_data_points_per_stream, ingestion_interval"
	@echo "      Example: make up_opcua_ingestion app=wind-turbine-anomaly-detection num_of_streams=2"
	@echo "  make down                         - Stop Docker containers and remove volumes"
	@echo "      No parameters required."
	@echo "  make status                       - Show status of deployed containers and check for errors"
	@echo "      No parameters required."
	@echo "  make check_env_variables          - Validate required .env variables"
	@echo "      No parameters required."
	@echo "  make push_images                  - Push the images to docker registry"
	@echo "      Mandatory: DOCKER_REGISTRY (set in .env or as param)"
	@echo "      Example: make push_images DOCKER_REGISTRY=myregistry"
	@echo "  make gen_helm_charts              - Generate Helm packages for the selected sample app"
	@echo "      Mandatory: app (default: wind-turbine-anomaly-detection)"
	@echo "      Optional: version (default: 1.1.0-weekly)"
	@echo "      Example: make gen_helm_charts app=weld-anomaly-detection version=1.2.0"
	@echo "  make help                         - Display this help message"
	@echo "      No parameters required."
