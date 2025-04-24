# Copyright Intel Corporation

TARGET ?= default_target

DOCKER_COMPOSE_FILE = ./docker-compose.yml
DOCKER_COMPOSE_SECURE_MODE_FILE = ./docker-compose-secure-mode.override.yml
DOCKER_COMPOSE_VALIDATION_FILE=./docker-compose-validation.override.yml
DOCKER_COMPOSE = docker compose

# Define the path to the .env file and scripts
ENV_FILE = ./.env
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
	@rm -f ../../tools/opcua_server/windturbine_data.csv

# Run Docker containers

.PHONY: up_mqtt_ingestion
up_mqtt_ingestion: down
	@export TELEGRAF_INPUT_PLUGIN=$$(if [ $(TARGET) = 'validation' ]; then echo "mqtt_consumer:net:cpu:disk:docker:diskio:kernel:mem:processes:swap:system"; else echo "mqtt_consumer"; fi); \
    if [ $(SECURE_MODE) = 'false' ]; then \
        echo "Starting Docker containers..."; \
        $(DOCKER_COMPOSE) up --scale ia-opcua-server=0 -d ;\
	else \
		echo "Generating Certificates"; \
		$(CERT_SCRIPT); \
		echo "Certificates generated"; \
		echo "Starting Docker containers..."; \
		if [ $(TARGET) = 'validation' ]; then \
			$(DOCKER_COMPOSE) -f $(DOCKER_COMPOSE_FILE) -f $(DOCKER_COMPOSE_SECURE_MODE_FILE) -f $(DOCKER_COMPOSE_VALIDATION_FILE) up --scale ia-opcua-server=0 -d; \
		else \
			$(DOCKER_COMPOSE) -f $(DOCKER_COMPOSE_FILE) -f $(DOCKER_COMPOSE_SECURE_MODE_FILE) up --scale ia-opcua-server=0 -d; \
		fi \
    fi
	${MAKE} status

# Run Docker containers
.PHONY: up_opcua_ingestion
up_opcua_ingestion: down
	@export TELEGRAF_INPUT_PLUGIN=$$(if [ $(TARGET) = 'validation' ]; then echo "opcua:net:cpu:disk:docker:diskio:kernel:mem:processes:swap:system"; else echo "opcua"; fi); \
	if [ $(SECURE_MODE) = 'false' ]; then \
		echo "Starting Docker containers..."; \
		$(DOCKER_COMPOSE) up --scale ia-mqtt-publisher=0 -d ;\
	else \
		echo "Generating Certificates"; \
		$(CERT_SCRIPT); \
		echo "Certificates generated"; \
		echo "Starting Docker containers..."; \
		if [ $(TARGET) = 'validation' ]; then \
			$(DOCKER_COMPOSE) -f $(DOCKER_COMPOSE_FILE) -f $(DOCKER_COMPOSE_SECURE_MODE_FILE) -f $(DOCKER_COMPOSE_VALIDATION_FILE) up --scale ia-mqtt-publisher=0 -d; \
		else \
			$(DOCKER_COMPOSE) -f $(DOCKER_COMPOSE_FILE) -f $(DOCKER_COMPOSE_SECURE_MODE_FILE) up --scale ia-mqtt-publisher=0 -d; \
		fi \
	fi
	${MAKE} status

# Status of the deployed containers
.PHONY: status
status:
	@echo "Status of the deployed containers..."; \
	docker ps -a --filter "name=^ia-" --format "table {{.ID}}\t{{.Names}}\t{{.Status}}\t{{.Ports}}"; \
	echo "Wait for few seconds for deployed containers to come up fully..."; \
	sleep 10; \
	containers=$$(docker ps -a --filter "name=^ia-" --format "{{.Names}}"); \
	for container in $$containers; do \
		errors=$$(docker logs --tail 10 $$container 2>&1 | grep -i "error"); \
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
		fi; \
	done \
	
# Stop Docker containers
.PHONY: down
down:
	@echo "Stopping Docker containers..."
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
	docker build -t $(DOCKER_REGISTRY)ia-time-series-analytics-microservice-windturbine:1.0.0 time_series_analytics_microservice/.
	docker push $(DOCKER_REGISTRY)ia-time-series-analytics-microservice-windturbine:1.0.0

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
