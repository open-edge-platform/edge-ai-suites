# NICU Warmer — Intelligent Patient Monitoring System

Real-time NICU (Neonatal Intensive Care Unit) warmer monitoring using multi-model
AI inference on Intel hardware. Detects patient presence, caretaker activity, warmer
latch status, contactless vital signs (heart rate & respiration via rPPG), and
action recognition — all running through a GPU/NPU-accelerated DL Streamer pipeline
with a live React dashboard.

> **Built on Intel Edge AI Suite** — leverages Intel DL Streamer Pipeline Server,
> OpenVINO, Intel Arc GPU, and Intel NPU (AI Boost) for optimised inference.

---

## Table of Contents

- [Overview](#overview)
- [Features](#features)
- [Architecture](#architecture)
- [Hardware Requirements](#hardware-requirements)
- [Prerequisites](#prerequisites)
- [Quick Start](#quick-start)
- [Model Download & Setup](#model-download--setup)
- [Configuration](#configuration)
- [Dashboard Guide](#dashboard-guide)
- [REST API Reference](#rest-api-reference)
- [AI Models & Pipeline](#ai-models--pipeline)
- [Per-Workload Performance Metrics](#per-workload-performance-metrics)
- [Project Structure](#project-structure)
- [Troubleshooting](#troubleshooting)
- [Development](#development)
- [Make Targets](#make-targets)

---

## Overview

The NICU Warmer system provides continuous, non-contact monitoring of neonatal
patients in hospital warmer beds. It processes a single video stream through
5 AI models simultaneously, extracting:

| Capability | Technology | Hardware |
|------------|-----------|----------|
| Person Detection | Custom OpenVINO FP32 model | GPU |
| Patient Detection | Custom OpenVINO FP32 model | GPU |
| Latch Status | Custom OpenVINO FP32 model | GPU |
| Vital Signs (rPPG) | MTTS-CAN (converted from Keras HDF5) | CPU |
| Action Recognition | Open Model Zoo encoder/decoder | NPU |

All models run in a **single GStreamer pipeline** managed by Intel DL Streamer
Pipeline Server (DLSPS), communicating via MQTT to a Flask backend that streams
results to the React UI over Server-Sent Events (SSE).

---

## Features

- **Multi-Model Pipeline**: 5 AI models running in one GStreamer pipeline at ~15 FPS
- **GPU/NPU Acceleration**: Detection on Intel Arc GPU, action recognition on Intel NPU
- **Contactless Vital Signs**: Heart rate and respiration rate via remote photoplethysmography (rPPG)
- **Action Recognition**: Kinetics-400 encoder/decoder mapped to 11 NICU-specific categories
- **Motion Analysis**: Frame-differencing for real-time activity level detection
- **Live Dashboard**: React + Vite UI with real-time video feed, detection cards, waveform charts
- **Per-Workload Metrics**: Device assignment and status tracked per model in the Pipeline Performance table
- **Hardware Monitoring**: CPU, GPU, NPU, memory, and power utilization charts
- **Device Configuration Profiles**: Pre-built deployment profiles (all-CPU, all-GPU, all-NPU, mixed-optimized) with runtime optimization lookup
- **Runtime Device Optimization**: Automatic pipeline tuning (decode, pre-process, inference options) based on selected hardware per workload
- **Configurable Pipeline**: Upload custom videos, set face ROI, choose device per workload
- **Apply & Restart**: Change configuration while pipeline is running — apply with one click
- **NPU Fallback**: Automatic CPU fallback if NPU is unavailable
- **Model Download Service**: `make setup` downloads all models and video from remote sources

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  Docker Compose Network (--profile dlsps)                                   │
│                                                                             │
│  ┌──────────────┐   MQTT    ┌─────────────┐   SSE    ┌──────────────────┐  │
│  │ nicu-dlsps   │ ───────►  │ nicu-backend │ ──────►  │ nicu-ui          │  │
│  │ :8080        │  nicu/    │ :5001        │          │ :3001 (nginx)    │  │
│  │              │  detections│              │          │                  │  │
│  │ GStreamer    │           │ Flask + SSE  │          │ React + Vite     │  │
│  │ Pipeline:    │           │ MQTT sub     │          │ Redux + Chart.js │  │
│  │  decodebin3  │           │ Aggregator   │          │ ConfigModal      │  │
│  │  gvadetect×3 │           │ rPPG/Action  │          │ Performance tbl  │  │
│  │  rPPG (gva)  │           │ lifecycle    │          │ Resource charts  │  │
│  │  Action (gva)│           └──────┬───────┘          └──────────────────┘  │
│  │  MQTTPublish │                  │                                        │
│  └──────┬───────┘                  │                                        │
│         │                ┌─────────▼──────────┐                             │
│  ┌──────▼───────┐        │ nicu-metrics-      │                             │
│  │ nicu-mqtt    │        │ collector :9100     │                             │
│  │ :1883        │        │ CPU/GPU/NPU/Memory  │                             │
│  │ Mosquitto    │        └────────────────────┘                             │
│  └──────────────┘                                                           │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Data Flow

```
Video Source (file or uploaded .mp4)
    │
    ▼
decodebin3 (VA-API hardware decode)
    │
    ▼
gvadetect × 3 (GPU — Intel Arc / Meteor Lake)
    ├── person-detect-fp32    → Person bounding boxes
    ├── patient-detect-fp32   → Patient bounding boxes
    └── latch-detect-fp32     → Latch clip bounding boxes
    │
    ▼
gvapython: RppgCallback (CPU — OpenVINO)
    └── MTTS-CAN model → Heart Rate, Respiration Rate, Waveforms
    │
    ▼
gvapython: ActionCallback (NPU — OpenVINO)
    ├── Encoder: per-frame 512-dim feature extraction
    ├── Decoder: every 8 frames → Kinetics-400 classification
    ├── Motion analyser: frame-differencing → activity level
    └── NICU category mapping (11 categories)
    │
    ▼
gvapython: MQTTPublisher → MQTT topic "nicu/detections"
    │
    ▼
Flask Backend (MQTT subscriber)
    ├── RuntimeAggregator → normalise detections + rPPG + action
    ├── Per-workload device & status tracking
    ├── SSE stream → delta events to React UI
    │
    ▼
React Dashboard (http://localhost:3001)
    ├── VideoFeed (MJPEG from /video_feed)
    ├── Detection Cards (patient / caretaker / latch)
    ├── RppgCard (HR / RR waveform charts)
    ├── ActionCard (activity + motion level)
    ├── Pipeline Performance (per-model device + status)
    └── Resource Utilization (CPU / GPU / NPU / Memory / Power)
```

---

## Hardware Requirements

| Component | Minimum | Recommended |
|-----------|---------|-------------|
| CPU | Intel Core Ultra / 12th+ Gen | Intel Core Ultra 7 165HL |
| GPU | Intel integrated graphics | Intel Arc Graphics (Meteor Lake) |
| NPU | Optional (auto-fallback to CPU) | Intel AI Boost (NPU) |
| RAM | 16 GB | 32+ GB |
| OS | Ubuntu 22.04+ | Ubuntu 24.04 |
| Docker | 24.0+ | Latest |

The system auto-detects available hardware. If NPU is not present, action
recognition automatically falls back to CPU with a "fallback" indicator in the UI.

---

## Prerequisites

| Requirement | Version |
|-------------|---------|
| Docker Engine | 24.0+ |
| Docker Compose | v2.20+ |
| GNU Make | Any |

> **Proxy note**: If behind a corporate proxy, set `HTTP_PROXY`, `HTTPS_PROXY`,
> `http_proxy`, `https_proxy` environment variables before running.
> The compose file forwards them to all containers automatically.

---

## Quick Start

### 1. Clone and enter the directory

```bash
git clone https://github.com/sakshijha11/edge-ai-suites.git
cd edge-ai-suites/health-and-life-sciences-ai-suite/NICU-Warmer
```

### 2. Download models and video (first-time setup)

```bash
make setup
```

This runs the **model-downloader** service which:
- Downloads 3 detection models (person, patient, latch) from GitHub Release assets
- Downloads action recognition encoder/decoder from Open Model Zoo
- Downloads the MTTS-CAN rPPG model (HDF5) and converts it to OpenVINO IR
- Downloads the test video file

All files are saved locally and cached — subsequent runs skip existing files.

### 3. Start all services

```bash
make run
```

This builds and starts 5 containers:

| Service | Port | Purpose |
|---------|------|---------|
| `nicu-backend` | 5001 | Flask API + SSE stream + MQTT subscriber |
| `nicu-ui` | 3001 | React dashboard (nginx reverse proxy) |
| `nicu-dlsps` | 8080 | DL Streamer Pipeline Server (GStreamer) |
| `nicu-mqtt` | 1883 | Eclipse Mosquitto MQTT broker |
| `nicu-metrics-collector` | 9100 | Hardware telemetry (CPU/GPU/NPU/Memory) |

### 4. Open the dashboard

Navigate to **http://localhost:3001** in a browser.

### 5. Start monitoring

Click **Prepare & Run** in the dashboard. The pipeline will:
1. Start the DLSPS GStreamer pipeline with all 5 models
2. Begin processing video frames at ~15 FPS
3. Stream detections, rPPG vitals, and action data via MQTT
4. Display everything in real-time on the dashboard

### 6. Stop

Click **Stop** in the dashboard, or:

```bash
make down
```

---

## Model Download & Setup

Models are **not stored in Git** — they are downloaded on first run via `make setup`.

### How It Works

The `nicu-model-downloader` Docker service reads `services/model-downloader/model-registry.yaml`
and downloads all models + video to local directories:

| Model Group | Source | Target Directory |
|-------------|--------|-----------------|
| Detection (person, patient, latch) | GitHub Release assets | `./model_artifacts/` |
| Action Recognition (encoder, decoder) | Open Model Zoo | `./model_artifacts/action/` |
| rPPG (MTTS-CAN) | GitHub (HDF5) → OpenVINO IR conversion | `./models_rppg/` |
| Test Video | GitHub Release assets | `./` (project root) |

### rPPG Model Conversion

The rPPG model is special — it's distributed as a Keras HDF5 file from the
[MTTS-CAN repository](https://github.com/xliucs/MTTS-CAN). The downloader:

1. Downloads `mtts_can.hdf5` (~25 MB)
2. Registers custom Keras layers (`TSM`, `Attention_mask`)
3. Loads with TensorFlow and converts via `openvino.convert_model()`
4. Saves as `mtts_can.xml` + `mtts_can.bin` (OpenVINO IR)

This conversion is deterministic and cached — it only runs once.

### Manual Download (without Docker)

```bash
cd services/model-downloader
pip install -r requirements.txt
python download_service.py --output /path/to/models
```

---

## Configuration

### Pipeline Configuration (UI)

Open the **Settings** (gear icon) in the dashboard to configure:

| Tab | Options |
|-----|---------|
| **Video Source** | Upload a custom .mp4/.avi/.mkv file (max 500 MB), or use default |
| **Face ROI** | Set normalised coordinates (0–1) for rPPG face region |
| **Devices** | Choose CPU / GPU / NPU per workload (detect, rPPG, action) |

Configuration can be changed **while the pipeline is running**. After making
changes, click **Apply & Restart Pipeline** in the modal footer to restart
with the new settings.

### Backend Configuration

All backend settings are in `configs/mvp-backend.yaml`:

| Key | Description | Default |
|-----|-------------|---------|
| `preparation.video_path` | Default video source | `./Warmer_Testbed_YTHD.mp4` |
| `preparation.rppg_model_path` | rPPG model path | `./models_rppg/mtts_can.xml` |
| `dlsps.base_url` | DLSPS service endpoint | `http://nicu-dlsps:8080` |
| `dlsps.mqtt_broker` | MQTT broker address | `nicu-mqtt:1883` |
| `dlsps.device` | Default inference device | `GPU` |
| `metrics_collector.base_url` | Metrics service endpoint | `http://nicu-metrics-collector:9100` |

### Device Targeting

The default device assignment is optimised for Intel Meteor Lake:

| Workload | Default Device | Rationale |
|----------|---------------|-----------|
| Person / Patient / Latch Detection | GPU | Biggest FPS bottleneck — GPU gives best throughput |
| rPPG (MTTS-CAN) | CPU | Small model, fast inference (~2 ms) |
| Action Recognition | NPU | Frees CPU for rPPG; encoder+decoder fits NPU well |

### Device Configuration Profiles

Pre-built deployment profiles set environment variables for all device and model
settings at container start. Select a profile at launch via `DEVICE_ENV`:

```bash
make run                # Default (mixed-optimized)
make run-cpu            # All workloads on CPU
make run-gpu            # All workloads on GPU
make run-npu            # All workloads on NPU
make run-mixed          # Explicit mixed-optimized
```

Profiles are defined in `configs/res/`:

| Profile | File | Detection | rPPG | Action |
|---------|------|-----------|------|--------|
| Mixed-Optimized (default) | `mixed-optimized.env` | GPU | CPU | NPU |
| All-CPU | `all-cpu.env` | CPU | CPU | CPU |
| All-GPU | `all-gpu.env` | GPU | GPU | GPU |
| All-NPU | `all-npu.env` | NPU | NPU | NPU |

### Runtime Device Optimization

When a user selects devices from the UI (or via the `/config/devices` API),
the backend automatically resolves optimal pipeline settings through
`backend_mvp/device_profiles.py`. For each device, the system applies:

- **Decode method**: VA-API hardware decode for GPU, software decode for CPU/NPU
- **Pre-process backend**: VA-API surface sharing for GPU, OpenCV for CPU/NPU
- **Inference options**: Device-specific OpenVINO configs (e.g., `PERFORMANCE_HINT=THROUGHPUT` for GPU)
- **Model precision**: FP32 (current), extensible to FP16/INT8

The `/device-profile` API endpoint returns the current device assignments along
with the resolved optimization settings.

---

## Dashboard Guide

### Main Panel (Left)

- **Video Feed**: Live MJPEG stream with bounding box overlays
- **Detection Cards**: Patient presence, caretaker presence, latch status
- **rPPG Card**: Heart rate (BPM), respiration rate, pulse/resp waveform charts
- **Action Card**: Current activity (e.g., "Arm Movement"), motion level, confidence

### Right Panel

- **Pipeline Performance**: Per-workload table showing model, device, and status
- **Resource Utilization**: Real-time CPU, GPU, NPU, memory, and power charts
- **Platform Info**: Processor, GPU, NPU, memory, OS details

### Controls

- **Prepare & Run / Stop**: Start or stop the full pipeline
- **Settings** (gear icon): Open ConfigModal for video, ROI, device settings
- **Apply & Restart**: Appears when config changes are pending on a running pipeline

---

## REST API Reference

### Core Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/health` | Health check (`healthy` / `degraded`) |
| `GET` | `/readiness` | Readiness probe with check details |
| `GET` | `/status` | Full state snapshot (analytics + metrics) |
| `POST` | `/start` | Start the DLSPS pipeline |
| `POST` | `/stop` | Stop the pipeline gracefully |
| `GET` | `/events` | SSE event stream (full + delta snapshots) |
| `GET` | `/video_feed` | MJPEG live video stream |
| `GET` | `/frame/latest` | Latest JPEG frame (base64 optional) |
| `GET` | `/metrics` | Runtime metrics (FPS, frame count) |
| `GET` | `/hardware-metrics` | CPU/GPU/NPU/Memory/Power (proxied) |
| `GET` | `/platform-info` | Hardware platform details (proxied) |

### Configuration Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/config` | Full config state (video, ROI, devices, pending) |
| `POST` | `/config/video` | Upload video file (multipart form) |
| `DELETE` | `/config/video` | Revert to default video |
| `POST` | `/config/roi` | Set rPPG face ROI (JSON: top/left/bottom/right) |
| `DELETE` | `/config/roi` | Reset ROI to defaults |
| `POST` | `/config/devices` | Set device per workload (JSON: detect/rppg/action) |
| `GET` | `/config/devices/available` | Probe available hardware (CPU/GPU/NPU) |
| `POST` | `/config/apply` | Apply pending config (stop → restart pipeline) |
| `GET` | `/device-profile` | Current device assignments + resolved optimizations |

### SSE Event Format

The `/events` endpoint emits `full` (on connect + every 10s) and `delta` (each second):

```json
{
  "lifecycle": "running",
  "analytics": {
    "patient_presence": true,
    "caretaker_presence": true,
    "latch_status": "closed",
    "action": {
      "top_activity": "Arm Movement",
      "top_confidence": 0.45,
      "motion_level": "moderate"
    }
  },
  "rppg": {
    "heart_rate_bpm": 72.3,
    "respiration_rate_bpm": 18.5,
    "signal_confidence": 0.82,
    "status": "valid"
  },
  "metrics": {
    "fps": 15.6,
    "frame_count": 1234,
    "runtime_status": "running"
  },
  "pipeline_performance": {
    "workloads": [
      {"name": "Person Detection", "device": "GPU", "fps": 15.6, "status": "running"},
      {"name": "rPPG", "device": "CPU", "fps": 15.6, "latency_ms": 2.3, "status": "running"},
      {"name": "Action Recognition", "device": "NPU", "fps": 15.6, "latency_ms": 5.1, "status": "running"}
    ],
    "pipeline_fps": 15.6,
    "decode": "decodebin3 (VA-API HW)"
  }
}
```

---

## AI Models & Pipeline

### GStreamer Pipeline

```
filesrc → decodebin3 (VA-API HW decode)
    → gvadetect (person-detect-fp32, GPU)
    → gvadetect (patient-detect-fp32, GPU)
    → gvadetect (latch-detect-fp32, GPU)
    → videoconvert
    → gvapython (RppgCallback — MTTS-CAN on CPU)
    → gvapython (ActionCallback — encoder/decoder on NPU)
    → gvametaconvert
    → gvapython (MQTTPublisher → nicu/detections)
    → gvafpscounter
    → appsink
```

### Model Details

| Model | Architecture | Input | Output | Size |
|-------|-------------|-------|--------|------|
| person-detect-fp32 | SSD MobileNet v2 (custom) | 800×992 | Bounding boxes + confidence | ~14 MB |
| patient-detect-fp32 | SSD MobileNet v2 (custom) | 800×992 | Bounding boxes + confidence | ~14 MB |
| latch-detect-fp32 | SSD MobileNet v2 (custom) | 800×992 | Latch clip boxes | ~14 MB |
| MTTS-CAN (rPPG) | Multi-task temporal shift CNN | 36×36×6 (diff+appearance) | HR/RR signals | ~25 MB |
| Action encoder | ResNet-34 backbone | 224×224 RGB | 512-dim feature vector | ~85 MB |
| Action decoder | FC classifier | 16×512 sequence | 400-class softmax (Kinetics) | ~13 MB |

### Action Recognition Categories (NICU-Mapped)

The Kinetics-400 raw predictions are mapped to 11 NICU-relevant categories:

1. Arm Movement
2. Hand Movement
3. Patient Handling
4. Reaching / Adjusting
5. Patient Distress
6. Resting / Still
7. Walking / Moving
8. Bending / Leaning
9. Monitoring / Observing
10. Food / Equipment Prep
11. Sports / Recreation

---

## Per-Workload Performance Metrics

The Pipeline Performance table shows **live per-workload metrics**:

| Column | Source | Description |
|--------|--------|------------|
| **Model** | Pipeline config | Workload name (Detection, rPPG, Action Recognition) |
| **Device** | Config API + SSE | Current hardware accelerator (CPU/GPU/NPU) |
| **Status** | SSE pipeline_performance | Running / Idle indicator |

---

## Project Structure

```
NICU-Warmer/
├── backend_mvp/                    # Flask backend application
│   ├── app.py                      # Main app: endpoints, SSE, MQTT, inference loop
│   ├── aggregator.py               # Detection normalisation
│   ├── device_profiles.py          # Runtime device optimization lookup
│   ├── dlsps_controller.py         # DLSPS REST client + pipeline payload builder
│   ├── frame_service.py            # MJPEG frame management
│   ├── lifecycle.py                # Pipeline state machine
│   └── state_store.py              # In-memory state store
├── configs/
│   ├── mvp-backend.yaml            # Backend configuration
│   ├── workload_to_device.json     # Workload-to-device mapping
│   ├── mosquitto.conf              # MQTT broker config
│   └── res/                        # Device configuration profiles
│       ├── mixed-optimized.env     # Default: GPU detect, CPU rPPG, NPU action
│       ├── all-cpu.env             # All workloads on CPU
│       ├── all-gpu.env             # All workloads on GPU
│       └── all-npu.env             # All workloads on NPU
├── dlsps/
│   ├── config.json                 # DLSPS server config
│   └── user_defined_pipelines/     # GStreamer pipeline templates
│       └── nicu_tee/pipeline.json
├── extensions/                     # gvapython callbacks (mounted into DLSPS)
│   ├── rppg_gva.py                 # rPPG (MTTS-CAN) callback
│   ├── action_gva.py               # Action Recognition callback
│   └── publisher_utils_patched.py  # MQTT publisher frame encoder
├── services/
│   └── model-downloader/           # Model download service
│       ├── download_service.py     # Main downloader (XML+BIN, HDF5→IR, video)
│       ├── model-registry.yaml     # Download URLs per model group
│       ├── scripts/
│       │   └── rppg_convert.py     # HDF5 → OpenVINO IR converter
│       ├── Dockerfile
│       └── requirements.txt
├── ui/                             # React + Vite frontend
│   └── src/
│       ├── components/
│       │   ├── NicuPanel/          # VideoFeed, DetectionCards, RppgCard, ActionCard
│       │   ├── RightPanel/         # PipelinePerformance, ResourceUtilization
│       │   └── ConfigModal/        # Settings UI (video, ROI, devices)
│       ├── redux/                  # Redux Toolkit + SSE middleware
│       └── services/api.ts         # Backend API client
├── reference/                      # Documentation & benchmarks
│   ├── COMPLETION_STATUS.md        # Phase completion report
│   └── FPS_BENCHMARK.md            # Device permutation benchmark
├── docker-compose.yaml             # 5-service orchestration
├── Dockerfile                      # Backend container image
├── Makefile                        # Build & run targets
└── .gitignore                      # Excludes models, videos, binaries
```

---

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| `make run` fails with missing models | First-time setup not done | Run `make setup` first |
| No video after clicking Start | DLSPS not started | Ensure `make run` uses `--profile dlsps` |
| rPPG shows "warming_up" | Needs 10+ frames to buffer | Wait 10-15 seconds after start |
| Action shows "warming_up" | Needs 16 frames for decoder | Wait 20+ seconds |
| NPU errors in logs | NPU driver not installed | System auto-falls back to CPU (check "fallback" badge) |
| GPU utilization 0% | Metrics collector issue | Verify `pid: host` and `/dev/dri` in docker-compose |
| Port 3001 in use | Another service | `make down` then check for conflicts |
| Upload fails (413) | File > 500 MB | Use a smaller video file |
| Config changes don't take effect | Pipeline needs restart | Click "Apply & Restart Pipeline" in Settings |

---

## Development

### Local Backend (without Docker)

```bash
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
python run_mvp_backend.py --config configs/mvp-backend.yaml
```

### Local Frontend

```bash
cd ui
npm install
npm run dev    # Vite dev server on http://localhost:5173
```

---

## Make Targets

```bash
make setup             # Download models + video (first-time)
make run               # Start all 5 services (mixed-optimized profile)
make run-cpu           # Start with all-CPU device profile
make run-gpu           # Start with all-GPU device profile
make run-npu           # Start with all-NPU device profile
make run-mixed         # Start with mixed-optimized profile (explicit)
make down              # Stop and remove all containers
make run-model-setup   # Re-run model downloader
make run-mvp           # Run backend locally (outside Docker)
```

---

## License

See the repository root for license information.
