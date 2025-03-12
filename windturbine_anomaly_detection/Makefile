# Copyright Intel Corporation

DOCKER_COMPOSE_FILE = ./docker-compose.yml
DOCKER_COMPOSE_SECURE_MODE_FILE = ./docker-compose-secure-mode.override.yml
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
	$(DOCKER_COMPOSE) build

# Run Docker containers

.PHONY: up_mqtt_ingestion
up_mqtt_ingestion: down
	@export TELEGRAF_INPUT_PLUGIN="mqtt_consumer"; \
    if [ $(SECURE_MODE) = 'false' ]; then \
        echo "Starting Docker containers..."; \
        $(DOCKER_COMPOSE) up --scale ia-opcua-server=0 -d ;\
    else \
        echo "Generating Certificates"; \
        $(CERT_SCRIPT); \
        echo "Certificates generated"; \
        echo "Starting Docker containers..."; \
        $(DOCKER_COMPOSE) -f $(DOCKER_COMPOSE_FILE) -f $(DOCKER_COMPOSE_SECURE_MODE_FILE) up --scale ia-opcua-server=0 -d; \
    fi

# Run Docker containers
.PHONY: up_opcua_ingestion
up_opcua_ingestion: down
	@export TELEGRAF_INPUT_PLUGIN="opcua"; \
	if [ $(SECURE_MODE) = 'false' ]; then \
		echo "Starting Docker containers..."; \
		$(DOCKER_COMPOSE) up --scale ia-mqtt-publisher=0 -d ;\
	else \
		echo "Generating Certificates"; \
		$(CERT_SCRIPT); \
		echo "Certificates generated"; \
		echo "Starting Docker containers..."; \
		$(DOCKER_COMPOSE) -f $(DOCKER_COMPOSE_FILE) -f $(DOCKER_COMPOSE_SECURE_MODE_FILE) up --scale ia-mqtt-publisher=0 -d; \
	fi

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
push_images:
	@echo "Pushing the images to docker registry"
	docker compose -f $(DOCKER_COMPOSE_FILE) push

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
