# Surgical Instrument — developer workflow targets.
# Run `make help` to see what's available.

SHELL := /bin/bash
.DEFAULT_GOAL := help

# ---- Tunables (override on the CLI: `make up UI_HOST_PORT=9000`) -----------
UI_HOST_PORT       ?= 8080
DETECTION_DEVICE   ?= GPU
COMPOSE            ?= docker compose
ENV_FILE           ?= .env
MQTT_PASSWD_FILE   ?= configs/mqtt_passwd
MQTT_USERNAME      ?= surgical

# ---- Targets ----------------------------------------------------------------

.PHONY: help
help:  ## Show this help
	@awk 'BEGIN {FS = ":.*##"; printf "Available targets:\n"} /^[a-zA-Z_-]+:.*?##/ { printf "  \033[36m%-22s\033[0m %s\n", $$1, $$2 }' $(MAKEFILE_LIST)

.PHONY: env
env:  ## Create .env from .env.example if missing
	@if [ ! -f $(ENV_FILE) ]; then \
		cp configs/.env.example $(ENV_FILE); \
		echo "[env] Created $(ENV_FILE) — edit MQTT_PASSWORD before \`make up\`"; \
	else \
		echo "[env] $(ENV_FILE) already exists"; \
	fi

.PHONY: mqtt-passwd
mqtt-passwd: env  ## Generate configs/mqtt_passwd from MQTT_PASSWORD in .env
	@if [ ! -f $(ENV_FILE) ]; then echo "ERROR: run 'make env' first and set MQTT_PASSWORD"; exit 1; fi
	@. ./$(ENV_FILE); \
	if [ -z "$$MQTT_PASSWORD" ]; then echo "ERROR: MQTT_PASSWORD is empty in $(ENV_FILE)"; exit 1; fi; \
	docker run --rm -i -v "$$(pwd)/configs:/c" eclipse-mosquitto:2 \
		mosquitto_passwd -b -c /c/mqtt_passwd $(MQTT_USERNAME) "$$MQTT_PASSWORD"
	@chmod 600 $(MQTT_PASSWD_FILE)
	@echo "[mqtt-passwd] $(MQTT_PASSWD_FILE) written (user=$(MQTT_USERNAME))"

.PHONY: assets
assets:  ## Fetch / validate model and sample video
	@echo "[assets] TODO (Phase 2): fetch yolo11n IR + polyp_test.mp4 from artifact server"
	@test -f models/yolo_polyp/best.xml || echo "  WARN: models/yolo_polyp/best.xml missing"
	@test -f videos/polyp_test.mp4      || echo "  WARN: videos/polyp_test.mp4 missing"

.PHONY: validate-models
validate-models:  ## Sanity-check model files
	@for f in models/yolo_polyp/best.xml models/yolo_polyp/best.bin models/yolo_polyp/yolo_polyp.json; do \
		if [ ! -f "$$f" ]; then echo "MISSING $$f"; exit 1; fi; \
		echo "OK $$f"; \
	done

.PHONY: config
config:  ## Validate docker-compose configuration
	@$(COMPOSE) config >/dev/null && echo "[config] docker-compose.yaml is valid"

.PHONY: build
build:  ## Build all service images
	$(COMPOSE) build

.PHONY: up
up: env  ## Bring the stack up (detached)
	@test -f $(MQTT_PASSWD_FILE) || (echo "ERROR: run 'make mqtt-passwd' first"; exit 1)
	UI_HOST_PORT=$(UI_HOST_PORT) DETECTION_DEVICE=$(DETECTION_DEVICE) \
		$(COMPOSE) --env-file $(ENV_FILE) up -d
	@echo "[up] UI:    http://localhost:$(UI_HOST_PORT)"

.PHONY: ps
ps:  ## Show running services
	$(COMPOSE) ps

.PHONY: logs
logs:  ## Tail logs for all services
	$(COMPOSE) logs -f --tail=100

.PHONY: down
down:  ## Stop and remove containers
	$(COMPOSE) down

.PHONY: clean
clean: down  ## Remove containers, named volumes, and built images
	$(COMPOSE) down -v --rmi local || true
	@echo "[clean] done"

.PHONY: port-audit
port-audit:  ## Assert only one host-published port exists (UI:8080)
	@N=$$($(COMPOSE) config | awk '/^[[:space:]]+ports:/{flag=1;next} /^[[:space:]]+[a-z]+:/{flag=0} flag && /^[[:space:]]+- /{count++} END{print count+0}'); \
	if [ "$$N" -ne 1 ]; then echo "FAIL: expected 1 published port, found $$N"; exit 1; fi; \
	echo "PASS: exactly 1 published port"
