# SPDX-FileCopyrightText: (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

COMPOSE_PYMAV  := docker-compose-pymavlink.yml
COMPOSE_MAVSDK := docker-compose-mavsdk.yml
DLSPS          := dlstreamer-pipeline-server
MODEL_DIR      := resources/models/yolov8n-visdrone
VENV           := resources/venv

.PHONY: help build model \
        pymav-up pymav-down \
        mavsdk-up mavsdk-down \
        start-rtsp start-udpsink

help: ## Show available targets
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
	  | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

# ── Model ────────────────────────────────────────────────────────────────────

model: ## Download YOLOv8n-VisDrone and export to OpenVINO FP16
	@echo "[model] Creating virtualenv..."
	python3 -m venv $(VENV)
	@echo "[model] Installing dependencies..."
	$(VENV)/bin/pip install --quiet -r resources/requirements.txt
	@echo "[model] Downloading checkpoint from HuggingFace..."
	$(VENV)/bin/hf download mshamrai/yolov8n-visdrone best.pt \
	  --local-dir ./$(MODEL_DIR)
	@echo "[model] Exporting to OpenVINO FP16..."
	$(VENV)/bin/yolo export \
	  model=./$(MODEL_DIR)/best.pt \
	  format=openvino \
	  dynamic=True \
	  opset=18 \
	  imgsz=640 \
	  half=True
	@echo "[model] Done. Model at: $(MODEL_DIR)/best_openvino_model/"

# ── pymavlink stack ───────────────────────────────────────────────────────────

pymav-up: ## Start standalone pymavlink stack (PX4 SITL + broker + DLSPS + mediamtx)
	docker compose -f $(COMPOSE_PYMAV) up -d

pymav-down: ## Stop and remove pymavlink stack (includes volumes)
	docker compose -f $(COMPOSE_PYMAV) down -v

# ── MAVSDK stack ──────────────────────────────────────────────────────────────

mavsdk-up: ## Start MAVSDK stack (requires fedaero-drone-sdk-poc running first)
	docker compose -f $(COMPOSE_MAVSDK) up -d

mavsdk-down: ## Stop and remove MAVSDK stack (includes volumes)
	docker compose -f $(COMPOSE_MAVSDK) down -v

# ── Pipeline management ───────────────────────────────────────────────────────

start-rtsp: ## Start pipelines with RTSP output (exec into running DLSPS container)
	docker exec -it $(DLSPS) bash -c \
	  "python3 /home/pipeline-server/scripts/mavlink_pipeline_manager.py"

start-udpsink: ## Start pipelines with UDP sink output (exec into running DLSPS container)
	docker exec -it $(DLSPS) bash -c \
	  "python3 /home/pipeline-server/scripts/mavlink_pipeline_manager_udpsink.py"

# ── Convenience alias ─────────────────────────────────────────────────────────

build: pymav-up ## Alias: start the default pymavlink stack
