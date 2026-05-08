# System Requirements

This section lists the hardware, software, and network requirements for running the application.

## Host Operating System

- Ubuntu 24.04 LTS (recommended and validated).
- Ubuntu 22.04 LTS is also supported.
- Other recent 64‑bit Linux distributions may work, but are not fully validated.

## Hardware Requirements

- **CPU:**
  - Intel Core Ultra (Meteor Lake) or 12th Gen Intel Core or newer.
  - x86_64 architecture with support for AVX2.
  - Recommended: Intel Core Ultra 7 165HL.

- **System Memory (RAM):**
  - Minimum: 16 GB.
  - Recommended: 32 GB for smoother multi‑model operation and development work.

- **Storage:**
  - Minimum free disk space: 20 GB.
  - Recommended: 40 GB+ to accommodate Docker images, models, video assets, and logs.

- **Graphics / Accelerators:**
  - Required: Intel integrated GPU supported by Intel® Graphics Compute Runtime.
  - Optional (recommended for full experience):
    - Intel Arc Graphics (Meteor Lake iGPU) for detection workloads.
    - Intel NPU (AI Boost) for action recognition workload.

  - The host must expose GPU and NPU devices to Docker:
    - `/dev/dri` (GPU)
    - `/dev/accel/accel0` (NPU)

  - If NPU is not available, the action recognition workload automatically falls back to CPU
    with a "fallback" indicator in the dashboard.

## Software Requirements

- **Docker and Container Runtime:**
  - Docker Engine 24.x or newer.
  - Docker Compose v2 (integrated as `docker compose`) or compatible compose plugin.
  - Ability to run containers with:
    - `pid: host` (for metrics-collector GPU telemetry).
    - Device mappings for GPU and NPU.

- **Python (for helper scripts):**
  - Python 3.10 or newer (used by `make setup` model download scripts).
  - Requires `pyyaml` package (`pip install pyyaml`).
  - Application containers include their own Python runtimes.

- **Git and Make:**
  - `git` for cloning the repository (sparse checkout supported).
  - `make` to run provided automation targets (e.g., `make setup`, `make run`, `make down`).

## AI Models and Workloads

The application uses several AI workloads, each with its own model:

- **Person Detection Workload:**
  - **Model:** person-detect-fp32 (SSD MobileNet v2, custom trained).
  - **Input:** Video frames (800×992 RGB).
  - **Output:** Bounding boxes with confidence scores for caretaker presence.
  - **Target device:** Intel GPU via OpenVINO.

- **Patient Detection Workload:**
  - **Model:** patient-detect-fp32 (SSD MobileNet v2, custom trained).
  - **Input:** Video frames (800×992 RGB).
  - **Output:** Bounding boxes with confidence scores for infant presence.
  - **Target device:** Intel GPU via OpenVINO.

- **Latch Detection Workload:**
  - **Model:** latch-detect-fp32 (SSD MobileNet v2, custom trained).
  - **Input:** Video frames (800×992 RGB).
  - **Output:** Bounding boxes for warmer latch clip status.
  - **Target device:** Intel GPU via OpenVINO.

- **rPPG (Remote Photoplethysmography) Workload:**
  - **Model:** MTTS-CAN (Multi-Task Temporal Shift Convolutional Attention Network),
    converted from Keras HDF5 to OpenVINO IR.
  - **Input:** Facial video frames (36×36×6, difference + appearance channels).
  - **Output:** Pulse and respiration waveforms, heart rate (HR) in BPM, and respiratory
    rate (RR) in BrPM.
  - **Target device:** Intel CPU via OpenVINO.

- **Action Recognition Workload:**
  - **Model:** action-recognition-0001-encoder + action-recognition-0001-decoder from
    Open Model Zoo.
  - **Input:** Video frames (224×224 RGB), processed in 16-frame sequences.
  - **Output:** Kinetics-400 classification mapped to 11 NICU-specific activity categories.
  - **Target device:** Intel NPU via OpenVINO (falls back to CPU if NPU unavailable).

## Network and Proxy

- **Network Access:**
  - Local network connectivity to access the UI (default: `http://localhost:3001`).
  - Outbound internet access required for initial `make setup` (model and video download).
  - No network required at runtime — all inference is local.

- **Proxy Support (optional):**
  - If your environment uses HTTP/HTTPS proxies, configure:
    - `HTTP_PROXY`, `HTTPS_PROXY`, `http_proxy`, `https_proxy` in the shell before running
      `make`.
  - The Docker Compose file forwards proxy variables to all containers automatically.

## Permissions

- Ability to run Docker as a user in the `docker` group or with `sudo`.
- Sufficient permissions to access device nodes for GPU and NPU (typically via membership in
  groups such as `video` and `render`, or via explicit `devices` configuration in Docker
  Compose).

## Browser Requirements

- Any modern browser (Chrome, Firefox, Edge) with JavaScript enabled.
- WebSocket/SSE support required for real-time data streaming.
