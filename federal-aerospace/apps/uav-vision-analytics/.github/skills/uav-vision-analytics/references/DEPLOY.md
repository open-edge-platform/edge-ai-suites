<!-- SPDX-FileCopyrightText: (C) 2026 Intel Corporation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Deployment Reference — UAV Vision Analytics

## Docker Compose Service Map

### pymavlink mode (`docker-compose-pymavlink.yml`)

| Service | Image | Ports | Role |
|---------|-------|-------|------|
| `dlstreamer-pipeline-server` | `${DLSTREAMER_PIPELINE_SERVER_IMAGE}`-pymavlink (built inline with `pip install pymavlink`) | `8081`, `8555` | AI inference + RTSP output |
| `broker` | `eclipse-mosquitto:2.0.22` | `1883` | MQTT broker for detection metadata |
| `px4` | `px4io/px4-sitl:latest` | — | PX4 SITL flight controller simulator |
| `mavlink-router` | custom build | — | Routes MAVLink :14550 → :14541 |
| `metrics-manager` | `intel/metrics-manager:2026.1.0-*` | — | CPU/GPU/NPU/power metrics collection |

### UAVSDK mode (`docker-compose-uavsdk.yml`)

| Service | Image | Ports | Role |
|---------|-------|-------|------|
| `dlstreamer-pipeline-server` | `${DLSTREAMER_PIPELINE_SERVER_IMAGE}` | `8081`, `8555` | AI inference + RTSP output |

**Prerequisite:** `uav-mission-compute-sdk` must already be running.

---

## mavlink-router Self-Containment (pymavlink mode)

The pymavlink stack MUST be fully self-contained and buildable without any
sibling repository being checked out. Never set the `mavlink-router` service's
build `context` to a path outside `{{STACK_DIR}}` (for example, do NOT
reference `../../uav-mission-compute-sdk/infra/px4-sim/mavlink-router`) —
that path will not exist for a standalone `{{STACK_DIR}}` and `docker compose
up` fails with `unable to prepare context: path ... not found`.

Always copy both files into the generated stack and build from the local
directory:

```
{{STACK_DIR}}/mavlink-router/
├── Dockerfile     # builds mavlink-router from source (ubuntu:24.04 base)
└── main.conf      # routing config (may be stack-specific, see TELEMETRY.md)
```

```yaml
mavlink-router:
  build:
    context: ./mavlink-router
    dockerfile: Dockerfile
    args:
      http_proxy:  ${http_proxy:-}
      https_proxy: ${https_proxy:-}
      no_proxy:    ${no_proxy:-localhost,127.0.0.0/8}
      NO_PROXY:    ${NO_PROXY:-localhost,127.0.0.0/8}
  container_name: mavlink-router
  restart: unless-stopped
  volumes:
    - ./mavlink-router/main.conf:/etc/mavlink-router/main.conf
  networks:
    - app_network
```

The `Dockerfile` source (clones and builds `mavlink-router` from GitHub) can
be copied from any existing pymavlink stack's `mavlink-router/Dockerfile` in
this repo, or reused as-is:

```dockerfile
FROM ubuntu:24.04

ARG DEBIAN_FRONTEND=noninteractive
ARG http_proxy
ARG https_proxy
ARG no_proxy
ENV http_proxy=${http_proxy} https_proxy=${https_proxy} no_proxy=${no_proxy}

RUN apt-get update && apt-get install -y --no-install-recommends \
    git ca-certificates build-essential pkg-config \
    libssl-dev meson ninja-build python3-pip \
    && rm -rf /var/lib/apt/lists/*

RUN git clone --depth 1 https://github.com/mavlink-router/mavlink-router.git /src \
    && cd /src \
    && git submodule update --init --recursive \
    && meson setup build . -Dsystemdsystemunitdir=/usr/lib/systemd/system \
    && ninja -C build \
    && ninja -C build install \
    && rm -rf /src

ENV http_proxy= https_proxy= no_proxy=

COPY main.conf /etc/mavlink-router/main.conf

CMD ["mavlink-routerd", "-c", "/etc/mavlink-router/main.conf"]
```

The `main.conf` bind-mounted at runtime overrides the one baked in at build
time, so stack-specific routing (e.g. broadcast vs. point-to-point UDP
endpoints, see `references/TELEMETRY.md`) always takes effect.

---

## DLSPS Docker Compose Fragment

```yaml
dlstreamer-pipeline-server:
  build:
    context: .
    dockerfile_inline: |
      FROM ${DLSTREAMER_PIPELINE_SERVER_IMAGE}
      RUN pip install --no-cache-dir pymavlink    # pymavlink mode only
  image: ${DLSTREAMER_PIPELINE_SERVER_IMAGE}-pymavlink
  container_name: dlstreamer-pipeline-server
  environment:
    - http_proxy=${http_proxy}
    - https_proxy=${https_proxy}
    - no_proxy=${no_proxy},${HOST_IP}
    - NO_PROXY=${no_proxy},${HOST_IP}
    - ENABLE_RTSP=true
    - RTSP_PORT=8555
    - RUN_MODE=EVA
    - EMIT_SOURCE_AND_DESTINATION=true
    - REST_SERVER_PORT=8081
    - SERVICE_NAME=dlstreamer-pipeline-server
    - MQTT_HOST=broker
    - MQTT_PORT=1883
    - APPEND_PIPELINE_NAME_TO_PUBLISHER_TOPIC=true
    - ZE_ENABLE_ALT_DRIVERS=libze_intel_npu.so
  volumes:
    - dlstreamer-pipeline-server-pipeline-root:/var/cache/pipeline_root:uid=1999,gid=1999
    - "./resources:/home/pipeline-server/resources"
    - "./configs/config-pymavlink.json:/home/pipeline-server/config.json"
    - "./gvapython/telemetry-overlay-pymavlink.py:/home/pipeline-server/gvapython/telemetry-overlay-pymavlink.py"
    - "./scripts/mavlink_pipeline_manager.py:/home/pipeline-server/scripts/pipeline_manager.py"
    - "/run/udev:/run/udev:ro"
    - "/dev:/dev"
    - "/tmp:/tmp"
  group_add:
    - "44"    # video
    - "109"   # render (adjust per host: stat -c %g /dev/dri/render*)
    - "110"
    - "990"
    - "992"
    - "993"
    - "994"
    - "996"
  device_cgroup_rules:
    - "c 189:* rmw"
    - "c 209:* rmw"
    - "a 189:* rwm"
  devices:
    - "/dev:/dev"
  ports:
    - '8081:8081'
    - "8555:8555"
  networks:
    - app_network
  extra_hosts:
    - "host.docker.internal:host-gateway"
```

**For UAVSDK mode** mount the UAVSDK overlay and manager instead:
```yaml
    - "./gvapython/telemetry-overlay-uavsdk.py:/home/pipeline-server/gvapython/telemetry-overlay-uavsdk.py"
    - "./scripts/uavsdk_pipeline_manager.py:/home/pipeline-server/scripts/pipeline_manager.py"
```
And set `UAV_ID` env var (default `uav-1`).

---

## .env Variables

```bash
# Host network
HOST_IP=192.168.1.x           # LAN IP — NOT 127.0.0.1; used for RTSP URLs

# DL Streamer image
DLSTREAMER_PIPELINE_SERVER_IMAGE=intel/dlstreamer-pipeline-server:2026.1.0-ubuntu24

# Proxy (leave blank if not behind corporate proxy)
http_proxy=
https_proxy=
no_proxy=localhost,127.0.0.0/8
```

---

## Makefile Targets

```makefile
.PHONY: init model pymav-up pymav-down uavsdk-up uavsdk-down start-rtsp

init:        ## Create .env from .env.example and auto-detect GPU/NPU device paths
model:       ## Download and export YOLOv8n-VisDrone to OpenVINO FP16
pymav-up:    ## Start pymavlink stack (docker-compose-pymavlink.yml)
pymav-down:  ## Stop pymavlink stack
uavsdk-up:   ## Start UAVSDK stack (requires uav-mission-compute-sdk running first)
uavsdk-down: ## Stop UAVSDK stack
start-rtsp:  ## Launch pipeline_manager.py --sink rtsp inside container
```

Full Makefile is in `apps/uav-vision-analytics/Makefile`.

---

## Network Architecture

### pymavlink

```
PX4 SITL ──MAVLink──▶ mavlink-router (:14550 server → :14541 broadcast)
                                           │
                           DLSPS ◀─UDP :14541─┘
                             │
                        ┌────┤
                        │    └──▶ RTSP :8555 → QGC / ffplay rtsp://...
                        │
                    MQTT :1883 ──▶ Mosquitto broker
```

### MAVSDK

```
uav-mission-compute-sdk:
  PX4+Gazebo → companion-bridge → MQTT broker (:1884)
                               → RTSP server (:8554) [camera streams]

DLSPS container:
  MQTT subscriber → on ARMED → POST pipelines
  rtspsrc ← RTSP (:8554) [nadir/forward/rear]
  appsink → RTSP output :8555
```

---

## Device Group IDs

The `group_add` list must include the numeric GIDs for `/dev/dri` (GPU) and
`/dev/accel` (NPU). Check on the host:

```bash
stat -c %g /dev/dri/render*
stat -c %g /dev/accel/accel*
```

Update the `group_add` list in the compose file accordingly.

---

## Volumes

```yaml
volumes:
  dlstreamer-pipeline-server-pipeline-root:
    driver: local
    driver_opts:
      type: tmpfs
      device: tmpfs
```

The pipeline root is a tmpfs (in-memory) volume, reset on every container
recreation. Always use `docker compose up -d --force-recreate` (not `restart`)
when changing `config.json` — plain `restart` keeps the stale tmpfs.
