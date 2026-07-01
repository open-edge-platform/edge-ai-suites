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

# ---- Model artifact locations (align with backend/config/model.yaml) --------
MODEL_NAME       ?= yolo11n_polyp
IR_DIR           ?= models/$(MODEL_NAME)/best_openvino_model
IR_MARKER        ?= models/$(MODEL_NAME)/.trained_ok
DEMO_VIDEO       ?= videos/polyp_test.mp4
# Local POC scratch — used to seed the pretrained IR without re-training.
POC_IR_DIR       ?= poc/st2_app/artifacts/yolo11n_xpu/best_openvino_model
POC_DEMO_VIDEO   ?= poc/st1_artifacts/polyp_test.mp4

.PHONY: assets
assets:  ## Seed pretrained IR + demo video from POC (skips training)
	@mkdir -p $(IR_DIR) videos
	@if [ -d $(POC_IR_DIR) ]; then \
		cp -v $(POC_IR_DIR)/best.xml  $(IR_DIR)/; \
		cp -v $(POC_IR_DIR)/best.bin  $(IR_DIR)/; \
		cp -v $(POC_IR_DIR)/metadata.yaml $(IR_DIR)/; \
		echo "externally_seeded_at=$$(date -Is)" > $(IR_MARKER); \
		echo "source=$(POC_IR_DIR)" >> $(IR_MARKER); \
		echo "[assets] seeded IR at $(IR_DIR)"; \
	else \
		echo "[assets] POC IR not found at $(POC_IR_DIR); run 'make backend-bootstrap' to train from scratch"; \
	fi
	@if [ -f $(POC_DEMO_VIDEO) ]; then \
		cp -v $(POC_DEMO_VIDEO) $(DEMO_VIDEO); \
	elif [ -f $(DEMO_VIDEO) ]; then \
		echo "[assets] demo video already present at $(DEMO_VIDEO)"; \
	else \
		echo "[assets] WARN: $(POC_DEMO_VIDEO) missing — supply your own $(DEMO_VIDEO)"; \
	fi

.PHONY: validate-models
validate-models:  ## Sanity-check model files
	@for f in $(IR_DIR)/best.xml $(IR_DIR)/best.bin; do \
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

# ---- Dev-only targets (no Docker) -------------------------------------------

.PHONY: mock-backend
mock-backend:  ## Run the Phase 1 mock backend (offline UI dev)
	@python3 -c "import flask, PIL" 2>/dev/null || ( \
		echo "[mock] Installing mock deps into .venv-mock"; \
		python3 -m venv .venv-mock && \
		. .venv-mock/bin/activate && \
		pip install -q -r backend_mvp/requirements-mock.txt; \
	)
	@if [ -d .venv-mock ]; then . .venv-mock/bin/activate; fi; \
		PORT=5001 python3 -m backend_mvp.mock_server

.PHONY: ui-dev
ui-dev:  ## Run the Vite dev server (proxies to mock-backend on :5001)
	cd ui && npm install && npm run dev

# ---- Backend (Phase 2 — bootstrap orchestrator + streaming inference) -------

BACKEND_VENV     ?= .venv-backend
BACKEND_PY       ?= $(BACKEND_VENV)/bin/python
TORCH_XPU_INDEX  ?= https://download.pytorch.org/whl/xpu

.PHONY: backend-venv
backend-venv:  ## Create .venv-backend with torch+xpu + Ultralytics + OpenVINO
	@if [ ! -d $(BACKEND_VENV) ]; then \
		python3 -m venv $(BACKEND_VENV); \
		$(BACKEND_PY) -m pip install -U pip wheel; \
	fi
	@echo "[backend-venv] installing torch+xpu wheels"
	$(BACKEND_PY) -m pip install --index-url $(TORCH_XPU_INDEX) torch==2.7.1 torchvision==0.22.1
	@echo "[backend-venv] installing backend requirements"
	$(BACKEND_PY) -m pip install -r backend/requirements.txt
	@echo "[backend-venv] ready — activate with 'source $(BACKEND_VENV)/bin/activate'"

.PHONY: backend-bootstrap
backend-bootstrap:  ## Run the cache-first bootstrap (skips train if IR cached)
	@test -x $(BACKEND_PY) || (echo "[backend-bootstrap] run 'make backend-venv' first"; exit 1)
	$(BACKEND_PY) -m backend.main_bootstrap

.PHONY: backend-infer
backend-infer:  ## Run standalone annotated inference on $(DEMO_VIDEO)
	@test -x $(BACKEND_PY) || (echo "[backend-infer] run 'make backend-venv' first"; exit 1)
	@test -f $(IR_DIR)/best.xml || (echo "[backend-infer] IR missing — run 'make assets' or 'make backend-bootstrap'"; exit 1)
	@test -f $(DEMO_VIDEO)      || (echo "[backend-infer] $(DEMO_VIDEO) missing — run 'make assets'"; exit 1)
	@mkdir -p out
	$(BACKEND_PY) -m backend.main_infer --ir $(IR_DIR) --video $(DEMO_VIDEO) \
		--out-video out/annotated.mp4 --out-csv out/per_frame.csv

.PHONY: backend-serve
backend-serve:  ## Run the real Phase 3 Flask server on :5001 (replaces mock-backend)
	@test -x $(BACKEND_PY) || (echo "[backend-serve] run 'make backend-venv' first"; exit 1)
	@echo "[backend-serve] starting on http://0.0.0.0:5001"
	PORT=5001 BACKEND_CONFIG=backend/config/model.yaml $(BACKEND_PY) -m backend.main_server


