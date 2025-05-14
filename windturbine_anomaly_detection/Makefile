#
# Apache v2 license
# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
#

INCLUDE ?= default_INCLUDE

DOCKER_COMPOSE_FILE = ./docker-compose.yml
DOCKER_COMPOSE_SECURE_MODE_FILE = ./docker-compose-secure-mode.override.yml
DOCKER_COMPOSE_VALIDATION_FILE=./docker-compose-validation.override.yml
DOCKER_COMPOSE = docker compose
SECURE_MODE='false'

# Define the path to the .env file and scripts
ENV_FILE = ./.env
MODEL_REGISTRY_ENV_FILE = ./model_registry/docker/.env
CERT_SCRIPT = ./../../tools/cert_gen.sh
HELM_PACKAGE_SCRIPT = ./package_helm.sh

include $(ENV_FILE)
export $(shell sed 's/=.*//' $(ENV_FILE))

# Build Docker containers
.PHONY: build
build:
	@echo "Building Docker containers..."
	@cp -f ../../tools/mqtt/publisher/input_data/windturbine/windturbine_data.csv ../../tools/opcua_server/windturbine_data.csv
	$(DOCKER_COMPOSE) build
	@if [ "$(INCLUDE)" = "model_registry" ]; then \
		echo "Building Model Registry Docker containers..."; \
		cd ./model_registry/docker; \
		if [ ! -f .env ]; then \
			cp .env.template .env; \
		fi; \
		docker compose build; \
	fi
	@rm -f ../../tools/opcua_server/windturbine_data.csv



# Check if multiple particular variables in .env are assigned with values
.PHONY: check_env_variables
check_env_variables:
	@echo "Checking if username/password in .env are assigned..."
	@variables="INFLUXDB_USERNAME INFLUXDB_PASSWORD VISUALIZER_GRAFANA_USER VISUALIZER_GRAFANA_PASSWORD"; \
	for variable_name in $$variables; do \
		value=$$(grep -E "^$$variable_name=" $(ENV_FILE) | cut -d'=' -f2); \
		if [ -z "$$value" ]; then \
			echo "'$$variable_name' in $(ENV_FILE) is unassigned."; \
			exit 1; \
		fi; \
	done;
	@if [ "$(INCLUDE)" = "model_registry" ]; then \
		vars="MR_PSQL_PASSWORD MR_MINIO_ACCESS_KEY MR_MINIO_SECRET_KEY"; \
		for variable_name in $$vars; do \
			value=$$(grep -E "^$$variable_name=" $(MODEL_REGISTRY_ENV_FILE) | cut -d'=' -f2); \
			if [ -z "$$value" ]; then \
				echo "'$$variable_name' in $(MODEL_REGISTRY_ENV_FILE) is unassigned."; \
				exit 1; \
			fi; \
		done; \
	fi

.PHONY: up_mqtt_ingestion
up_mqtt_ingestion: down check_env_variables
	@export TELEGRAF_INPUT_PLUGIN=$$(if [ $(INCLUDE) = 'validation' ]; then echo "mqtt_consumer:net:cpu:disk:docker:diskio:kernel:mem:processes:swap:system"; else echo "mqtt_consumer"; fi); \
	if [ $(SECURE_MODE) = 'false' ]; then \
		if [ $(INCLUDE) = 'model_registry' ]; then \
			${MAKE} init_mraas; \
		fi; \
		echo "Starting Docker containers..."; \
		if [ $(INCLUDE) = 'validation' ]; then \
			$(DOCKER_COMPOSE) -f $(DOCKER_COMPOSE_FILE) -f $(DOCKER_COMPOSE_VALIDATION_FILE) up --scale ia-opcua-server=0 -d ;\
		else \
			$(DOCKER_COMPOSE) up --scale ia-opcua-server=0 -d ;\
		fi \
	else \
		echo "Generating Certificates"; \
		$(CERT_SCRIPT); \
		echo "Certificates generated"; \
		if [ $(INCLUDE) = 'model_registry' ]; then \
			${MAKE} init_mraas; \
		fi; \
		echo "Starting Docker containers..."; \
		if [ $(INCLUDE) = 'validation' ]; then \
			$(DOCKER_COMPOSE) -f $(DOCKER_COMPOSE_FILE) -f $(DOCKER_COMPOSE_SECURE_MODE_FILE) -f $(DOCKER_COMPOSE_VALIDATION_FILE) up --scale ia-opcua-server=0 -d; \
		else \
			$(DOCKER_COMPOSE) -f $(DOCKER_COMPOSE_FILE) -f $(DOCKER_COMPOSE_SECURE_MODE_FILE) up --scale ia-opcua-server=0 -d; \
		fi \
	fi; \
	if [ $(INCLUDE) = 'model_registry' ]; then \
		${MAKE} mraas_up; \
	fi; \

# Run Docker containers
.PHONY: up_opcua_ingestion
up_opcua_ingestion: down check_env_variables
	@export TELEGRAF_INPUT_PLUGIN=$$(if [ $(INCLUDE) = 'validation' ]; then echo "opcua:net:cpu:disk:docker:diskio:kernel:mem:processes:swap:system"; else echo "opcua"; fi); \
	if [ $(SECURE_MODE) = 'false' ]; then \
		if [ $(INCLUDE) = 'model_registry' ]; then \
			${MAKE} init_mraas; \
		fi; \
		echo "Starting Docker containers..."; \
		if [ $(INCLUDE) = 'validation' ]; then \
        	$(DOCKER_COMPOSE) -f $(DOCKER_COMPOSE_FILE) -f $(DOCKER_COMPOSE_VALIDATION_FILE) up --scale ia-mqtt-publisher=0 -d ;\
		else \
			$(DOCKER_COMPOSE) up --scale ia-mqtt-publisher=0 -d ;\
		fi \
	else \
		echo "Generating Certificates"; \
		$(CERT_SCRIPT); \
		echo "Certificates generated"; \
		if [ $(INCLUDE) = 'model_registry' ]; then \
			${MAKE} init_mraas; \
		fi; \
		echo "Starting Docker containers..."; \
		if [ $(INCLUDE) = 'validation' ]; then \
			$(DOCKER_COMPOSE) -f $(DOCKER_COMPOSE_FILE) -f $(DOCKER_COMPOSE_SECURE_MODE_FILE) -f $(DOCKER_COMPOSE_VALIDATION_FILE) up --scale ia-mqtt-publisher=0 -d; \
		else \
			$(DOCKER_COMPOSE) -f $(DOCKER_COMPOSE_FILE) -f $(DOCKER_COMPOSE_SECURE_MODE_FILE) up --scale ia-mqtt-publisher=0 -d; \
		fi \
	fi; \
	if [ $(INCLUDE) = 'model_registry' ]; then \
		${MAKE} mraas_up; \
	fi; \

.PHONY: init_mraas
init_mraas:
	@echo "Initializing Model Registry Docker containers..."; \
	cd ./model_registry/docker; \
	sudo rm -rf Certificates; \
	sed -i -e "s|ENABLE_HTTPS_MODE=.*|ENABLE_HTTPS_MODE=$(SECURE_MODE)|g" .env; \
	sudo ./../scripts/init_mr_data_dirs.sh; \
	sed -i -e "s|- mr.*|- timeseriessoftware_timeseries_network|g" docker-compose.yml; \
	sed -i -e "s|mr:.*|timeseriessoftware_timeseries_network:|g" docker-compose.yml; \
	sed -i -e "s|driver:.*|external: true|g" docker-compose.yml; \
	if [ $(SECURE_MODE) = 'true' ]; then \
		cp ./../scripts/generate_ssl_files.sh .; \
		./generate_ssl_files.sh; \
		sudo mkdir -p ./../../Certificates/model_registry; \
		sudo cp ./Certificates/ssl/server-ca.crt ./../../Certificates/model_registry/server-ca.crt; \
		sudo chown $(TIMESERIES_UID):$(TIMESERIES_UID) ./../../Certificates/model_registry/server-ca.crt; \
	fi

.PHONY: mraas_up
mraas_up:
	@echo "Starting Model Registry Docker containers..."; \
	cd ./model_registry/docker; \
	docker compose up -d


# Status of the deployed containers
.PHONY: status
status:
	@echo "Status of the deployed containers..."; \
	docker ps -a --filter "name=^ia-" --format "table {{.ID}}\t{{.Names}}\t{{.Status}}\t{{.Ports}}"; \
	echo "Parsing the logs of all containers to catch any error messages..."; \
	sleep 10; \
	containers=$$(docker ps -a --filter "name=^ia-" --format "{{.Names}}"); \
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
	
# Stop Docker containers
.PHONY: down
down:
	@echo "Stopping Docker containers..."
	echo "Checking if Model Registry container is running..."; 
	@if [ -n $$(docker ps --filter "name=model-registry" --filter "status=running" --format "{{.Names}}") ]; then \
		echo "Stopping Model Registry container..."; \
		cd ./model_registry/docker; \
		if [ ! -f .env ]; then \
			cp .env.template .env; \
		fi; \
		docker compose down -v; \
	fi; 
	$(DOCKER_COMPOSE) -f $(DOCKER_COMPOSE_FILE)  down -v

# Remove all stopped containers and unused images
.PHONY: clean
clean:
	@echo "Cleaning up unused Docker resources..."
	docker system prune -f

# Push the docker images to docker registry
push_images: build
	bash ./package_helm.sh
	@echo "Pushing the images to docker registry"
	docker compose -f $(DOCKER_COMPOSE_FILE) push
	docker tag ia-cert-generator:1.0.0 $(DOCKER_REGISTRY)ia-cert-generator:1.0.0 
	docker push $(DOCKER_REGISTRY)ia-cert-generator:1.0.0

# Generate helm packages
.PHONY: gen_helm_charts
gen_helm_charts:
	@echo "Generating Helm packages"
	$(HELM_PACKAGE_SCRIPT)
	@echo "Helm packages generated"

# Help
.PHONY: help
help:
	@echo "Makefile commands:"
	@echo "  make build    - Build Docker containers"
	@echo "  make up_mqtt_ingestion     - Start Docker containers using mqtt ingestion"
	@echo "  make up_opcua_ingestion    - Start Docker containers using opcua ingestion"
	@echo "  make down     - Stop Docker containers"
	@echo "  make restart  - Restart Docker containers"
	@echo "  make clean    - Remove all stopped containers and unused images"
	@echo "  make push_images     - Push the images to docker registry"
	@echo "  make gen_helm_charts	- Generate helm packages"
	@echo "  make help     - Display this help message"
