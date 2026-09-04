<!--
SPDX-FileCopyrightText: (C) 2026 Intel Corporation
SPDX-License-Identifier: Apache-2.0
-->

# Install OEP SDKs

This page covers installing the OEP Vision AI SDK on a provisioned Handheld (Soldier System) target and validating the stack with a sample object detection pipeline.

The provisioned image ships with system-level dependencies only — kernel, GPU/NPU drivers, Docker Engine, and container device plugins. The OEP Vision AI SDK, DL Streamer container images, sample models, and OpenVINO Python runtime must be installed on the target as described below.

For image build and platform provisioning, see [Infrastructure Setup](./infrastructure-setup.md).

## Prerequisites

- Handheld platform provisioned per [Infrastructure Setup](./infrastructure-setup.md).
- Passwordless SSH or console access to the target.
- Internet connectivity (or configured proxy) on the target for package and container image downloads.
- Minimum 20 GB free disk space for SDK content, images, and sample models.

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

## Step 2: Install the OEP Vision AI SDK

Run the official OEP Vision AI SDK installer on the target. It configures Docker, pulls the DL Streamer image, and installs the OpenVINO tooling and sample content:

```bash
curl https://raw.githubusercontent.com/open-edge-platform/edge-ai-suites/refs/heads/main/metro-ai-suite/metro-sdk-manager/scripts/oep-vision-ai-sdk.sh | bash
```

The installer sets up:

- Docker containerization platform (verified/configured)
- DL Streamer video analytics framework (container image)
- OpenVINO inference optimization toolkit
- Pre-trained model repositories and sample implementations

For full details, see the [OEP Vision AI SDK Get Started guide](https://docs.openedgeplatform.intel.com/2026.2/OEP-articles/oep-sdk-manager/oep-vision-ai-sdk/get-started.html).

## Step 3: Run the Sample Object Detection Pipeline

Validate the installation with the SDK's sample detection workflow.

Create a working directory:

```bash
mkdir -p ~/oep/oep-vision-get-started-tutorial
cd ~/oep/oep-vision-get-started-tutorial
```

Download the sample video and model:

```bash
wget -O sample.mp4 \
  https://github.com/intel-iot-devkit/sample-videos/raw/master/person-bicycle-car-detection.mp4

mkdir -p models/intel/pedestrian-and-vehicle-detector-adas-0001/FP32/

wget -O "models/intel/pedestrian-and-vehicle-detector-adas-0001/FP32/pedestrian-and-vehicle-detector-adas-0001.xml" \
  "https://storage.openvinotoolkit.org/repositories/open_model_zoo/2023.0/models_bin/1/pedestrian-and-vehicle-detector-adas-0001/FP32/pedestrian-and-vehicle-detector-adas-0001.xml?raw=true"

wget -O "models/intel/pedestrian-and-vehicle-detector-adas-0001/FP32/pedestrian-and-vehicle-detector-adas-0001.bin" \
  "https://storage.openvinotoolkit.org/repositories/open_model_zoo/2023.0/models_bin/1/pedestrian-and-vehicle-detector-adas-0001/FP32/pedestrian-and-vehicle-detector-adas-0001.bin?raw=true"

wget -O "models/intel/pedestrian-and-vehicle-detector-adas-0001/pedestrian-and-vehicle-detector-adas-0001.json" \
  "https://raw.githubusercontent.com/open-edge-platform/dlstreamer/refs/heads/main/samples/gstreamer/model_proc/intel/pedestrian-and-vehicle-detector-adas-0001.json"
```

Start the DL Streamer container with display forwarding:

```bash
xhost +

docker run --rm -it --name dlstreamer \
  -v $PWD:/data \
  -e DISPLAY=$DISPLAY \
  -v /tmp/.X11-unix:/tmp/.X11-unix \
  intel/dlstreamer:2026.2.0-ubuntu24-rc2
```

Inside the container, run the detection pipeline:

```bash
gst-launch-1.0 filesrc location=/data/sample.mp4 ! \
  decodebin ! videoconvert ! \
  gvadetect model=/data/models/intel/pedestrian-and-vehicle-detector-adas-0001/FP32/pedestrian-and-vehicle-detector-adas-0001.xml \
    model-proc=/data/models/intel/pedestrian-and-vehicle-detector-adas-0001/pedestrian-and-vehicle-detector-adas-0001.json \
    device=CPU ! \
  gvawatermark ! videoconvert ! autovideosink
```

The video plays with detection boxes overlaid on pedestrians and vehicles. To target the GPU or NPU instead, change `device=CPU` to `device=GPU` or `device=NPU` (add `--device intel.com/gpu=card0` and/or `--device intel.com/npu=npu0` to the `docker run` command).

Exit the container with `exit`.

## Next Steps

Continue with the OEP Vision AI SDK tutorials to explore benchmarking, multi-stream processing, real-time detection, and profiling:

- [Tutorial 1: OpenVINO Model Benchmark](https://docs.openedgeplatform.intel.com/2026.2/OEP-articles/oep-sdk-manager/oep-vision-ai-sdk/tutorial-1.html)
- [Tutorial 2: Multi-Stream Video Processing](https://docs.openedgeplatform.intel.com/2026.2/OEP-articles/oep-sdk-manager/oep-vision-ai-sdk/tutorial-2.html)
- [Tutorial 3: Real-Time Object Detection](https://docs.openedgeplatform.intel.com/2026.2/OEP-articles/oep-sdk-manager/oep-vision-ai-sdk/tutorial-3.html)
- [Tutorial 4: Advanced Video Analytics Pipelines](https://docs.openedgeplatform.intel.com/2026.2/OEP-articles/oep-sdk-manager/oep-vision-ai-sdk/tutorial-4.html)
- [Tutorial 5: Profiling](https://docs.openedgeplatform.intel.com/2026.2/OEP-articles/oep-sdk-manager/oep-vision-ai-sdk/tutorial-5.html)

## Related Guides

- [DL Streamer Pipelines Guide](https://docs.openedgeplatform.intel.com/2026.2/edge-ai-suites/ai-suite-federal-and-aerospace/edge-node-infrastructure-blueprint/how-to/build-dlstreamer-pipelines.html) — pipeline reference and variants
- [Edge Workloads and Benchmarks Guide](https://docs.openedgeplatform.intel.com/2026.2/edge-ai-suites/ai-suite-federal-and-aerospace/edge-node-infrastructure-blueprint/how-to/run-edge-benchmarks.html) — reproducible benchmark suite
- [Container Device Interface Guide](https://docs.openedgeplatform.intel.com/2026.2/edge-ai-suites/ai-suite-federal-and-aerospace/edge-node-infrastructure-blueprint/how-to/configure-cdi.html) — CDI setup for GPU/NPU access from containers
