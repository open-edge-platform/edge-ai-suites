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

For details on deployment options and restart procedures, see the [UAV Mission Compute SDK Get Started guide](https://github.com/open-edge-platform/edge-ai-suites/blob/release-2026.2.0/federal-and-aerospace-ai-suite/uav-mission-compute-sdk/docs/user-guide/get-started.md).

## Step 3: Validate the Running Stack

After the stack is running, follow these steps to arm the UAV and confirm live camera streams.

### Step 3.1: Wait for PX4 to be healthy

First boot takes ~60–90 seconds:

```bash
docker compose ps px4
```

Wait until `px4` reports a healthy status.

### Step 3.2: Arm the UAV (activate cameras)

Cameras only stream when the UAV is armed. Arm it via the REST API:

```bash
curl -X POST http://localhost:8080/action/arm
```

### Step 3.3: Take off (generate motion in the scene)

Command takeoff so the UAV climbs and moves through the Gazebo world — cameras then produce meaningful frames instead of a static ground view:

```bash
curl -X POST http://localhost:8080/action/takeoff
```

The UAV climbs to the default hover altitude.

### Step 3.4: Capture the Video Stream during flight (Optional)

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

### Step 3.5: Access dashboards and APIs

- **Grafana dashboards:** `http://localhost:3000` — flight and platform metrics
  - Credentials are available in the `.env` file.
  - On a headless target, Grafana is only reachable through a reverse tunnel from a machine with a GUI/browser.
- **REST API:** `http://localhost:8080` — flight control commands (`arm`, `takeoff`, `land`)

### Step 3.6: Stop the stack

When done, land the UAV with:

```bash
curl -X POST http://localhost:8080/action/land
```

To stop the entire infrastructure stack:

```bash
make down
```

## Next Steps

- Review the upstream [UAV Mission Compute SDK Get Started](https://github.com/open-edge-platform/edge-ai-suites/blob/release-2026.2.0/federal-and-aerospace-ai-suite/uav-mission-compute-sdk/docs/user-guide/get-started.md) for USB camera setup and advanced configuration.

- Review the [UAV Mission Compute SDK Benchmarking Guide](https://github.com/open-edge-platform/edge-ai-suites/blob/release-2026.2.0/federal-and-aerospace-ai-suite/uav-mission-compute-sdk/docs/user-guide/benchmarking.md) for telemetry and bridge performance benchmarking.

- Refer to [Get Started — UAV Mission Compute SDK Mode](./get-started-uavsdk.md) for application deployment and running the vision analytics stack against the live UAV SDK services.

## Related Guides

- [DL Streamer Pipelines Guide](../infrastructure/build-dlstreamer-pipelines.md) — pipeline reference and variants
- [Edge Workloads and Benchmarks Guide](../benchmarking/run-edge-benchmarks.md) — reproducible benchmark suite
- [Container Device Interface Guide](../infrastructure/configure-cdi.md) — CDI setup for GPU/NPU access from containers
