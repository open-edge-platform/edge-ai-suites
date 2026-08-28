# Surgical Instrument — developer workflow targets.
# Run `make help` to see what's available.

SHELL := /bin/bash
.DEFAULT_GOAL := help

# ---- Tunables (override on the CLI: `make up UI_HOST_PORT=9000`) -----------
UI_HOST_PORT       ?= 8080
DETECTION_DEVICE   ?= GPU
COMPOSE            ?= docker compose

# ---- Image source: registry pull vs build-from-source ---------------------
# REGISTRY=true  (default) runs prebuilt images (pulled from the registry).
# REGISTRY=false builds every image locally from its Dockerfile.
#   make up                   # pull prebuilt images at $(TAG)
#   make up REGISTRY=false     # build all images from source
REGISTRY      ?= true
# Optional registry / namespace prefix (include the trailing slash), e.g.
#   REGISTRY_URL=intel/   or   REGISTRY_URL=myreg.example.com:5000/intel/
REGISTRY_URL  ?=
TAG           ?= latest
export TAG
# Image references shared with docker-compose.yaml. Same names in both modes;
# only the build-vs-pull action differs. Override individually if needed.

# Registry mode lets `docker compose up` pull the images; source mode adds
# `--build` so compose builds them from the Dockerfiles.
_BUILD_FLAG := $(if $(filter true,$(REGISTRY)),,--build)
# Runtime pipeline knobs (overridable via `make up VAR=...`).
SOURCE_KIND           ?= file
SOURCE_ARG            ?=

# ---- Finalized Basler live pipeline defaults ------------------------------
# When SOURCE_KIND=basler, `make up` activates the tuned production Basler
# pipeline documented in docs/user-guide/basler-final-pipeline.md:
#
#   gencamsrc(ycbcr422_8,1280x720) ! vapostproc !
#     video/x-raw(memory:VAMemory),format=NV12 ! queue !
#     gvadetect(va-surface-sharing, GPU, latency) ! queue !
#     gvawatermark ! gvafpscounter ! vapostproc ! xvimagesink sync=true
#
# with `taskset -c 3-5 chrt -f 70` core pinning applied by the launcher.
#
# Any knob can still be overridden on the CLI (e.g. `make up SOURCE_KIND=basler
# SOURCE_ARG=40067928 BASLER_PIXEL_FORMAT=bayerbggr`).
ifeq ($(strip $(SOURCE_KIND)),basler)
  BASLER_PIXEL_FORMAT           ?= ycbcr422_8
  # DeviceLinkThroughputLimit in bytes/sec; 400 MB/s lifts the dart camera off
  # its 160 MB/s default cap. Override on the CLI to change or set empty.
  BASLER_THROUGHPUT_LIMIT       ?= 400000000
  PIPELINE_PREPROC_BACKEND      ?= va-surface-sharing
  SCHEDULING_POLICY             ?= latency
  BATCH_SIZE                    ?= 1
  # Core pinning (taskset -c) and RT priority (chrt -f) are opt-in only —
  # pass PIPELINE_GST_CORES / PIPELINE_GST_RT_PRIORITY on the CLI to enable.
  PIPELINE_DISPLAY_VIEW         ?= 1
  # autovideosink is avoided here: in-container it auto-selects kmssink, which
  # fails with a DRM resource error and crash-loops. xvimagesink is the
  # reliable X sink for this stack.
  PIPELINE_VIDEO_SINK           ?= xvimagesink
  PIPELINE_SINK_SYNC            ?= true
endif

SCHEDULING_POLICY     ?=
BATCH_SIZE            ?=
PIPELINE_PREPROC_BACKEND ?=
PIPELINE_IE_CONFIG    ?= PERFORMANCE_HINT=LATENCY
PIPELINE_FPSCOUNTER   ?= 1
DETECT                ?= 1
WATERMARK             ?= 1
# PIPELINE_IDENTITY controls the passthrough `identity` element in the main
# chain. Default is 0 (dropped) for the production live path. Set to 1 to
# insert it explicitly (e.g. for A/B testing or for external tooling that
# hooks into it). NOTE: When PIPELINE_FRAME_LIMIT > 0, `identity eos-after=N`
# is always kept regardless of this flag because it is structurally required
# for clean EOS termination in bench runs.
PIPELINE_IDENTITY     ?= 0
MINIMAL               ?= 0
# PIPELINE_SINK_SYNC=true|false forces the video sink's `sync=` property
# (aka clock-sync). Empty (default) picks sync=true for file sources and
# sync=false for live basler sources.
PIPELINE_SINK_SYNC    ?=
PIPELINE_DISPLAY_VIEW ?= 0
PIPELINE_VIDEO_SINK   ?= autovideosink
PIPELINE_X_DISPLAY    ?= $(or $(DISPLAY),$(if $(wildcard /tmp/.X11-unix/X0),:0,))

# Friendly alias: `make up AUTOVIDEOSINK=true` -> DISPLAY_VIEW=1 + SINK_SYNC=true
#                 `make up AUTOVIDEOSINK=false` -> DISPLAY_VIEW=0 + SINK_SYNC=false
AUTOVIDEOSINK ?=
ifneq ($(strip $(AUTOVIDEOSINK)),)
  ifeq ($(strip $(AUTOVIDEOSINK)),true)
    PIPELINE_DISPLAY_VIEW := 1
    PIPELINE_SINK_SYNC    := true
  else
    PIPELINE_DISPLAY_VIEW := 0
    PIPELINE_SINK_SYNC    := false
  endif
endif

# PIPELINE_MINIMAL_DISPLAY=1 is a short alias for AUTOVIDEOSINK=true that
# matches the user-facing Case 4 command style.
PIPELINE_MINIMAL_DISPLAY ?=
ifeq ($(strip $(PIPELINE_MINIMAL_DISPLAY)),1)
  PIPELINE_DISPLAY_VIEW := 1
  PIPELINE_SINK_SYNC    := false
endif

# ---- Case 4: core-pinning + Basler fixed-camera tuning knobs ---------------
# CPU affinity (taskset -c) and RT priority (chrt -f) for each leg of the pipe.
# Both parts of each pair must be set for the wrapper to apply; setting only
# one of the pair is silently ignored (prevents half-configured taskset runs).
PIPELINE_GST_CORES            ?=
PIPELINE_GST_RT_PRIORITY      ?=
# Basler fixed-camera tuning. BASLER_FIXED_CAMERA=1 disables auto-exposure /
# auto-gain; the specific values below are then applied. Default (0) keeps the
# existing auto-exposure + upper-limit cap from Cases 1-3 unchanged.
BASLER_FIXED_CAMERA  ?= 0
BASLER_EXPOSURE_US   ?=
BASLER_GAIN          ?=
BASLER_THROUGHPUT_LIMIT ?=
BASLER_PIXEL_FORMAT  ?= bayerbggr

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
build:  ## Build all service images from source (tags them at $(TAG))
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
	@DISPLAY=$(PIPELINE_X_DISPLAY) xhost +local:root >/dev/null 2>&1 || true
	@$(MAKE) --no-print-directory _camera-override
	@$(MAKE) --no-print-directory port-audit
	DISPLAY=$(PIPELINE_X_DISPLAY) UI_HOST_PORT=$(UI_HOST_PORT) DETECTION_DEVICE=$(DETECTION_DEVICE) \
	SOURCE_KIND=$(SOURCE_KIND) SOURCE_ARG=$(SOURCE_ARG) \
	SCHEDULING_POLICY=$(SCHEDULING_POLICY) BATCH_SIZE=$(BATCH_SIZE) \
	DETECT=$(DETECT) MINIMAL=$(MINIMAL) WATERMARK=$(WATERMARK) \
	PIPELINE_IDENTITY=$(PIPELINE_IDENTITY) PIPELINE_SINK_SYNC=$(PIPELINE_SINK_SYNC) \
	PIPELINE_DISPLAY_VIEW=$(PIPELINE_DISPLAY_VIEW) PIPELINE_VIDEO_SINK=$(PIPELINE_VIDEO_SINK) \
	PIPELINE_GST_CORES=$(PIPELINE_GST_CORES) \
	PIPELINE_GST_RT_PRIORITY=$(PIPELINE_GST_RT_PRIORITY) \
	PIPELINE_PREPROC_BACKEND=$(PIPELINE_PREPROC_BACKEND) \
	PIPELINE_IE_CONFIG=$(PIPELINE_IE_CONFIG) \
	PIPELINE_FPSCOUNTER=$(PIPELINE_FPSCOUNTER) \
	BASLER_FIXED_CAMERA=$(BASLER_FIXED_CAMERA) BASLER_EXPOSURE_US=$(BASLER_EXPOSURE_US) BASLER_GAIN=$(BASLER_GAIN) \
	BASLER_THROUGHPUT_LIMIT=$(BASLER_THROUGHPUT_LIMIT) \
	BASLER_PIXEL_FORMAT=$(BASLER_PIXEL_FORMAT) \
	RENDER_GID=$(RENDER_GID) VIDEO_GID=$(VIDEO_GID) \
		$(COMPOSE) -f docker-compose.yaml $$(test -f $(CAMERA_OVERRIDE) && echo -f $(CAMERA_OVERRIDE)) up -d $(_BUILD_FLAG)
	@echo "[up] image mode: $(if $(filter true,$(REGISTRY)),REGISTRY (prebuilt images @ $(TAG)),SOURCE (built from Dockerfiles))"
	@echo "[up] First boot may take 20-35 min while YOLO11n trains on the iGPU."
	@echo "[up] Follow progress: make logs"
	$(_print_urls)

.PHONY: run
run:  ## Fast subsequent boot: start stack without rebuild. Requires cached IR.
	@test -f $(IR_DIR)/best.xml -a -f $(IR_MARKER) || ( \
		echo "[run] No cached IR at $(IR_DIR)/ — run 'make up' first for first-boot train,"; \
		echo "[run] or 'make assets' to seed IR from POC."; \
		exit 1)
	@DISPLAY=$(PIPELINE_X_DISPLAY) xhost +local:root >/dev/null 2>&1 || true
	@$(MAKE) --no-print-directory _camera-override
	@$(MAKE) --no-print-directory port-audit
	DISPLAY=$(PIPELINE_X_DISPLAY) UI_HOST_PORT=$(UI_HOST_PORT) DETECTION_DEVICE=$(DETECTION_DEVICE) \
	SOURCE_KIND=$(SOURCE_KIND) SOURCE_ARG=$(SOURCE_ARG) \
	SCHEDULING_POLICY=$(SCHEDULING_POLICY) BATCH_SIZE=$(BATCH_SIZE) \
	DETECT=$(DETECT) MINIMAL=$(MINIMAL) WATERMARK=$(WATERMARK) \
	PIPELINE_IDENTITY=$(PIPELINE_IDENTITY) PIPELINE_SINK_SYNC=$(PIPELINE_SINK_SYNC) \
	PIPELINE_DISPLAY_VIEW=$(PIPELINE_DISPLAY_VIEW) PIPELINE_VIDEO_SINK=$(PIPELINE_VIDEO_SINK) \
	PIPELINE_GST_CORES=$(PIPELINE_GST_CORES) \
	PIPELINE_GST_RT_PRIORITY=$(PIPELINE_GST_RT_PRIORITY) \
	PIPELINE_PREPROC_BACKEND=$(PIPELINE_PREPROC_BACKEND) \
	PIPELINE_IE_CONFIG=$(PIPELINE_IE_CONFIG) \
	PIPELINE_FPSCOUNTER=$(PIPELINE_FPSCOUNTER) \
	BASLER_FIXED_CAMERA=$(BASLER_FIXED_CAMERA) BASLER_EXPOSURE_US=$(BASLER_EXPOSURE_US) BASLER_GAIN=$(BASLER_GAIN) \
	BASLER_THROUGHPUT_LIMIT=$(BASLER_THROUGHPUT_LIMIT) \
	BASLER_PIXEL_FORMAT=$(BASLER_PIXEL_FORMAT) \
	RENDER_GID=$(RENDER_GID) VIDEO_GID=$(VIDEO_GID) \
		$(COMPOSE) -f docker-compose.yaml $$(test -f $(CAMERA_OVERRIDE) && echo -f $(CAMERA_OVERRIDE)) up -d
	$(_print_urls)

.PHONY: show-cores
show-cores:  ## Show P-core / E-core CPU sets for optimal core-pinning (Case 4)
	@ALL=$$(cat /sys/devices/system/cpu/present 2>/dev/null || echo 'unknown'); \
	PCORE=$$(cat /sys/devices/cpu_core/cpus 2>/dev/null); \
	ECORE=$$(cat /sys/devices/cpu_atom/cpus 2>/dev/null); \
	N=$$(nproc 2>/dev/null || echo '?'); \
	printf '\n[cores] all CPUs        : %s  (nproc=%s)\n' "$$ALL" "$$N"; \
	if [ -n "$$PCORE" ]; then \
	  printf '[cores] P-cores (perf)  : %s  <-- use for PIPELINE_GST_CORES\n' "$$PCORE"; \
	  printf '[cores] E-cores (effic) : %s\n' "$$ECORE"; \
	  FIRST=$$(echo "$$PCORE" | grep -oE '^[0-9]+'); \
	  REST=$$(echo "$$PCORE" | sed "s/^[0-9]*-*[0-9]*$$/&/" | \
	          awk -F'-' -v f="$$FIRST" \
	          '{if($$1==f && $$2!="") printf "%d-%s",$$1+1,$$2; else printf "%d",$$1+1}'); \
	  printf '[cores] hint: PIPELINE_GST_CORES=%s\n' "$$PCORE"; \
	  printf '              PIPELINE_GST_RT_PRIORITY=70\n'; \
	else \
	  printf '[cores] no P/E core split detected (non-hybrid CPU or older kernel)\n'; \
	  printf '[cores] all cores are equivalent; use taskset freely.\n'; \
	fi; \
	printf '\n[cores] lscpu sample (top 6 rows):\n'; \
	lscpu -e 2>/dev/null | head -7 || lscpu | head -10; \
	printf '\n'

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
list-cameras:  ## List /dev/video* + Basler serials (SOURCE_ARG values)
	@ls -la /dev/video* 2>/dev/null || echo "[list-cameras] no /dev/video* present"
	@echo ""
	@lsusb -d 2676: 2>/dev/null || echo "[list-cameras] no Basler USB device present"
	@echo ""
	@echo "[list-cameras] Basler serials (SOURCE_ARG candidates):"
	@if python3 -c "import pypylon" >/dev/null 2>&1; then \
		python3 scripts/list_basler.py; \
	elif docker ps --format '{{.Names}}' 2>/dev/null | grep -qx surgical-pipeline; then \
		docker exec surgical-pipeline python3 -c "from pypylon import pylon;\
 devs = pylon.TlFactory.GetInstance().EnumerateDevices();\
 print('  (none)') if not devs else [print(f'  serial={d.GetSerialNumber()}  model={d.GetModelName()}') for d in devs]" \
			2>/dev/null || echo "  (pypylon query failed inside surgical-pipeline)"; \
	elif docker image inspect surgical-pipeline:dev >/dev/null 2>&1; then \
		docker run --rm --entrypoint python3 \
			--device /dev/bus/usb:/dev/bus/usb \
			-v $(PWD)/scripts/list_basler.py:/opt/list_basler.py:ro \
			surgical-pipeline:dev /opt/list_basler.py \
			2>/dev/null || echo "  (pypylon query failed in one-shot container)"; \
	else \
		echo "  (host pypylon missing; install with 'python3 -m pip install pypylon'"; \
		echo "   or run 'make up' once to build the pipeline image and re-run this target)"; \
	fi

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
		if [ -n "$$CAMS" ]; then \
			echo "  surgical-pipeline:"                                                >> $(CAMERA_OVERRIDE); \
			echo "    devices:"                                                        >> $(CAMERA_OVERRIDE); \
			for c in $$CAMS; do echo "      - $$c:$$c"                                >> $(CAMERA_OVERRIDE); done; \
		fi; \
		if [ -n "$$CAMS" ] || [ -n "$$BASLER" ]; then \
			echo "  surgical-backend:"                                                >> $(CAMERA_OVERRIDE); \
			if [ -n "$$CAMS" ]; then \
				echo "    volumes:"                                                    >> $(CAMERA_OVERRIDE); \
				echo "      - /sys/class/video4linux:/sys/class/video4linux:ro"      >> $(CAMERA_OVERRIDE); \
			fi; \
			if [ -n "$$BASLER" ]; then \
				echo "    devices:"                                                    >> $(CAMERA_OVERRIDE); \
				echo "      - /dev/bus/usb:/dev/bus/usb"                              >> $(CAMERA_OVERRIDE); \
				echo "    device_cgroup_rules:"                                        >> $(CAMERA_OVERRIDE); \
				echo "      - 'c 189:* rmw'"                                          >> $(CAMERA_OVERRIDE); \
			fi; \
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
	@DISPLAY=$(PIPELINE_X_DISPLAY) xhost -local:root >/dev/null 2>&1 || true

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
	missing_l0=""; \
	for pkg in $(L0_PKGS); do \
	  if ! dpkg-query -W -f='$${Status}' "$$pkg" 2>/dev/null | grep -q "install ok installed"; then \
	    missing_l0="$$missing_l0 $$pkg"; \
	  fi; \
	done; \
	if [ -z "$$missing_l0" ]; then \
	  printf "  [ OK ] intel gpu compute runtime (Level Zero + IGC + GMM) installed\n"; \
	else \
	  printf "  [WARN] missing host packages required by 'make backend-bootstrap':%s\n" "$$missing_l0"; \
	  printf "         (in-container 'make up' is unaffected — see docs/user-guide/quickstart.md §1a)\n"; \
	  printf "         install with 'make check-l0' to see the exact apt commands\n"; \
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

# Intel GPU compute runtime packages required on the HOST for `make
# backend-bootstrap` (torch+xpu loads Level Zero + IGC + GMM from the host).
# Container-side runs (`make up`) install these inside the image and are
# unaffected. Keep this list in sync with the Dockerfile and with the
# "Host prerequisites" section of docs/user-guide/quickstart.md.
L0_PKGS ?= libze1 libze-intel-gpu1 intel-igc-core-2 libigdgmm12 intel-opencl-icd

# Preflight helper: prints [ OK ] / [FAIL] for every L0_PKGS entry. Prints
# copy-pasteable apt commands and exits non-zero if any are missing. Used
# by `backend-venv` and `backend-bootstrap` so operators do not silently
# hit `torch.xpu.is_available() == False` or `zeInit` loader errors.
define _check_l0_pkgs
	@missing=""; \
	for pkg in $(L0_PKGS); do \
	  if dpkg-query -W -f='$${Status}' "$$pkg" 2>/dev/null | grep -q "install ok installed"; then \
	    printf "  [ OK ] $$pkg\n"; \
	  else \
	    printf "  [FAIL] $$pkg (not installed)\n"; \
	    missing="$$missing $$pkg"; \
	  fi; \
	done; \
	if [ -n "$$missing" ]; then \
	  echo ""; \
	  echo "  Missing Intel GPU compute runtime packages required by torch+xpu."; \
	  echo "  Install them once from the Intel graphics apt repo (Ubuntu 24.04):"; \
	  echo ""; \
	  echo "    sudo apt-get update && sudo apt-get install -y ca-certificates gnupg wget"; \
	  echo "    wget -qO - https://repositories.intel.com/gpu/intel-graphics.key \\"; \
	  echo "      | sudo gpg --dearmor -o /usr/share/keyrings/intel-graphics.gpg"; \
	  echo "    echo \"deb [arch=amd64 signed-by=/usr/share/keyrings/intel-graphics.gpg] \\"; \
	  echo "    https://repositories.intel.com/gpu/ubuntu noble unified\" \\"; \
	  echo "      | sudo tee /etc/apt/sources.list.d/intel-gpu-noble.list"; \
	  echo "    sudo apt-get update && sudo apt-get install -y$$missing intel-media-va-driver-non-free"; \
	  echo ""; \
	  echo "  See docs/user-guide/quickstart.md \"1a. Intel GPU compute runtime\" for details."; \
	  exit 1; \
	fi
endef

.PHONY: check-l0
check-l0:  ## Verify host Intel GPU compute runtime (Level Zero + IGC + GMM) is installed
	@printf "[check-l0] verifying host Intel GPU compute runtime packages...\n"
	$(_check_l0_pkgs)
	@printf "[check-l0] all required packages present.\n"

.PHONY: backend-venv
backend-venv:  ## Create .venv-backend with torch+xpu + Ultralytics + OpenVINO
	@printf "[backend-venv] checking host Intel GPU compute runtime...\n"
	$(_check_l0_pkgs)
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
	@printf "[backend-bootstrap] checking host Intel GPU compute runtime...\n"
	$(_check_l0_pkgs)
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


