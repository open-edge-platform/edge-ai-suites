<!--
SPDX-FileCopyrightText: (C) 2026 Intel Corporation
SPDX-License-Identifier: Apache-2.0
-->

# Troubleshooting

---

## Table of Contents

- [Setup & Installation](#setup--installation)
- [Stack & Containers](#stack--containers)
- [Pipelines](#pipelines)
- [Benchmark](#benchmark)
- [QGroundControl](#qgroundcontrol)

---

## Setup & Installation

### `make model` fails — `python3-venv` not available

**Symptom:**

```
The virtual environment was not created successfully because ensurepip is not available.
On Debian/Ubuntu systems, you need to install the python3-venv package using the following command.
    apt install python3.12-venv
Failing command: .../resources/venv/bin/python3
make: *** [Makefile:28: model] Error 1
```

**Resolution:** Install the `python3-venv` package and re-run:

```bash
sudo apt install python3.12-venv
make model
```

---

### `make pymav-up` fails — pip install cannot reach PyPI

**Symptom:**

```
WARNING: Retrying after connection broken by 'NewConnectionError([Errno 101] Network is unreachable)': /simple/pymavlink/
ERROR: Could not find a version that satisfies the requirement pymavlink
```

**Cause:** The Docker build container for `dlstreamer-pipeline-server` (which runs `pip install pymavlink`) does not have proxy environment variables set. `https_proxy` set in `/etc/environment` on the host is not automatically inherited by Docker build containers.

**Resolution:** Pass proxy variables as build args in `docker-compose-pymavlink.yml` for the `dlstreamer-pipeline-server` service:

```yaml
services:
  dlstreamer-pipeline-server:
    build:
      context: .
      args:
        http_proxy:  ${http_proxy:-}
        https_proxy: ${https_proxy:-}
        no_proxy:    ${no_proxy:-localhost,127.0.0.0/8}
      dockerfile_inline: |
        FROM ${DLSTREAMER_PIPELINE_SERVER_IMAGE}
        ARG http_proxy
        ARG https_proxy
        ARG no_proxy
        RUN pip install --no-cache-dir pymavlink
```

---

### `make pymav-up` fails — `/dev/dri/card0: no such file or directory`

On some machines the Intel iGPU is assigned `card1` instead of `card0` (e.g., when another GPU or firmware device claims `card0` first). Run `init` to auto-detect the correct paths:

```bash
make init          # detects /dev/dri/card* and /dev/dri/renderD* and writes them to .env
make pymav-up
```

To verify the detected device belongs to the Intel iGPU:

```bash
ls -la /sys/class/drm/ | grep card
# card1 -> .../0000:00:02.0/drm/card1  ← Intel iGPU at PCI 00:02.0
```

If `make init` already ran (`.env` exists), edit `.env` manually:

```bash
GPU_DEVICE=/dev/dri/card1
GPU_RENDER_DEVICE=/dev/dri/renderD128
```

---

### `ffplay: command not found`

**Symptom:**

```
ffplay rtsp://<HOST_IP>:8555/uav-mavlink-cpu
Command 'ffplay' not found, but can be installed with:
sudo apt install ffmpeg
```

**Resolution:** `ffplay` is part of the `ffmpeg` package:

```bash
sudo apt install ffmpeg

# Then verify RTSP stream
ffplay rtsp://<HOST_IP>:8555/uav-mavlink-cpu
```

To view the output stream without `ffplay` (e.g., on a headless server), record it instead:

```bash
ffmpeg -rtsp_transport tcp \
  -i "rtsp://<HOST_IP>:8555/uav-mavlink-cpu" \
  -c copy -t 30 output.mkv
```

---

## Stack & Containers

### DL Streamer container keeps restarting

- Check logs: `docker logs dlstreamer-pipeline-server`
- Verify the model files exist:
  ```bash
  docker exec dlstreamer-pipeline-server ls \
    /home/pipeline-server/resources/models/yolov8n-visdrone/best_openvino_model/
  ```
- Confirm `HOST_IP` is set correctly in `.env`.
- If the model is missing, run `make model`, then restart the stack:
  ```bash
  make pymav-down && make pymav-up
  ```

---

### PX4 SITL — image pull or runtime issues

**Symptom:** The `px4` service fails to start or behaves unexpectedly with the `latest` tag.

**Resolution:** Pin the PX4 SITL image to a known-good digest in `docker-compose-pymavlink.yml`:

```diff
-image: px4io/px4-sitl:latest
+image: px4io/px4-sitl@sha256:01866d912ac22ca6119a996b830cf628a6d47dfb60fdccc41cd9f44b62935a44
```

---

## Pipelines

### No telemetry overlay on stream (all zeros)

**pymavlink mode:** Confirm `mavlink-router` is running and forwarding MAVLink from PX4:

```bash
docker logs mavlink-router
docker logs px4 | grep -i mavlink
```

**uav-mission-compute-sdk mode:** Confirm the SDK MQTT broker is reachable and publishing telemetry:

```bash
mosquitto_sub -h localhost -p 1884 -t "uav/uav-1/telemetry/#" -v
```

---

### Pipelines not starting in uav-mission-compute-sdk mode

- Confirm `pipeline_manager.py` is running inside the container:
  ```bash
  docker exec dlstreamer-pipeline-server ps aux | grep pipeline
  ```
- Check that the RTSP sources from the SDK are available:
  ```bash
  ffprobe rtsp://localhost:8554/uav-1/nadir
  ```
- Verify the UAV is armed — pipelines only start on ARMED state.

---

### NPU inference fails

- Confirm `ZE_ENABLE_ALT_DRIVERS=libze_intel_npu.so` is set (it is by default in the compose files).
- Check that the NPU device node is available: `ls /dev/accel*`
- Verify driver version: `dmesg | grep -i npu`

---

### GPU pipeline falls back to CPU

- Confirm device group IDs are present: `getent group | grep -E '^(video|render)'`
- The compose files add groups `44`, `109`, `110` for video/render device access.
- Check for the render node: `ls /dev/dri/renderD128`

---

### UDP sink pipeline not working

**Symptom:** The UDP sink pipeline fails to send or receive data.

**Resolution:** Replace `127.0.0.1` with `0.0.0.0` in the sink address so it binds to all interfaces:

```diff
-udpsink host=127.0.0.1 port=5600
+udpsink host=0.0.0.0 port=5600
```

---

### Pipeline fails with `gst_parse_error: no element "vah264enc"`

Replace `vah264enc` with `vah264lpenc`

```bash
{"levelname": "ERROR", "asctime": "2026-08-15 11:53:30,507", "message": "Error on Pipeline ef2c39be989f11f189d8c9d3068f2a21: gst_parse_error: no element \"vah264enc\" (1)", "module": "gstreamer_pipeline"}
```

---

## Benchmark

### `jq: command not found`

`jq` is not installed on the benchmark host. Two options:

```bash
# Option 1: install via apt (requires sudo)
sudo apt-get install -y jq

# Option 2: docker exec wrapper (no root needed, works when DLSPS container is running)
mkdir -p ~/.local/bin
cat > ~/.local/bin/jq << 'EOF'
#!/usr/bin/env bash
CONTAINER="dlstreamer-pipeline-server"
args=()
for arg in "$@"; do
  if [[ -f "$arg" ]]; then
    cat "$arg" | docker exec -i "$CONTAINER" jq "${args[@]}"
    exit $?
  else
    args+=("$arg")
  fi
done
docker exec -i "$CONTAINER" jq "${args[@]}"
EOF
chmod +x ~/.local/bin/jq
export PATH="$HOME/.local/bin:$PATH"
# To make permanent:
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
```

---

### `gawk: command not found`

```bash
sudo apt-get install -y gawk
```

---

### `Error: DLSPS not reachable at http://localhost:8081`

The `dlstreamer-pipeline-server` container is not running. Start the full stack:

```bash
make pymav-up
```

If the port mapping differs from the default `8081`, override:

```bash
DLSPS_PORT=8080 ./benchmark/calc_stream_density.sh ...
```

---

### `fps=0` / `throughput min: 0` after a run

Possible causes:

- **DLSPS pipeline in ERROR state** — often a shared `model-instance-id` from a previous aborted run:
  ```bash
  docker restart dlstreamer-pipeline-server
  ```
- **RTSP path conflict** — restart DLSPS to clear leftover path registrations.
- **Video file missing inside the container:**
  ```bash
  docker exec dlstreamer-pipeline-server ls \
    /home/pipeline-server/resources/videos/
  ```

---

## QGroundControl

### "Network Not Available" warnings

See [QGroundControl](./qgroundcontrol.md) for installation and video stream configuration.

**Symptom:** The following warnings appear in the QGroundControl logs:

```
16.701 Warning: 1 "Network Not Available" - QtLocationPlugin.QGeoTiledMapReplyQGC - (unknown:0)
```

**Cause:** NetworkManager's connectivity check is failing, which causes it to report the network as `limited` or `none` even when the host has a valid local connection.

**Resolution:**

1. Confirm the connectivity state:

    ```bash
    nmcli networking connectivity check   # expected: "limited" or "none"
    ```

2. Disable the NetworkManager connectivity check:

    ```bash
    sudo mkdir -p /etc/NetworkManager/conf.d
    sudo tee /etc/NetworkManager/conf.d/20-connectivity.conf <<'EOF'
    [connectivity]
    enabled=false
    EOF
    sudo systemctl restart NetworkManager
    ```

3. Verify the state is now reported as full:

    ```bash
    nmcli networking connectivity check   # expected: "full"
    ```

**Symptom:**

```
The virtual environment was not created successfully because ensurepip is not available.
On Debian/Ubuntu systems, you need to install the python3-venv package using the following command.
    apt install python3.12-venv
Failing command: .../resources/venv/bin/python3
make: *** [Makefile:28: model] Error 1
```

**Resolution:** Install the `python3-venv` package and re-run:

```bash
sudo apt install python3.12-venv
make model
```

