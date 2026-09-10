<!--
SPDX-FileCopyrightText: (C) 2026 Intel Corporation
SPDX-License-Identifier: Apache-2.0
-->

# Install OEP SDK and Usage

This page covers installing the UAV Mission Compute SDK on a provisioned Uncrewed Aerial Vehicle (UAV) target and validating the stack with the built-in PX4 + Gazebo simulation, RTSP streams, and OpenVINO vision processor.

The provisioned image ships with system-level dependencies only — kernel, GPU/NPU drivers, Docker Engine, and container device plugins. The UAV Mission Compute SDK, container images, simulation stack, and OpenVINO Python runtime must be installed on the target as described below.

For image build and platform provisioning, see [Infrastructure Setup](../infrastructure-setup.md).

## OEP SDK installation

### Prerequisites

- UAV platform provisioned per [Infrastructure Setup](../infrastructure-setup.md).
- Passwordless SSH or console access to the target.
- Internet connectivity (or configured proxy) on the target for package and container image downloads.
- Minimum 16 GB RAM (32 GB recommended) and 100 GB free disk space for the simulation stack, container images, and models.
- Intel Core Ultra Series 3 (Panther Lake) with integrated GPU recommended.

### Step 1: Verify Hardware Accelerators

Confirm the GPU and NPU are visible to the OS before installing the SDK:

```bash
# GPU (integrated Arc, exposed as DRI render device)
ls -l /dev/dri/

# NPU (exposed via intel_vpu driver)
ls -l /dev/accel/
lsmod | grep intel_vpu
```

Expected: `card0`/`renderD128` under `/dev/dri`, `accel0` under `/dev/accel`, and the `intel_vpu` module loaded.

### Step 2: Install the UAV Mission Compute SDK

Get the UAV Mission Compute SDK source on the target and start the simulation stack.

```bash
curl -OjL https://github.com/open-edge-platform/edge-ai-suites/releases/download/fedaero-latest/uav-mission-apps.zip
unzip uav-mission-apps.zip
cd uav-mission-compute-sdk/
```

Then, initialize and start the SDK:

```bash
make init
make up-sim-camera
```

This startup flow brings up:

- PX4 autopilot simulation with Gazebo Harmonic
- Multi-camera bridge (nadir, forward, rear at 416×416 @20 fps)
- Companion telemetry bridge (MAVLink → MQTT)
- MQTT broker (Mosquitto) and MediaMTX RTSP server
- InfluxDB time-series storage and Grafana dashboards
- Metrics manager for host platform monitoring
- OpenVINO-based vision processor (YOLOv2 vehicle detection on Intel GPU)

The initial image build typically takes 10-15 minutes. After startup completes, the full stack is running from the `uav-mission-compute-sdk` directory.

For details on deployment options and restart procedures, see the [UAV Mission Compute SDK Get Started guide](https://github.com/open-edge-platform/edge-ai-suites/blob/main/federal-and-aerospace-ai-suite/uav-mission-compute-sdk/docs/user-guide/get-started.md).

### Step 3: Validate the Running Stack

After the stack is running, follow these steps to arm the UAV and confirm live camera streams.

#### Step 3.1: Wait for PX4 to be healthy

First boot takes ~60–90 seconds:

```bash
docker compose ps px4
```

Wait until `px4` reports a healthy status.

#### Step 3.2: Arm the UAV (activate cameras)

Cameras only stream when the UAV is armed. Arm it via the REST API:

```bash
curl -X POST http://localhost:8080/action/arm
```

#### Step 3.3: Take off (generate motion in the scene)

Command takeoff so the UAV climbs and moves through the Gazebo world — cameras then produce meaningful frames instead of a static ground view:

```bash
curl -X POST http://localhost:8080/action/takeoff
```

The UAV climbs to the default hover altitude.

#### Step 3.4: Capture the Video Stream during flight (Optional)

Once the UAV is in flight, verify the state before capturing video streams:

```bash
curl -X GET http://localhost:8080/state
# Expect: "armed": true; Retry arm and takeoff if false
```

Now, record the UAV camera stream to disk with `ffmpeg`:

```bash
# Records a footage for 10 seconds and saves to nadir.mkv
ffmpeg -rtsp_transport tcp -i rtsp://localhost:8554/uav-1/nadir -t 10 -c:v copy nadir.mkv
```

To preview the live stream instead of recording (if not on a headless system):

```bash
ffplay rtsp://localhost:8554/uav-1/nadir
```

Available cameras: `nadir`, `forward`, `rear`.

#### Step 3.5: Access dashboards and APIs

- **Grafana dashboards:** `http://localhost:3000` — flight and platform metrics
  - Credentials are available in the `.env` file.
  - On a headless target, Grafana is only reachable through a reverse tunnel from a machine with a GUI/browser.
- **REST API:** `http://localhost:8080` — flight control commands (`arm`, `takeoff`, `land`)

#### Step 3.6: Stop the stack

When done, land the UAV with:

```bash
curl -X POST http://localhost:8080/action/land
```

To stop the entire infrastructure stack:

```bash
make down
```

## Developer Experience

This section is a practical guide for developers building a new application on top of a running SDK stack. It focuses on the integration contracts your app must respect, a minimal app skeleton, an inner development loop, and a tuning workflow.

The [UAV Vision Analytics](./get-started-uavsdk.md) application is referenced only as a working example of these patterns; you do not need to replicate its structure.

### 1) What the SDK gives your app

Once `make up-sim-camera` is up, treat the SDK as a fixed platform layer that your app consumes over three well-defined interfaces:

| Interface | Endpoint (default) | What your app does with it |
|---|---|---|
| Telemetry (MQTT) | `mqtt://<host>:1884`, topics `uav/<id>/telemetry/#` | Subscribe to position, attitude, battery, GPS, and armed/disarmed state |
| Video (RTSP) | `rtsp://<host>:8554/uav-1/{nadir,forward,rear}` | Read one or more H.264 camera streams |
| Vehicle control (REST) | `http://<host>:8080/action/*`, `/telemetry`, `/state` | Arm, takeoff, land, return, or query current state |
| Results/publish (MQTT) | `mqtt://<host>:1884`, custom topics under `uav/<id>/app/...` | Publish detections, alerts, or app events |
| Observability (optional) | InfluxDB `:8086`, Grafana `:3000` | Persist and visualize app metrics |

Key runtime facts to design around:

- **Camera streams are gated by armed state.** RTSP paths return 404 while the UAV is disarmed; subscribe to `uav/<id>/telemetry/status` and (re)connect on transitions.
- **Sim and USB camera profiles are mutually exclusive.** Do not assume all three cameras exist; read `VISION_CAMERA_IDS` (or your own app config) instead of hard-coding.
- **Ports are bound to `HOST_IP` from `.env`.** If your app runs in a separate container/network, set `HOST_IP=0.0.0.0` in the SDK's `.env` before `make up-sim-camera`, otherwise services will be reachable only on loopback.

### 2) Build your app

#### Choose a deployment shape

Pick one based on how tightly your app needs to co-locate with the SDK:

- **Sidecar container on the SDK Compose network** — simplest for accessing services by DNS name (`mosquitto`, `mediamtx`, `companion-bridge`) without exposing ports. Add a service to your own `docker-compose.yml` and attach `networks: [uav-mission-compute-sdk_default]` (or the actual network name from `docker network ls`).
- **Standalone container / host process** — connect to published host ports (`localhost:1884`, `localhost:8554`, `localhost:8080`). Requires `HOST_IP=0.0.0.0` in the SDK's `.env`.
- **Remote host** — same as standalone, but point at the SDK host's IP. Use only in a trusted network; MQTT and RTSP are unauthenticated by default.

#### Minimal app skeleton

A typical app has three concerns:

1. **State awareness** — an MQTT subscriber on `uav/<id>/telemetry/status` that pauses/resumes work when the drone arms or disarms.
2. **Data pipeline** — one or more consumers of RTSP (video) and/or MQTT telemetry that run your logic (inference, fusion, mission planning, logging).
3. **Output** — publish results back to MQTT, expose a REST/UI endpoint, or write files/streams.

Suggested layout:

```text
my-uav-app/
  docker-compose.yml       # your service(s), attached to the SDK network
  Dockerfile
  app/
    main.py                # bootstrap, config, health endpoint
    telemetry.py           # MQTT subscribe: armed state + topics you need
    video.py               # RTSP consumer (GStreamer, OpenCV, FFmpeg)
    logic.py               # your inference / control logic
    publish.py             # MQTT publisher for detections / events
  .env.example             # HOST, UAV_ID, camera selection, model paths
  Makefile                 # up / down / logs / model / lint targets
```

For a concrete implementation of this shape, see [UAV Vision Analytics Get Started](./get-started-uavsdk.md).

#### Inner development loop

1. Bring up SDK infra once: `make up-sim-camera` from the SDK directory.
2. Verify interfaces from your dev shell before writing app code:
   ```bash
   mosquitto_sub -h localhost -p 1884 -t "uav/uav-1/telemetry/#" -v
   curl -s http://localhost:8080/state
   ffprobe -rtsp_transport tcp rtsp://localhost:8554/uav-1/nadir   # after arm
   ```
3. Arm and take off once to unlock RTSP streams; keep a mission running in a side terminal.
4. Build and run your app (`docker compose up --build` or `python -m app.main`); iterate on code with volume mounts or hot reload.
5. Tail SDK and app logs side by side (`docker compose logs -f <service>`).

#### Automate repetitive steps with agent skills

Use [SDK Agent Commands and MCP Tools](../infrastructure/uav-sdk-apps-skill.md) once the manual loop above is working, to shorten common cycles:

For prompt-driven workflows, review the [MCP server examples](https://github.com/open-edge-platform/edge-ai-suites/blob/main/federal-and-aerospace-ai-suite/uav-mission-compute-sdk/mcp-server/examples/README.md) (quick status, real-time monitoring, anomaly detection, battery prediction, video processing, and full application-development patterns for computer vision and time-series pipelines). These examples show that you can describe requirements in natural language and have the tooling compose and wire a complete app workflow from a single prompt, then refine it iteratively with additional prompts.

- Slash commands for stack lifecycle (start, validate, capture a frame, switch camera mode, cleanup).
- MCP tools for pipeline composition, telemetry queries, and app deployment actions.

### 3) Tune your app

Treat tuning as a measured loop, not one-off tweaks.

**App-level tuning** — driven by the [UAV Mission Compute SDK Benchmarking Guide](https://github.com/open-edge-platform/edge-ai-suites/blob/main/federal-and-aerospace-ai-suite/uav-mission-compute-sdk/docs/user-guide/benchmarking.md):

1. Capture a baseline with `make bench` (passive), `make bench-bridge-sweep` (publish-rate sweep), and `make bench-client-sweep` (subscriber fan-out).
2. Correlate against your app's own metrics: end-to-end latency, dropped frames, inference FPS, memory/GPU headroom.
3. Adjust the variables you actually control — model precision (FP16/INT8), inference device (CPU/GPU/NPU), pipeline resolution/framerate, subscribed cameras, MQTT QoS, and telemetry publish rates.
4. Re-benchmark and diff; commit the working configuration to your app's `.env` or config file.

**Platform-level tuning** — use [Infrastructure AI Agent Integration](../infrastructure/agent-skills.md) to apply and verify host-level policies:

- Power envelope (`set-power-profile`) and thermal policy (`set-thermal-profile`) for sustained performance.
- Combined stress + monitor (`combined-power-thermal-profiling`) to confirm your app holds up under real thermal load.

**Recommended targets to watch:**

- Telemetry avg latency < 5 ms, P99 < 20 ms, jitter < 5 ms on loopback.
- Rate CV < 10% across subscribers under your expected client count.
- GPU/NPU utilization steady (not throttling) at the selected power profile.

## Next Steps

- Review the upstream [UAV Mission Compute SDK Get Started](https://github.com/open-edge-platform/edge-ai-suites/blob/main/federal-and-aerospace-ai-suite/uav-mission-compute-sdk/docs/user-guide/get-started.md) for USB camera setup and advanced configuration.

- Review the [UAV Mission Compute SDK Benchmarking Guide](https://github.com/open-edge-platform/edge-ai-suites/blob/main/federal-and-aerospace-ai-suite/uav-mission-compute-sdk/docs/user-guide/benchmarking.md) for telemetry and bridge performance benchmarking.

- Refer to [Get Started — UAV Mission Compute SDK Mode](./get-started-uavsdk.md) for application deployment and running the vision analytics stack against the live UAV SDK services.

## Related Guides

- [DL Streamer Pipelines Guide](../infrastructure/build-dlstreamer-pipelines.md) — pipeline reference and variants
- [Edge Workloads and Benchmarks Guide](../benchmarking/run-edge-benchmarks.md) — reproducible benchmark suite
- [Container Device Interface Guide](../infrastructure/configure-cdi.md) — CDI setup for GPU/NPU access from containers
