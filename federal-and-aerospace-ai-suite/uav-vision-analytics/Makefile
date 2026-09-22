# SPDX-FileCopyrightText: (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

ifneq (,$(wildcard .env))
  include .env
  export
endif

COMPOSE_PYMAV  := docker-compose-pymavlink.yml
COMPOSE_SDK := docker-compose-uavsdk.yml
DLSPS          := dlstreamer-pipeline-server
MODEL_DIR      := resources/models/yolo11s
MODEL_XML      := $(MODEL_DIR)/yolo11s_openvino_model/yolo11s.xml
VENV           := resources/venv
DEVICE         ?= gpu
SSL_DIR        := configs/nginx/ssl

.PHONY: help init build model _check_model _check_certs _check_venv_pkg \
        pymav-up pymav-down \
        uavsdk-up uavsdk-down \
        start-rtsp

help: ## Show available targets
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / \
	  {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)

# ── Init ────────────────────────────────────────────────────────────────────

init: ## Create .env from template, auto-detect the host IP, and auto-detect GPU/NPU device paths
	@if test -f .env; then \
		echo ".env already exists — skipping (delete it to re-run init)"; \
	else \
		cp .env.example .env; \
		echo ".env created from .env.example"; \
		HOST_IP_DETECTED=$$(hostname -I 2>/dev/null | awk '{print $$1}'); \
		if [ -z "$$HOST_IP_DETECTED" ]; then \
			HOST_IP_DETECTED=127.0.0.1; \
			echo "⚠  Could not auto-detect host IP — defaulting HOST_IP=127.0.0.1 (edit .env manually if needed)."; \
		else \
			echo "✅ Host IP detected:"; \
			echo "   HOST_IP=$$HOST_IP_DETECTED"; \
			echo "   ⚠  Security: nginx's HTTPS (443) and RTSP (8555) ports will be published on"; \
			echo "      this LAN address so QGroundControl/ffplay/VLC on other devices can reach"; \
			echo "      them. Set HOST_IP=127.0.0.1 in .env for loopback-only access if this host"; \
			echo "      is not on a trusted, isolated network."; \
		fi; \
		sed -i "s|^HOST_IP=.*|HOST_IP=$$HOST_IP_DETECTED|" .env; \
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
		echo "   Run 'make model' first to download and export the YOLO11s model."; \
		exit 1; \
	fi
_check_certs: ## Generate a self-signed TLS certificate for nginx if missing
	@mkdir -p $(SSL_DIR); \
	if [ ! -f "$(SSL_DIR)/server.crt" ] || [ ! -f "$(SSL_DIR)/server.key" ]; then \
		echo "Generate self-signed certificate..."; \
		openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
		  -keyout $(SSL_DIR)/server.key -out $(SSL_DIR)/server.crt \
		  -subj "/C=US/ST=CA/L=San Francisco/O=Intel/OU=Edge AI/CN=localhost"; \
		chown -R "$$(id -u):$$(id -g)" $(SSL_DIR)/server.key $(SSL_DIR)/server.crt 2>/dev/null || true; \
	fi
# ── Model ────────────────────────────────────────────────────────────────────

_check_venv_pkg: ## Verify python3-venv (ensurepip) is installed; offer to install it if missing
	@if python3 -c "import ensurepip" >/dev/null 2>&1; then \
		exit 0; \
	fi; \
	PY_VER=$$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")'); \
	VENV_PKG="python3-venv"; \
	if command -v apt-cache >/dev/null 2>&1 && apt-cache show "python$${PY_VER}-venv" >/dev/null 2>&1; then \
		VENV_PKG="python$${PY_VER}-venv"; \
	fi; \
	echo "⚠  'python3 -m venv' requires the '$$VENV_PKG' package (ensurepip module not found), which is not installed."; \
	if ! command -v apt-get >/dev/null 2>&1; then \
		echo "❌ 'apt-get' not found — install '$$VENV_PKG' (or your distro's equivalent) manually and re-run 'make model'."; \
		exit 1; \
	fi; \
	printf "Install '%s' now via 'sudo apt install %s'? [y/N] " "$$VENV_PKG" "$$VENV_PKG"; \
	read -r REPLY; \
	case "$$REPLY" in \
		[yY]*) \
			sudo apt-get update && sudo apt-get install -y "$$VENV_PKG" || { \
				echo "❌ Failed to install $$VENV_PKG. Install it manually and re-run 'make model'."; \
				exit 1; \
			}; \
			;; \
		*) \
			echo "❌ '$$VENV_PKG' is required to create the model virtualenv. Install it manually (sudo apt install $$VENV_PKG) and re-run 'make model'."; \
			exit 1; \
			;; \
	esac

model: _check_venv_pkg ## Download YOLO11s (COCO-pretrained) and export to OpenVINO FP16
	@echo "[model] Creating virtualenv..."
	python3 -m venv $(VENV)
	@echo "[model] Installing dependencies..."
	$(VENV)/bin/pip install --quiet -r resources/requirements.txt
	@echo "[model] Downloading yolo11s.pt and exporting to OpenVINO FP16..."
	mkdir -p $(MODEL_DIR)
	cd $(MODEL_DIR) && $(CURDIR)/$(VENV)/bin/yolo export \
	  model=yolo11s.pt \
	  format=openvino \
	  dynamic=True \
	  opset=18 \
	  imgsz=640 \
	  half=True
	@echo "[model] Done. Model at: $(MODEL_DIR)/yolo11s_openvino_model/"

# ── pymavlink stack ───────────────────────────────────────────────────────────

pymav-up: _check_model _check_certs ## Start standalone pymavlink stack (PX4 SITL + broker + DLSPS + mediamtx)
	docker compose -f $(COMPOSE_PYMAV) up -d

pymav-down: ## Stop and remove pymavlink stack (includes volumes)
	docker compose -f $(COMPOSE_PYMAV) down -v

# ── UAV Mission Compute SDK stack ──────────────────────────────────────────────────────────────

uavsdk-up: _check_model _check_certs ## Start UAV Mission Compute SDK stack (requires edge-ai-suites/federal-and-aerospace-ai-suite/uav-mission-compute-sdk running first)
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
