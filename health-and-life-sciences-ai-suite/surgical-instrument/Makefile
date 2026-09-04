# Updated Endoscopy Demo — docker compose driven workflow.
#
# Independent of the rest of Surgical_Instrument. Just needs an OpenVINO IR and
# (for file mode) a video, mounted from the host.
#
#   make up LOWLATENCY=1 CAMERA_TRIGGER=vsync VSYNC_DIVISOR=2 SERIAL=<SERIAL_NUMBER>
#   make up LOWLATENCY=1 CAMERA_TRIGGER=vsync VSYNC_DIVISOR=2 SERIAL=<SERIAL_NUMBER> REGISTRY=false
#   make down
#   make logs
#
# Optional local model-prep flow (needed only if you do NOT already have a
# trained OpenVINO IR under $(MODELS_DIR)/yolo11n_polyp/best_openvino_model/):
#
#   make setup-prerequisites                 # install host prerequisites (Docker + Intel L0 stack)
#   make check-l0              # verify Intel Level Zero packages on the host
#   make download-dataset      # fetch REAL-Colon subset (~74 GB) for training
#   make backend-venv          # create .venv-backend with torch+xpu + Ultralytics + OpenVINO
#   make backend-bootstrap     # fetch dataset -> train YOLO11n -> export FP16 OpenVINO IR
#   make doctor                # preflight: docker, /dev/dri, IR + demo video, L0 stack
#
SHELL := /bin/bash

TAG          ?= latest
REGISTRY     ?= true
REGISTRY_URL ?= intel/

# --- Host paths passed to Docker Compose -------------------------------------
# MODELS_DIR must contain: yolo11n_polyp/best_openvino_model/best.xml
MODELS_DIR   ?= $(abspath ./models)
VIDEOS_DIR   ?= $(abspath ./videos)

# --- Runtime knobs -----------------------------------------------------------
# CPU | GPU | NPU
DEVICE       ?= GPU
FRAME_SKIP   ?= 1
THRESHOLD    ?= 0.5
# Basler serial ("" = first camera)
SERIAL       ?=
# V4L2 webcam index
DEVICE_INDEX ?= 0

# LOWLATENCY=1 flips the whole low-latency profile in one switch (software trigger +
# fullscreen direct-scanout + latency CSV). Individual knobs below still override it,
# e.g. LOWLATENCY=1 CAMERA_TRIGGER=vsync, or LOWLATENCY=1 FULLSCREEN=0.
LOWLATENCY   ?= 1
ifeq ($(LOWLATENCY),1)
# off | software | vsync (vsync = phase-locked to display)
CAMERA_TRIGGER ?= vsync
# fullscreen GL direct-scanout (bypass compositor)
FULLSCREEN     ?= 1
# print per-stage latency CSV
LATENCY_TRACE  ?= 1
else
# free-running capture (baseline)
CAMERA_TRIGGER ?= off
# windowed
FULLSCREEN     ?= 0
LATENCY_TRACE  ?= 0
endif
# vsync: capture every Nth vblank
VSYNC_DIVISOR  ?= 2
# fixed exposure in us ("" = leave camera as-is; lower = less latency but darker)
EXPOSURE_US    ?=
# CPU-core pinning + SCHED_FIFO priority for the capture/inference/display threads.
CPU_CAPTURE    ?=
CPU_INFERENCE  ?=
CPU_DISPLAY    ?=
RT_PRIORITY    ?= 0
# extra flags, e.g. EXTRA="--frame-skip 2"
EXTRA          ?=

# Proxy passthrough for build (optional)
HTTP_PROXY   ?=
HTTPS_PROXY  ?=
NO_PROXY     ?=

COMPOSE      := docker compose --project-directory . -f docker/docker-compose.yaml
REGISTRY_LOWER := $(shell echo $(REGISTRY) | tr A-Z a-z)
DEVICE_UPPER   := $(shell echo $(DEVICE) | tr a-z A-Z)
ifeq ($(DEVICE_UPPER),NPU)
COMPOSE := $(COMPOSE) -f docker/docker-compose.npu.yaml
endif

# Unified compose runtime selector:
#   SOURCE=file|camera|webcam|basler|v4l2
# Keep SOURCE_ARG explicit when passing file path/serial/index directly.
SOURCE       ?= camera
SOURCE_ARG   ?=

# --- Host USB plumbing (used by `make list-cameras`) -------------------------
USB          := -v /dev/bus/usb:/dev/bus/usb --device-cgroup-rule='c 189:* rmw'

.PHONY: _xhost
_xhost:
	@xhost +local:root >/dev/null 2>&1 || true

.PHONY: list-cameras
list-cameras: ## List connected Basler cameras (serial + model) -> SERIAL=
	@python3 src/utility.py 2>/dev/null || \
	docker run --rm $(USB) -v $(CURDIR)/src/utility.py:/tmp/utility.py:ro \
		--entrypoint python3 $(REGISTRY_URL)hls-si-endoscopy:$(TAG) /tmp/utility.py

.PHONY: show-cores
show-cores: ## Show P-core / E-core CPU sets for --cpu-* pinning
	@ALL=$$(cat /sys/devices/system/cpu/present 2>/dev/null || echo 'unknown'); \
	PCORE=$$(cat /sys/devices/cpu_core/cpus 2>/dev/null); \
	ECORE=$$(cat /sys/devices/cpu_atom/cpus 2>/dev/null); \
	N=$$(nproc 2>/dev/null || echo '?'); \
	printf '\n[cores] all CPUs        : %s  (nproc=%s)\n' "$$ALL" "$$N"; \
	if [ -n "$$PCORE" ]; then \
	  printf '[cores] P-cores (perf)  : %s  <-- pin --cpu-capture/--cpu-inference/--cpu-display here\n' "$$PCORE"; \
	  printf '[cores] E-cores (effic) : %s\n' "$$ECORE"; \
	  printf '[cores] hint: CPU_CAPTURE=1 CPU_INFERENCE=2 CPU_DISPLAY=3 RT_PRIORITY=80\n'; \
	else \
	  printf '[cores] no P/E core split detected (non-hybrid CPU or older kernel)\n'; \
	  printf '[cores] all cores are equivalent; pick any distinct --cpu-* indices.\n'; \
	fi; \
	printf '\n[cores] lscpu sample (top 6 rows):\n'; \
	lscpu -e 2>/dev/null | head -7 || lscpu | head -10; \
	printf '\n'

.PHONY: up
up: _xhost ## Start stack for all variations (SOURCE=file|camera|webcam, REGISTRY=true/false)
	@SRC="$(SOURCE)"; \
	ARG="$(SOURCE_ARG)"; \
	if [ "$$SRC" = "camera" ]; then SRC="basler"; ARG="$(SERIAL)"; fi; \
	if [ "$$SRC" = "webcam" ]; then SRC="v4l2"; ARG="$(DEVICE_INDEX)"; fi; \
	CAMERA_TRIGGER="$(CAMERA_TRIGGER)"; \
	if [ "$(REGISTRY_LOWER)" = "true" ]; then \
		echo "Pulling image from registry: $(REGISTRY_URL)hls-si-endoscopy:$(TAG)"; \
		DOCKER_REGISTRY=$(REGISTRY_URL) TAG=$(TAG) $(COMPOSE) pull; \
	else \
		echo "Building image from local source"; \
		TAG=$(TAG) $(COMPOSE) build; \
	fi; \
	DOCKER_REGISTRY=$(REGISTRY_URL) TAG=$(TAG) \
	SOURCE="$$SRC" SOURCE_ARG="$$ARG" CAMERA_TRIGGER="$$CAMERA_TRIGGER" \
	FULLSCREEN="$(FULLSCREEN)" LATENCY_TRACE="$(LATENCY_TRACE)" \
	VSYNC_DIVISOR="$(VSYNC_DIVISOR)" EXPOSURE_US="$(EXPOSURE_US)" \
	MODELS_DIR="$(MODELS_DIR)" VIDEOS_DIR="$(VIDEOS_DIR)" \
	CPU_CAPTURE="$(CPU_CAPTURE)" CPU_INFERENCE="$(CPU_INFERENCE)" \
	CPU_DISPLAY="$(CPU_DISPLAY)" RT_PRIORITY="$(RT_PRIORITY)" \
	DEVICE="$(DEVICE)" \
	$(COMPOSE) up -d

.PHONY: down
down: ## Stop compose stack
	DOCKER_REGISTRY=$(REGISTRY_URL) TAG=$(TAG) $(COMPOSE) down

.PHONY: logs
logs: ## Tail compose logs
	DOCKER_REGISTRY=$(REGISTRY_URL) TAG=$(TAG) $(COMPOSE) logs -f

.PHONY: clean
clean: down ## Stop stack and remove image
	-docker rmi intel/hls-si-endoscopy:$(TAG) 2>/dev/null || true
	@xhost -local:root >/dev/null 2>&1 || true

.PHONY: help
help: ## List targets
	@grep -hE '^[a-zA-Z0-9_-]+:.*?## ' $(MAKEFILE_LIST) | \
		awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2}'

# =============================================================================
# Local model-prep flow (OPTIONAL) — only needed if you don't already have a
# trained OpenVINO IR at $(MODELS_DIR)/yolo11n_polyp/best_openvino_model/best.xml.
# The Docker Compose runtime above is independent of these targets; skip this
# section entirely if you're pulling a prebuilt model from the registry.
# =============================================================================

# Python interpreter used to bootstrap the training venv. Override via PY=python3.12.
PY          ?= python3
BACKEND_VENV ?= .venv-backend
PIP          := $(BACKEND_VENV)/bin/pip
PYVENV       := $(BACKEND_VENV)/bin/python

# Host L0 stack (mirrors what scripts/setup-prerequisites.sh installs). Used by check-l0 and doctor.
# NOTE: libigc2 is the IGC package on current Intel client GPU repos (Ubuntu Noble+);
# intel-igc-core-2 is the legacy name on older releases — either satisfies the IGC dependency.
L0_PACKAGES  := libze1 libze-intel-gpu1 libigdgmm12 \
                intel-opencl-icd intel-media-va-driver-non-free
L0_IGC_ALTS  := libigc2 intel-igc-core-2

.PHONY: setup-prerequisites
setup-prerequisites: ## Install host prerequisites (Docker, Intel L0 stack) — runs scripts/setup-prerequisites.sh
	@./scripts/setup-prerequisites.sh $(SETUP_ARGS)

.PHONY: download-dataset
download-dataset: ## Download the REAL-Colon subset (~74 GB) into datasets/REAL-Colon/raw
	@./scripts/download_realcolon_subset.sh $(DATASET_DIR)

.PHONY: check-l0
check-l0: ## Verify Intel Level Zero + OpenCL packages are installed on the host
	@ok=1; \
	for p in $(L0_PACKAGES); do \
	  if dpkg-query -W -f='$${Status}' $$p 2>/dev/null | grep -qE 'ok installed'; then \
	    printf '  [OK]      %s (%s)\n' "$$p" "$$(dpkg-query -W -f='$${Version}' $$p)"; \
	  else \
	    printf '  [MISSING] %s\n' "$$p"; ok=0; \
	  fi; \
	done; \
	igc_ok=0; \
	for p in $(L0_IGC_ALTS); do \
	  if dpkg-query -W -f='$${Status}' $$p 2>/dev/null | grep -qE 'ok installed'; then \
	    printf '  [OK]      %s (%s)  (IGC provider)\n' "$$p" "$$(dpkg-query -W -f='$${Version}' $$p)"; \
	    igc_ok=1; break; \
	  fi; \
	done; \
	if [ "$$igc_ok" -ne 1 ]; then printf '  [MISSING] no IGC package (need one of: $(L0_IGC_ALTS))\n'; ok=0; fi; \
	if [ ! -e /dev/dri ]; then printf '  [MISSING] /dev/dri (kernel i915/xe not loaded?)\n'; ok=0; \
	else printf '  [OK]      /dev/dri present\n'; fi; \
	if [ "$$ok" -ne 1 ]; then echo; echo 'Run: make setup-prerequisites   (installs missing prerequisites)'; exit 1; fi

$(BACKEND_VENV)/bin/python:
	@echo '[backend-venv] creating $(BACKEND_VENV) with $(PY) -m venv'
	@$(PY) -m venv $(BACKEND_VENV)
	@$(PIP) install --upgrade pip wheel

.PHONY: backend-venv
backend-venv: $(BACKEND_VENV)/bin/python ## Create .venv-backend with torch+xpu, Ultralytics, OpenVINO
	@echo '[backend-venv] installing torch+xpu (2.7.1) from pytorch xpu index'
	@$(PIP) install --index-url https://download.pytorch.org/whl/xpu \
	  torch==2.7.1 torchvision==0.22.1
	@echo '[backend-venv] installing backend/requirements.txt'
	@$(PIP) install -r backend/requirements.txt
	@echo '[backend-venv] verifying torch.xpu is available'
	@$(PYVENV) -c 'import torch; assert torch.xpu.is_available(), "torch.xpu not available; check L0 stack + /dev/dri"; print("[backend-venv] torch", torch.__version__, "xpu OK on", torch.xpu.get_device_name(0))'

.PHONY: backend-bootstrap
backend-bootstrap: ## Fetch dataset, train YOLO11n, export FP16 OpenVINO IR (cache-first)
	@if [ ! -x $(PYVENV) ]; then \
	  echo 'error: $(BACKEND_VENV) not found. Run: make backend-venv'; exit 1; \
	fi
	@$(PYVENV) -m backend.main_bootstrap

.PHONY: doctor
doctor: ## Preflight: docker, /dev/dri, cached OpenVINO IR, demo video, L0 stack
	@ok=1; \
	if command -v docker >/dev/null 2>&1; then \
	  printf '  [OK]      docker: %s\n' "$$(docker --version)"; \
	else printf '  [MISSING] docker not installed (run: make setup-prerequisites)\n'; ok=0; fi; \
	if docker compose version >/dev/null 2>&1; then \
	  printf '  [OK]      compose: %s\n' "$$(docker compose version | head -1)"; \
	else printf '  [MISSING] docker compose plugin (run: make setup-prerequisites)\n'; ok=0; fi; \
	if [ -e /dev/dri ]; then printf '  [OK]      /dev/dri present\n'; \
	else printf '  [MISSING] /dev/dri (iGPU inference will fail)\n'; ok=0; fi; \
	IR=$(MODELS_DIR)/yolo11n_polyp/best_openvino_model/best.xml; \
	if [ -s "$$IR" ]; then printf '  [OK]      OpenVINO IR: %s\n' "$$IR"; \
	else printf '  [MISSING] OpenVINO IR at %s (run: make backend-bootstrap)\n' "$$IR"; ok=0; fi; \
	VID=$(VIDEOS_DIR)/polyp_test.mp4; \
	if [ -s "$$VID" ]; then printf '  [OK]      demo video: %s\n' "$$VID"; \
	else printf '  [INFO]    demo video absent at %s (only needed for SOURCE=file)\n' "$$VID"; fi; \
	for p in $(L0_PACKAGES); do \
	  if dpkg-query -W -f='$${Status}' $$p 2>/dev/null | grep -qE 'ok installed'; then :; \
	  else printf '  [MISSING] L0 package: %s\n' "$$p"; ok=0; fi; \
	done; \
	igc_ok=0; \
	for p in $(L0_IGC_ALTS); do \
	  if dpkg-query -W -f='$${Status}' $$p 2>/dev/null | grep -qE 'ok installed'; then igc_ok=1; break; fi; \
	done; \
	if [ "$$igc_ok" -ne 1 ]; then printf '  [MISSING] no IGC package (need one of: $(L0_IGC_ALTS))\n'; ok=0; fi; \
	if [ "$$ok" -eq 1 ]; then echo; echo 'doctor: OK — ready for make up.'; \
	else echo; echo 'doctor: one or more prerequisites missing.'; exit 1; fi
