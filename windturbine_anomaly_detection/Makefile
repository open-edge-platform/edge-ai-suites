# Copyright Intel Corporation

DOCKER_COMPOSE_FILE = ./docker-compose.yml
DOCKER_COMPOSE_SECURE_MODE_FILE = ./docker-compose-secure-mode.override.yml
DOCKER_COMPOSE_WINDTURBINE = ./docker-compose-windturbine.override.yml
DOCKER_COMPOSE = docker compose

STACK_PATH = $(PWD)/../../stack

# Define the path to the .env file
ENV_FILE = $(STACK_PATH)/.env
CERT_SCRIPT = ./../tools/cert_gen.sh

include $(ENV_FILE)
export $(shell sed 's/=.*//' $(ENV_FILE))

# Default target
.PHONY: all
all: build up

# Build Docker containers
.PHONY: build
build:
	@echo "Building Docker containers..."
	cd $(STACK_PATH); \
	$(DOCKER_COMPOSE) -f $(DOCKER_COMPOSE_FILE) -f $(PWD)/$(DOCKER_COMPOSE_WINDTURBINE) build

# Run Docker containers
.PHONY: up
up:
	@if [ $(SECURE_MODE) = 'false' ]; then \
		echo "Starting Docker containers..."; \
		$(DOCKER_COMPOSE) -f $(STACK_PATH)/$(DOCKER_COMPOSE_FILE) -f $(DOCKER_COMPOSE_WINDTURBINE) up -d --scale ia-mqtt-publisher=0; \
	else \
		cd $(STACK_PATH); \
		echo "Generating Certificates"; \
		$(CERT_SCRIPT); \
		echo "Certificates generated"; \
		echo "Starting Docker containers..."; \
		$(DOCKER_COMPOSE) -f $(STACK_PATH)/$(DOCKER_COMPOSE_FILE) -f $(STACK_PATH)/$(DOCKER_COMPOSE_SECURE_MODE_FILE) -f $(PWD)/$(DOCKER_COMPOSE_WINDTURBINE) up -d --scale ia-mqtt-publisher=0; \
	fi

# Stop Docker containers
.PHONY: down
down:
	@echo "Stopping Docker containers..."
	$(DOCKER_COMPOSE) -f $(STACK_PATH)/$(DOCKER_COMPOSE_FILE) -f $(DOCKER_COMPOSE_WINDTURBINE) down -v

# Restart Docker containers
.PHONY: restart
restart: down up

# Remove all stopped containers and unused images
.PHONY: clean
clean:
	@echo "Cleaning up unused Docker resources..."
	docker system prune -f

# Push the docker images to docker registry
push_images:
	@echo "Pushing the images to docker registry"
	docker compose -f $(STACK_PATH)/$(DOCKER_COMPOSE_FILE) -f $(DOCKER_COMPOSE_WINDTURBINE) push

# Help
.PHONY: help
help:
	@echo "Makefile commands:"
	@echo "  make build    - Build Docker containers"
	@echo "  make up       - Start Docker containers"
	@echo "  make down     - Stop Docker containers"
	@echo "  make restart  - Restart Docker containers"
	@echo "  make clean    - Remove all stopped containers and unused images"
	@echo "  make push_images     - Push the images to docker registry"
	@echo "  make help     - Display this help message"