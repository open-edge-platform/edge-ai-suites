# SPDX-FileCopyrightText: (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

ifneq (,$(wildcard .env))
  include .env
  export
endif

COMPOSE_PYMAV  := docker-compose-pymavlink.yml
COMPOSE_SDK := docker-compose-uavsdk.yml
DLSPS          := dlstreamer-pipeline-server
MODEL_DIR      := resources/models/yolov8n-visdrone
MODEL_XML      := $(MODEL_DIR)/best_openvino_model/best.xml
VENV           := resources/venv
DEVICE         ?= gpu

.PHONY: help init build model _check_model \
        pymav-up pymav-down \
        uavsdk-up uavsdk-down \
        start-rtsp

help: ## Show available targets
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / \
	  {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)

# ── Init ────────────────────────────────────────────────────────────────────

init: ## Create .env from template and auto-detect GPU/NPU device paths
	@if test -f .env; then \
		echo ".env already exists — skipping (delete it to re-run init)"; \
	else \
		cp .env.example .env; \
		echo ".env created from .env.example"; \
		GPU_CARD=$$(ls -1 /dev/dri/card* 2>/dev/null | head -1); \
		GPU_RENDER=$$(ls -1 /dev/dri/renderD* 2>/dev/null | head -1); \
		if [ -n "$$GPU_CARD" ] && [ -n "$$GPU_RENDER" ]; then \
			echo "✅ GPU detected:"; \
			echo "   GPU_DEVICE=$$GPU_CARD"; \
			echo "   GPU_RENDER_DEVICE=$$GPU_RENDER"; \
			sed -i "s|^GPU_DEVICE=.*|GPU_DEVICE=$$GPU_CARD|" .env; \
			sed -i "s|^GPU_RENDER_DEVICE=.*|GPU_RENDER_DEVICE=$$GPU_RENDER|" .env; \
		else \
			echo "⚠  No Intel GPU found at /dev/dri/ — set GPU_DEVICE and GPU_RENDER_DEVICE in .env manually."; \
		fi; \
		NPU_DEV=$$(ls -1 /dev/accel/accel* 2>/dev/null | head -1); \
		if [ -n "$$NPU_DEV" ]; then \
			echo "✅ NPU detected:"; \
			echo "   NPU_DEVICE=$$NPU_DEV"; \
			if grep -q "^NPU_DEVICE=" .env; then \
				sed -i "s|^NPU_DEVICE=.*|NPU_DEVICE=$$NPU_DEV|" .env; \
			else \
				echo "NPU_DEVICE=$$NPU_DEV" >> .env; \
			fi; \
		else \
			echo "⚠  No Intel NPU found at /dev/accel/ — defaulting NPU_DEVICE=/dev/null (NPU pipelines will not work)."; \
			if grep -q "^NPU_DEVICE=" .env; then \
				sed -i "s|^NPU_DEVICE=.*|NPU_DEVICE=/dev/null|" .env; \
			else \
				echo "NPU_DEVICE=/dev/null" >> .env; \
			fi; \
		fi; \
		        RS_DEV=$$(v4l2-ctl --list-devices 2>/dev/null | \
                        awk '/\(usb-/{usb=1;next} usb && /\/dev\/video/{print $$1} /^[^[:space:]]/{usb=0}' | \
                        while IFS= read -r dev; do \
                            v4l2-ctl -d "$$dev" --list-formats 2>/dev/null | grep -qiE 'MJPG|YUYV' \
                                && echo "$$dev" && break; \
                        done); \
                if [ -n "$$RS_DEV" ]; then \
                        echo "✅ USB camera detected: $$RS_DEV → /dev/video4"; \
                        if grep -q "^REALSENSE_DEVICE=" .env; then \
                                sed -i "s|^REALSENSE_DEVICE=.*|REALSENSE_DEVICE=$$RS_DEV|" .env; \
                        else \
                                echo "REALSENSE_DEVICE=$$RS_DEV" >> .env; \
                        fi; \
                else \
                        echo "⚠  No USB camera found — REALSENSE_DEVICE=/dev/null (RealSense/camera pipelines disabled)."; \
                        if grep -q "^REALSENSE_DEVICE=" .env; then \
                                sed -i "s|^REALSENSE_DEVICE=.*|REALSENSE_DEVICE=/dev/null|" .env; \
                        else \
                                echo "REALSENSE_DEVICE=/dev/null" >> .env; \
                        fi; \
                fi; \
        fi

# ── Pre-flight check ────────────────────────────────────────────────────────

_check_model:
	@if [ ! -f "$(MODEL_XML)" ]; then \
		echo "❌ Model not found: $(MODEL_XML)"; \
		echo "   Run 'make model' first to download and export the YOLOv8n-VisDrone model."; \
		exit 1; \
	fi

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

pymav-up: _check_model ## Start standalone pymavlink stack (PX4 SITL + broker + DLSPS + mediamtx)
	docker compose -f $(COMPOSE_PYMAV) up -d

pymav-down: ## Stop and remove pymavlink stack (includes volumes)
	docker compose -f $(COMPOSE_PYMAV) down -v

# ── UAV Mission Compute SDK stack ──────────────────────────────────────────────────────────────

uavsdk-up: _check_model ## Start UAV Mission Compute SDK stack (requires edge-ai-suites/federal-and-aerospace-ai-suite/uav-mission-compute-sdk running first)
	docker compose -f $(COMPOSE_SDK) up -d

uavsdk-down: ## Stop and remove UAV Mission Compute SDK stack (includes volumes)
	docker compose -f $(COMPOSE_SDK) down -v

# ── Pipeline management ───────────────────────────────────────────────────────

start-rtsp: ## Start RTSP pipelines. DEVICE=cpu|gpu|npu|all (default: gpu)
	-docker exec -it \
	  -e HOST_IP=$(HOST_IP) \
	  -e PIPELINE_DEVICE=$(DEVICE) \
	  $(DLSPS) bash -c \
	  "python3 /home/pipeline-server/scripts/pipeline_manager.py --sink rtsp"

# ── Convenience alias ─────────────────────────────────────────────────────────

build: pymav-up ## Alias: start the default pymavlink stack
