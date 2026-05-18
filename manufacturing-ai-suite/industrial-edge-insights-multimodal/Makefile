#
# Apache v2 license
# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
#

INCLUDE ?= default_INCLUDE
HELM_REGISTRY = oci://registry-1.docker.io/intel
MAKEFLAGS += --no-print-directory

DOCKER_COMPOSE_FILE = ./docker-compose.yml
DOCKER_COMPOSE_VALIDATION_FILE=./docker-compose-validation.override.yml
DOCKER_COMPOSE = docker compose
SECURE_MODE='false'

DRI_MOUNT_PATH := $(shell [ -d /dev/dri ] && [ -n "$$(ls -A /dev/dri 2>/dev/null)" ] && echo "/dev/dri" || echo "/dev/null")
export DRI_MOUNT_PATH

ACCEL_MOUNT_PATH := $(shell [ -d /dev/accel ] && [ -n "$$(ls -A /dev/accel 2>/dev/null)" ] && echo "/dev/accel" || echo "/dev/null")
export ACCEL_MOUNT_PATH

# Define the path to the .env file and scripts
ENV_FILE = ./.env
HELM_PACKAGE_SCRIPT = ./package_helm.sh

include $(ENV_FILE)
export $(shell sed 's/=.*//' $(ENV_FILE))
$(shell chmod 600 .env helm/values.yaml)

# Default values
KEY_LENGTH=3072
DAYS=365
SHA_ALGO="sha384"

# Build Docker containers
.PHONY: build
build:
	@echo "Building Docker containers..."
	$(DOCKER_COMPOSE) build --pull;

.PHONY: build_copyleft_sources
build_copyleft_sources:
	@echo "Building Docker containers including copyleft licensed sources..."
	$(DOCKER_COMPOSE) build --build-arg COPYLEFT_SOURCES=true --pull;

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
	@variables="INFLUXDB_USERNAME INFLUXDB_PASSWORD VISUALIZER_GRAFANA_USER VISUALIZER_GRAFANA_PASSWORD MTX_WEBRTCICESERVERS2_0_USERNAME MTX_WEBRTCICESERVERS2_0_PASSWORD S3_STORAGE_USERNAME S3_STORAGE_PASSWORD"; \
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
			MTX_WEBRTCICESERVERS2_0_USERNAME) \
				if ! echo "$$value" | grep -Eq "^[A-Za-z]{5,}$$"; then \
					echo "MTX_WEBRTCICESERVERS2_0_USERNAME must contain only alphabets and be at least 5 characters minimum"; \
					exit 1; \
				fi \
				;; \
			MTX_WEBRTCICESERVERS2_0_PASSWORD) \
				if ! echo "$$value" | grep -Eq "^[A-Za-z0-9]{10,}$$" || ! echo "$$value" | grep -q "[0-9]" || ! echo "$$value" | grep -q "[A-Za-z]"; then \
					echo "MTX_WEBRTCICESERVERS2_0_PASSWORD length must be a minimum of 10 alphanumeric characters with at least one digit"; \
					exit 1; \
				fi \
				;; \
			S3_STORAGE_USERNAME) \
				if ! echo "$$value" | grep -Eq "^[A-Za-z]{5,}$$"; then \
					echo "S3_STORAGE_USERNAME must contain only alphabets and be at least 5 characters minimum"; \
					exit 1; \
				fi \
				;; \
			S3_STORAGE_PASSWORD) \
				if ! echo "$$value" | grep -Eq "^[A-Za-z0-9]{10,}$$" || ! echo "$$value" | grep -q "[0-9]" || ! echo "$$value" | grep -q "[A-Za-z]"; then \
					echo "S3_STORAGE_PASSWORD length must be a minimum of 10 alphanumeric characters with at least one digit"; \
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
	@echo "Creating UDF deployment tar for weld anomaly detection..."
	@config_dir=$(CURDIR)/configs/time-series-analytics-microservice; \
	tar_file=$(CURDIR)/configs/time-series-analytics-microservice/weld_anomaly_detector.tar; \
	rm -f $$tar_file; \
	cd $$config_dir && \
	folders="udfs tick_scripts"; \
	if [ -d models ] && [ -n "$$(ls -A models 2>/dev/null)" ]; then folders="$$folders models"; fi; \
	tar cf $$tar_file $$folders && \
	echo "Created: $$tar_file"
	@$(MAKE) wait_for_tsam
	@echo "Uploading UDF deployment tar for weld anomaly detection to Time-Series Analytics microservice..."; \
	tar_file=$(CURDIR)/configs/time-series-analytics-microservice/weld_anomaly_detector.tar; \
	response=$$(curl -s -o /tmp/upload_response.json -w "%{http_code}" \
		-X POST https://localhost:${GRAFANA_PORT}/ts-api/udfs/package \
		-F "file=@$$tar_file" \
		-k); \
	if [ "$$response" = "200" ]; then \
		echo "Upload successful (HTTP $$response)."; \
		$(MAKE) post_config; \
	else \
		echo "Upload failed (HTTP $$response). Response:"; \
		cat /tmp/upload_response.json; \
		exit 1; \
	fi

post_config:
	@config_file=$(CURDIR)/configs/time-series-analytics-microservice/config.json; \
	if [ ! -f $$config_file ]; then \
		echo "Error: config.json not found at $$config_file"; \
		exit 1; \
	fi; \
	$(MAKE) wait_for_tsam; \
	echo "Posting config for weld anomaly detection to Time-Series Analytics microservice..."; \
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

.PHONY: up
up: check_env_variables validate_host_ip down
	@export TELEGRAF_INPUT_PLUGIN=$$(if [ $(INCLUDE) = 'validation' ]; then echo "mqtt_consumer:net:cpu:disk:docker:diskio:kernel:mem:processes:swap:system"; else echo "mqtt_consumer"; fi); \
	echo "Starting Docker containers..."; \
	echo "GPU device path set to: $(DRI_MOUNT_PATH) based on its existence"; \
	if [ $(INCLUDE) = 'validation' ]; then \
		$(DOCKER_COMPOSE) -f $(DOCKER_COMPOSE_FILE) -f $(DOCKER_COMPOSE_VALIDATION_FILE) up -d; \
	else \
		$(DOCKER_COMPOSE) up -d; \
	fi; \
	$(MAKE) upload_tar_file

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
	$(eval version := $(shell if [ -n "$(WEEKLY_BUILD_DATE)" ] && [ "$(WEEKLY_BUILD_DATE)" != '""' ]; then echo "$(IMAGE_SUFFIX)-$(WEEKLY_BUILD_DATE)-weekly"; else echo "$(IMAGE_SUFFIX)"; fi))
	@cp -f configs/grafana/* helm/
	@cp -f configs/influxdb/config/*.conf helm/
	@cp -f configs/influxdb/init-influxdb.sh helm/
	@cp -f configs/mqtt-broker/*.conf helm/
	@cp -f configs/telegraf/config/*.conf helm/
	@cp -f configs/telegraf/entrypoint.sh helm/telegraf_entrypoint.sh
	@cp -f configs/nginx/nginx-cert-gen.sh helm/nginx-cert-gen.sh
	@cp -f configs/nginx/nginx.conf helm/nginx.conf
	@cp -f configs/dlstreamer-pipeline-server/config.json helm/dlstreamer-pipeline-server.json
	@sed -i 's/"auto_start": true,/"auto_start": false,/' helm/dlstreamer-pipeline-server.json
	@cp -f configs/seaweedfs-s3/seaweedfs_s3_config.json.template helm/seaweedfs_s3_config.json.template
	@cp -f configs/seaweedfs-s3/s3-init-buckets.sh helm/s3-init-buckets.sh
	@sed -i "s/version: .*/version: ${version}/" "helm/Chart.yaml"
	@sed -i "s/appVersion: .*/appVersion: \"${version}\"/" "helm/Chart.yaml"
	@sed -i "s/weekly_build_date: .*/weekly_build_date: \"$(WEEKLY_BUILD_DATE)\"/" "helm/values.yaml"
	@echo "Helm packages generated with version: ${version}"

# To push the helm charts to docker registry, ensure to configure DOCKER_REGISTRY in .env
# and have logged into that. Applies mainly when one is dealing with internal docker registry.
# If you are using docker hub, ensure to have logged in with `docker login` command
# before running this command.
.PHONY: push_helm_charts
push_helm_charts: gen_helm_charts
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
	@echo "  make build_copyleft_sources       - Build Docker containers including copyleft licensed sources"
	@echo "  make up                           - Start Docker containers"
	@echo "  make down                         - Stop Docker containers"
	@echo "  make clean                        - Remove all stopped containers and unused images"
	@echo "  make push_images                  - Push the images to docker registry"
	@echo "  make gen_helm_charts              - Generate Helm packages for the selected sample app"
	@echo "  make push_helm_charts             - Package and Push Helm charts to docker registry"
	@echo "  make help                         - Display this help message"
