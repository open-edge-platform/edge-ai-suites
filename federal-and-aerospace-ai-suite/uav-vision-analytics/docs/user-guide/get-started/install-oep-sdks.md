<!--
SPDX-FileCopyrightText: (C) 2026 Intel Corporation
SPDX-License-Identifier: Apache-2.0
-->

# Install OEP SDKs

This page covers installing the UAV Mission Compute SDK on a provisioned Uncrewed Aerial Vehicle (UAV) target and validating the stack with the built-in PX4 + Gazebo simulation, RTSP streams, and OpenVINO vision processor.

The provisioned image ships with system-level dependencies only — kernel, GPU/NPU drivers, Docker Engine, and container device plugins. The UAV Mission Compute SDK, container images, simulation stack, and OpenVINO Python runtime must be installed on the target as described below.

For image build and platform provisioning, see [Infrastructure Setup](../infrastructure-setup.md).

## Prerequisites

- UAV platform provisioned per [Infrastructure Setup](../infrastructure-setup.md).
- Passwordless SSH or console access to the target.
- Internet connectivity (or configured proxy) on the target for package and container image downloads.
- Minimum 16 GB RAM (32 GB recommended) and 100 GB free disk space for the simulation stack, container images, and models.
- Intel Core Ultra Series 3 (Panther Lake) with integrated GPU recommended.

## Step 1: Verify Hardware Accelerators

Confirm the GPU and NPU are visible to the OS before installing the SDK:

```bash
# GPU (integrated Arc, exposed as DRI render device)
ls -l /dev/dri/

# NPU (exposed via intel_vpu driver)
ls -l /dev/accel/
lsmod | grep intel_vpu
```

Expected: `card0`/`renderD128` under `/dev/dri`, `accel0` under `/dev/accel`, and the `intel_vpu` module loaded.

## Step 2: Install the UAV Mission Compute SDK

Run the official UAV Mission Compute SDK installer on the target. It configures Docker, pulls the SDK images, and builds the full simulation stack:

```bash
curl -fsS https://raw.githubusercontent.com/open-edge-platform/edge-ai-suites/refs/heads/main/metro-ai-suite/metro-sdk-manager/scripts/uav-mission-compute-sdk.sh | bash
```

The installer sets up:

- Docker containerization platform
- PX4 autopilot simulation with Gazebo Harmonic
- Multi-camera bridge (nadir, forward, rear at 416×416 @20 fps)
- Companion telemetry bridge (MAVLink → MQTT)
- MQTT broker (Mosquitto) and MediaMTX RTSP server
- InfluxDB time-series storage and Grafana dashboards
- Metrics manager for host platform monitoring
- OpenVINO-based vision processor (YOLOv2 vehicle detection on Intel GPU)

Once the script completes, the full stack is built and running under `~/oep/edge-ai-suites/federal-and-aerospace-ai-suite/uav-mission-compute-sdk/`.

For full details, see the [UAV Mission Compute SDK Get Started guide](https://docs.openedgeplatform.intel.com/dev/OEP-articles/oep-sdk-manager/uav-mission-compute-sdk/get-started.html).

## Step 3: Validate the Running Stack

The installer starts the simulation stack automatically. Follow these steps to arm the UAV and confirm live camera streams with inference.

### Step 3.1: Wait for PX4 to be healthy

First boot takes ~60–90 seconds:

```bash
cd ~/oep/edge-ai-suites/federal-and-aerospace-ai-suite/uav-mission-compute-sdk
docker compose ps px4
```

Wait until `px4` reports a healthy status.

### Step 3.2: Arm the UAV (activate cameras)

Cameras only stream when the UAV is armed. Arm it via the REST API:

```bash
curl -X POST http://localhost:8080/action/arm
```

### Step 3.3: Take off (generate motion in the scene)

Command takeoff so the UAV climbs and moves through the Gazebo world — cameras then produce meaningful frames with vehicle detections instead of a static ground view:

```bash
curl -X POST http://localhost:8080/action/takeoff
```

The UAV climbs to the default hover altitude. When done, land it with:

```bash
curl -X POST http://localhost:8080/action/land
```

### Step 3.4: View an RTSP stream

Open any camera feed with an RTSP player:

```bash
# Raw feed
ffplay rtsp://localhost:8554/uav-1/nadir

# Annotated feed with OpenVINO YOLOv2 vehicle detection overlays
ffplay rtsp://localhost:8554/uav-1/nadir/processed
```

Available cameras: `nadir`, `forward`, `rear` (each exposes both the raw and `/processed` variants).

### Step 3.5: Access dashboards and APIs

- **Grafana dashboards:** `http://localhost:3000` (default `admin`/`admin`) — flight and platform metrics
- **REST API:** `http://localhost:8080` — flight control commands (`arm`, `takeoff`, `land`)

### Step 3.6: Stop the stack

To stop the entire infrastructure stack:

```bash
cd ~/oep/edge-ai-suites/federal-and-aerospace-ai-suite/uav-mission-compute-sdk
make down
```

## Step 4 (Optional): Install the OpenVINO Python Runtime

For direct use of `benchmark_app`, model conversion (`ovc`), or Python inference outside the SDK containers, install OpenVINO into a Python virtual environment:

```bash
python3 -m venv ~/ov-env
source ~/ov-env/bin/activate
pip install --upgrade pip
pip install openvino
```

To also enable LLM and VLM inference workflows:

```bash
pip install openvino-genai
```

Verify all three inference devices are visible to OpenVINO:

```bash
python3 -c "import openvino as ov; print(ov.Core().available_devices)"
```

Expected: `['CPU', 'GPU', 'NPU']` (device suffixes may include `GPU.0`).

## Step 5 (Optional): Configure Hugging Face Access

Some SDK extension paths and GenAI workflows pull gated models. Create a token with read scope at [https://huggingface.co/settings/tokens](https://huggingface.co/settings/tokens), accept the model licenses on each model's Hugging Face page with the same account, then export the token:

```bash
export HF_TOKEN=<your-hugging-face-token>
```

Add the export to `~/.bashrc` to persist it across sessions.

## Next Steps

- Review the upstream [UAV Mission Compute SDK Get Started](https://github.com/open-edge-platform/edge-ai-suites/blob/main/federal-and-aerospace-ai-suite/uav-mission-compute-sdk/docs/user-guide/get-started.md) for USB camera setup and advanced configuration.
- Explore the SDK source under `~/oep/edge-ai-suites/federal-and-aerospace-ai-suite/uav-mission-compute-sdk/`.

## Related Guides

- [DL Streamer Pipelines Guide](https://docs.openedgeplatform.intel.com/dev/edge-ai-suites/ai-suite-federal-and-aerospace/edge-node-infrastructure-blueprint/how-to/build-dlstreamer-pipelines.html) — pipeline reference and variants
- [Edge Workloads and Benchmarks Guide](https://docs.openedgeplatform.intel.com/dev/edge-ai-suites/ai-suite-federal-and-aerospace/edge-node-infrastructure-blueprint/how-to/run-edge-benchmarks.html) — reproducible benchmark suite
- [Container Device Interface Guide](https://docs.openedgeplatform.intel.com/dev/edge-ai-suites/ai-suite-federal-and-aerospace/edge-node-infrastructure-blueprint/how-to/configure-cdi.html) — CDI setup for GPU/NPU access from containers
