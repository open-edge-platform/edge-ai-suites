# System Requirements

This section summarizes the recommended hardware, software, and network requirements for
running the multi‑modal patient monitoring application.

## Host Operating System

- Ubuntu 22.04 LTS (recommended and validated).
- Other recent 64‑bit Linux distributions may work, but are not fully validated.

## Hardware Requirements

- **CPU:**
	- 4 physical cores (8 threads) or more recommended.
	- x86_64 architecture with support for AVX2.

- **System Memory (RAM):**
	- Minimum: 16 GB.
	- Recommended: 32 GB for smoother multi‑service operation and development work.

- **Storage:**
	- Minimum free disk space: 30 GB.
	- Recommended: 50 GB+ to accommodate Docker images, models, logs, and metrics.

- **Graphics / Accelerators:**
	- Required: Intel CPU.
	- Optional (recommended for full experience):
		- Intel integrated GPU supported by Intel® Graphics Compute Runtime.
		- Intel NPU supported by the linux‑npu‑driver stack.
	- The host must expose GPU and NPU devices to Docker, for example:
		- `/dev/dri` (GPU)
		- `/dev/accel/accel0` (NPU)

## Software Requirements

- **Docker and Container Runtime:**
	- Docker Engine 24.x or newer.
	- Docker Compose v2 (integrated as `docker compose`) or compatible compose plugin.
	- Ability to run containers with:
		- `--privileged` (for metrics‑collector).
		- Device mappings for GPU/NPU (for rPPG and metrics‑collector).

- **Python (for helper scripts and tools):**
	- Python 3.10 or newer recommended.
	- Used primarily for asset preparation scripts and local tooling; application containers
	include their own Python runtimes (for example, Python 3.12 in the rPPG service image).


- **Git and Make:**
	- `git` for cloning the repository and managing submodules.
	- `make` to run provided automation targets (e.g., `make run`, `make init-mdpnp`).

## AI Models and Workloads

The application bundles several AI workloads, each with its own model(s) and inputs/outputs:

- **RPPG (Remote Photoplethysmography) Workload:**
	- **Model:** MTTS‑CAN (Multi‑Task Temporal Shift Convolutional Attention Network)
	converted to OpenVINO IR (`/models/rppg/mtts_can.xml`).
	- **Input:** Facial video frames (RGB) from the shared `videos` volume.
	- **Output:** Pulse and respiration waveforms, heart rate (HR) in BPM, and respiratory
	rate (RR) in BrPM.
	- **Target devices:** Intel CPU, Intel integrated GPU, or Intel NPU via OpenVINO
	(`RPPG_DEVICE`).

- **3D‑Pose Estimation Workload:**
	- **Model:** `human-pose-estimation-3d-0001` from Open Model Zoo, converted to OpenVINO
	IR (`/models/3d-pose/human-pose-estimation-3d-0001.xml`).
	- **Input:** RGB video of a person in motion (`face-demographics-walking.mp4` under
	`/videos/3d-pose` has been provided for demonstration purposes).
	- **Output:** 3D human keypoints and pose estimation, streamed to the aggregator for
	visualization.
	- **Target devices:** Intel CPU and GPU via OpenVINO.

- **AI‑ECG Workload:**
	- **Models:** OpenVINO IR models for ECG rhythm classification located under
	`/models/ai-ecg`, for example:
		- `ecg_8960_ir10_fp16.xml`
		- `ecg_17920_ir10_fp16.xml`
	- **Input:** Preprocessed multi‑lead ECG time‑series segments of supported lengths (e.g.,
	8960 or 17920 samples).
	- **Output:** Rhythm classification labels (e.g., Normal sinus rhythm, Atrial Fibrillation,
	Other rhythm, or Too noisy to classify) with associated waveforms and timings.
	- **Target devices:** Intel CPU, GPU, or other OpenVINO‑supported devices configured via `ECG_DEVICE`.

## Network and Proxy

- **Network Access:**
	- Local network connectivity to access the UI (default: `http://<HOST_IP>:3000`).
	- Optional outbound internet access to download Docker base images, models, and assets
	(if not pre‑cached).

- **Proxy Support (optional):**
	- If your environment uses HTTP/HTTPS proxies, configure:
		- `HTTP_PROXY`, `HTTPS_PROXY`, `NO_PROXY` in the shell before running `make`.
	
## Permissions

- Ability to run Docker as a user in the `docker` group or with `sudo`.
- Sufficient permissions to access device nodes for GPU and NPU (typically via membership in
groups such as `video` or via explicit `devices` configuration in Docker Compose).

## Browser Requirements

- Modern web browser (Chrome, Edge, or Firefox) to access the UI dashboard.
- JavaScript enabled.

These requirements are intended for development and evaluation environments. For any
production‑like deployment, you should also consider additional factors such as security
hardening, monitoring, backup, and resource isolation.
