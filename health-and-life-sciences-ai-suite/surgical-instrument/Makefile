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
SHELL := /bin/bash

IMAGE        ?= endoscopy-demo:latest
CONTAINER    ?= endoscopy-demo
TAG          ?= latest
REGISTRY     ?= true
REGISTRY_URL ?= intel/

# --- Host paths mounted into the container -----------------------------------
# MODELS_DIR must contain: yolo11n_polyp/best_openvino_model/best.xml
MODELS_DIR   ?= $(abspath ./models)
VIDEOS_DIR   ?= $(abspath ./videos)
VIDEO        ?= /videos/polyp_test.mp4      # container-side path
MODEL        ?= /models/yolo11n_polyp/best_openvino_model/best.xml

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

# --- Host GPU/USB plumbing (auto-detected) -----------------------------------
RENDER_GID   := $(shell getent group render | cut -d: -f3)
VIDEO_GID    := $(shell getent group video  | cut -d: -f3)
GROUP_ARGS   := $(if $(RENDER_GID),--group-add $(RENDER_GID)) $(if $(VIDEO_GID),--group-add $(VIDEO_GID))

DRI          := $(if $(wildcard /dev/dri),--device /dev/dri:/dev/dri)
X11          := -e DISPLAY=$(DISPLAY) -e XDG_RUNTIME_DIR=$(XDG_RUNTIME_DIR) -v /tmp/.X11-unix:/tmp/.X11-unix:rw
USB          := -v /dev/bus/usb:/dev/bus/usb --device-cgroup-rule='c 189:* rmw'

MOUNTS       := -v $(MODELS_DIR):/models:ro -v $(VIDEOS_DIR):/videos:rw
# CAP_SYS_NICE + rtprio ulimit: required for --cpu-* affinity and --rt-priority
# (SCHED_FIFO) pinning; without them the app logs "Operation not permitted".
COMMON       := --rm --name $(CONTAINER) --net=host $(DRI) $(GROUP_ARGS) $(MOUNTS) \
                --cap-add SYS_NICE --ulimit rtprio=99 \
                -e MODEL=$(MODEL) -e DEVICE=$(DEVICE)

.PHONY: _xhost
_xhost:
	@xhost +local:root >/dev/null 2>&1 || true

.PHONY: list-cameras
list-cameras: ## List connected Basler cameras (serial + model) -> SERIAL=
	@python3 src/utility.py 2>/dev/null || \
	docker run --rm $(USB) -v $(CURDIR)/src/utility.py:/tmp/utility.py:ro \
		--entrypoint python3 $(IMAGE) /tmp/utility.py

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
	@grep -hE '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | \
		awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}'
