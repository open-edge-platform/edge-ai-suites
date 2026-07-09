# Surgical Instrument — developer workflow targets.
# Run `make help` to see what's available.

SHELL := /bin/bash
.DEFAULT_GOAL := help

# ---- Tunables (override on the CLI: `make up UI_HOST_PORT=9000`) -----------
UI_HOST_PORT       ?= 8080
DETECTION_DEVICE   ?= xpu
COMPOSE            ?= docker compose
# Render/video GIDs are auto-detected from the host so /dev/dri passthrough
# works without editing this file. Override on the CLI if needed.
RENDER_GID         ?= $(shell getent group render 2>/dev/null | cut -d: -f3)
VIDEO_GID          ?= $(shell getent group video  2>/dev/null | cut -d: -f3)

# ---- Targets ----------------------------------------------------------------

.PHONY: help
help:  ## Show this help
	@awk 'BEGIN {FS = ":.*##"; printf "Available targets:\n"} /^[a-zA-Z_-]+:.*?##/ { printf "  \033[36m%-22s\033[0m %s\n", $$1, $$2 }' $(MAKEFILE_LIST)

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

# Print the URLs the user can hit. `docker compose up -d` already blocks on
# `depends_on: condition: service_healthy`, so by the time we get here the
# backend is healthy and nginx is listening — no separate wait target needed.
define _print_urls
	@LAN_IP=$$(hostname -I 2>/dev/null | awk '{print $$1}'); \
	echo ""; \
	echo "  UI is up.  Open one of:"; \
	echo "    http://localhost:$(UI_HOST_PORT)      (from this box)"; \
	if [ -n "$$LAN_IP" ]; then \
	  echo "    http://$$LAN_IP:$(UI_HOST_PORT)   (from another machine on the LAN)"; \
	fi; \
	echo ""; \
	echo "  Tip: 'make up UI_HOST_PORT=80' publishes on the standard HTTP port"; \
	echo "       so the URL becomes plain http://<host>/ (no :port suffix)."; \
	echo ""
endef

.PHONY: up
up:  ## First-boot: build images + start stack. May take 20-35 min if no cached IR.
	UI_HOST_PORT=$(UI_HOST_PORT) DETECTION_DEVICE=$(DETECTION_DEVICE) \
	RENDER_GID=$(RENDER_GID) VIDEO_GID=$(VIDEO_GID) \
		$(COMPOSE) up -d --build
	@echo "[up] First boot may take 20-35 min while YOLO11n trains on the iGPU."
	@echo "[up] Follow progress: make logs"
	$(_print_urls)

.PHONY: run
run:  ## Fast subsequent boot: start stack without rebuild. Requires cached IR.
	@test -f $(IR_DIR)/best.xml -a -f $(IR_MARKER) || ( \
		echo "[run] No cached IR at $(IR_DIR)/ — run 'make up' first for first-boot train,"; \
		echo "[run] or 'make assets' to seed IR from POC."; \
		exit 1)
	UI_HOST_PORT=$(UI_HOST_PORT) DETECTION_DEVICE=$(DETECTION_DEVICE) \
	RENDER_GID=$(RENDER_GID) VIDEO_GID=$(VIDEO_GID) \
		$(COMPOSE) up -d
	$(_print_urls)

# ---- v4l2 camera passthrough (slice A) --------------------------------------
# A hardcoded `/dev/videoN` in docker-compose.yaml would fail on hosts with no
# camera. Instead we detect the devices at run-time and inject them via a
# generated compose override, which is git-ignored.
CAMERA_OVERRIDE ?= docker-compose.camera.override.yaml

.PHONY: list-cameras
list-cameras:  ## List /dev/video* devices visible on this host
	@ls -la /dev/video* 2>/dev/null || echo "[list-cameras] no /dev/video* present"

.PHONY: up-with-camera
up-with-camera:  ## Start stack with all attached /dev/video* passed through to the pipeline
	@CAMS=$$(ls /dev/video* 2>/dev/null); \
	if [ -z "$$CAMS" ]; then \
		echo "[up-with-camera] no /dev/video* on this host — plug a UVC/Basler camera in first,"; \
		echo "                  or run 'make up' for the recorded-video flow."; \
		exit 1; \
	fi; \
	echo "# Auto-generated by 'make up-with-camera'. Do not edit; do not commit." > $(CAMERA_OVERRIDE); \
	echo "services:"                                                          >> $(CAMERA_OVERRIDE); \
	echo "  surgical-pipeline:"                                                >> $(CAMERA_OVERRIDE); \
	echo "    devices:"                                                       >> $(CAMERA_OVERRIDE); \
	for c in $$CAMS; do echo "      - $$c:$$c"                                >> $(CAMERA_OVERRIDE); done; \
	echo "[up-with-camera] wrote $(CAMERA_OVERRIDE) with:"; sed -n 's/^      - /  /p' $(CAMERA_OVERRIDE)
	UI_HOST_PORT=$(UI_HOST_PORT) DETECTION_DEVICE=$(DETECTION_DEVICE) \
	RENDER_GID=$(RENDER_GID) VIDEO_GID=$(VIDEO_GID) \
		$(COMPOSE) -f docker-compose.yaml -f $(CAMERA_OVERRIDE) up -d
	$(_print_urls)

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
backend-infer:  ## (Removed in Phase 5 — inference now runs in the surgical-pipeline container)
	@echo "[backend-infer] Inline Ultralytics inference was removed in Phase 5."
	@echo "[backend-infer] Use 'make up' and drive the pipeline via the UI or:"
	@echo "  curl -X POST http://<host>:<pipeline-port>/start -d '{\"device\":\"GPU\"}' -H 'Content-Type: application/json'"

.PHONY: backend-serve
backend-serve:  ## Run the real Phase 3 Flask server on :5001 (replaces mock-backend)
	@test -x $(BACKEND_PY) || (echo "[backend-serve] run 'make backend-venv' first"; exit 1)
	@echo "[backend-serve] starting on http://0.0.0.0:5001"
	PORT=5001 BACKEND_CONFIG=backend/config/model.yaml $(BACKEND_PY) -m backend.main_server


