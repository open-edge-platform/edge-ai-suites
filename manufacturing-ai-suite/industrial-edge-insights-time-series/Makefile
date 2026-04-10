#
# Apache v2 license
# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
#

DEFAULT_SAMPLE_APP := wind-turbine-anomaly-detection
SAMPLE_APP_LIST := wind-turbine-anomaly-detection weld-anomaly-detection
HELM_REGISTRY := oci://registry-1.docker.io/intel
MAKEFLAGS += --no-print-directory

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
DRI_MOUNT_PATH := $(shell [ -d /dev/dri ] && [ -n "$$(ls -A /dev/dri 2>/dev/null)" ] && echo "/dev/dri" || echo "/dev/null")
export DRI_MOUNT_PATH
$(shell chmod 600 .env helm/values.yaml)

# Build Docker containers
.PHONY: build
build:
	@echo "Building Docker containers..."
	$(DOCKER_COMPOSE) build --pull;

.PHONY: build_copyleft_sources
build_copyleft_sources:
	@echo "Building Docker containers including copyleft licensed sources..."
	$(DOCKER_COMPOSE) build --build-arg COPYLEFT_SOURCES=true --pull;

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

wait_for_tsam:
	@echo "Waiting for Time-Series Analytics microservice to be accessible..."; \
	max_retries=30; \
	retry=0; \
	until [ "$$(curl -sk -o /dev/null -w '%{http_code}' https://localhost:3000/ts-api/health)" != "000" ]; do \
		retry=$$((retry + 1)); \
		if [ $$retry -ge $$max_retries ]; then \
			echo "Timed out waiting for Time-Series Analytics microservice after $$max_retries attempts."; \
			exit 1; \
		fi; \
		echo "  Not accessible yet (attempt $$retry/$$max_retries), retrying in 5s..."; \
		sleep 5; \
	done; \
	echo "Time-Series Analytics microservice is accessible."

upload_tar_file:
	@echo "Creating UDF deployment tar for $(SAMPLE_APP)..."
	@config_dir=$(CURDIR)/apps/$(SAMPLE_APP)/time-series-analytics-config; \
	tar_file=$(CURDIR)/apps/$(SAMPLE_APP)/time-series-analytics-config/$(SAMPLE_APP).tar; \
	rm -f $$tar_file; \
	cd $$config_dir && \
	folders="udfs tick_scripts"; \
	if [ -d models ] && [ -n "$$(ls -A models 2>/dev/null)" ]; then folders="$$folders models"; fi; \
	tar cf $$tar_file $$folders && \
	echo "Created: $$tar_file"
	@$(MAKE) wait_for_tsam
	@echo "Uploading UDF deployment tar for $(SAMPLE_APP) to Time-Series Analytics microservice..."; \
	tar_file=$(CURDIR)/apps/$(SAMPLE_APP)/time-series-analytics-config/$(SAMPLE_APP).tar; \
	response=$$(curl -s -o /tmp/upload_response.json -w "%{http_code}" \
		-X POST https://localhost:${GRAFANA_PORT}/ts-api/udfs/package \
		-F "file=@$$tar_file" \
		-k); \
	if [ "$$response" = "200" ]; then \
		echo "Upload successful (HTTP $$response)."; \
		$(MAKE) post_config app=$(SAMPLE_APP); \
	else \
		echo "Upload failed (HTTP $$response). Response:"; \
		cat /tmp/upload_response.json; \
		exit 1; \
	fi

post_config:
	@config_file=$(CURDIR)/apps/$(SAMPLE_APP)/time-series-analytics-config/config.json; \
	if [ ! -f $$config_file ]; then \
		echo "Error: config.json not found at $$config_file"; \
		exit 1; \
	fi; \
	$(MAKE) wait_for_tsam; \
	echo "Posting config for $(SAMPLE_APP) to Time-Series Analytics microservice..."; \
	response=$$(curl -s -o /tmp/config_response.json -w "%{http_code}" \
		-X POST https://localhost:${GRAFANA_PORT}/ts-api/config \
		-H 'accept: application/json' \
		-H 'Content-Type: application/json' \
		-d @$$config_file \
		-k); \
	if [ "$$response" = "200" ]; then \
		echo "Config posted successfully (HTTP $$response)."; \
	else \
		echo "Config post failed (HTTP $$response). Response:"; \
		cat /tmp/config_response.json; \
		exit 1; \
	fi

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
	echo "GPU device path set to: $(DRI_MOUNT_PATH) based on its existence"; \
	if [ $(INCLUDE) = 'validation' ]; then \
		$(DOCKER_COMPOSE) -f $(DOCKER_COMPOSE_FILE) -f $(DOCKER_COMPOSE_VALIDATION_FILE) up --scale ia-opcua-server=0 -d; \
	else \
		for i in $$(seq 1 $(num_of_streams)); do \
			echo "Starting ia-mqtt-publisher instance $$i for SAMPLE_APP: $$SAMPLE_APP";\
			$(DOCKER_COMPOSE) run -d --name ia-mqtt-publisher-$$i -e INSTANCE_ID=$$i ia-mqtt-publisher; \
		done; \
		$(DOCKER_COMPOSE) up --scale ia-opcua-server=0 -d $(shell $(DOCKER_COMPOSE) config --services | grep -v ia-mqtt-publisher); \
	fi; \
	$(MAKE) upload_tar_file app=$(SAMPLE_APP);

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
	echo "GPU device path set to: $(DRI_MOUNT_PATH) based on its existence"; \
	if [ $(INCLUDE) = 'validation' ]; then \
		$(DOCKER_COMPOSE) -f $(DOCKER_COMPOSE_FILE) -f $(DOCKER_COMPOSE_VALIDATION_FILE) up --scale ia-mqtt-publisher=0 -d ;\
	else \
		$(DOCKER_COMPOSE) up --scale ia-opcua-server=$(num_of_streams) --scale ia-mqtt-publisher=0 -d; \
	fi; \
	$(MAKE) upload_tar_file app=$(SAMPLE_APP);


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

# To push the docker images to docker registry, ensure to configure DOCKER_REGISTRY in .env
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
	$(eval version := $(shell if [ -n "$(WEEKLY_BUILD_DATE)" ] && [ "$(WEEKLY_BUILD_DATE)" != '""' ]; then echo "$(IMAGE_SUFFIX)-$(WEEKLY_BUILD_DATE)-weekly"; else echo "$(IMAGE_SUFFIX)"; fi))
	@cp -f configs/grafana/dashboards/*.yml helm/
	@cp -f apps/${SAMPLE_APP}/grafana-dashboard.json helm/
	@cp -f configs/influxdb/config/*.conf helm/
	@cp -f configs/influxdb/init-influxdb.sh helm/
	@cp -f configs/mqtt-broker/*.conf helm/
	@rm -rf helm/simulation-data
	@cp -rf apps/${SAMPLE_APP}/simulation-data helm/
	@cp -f apps/${SAMPLE_APP}/telegraf-config/*.conf helm
	@cp -f configs/telegraf/entrypoint.sh helm/telegraf_entrypoint.sh
	@cp -f configs/nginx/nginx-cert-gen.sh helm/nginx-cert-gen.sh
	@cp -f configs/nginx/nginx.conf helm/nginx.conf
	@sed -i "s/name: .*/name: ${SAMPLE_APP}-sample-app/" "helm/Chart.yaml"
	@sed -i "s/description: .*/description: Helm charts for ${SAMPLE_APP} sample app/" "helm/Chart.yaml"
	@sed -i "s/version: .*/version: ${version}/" "helm/Chart.yaml"
	@sed -i "s/appVersion: .*/appVersion: \"${version}\"/" "helm/Chart.yaml"
	@sed -i "s/SAMPLE_APP: .*/SAMPLE_APP: ${SAMPLE_APP}/" "helm/values.yaml"
	@sed -i "s/weekly_build_date: .*/weekly_build_date: \"$(WEEKLY_BUILD_DATE)\"/" "helm/values.yaml"
	@echo "Helm packages generated with version: ${version}"

# To push the helm charts to docker registry, ensure to configure DOCKER_REGISTRY in .env
# and have logged into that. Applies mainly when one is dealing with internal docker registry.
# If you are using docker hub, ensure to have logged in with `docker login` command
# before running this command.
.PHONY: push_helm_charts
push_helm_charts: gen_helm_charts
	@echo "Packaging Helm chart for ${SAMPLE_APP}"
	@mkdir -p helm-packages
	@rm -f helm-packages/*.tgz
	@pkg_file=$$(helm package helm/ -d helm-packages/ | awk '{print $$NF}'); \
	echo "Helm chart packaged successfully: $$pkg_file"; \
	helm push $$pkg_file $(HELM_REGISTRY) && echo "Helm chart package pushed successfully to $(HELM_REGISTRY)"; \
	cd ..
# Help
.PHONY: help
help:
	@echo "Makefile commands:"
	@echo "  make build                        - Build Docker containers"
	@echo "      No parameters required."
	@echo "  make build_copyleft_sources       - Build Docker containers including copyleft licensed sources"
	@echo "      No parameters required."
	@echo "  make up_mqtt_ingestion            - Start Docker containers using MQTT ingestion"
	@echo "      Optional: app (default: wind-turbine-anomaly-detection), num_of_streams (default: 1), number_of_data_points_per_stream, ingestion_interval"
	@echo "      Example: make up_mqtt_ingestion app=wind-turbine-anomaly-detection num_of_streams=2"
	@echo "  make up_opcua_ingestion           - Start Docker containers using OPC UA ingestion"
	@echo "      Optional: app (default: wind-turbine-anomaly-detection), num_of_streams (default: 1), number_of_data_points_per_stream, ingestion_interval"
	@echo "      Example: make up_opcua_ingestion app=wind-turbine-anomaly-detection num_of_streams=2"
	@echo "  make down                         - Stop Docker containers and remove volumes"
	@echo "      No parameters required."
	@echo "  make status                       - Show status of deployed containers and check for errors"
	@echo "      No parameters required."
	@echo "  make check_env_variables          - Validate required .env variables"
	@echo "      No parameters required."
	@echo "  make push_images                  - Push the images to docker registry"
	@echo "      Optional: DOCKER_REGISTRY (set in .env or as param)"
	@echo "      Example: make push_images DOCKER_REGISTRY=myregistry"
	@echo "  make gen_helm_charts              - Generate Helm packages for the selected sample app"
	@echo "      Optional: app (default: wind-turbine-anomaly-detection)"
	@echo "      Example: make gen_helm_charts app=weld-anomaly-detection"
	@echo "  make push_helm_charts              - Package and push Helm charts to docker registry"
	@echo "      Optional: app (default: wind-turbine-anomaly-detection)"
	@echo "      Example: make push_helm_charts app=weld-anomaly-detection"
	@echo "  make help                         - Display this help message"
	@echo "      No parameters required."

