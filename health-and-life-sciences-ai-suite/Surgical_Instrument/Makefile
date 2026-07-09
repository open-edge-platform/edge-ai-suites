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
	@$(MAKE) --no-print-directory _camera-override
	UI_HOST_PORT=$(UI_HOST_PORT) DETECTION_DEVICE=$(DETECTION_DEVICE) \
	RENDER_GID=$(RENDER_GID) VIDEO_GID=$(VIDEO_GID) \
		$(COMPOSE) $(_COMPOSE_FILES) up -d --build
	@echo "[up] First boot may take 20-35 min while YOLO11n trains on the iGPU."
	@echo "[up] Follow progress: make logs"
	$(_print_urls)

.PHONY: run
run:  ## Fast subsequent boot: start stack without rebuild. Requires cached IR.
	@test -f $(IR_DIR)/best.xml -a -f $(IR_MARKER) || ( \
		echo "[run] No cached IR at $(IR_DIR)/ — run 'make up' first for first-boot train,"; \
		echo "[run] or 'make assets' to seed IR from POC."; \
		exit 1)
	@$(MAKE) --no-print-directory _camera-override
	UI_HOST_PORT=$(UI_HOST_PORT) DETECTION_DEVICE=$(DETECTION_DEVICE) \
	RENDER_GID=$(RENDER_GID) VIDEO_GID=$(VIDEO_GID) \
		$(COMPOSE) $(_COMPOSE_FILES) up -d
	$(_print_urls)

# ---- Camera passthrough (auto-detected by `up` / `run`) ---------------------
# Hardcoding /dev/videoN in docker-compose.yaml would break `make up` on
# camera-less hosts. Instead: detect at run-time, emit an override, and layer
# it in via `-f`. If no camera is present, no override is generated and the
# base compose is used unchanged — the recorded-video flow still works.
#
# The UI's Input Source picker is the primary route for selecting the source
# at runtime. Any /dev/video* found here is simply *made available* to the
# pipeline container; the UI decides whether to actually use it.
CAMERA_OVERRIDE ?= docker-compose.camera.override.yaml
_COMPOSE_FILES   = -f docker-compose.yaml $(if $(wildcard $(CAMERA_OVERRIDE)),-f $(CAMERA_OVERRIDE),)

.PHONY: list-cameras
list-cameras:  ## List /dev/video* devices visible on this host
	@ls -la /dev/video* 2>/dev/null || echo "[list-cameras] no /dev/video* present"
	@echo ""
	@lsusb -d 2676: 2>/dev/null || echo "[list-cameras] no Basler USB device present"

# Internal: (re)generate the camera override if any /dev/video* exist, else
# remove any stale override so `_COMPOSE_FILES` stays base-only. Idempotent.
.PHONY: _camera-override
_camera-override:
	@CAMS=$$(ls /dev/video* 2>/dev/null); \
	BASLER=$$(lsusb -d 2676: 2>/dev/null); \
	if [ -z "$$CAMS" ] && [ -z "$$BASLER" ]; then \
		rm -f $(CAMERA_OVERRIDE); \
		echo "[camera] no /dev/video* or Basler USB found — recorded-video only"; \
	else \
		echo "# Auto-generated by 'make up' / 'make run'. Do not edit; do not commit." > $(CAMERA_OVERRIDE); \
		echo "services:"                                                              >> $(CAMERA_OVERRIDE); \
		echo "  surgical-pipeline:"                                                    >> $(CAMERA_OVERRIDE); \
		if [ -n "$$CAMS" ] || [ -n "$$BASLER" ]; then \
			echo "    devices:"                                                        >> $(CAMERA_OVERRIDE); \
			for c in $$CAMS; do echo "      - $$c:$$c"                                >> $(CAMERA_OVERRIDE); done; \
			if [ -n "$$BASLER" ]; then \
				echo "      - /dev/bus/usb:/dev/bus/usb"                              >> $(CAMERA_OVERRIDE); \
				echo "    device_cgroup_rules:"                                        >> $(CAMERA_OVERRIDE); \
				echo "      - 'c 189:* rmw'"                                          >> $(CAMERA_OVERRIDE); \
			fi; \
		fi; \
		echo "  surgical-backend:"                                                    >> $(CAMERA_OVERRIDE); \
		if [ -n "$$CAMS" ]; then \
			echo "    volumes:"                                                        >> $(CAMERA_OVERRIDE); \
			echo "      - /sys/class/video4linux:/sys/class/video4linux:ro"          >> $(CAMERA_OVERRIDE); \
		fi; \
		if [ -n "$$BASLER" ]; then \
			echo "    devices:"                                                        >> $(CAMERA_OVERRIDE); \
			echo "      - /dev/bus/usb:/dev/bus/usb"                                  >> $(CAMERA_OVERRIDE); \
			echo "    device_cgroup_rules:"                                            >> $(CAMERA_OVERRIDE); \
			echo "      - 'c 189:* rmw'"                                              >> $(CAMERA_OVERRIDE); \
		fi; \
		echo "[camera] wrote $(CAMERA_OVERRIDE):"; sed -n 's/^      - /  /p' $(CAMERA_OVERRIDE); \
		if [ -n "$$BASLER" ]; then echo "[camera] Basler USB detected: $$BASLER"; fi; \
	fi

# Developer-only alias: keep the original explicit target so a dev can force
# the camera-flow refresh without a full `make up`. Not part of the user path;
# `make up` and `make run` already do the right thing.
.PHONY: up-with-camera
up-with-camera: up   # (dev alias — same as `make up`; kept for backward compat)

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

# ---- Doctor: pre-flight health check (slice G) ------------------------------
# `make doctor` is a read-only sanity sweep the operator can run before
# `make up`. Every check prints [ OK ] / [WARN] / [FAIL] and the target exits
# non-zero only if a genuinely fatal condition is found (missing Docker, no
# demo asset, port collision). Warnings — e.g. NPU not visible — are fine on
# hosts where the workload will run on CPU/GPU only.

.PHONY: doctor
doctor:  ## Pre-flight: check Docker, /dev/dri, models, videos, ports
	@fail=0; \
	printf "\n[doctor] --- host prerequisites ---\n"; \
	if command -v docker >/dev/null 2>&1; then \
	  printf "  [ OK ] docker : %s\n" "$$(docker --version)"; \
	else \
	  printf "  [FAIL] docker : not installed\n"; fail=1; \
	fi; \
	if docker compose version >/dev/null 2>&1; then \
	  printf "  [ OK ] compose: %s\n" "$$(docker compose version --short)"; \
	elif command -v docker-compose >/dev/null 2>&1; then \
	  printf "  [WARN] compose: v1 detected (`docker-compose`) — v2 (`docker compose`) recommended\n"; \
	else \
	  printf "  [FAIL] compose: not installed\n"; fail=1; \
	fi; \
	if docker info >/dev/null 2>&1; then \
	  printf "  [ OK ] docker daemon reachable\n"; \
	else \
	  printf "  [FAIL] docker daemon not reachable — is the service running and is your user in the docker group?\n"; fail=1; \
	fi; \
	printf "\n[doctor] --- accelerator visibility ---\n"; \
	if [ -e /dev/dri ]; then \
	  RENDERS=$$(ls /dev/dri/renderD* 2>/dev/null | wc -l); \
	  printf "  [ OK ] /dev/dri present (renderD* count: %s)\n" "$$RENDERS"; \
	else \
	  printf "  [WARN] /dev/dri missing — GPU inference will not work; CPU-only fallback\n"; \
	fi; \
	if [ -e /dev/accel/accel0 ]; then \
	  printf "  [ OK ] /dev/accel/accel0 present (NPU visible)\n"; \
	else \
	  printf "  [WARN] /dev/accel/accel0 missing — NPU device selection will fail; use CPU or GPU\n"; \
	fi; \
	if [ -n "$(RENDER_GID)" ]; then \
	  printf "  [ OK ] render group gid=%s (auto-detected)\n" "$(RENDER_GID)"; \
	else \
	  printf "  [WARN] render group not on this host — /dev/dri passthrough may need manual chgrp\n"; \
	fi; \
	printf "\n[doctor] --- cameras (optional) ---\n"; \
	CAMS=$$(ls /dev/video* 2>/dev/null); \
	if [ -n "$$CAMS" ]; then \
	  printf "  [ OK ] /dev/video* found: %s\n" "$$CAMS"; \
	  printf "         (make up/run will auto-passthrough these; UI selects at runtime)\n"; \
	else \
	  printf "  [INFO] no /dev/video* — recorded-video only (fine for demo)\n"; \
	fi; \
	printf "\n[doctor] --- assets ---\n"; \
	if [ -f "$(IR_DIR)/best.xml" ] && [ -f "$(IR_DIR)/best.bin" ]; then \
	  SIZE=$$(du -sh "$(IR_DIR)" | awk '{print $$1}'); \
	  printf "  [ OK ] cached IR : %s (%s)\n" "$(IR_DIR)" "$$SIZE"; \
	else \
	  printf "  [WARN] no cached IR at %s — first-boot train will kick in on 'make up'\n" "$(IR_DIR)"; \
	fi; \
	VIDS=$$(ls videos/*.mp4 videos/*.mkv videos/*.avi videos/*.mov videos/*.ts 2>/dev/null | wc -l); \
	if [ "$$VIDS" -gt 0 ]; then \
	  printf "  [ OK ] %s demo video(s) under ./videos/\n" "$$VIDS"; \
	else \
	  printf "  [FAIL] no video assets under ./videos/ — run 'make assets' or drop an mp4 in\n"; fail=1; \
	fi; \
	printf "\n[doctor] --- port availability ---\n"; \
	if $(COMPOSE) ps --services --filter status=running 2>/dev/null | grep -q surgical-ui; then \
	  printf "  [ OK ] port %s in use by our own stack (surgical-ui already up)\n" "$(UI_HOST_PORT)"; \
	elif command -v ss >/dev/null 2>&1; then \
	  if ss -Htln "sport = :$(UI_HOST_PORT)" 2>/dev/null | grep -q .; then \
	    OWNER=$$(ss -Htlnp "sport = :$(UI_HOST_PORT)" 2>/dev/null | head -1); \
	    printf "  [FAIL] port %s in use by another process: %s\n" "$(UI_HOST_PORT)" "$$OWNER"; \
	    printf "         (override on the CLI: make up UI_HOST_PORT=9000)\n"; fail=1; \
	  else \
	    printf "  [ OK ] port %s free\n" "$(UI_HOST_PORT)"; \
	  fi; \
	else \
	  printf "  [WARN] 'ss' not installed — cannot verify port %s is free\n" "$(UI_HOST_PORT)"; \
	fi; \
	printf "\n[doctor] --- compose config ---\n"; \
	if $(COMPOSE) config >/dev/null 2>&1; then \
	  printf "  [ OK ] docker-compose.yaml parses cleanly\n"; \
	else \
	  printf "  [FAIL] docker-compose.yaml is invalid (run '$(COMPOSE) config' to see why)\n"; fail=1; \
	fi; \
	printf "\n"; \
	if [ "$$fail" -ne 0 ]; then \
	  printf "[doctor] FAIL — fix the [FAIL] items above then re-run.\n\n"; exit 1; \
	fi; \
	printf "[doctor] all critical checks passed — 'make up' should succeed.\n\n"

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


