# Get Started

This guide walks you through cloning the repository, downloading AI models, and running the NICU Warmer application.

## Prerequisites

Ensure your system meets the [System Requirements](./get-started/system-requirements.md) before proceeding.

## 1. Clone the Repository

Use sparse checkout to download only the NICU Warmer component.
If you want to clone a specific release branch, replace `main` with the desired tag.
To learn more on partial cloning, check the [Repository Cloning guide](https://docs.openedgeplatform.intel.com/dev/OEP-articles/contribution-guide.html#repository-cloning-partial-cloning).

```bash
git clone --filter=blob:none --sparse --branch main \
  https://github.com/open-edge-platform/edge-ai-suites.git
cd edge-ai-suites
git sparse-checkout set health-and-life-sciences-ai-suite/NICU-Warmer
cd health-and-life-sciences-ai-suite/NICU-Warmer
```

## 2. Download Models and Video

Run the model downloader to fetch all required AI models and the test video:

```bash
make setup
```

This downloads:
- 3 detection models (person, patient, latch) from GitHub Release assets
- Action recognition encoder/decoder from Open Model Zoo
- MTTS-CAN rPPG model (converted to OpenVINO IR)
- Test video file (`Warmer_Testbed_YTHD.mp4`)

All files are cached locally — subsequent runs skip existing files.

> **Important**: `make setup` must complete before `make run`. If `docker compose up`
> runs first, Docker creates empty directories for missing bind-mount sources, causing
> pipeline failures.

## 3. Run the Application

Start all services (default mixed-optimized device profile):

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

### Device Profiles

Select a specific device profile at launch:

```bash
make run           # Mixed-optimized (GPU detect, CPU rPPG, NPU action)
make run-cpu       # All workloads on CPU
make run-gpu       # All workloads on GPU
make run-npu       # All workloads on NPU
```

## 4. Open the Dashboard

Navigate to **http://localhost:3001** in a browser.

Click **Prepare & Run** to start the AI pipeline. The system will:
1. Start the GStreamer pipeline with all 5 models
2. Process video at ~15 FPS
3. Stream detections and vitals via MQTT
4. Display results in real-time on the dashboard

## 5. Stop the Application

Click **Stop** in the dashboard, or from the terminal:

```bash
make down
```

## Troubleshooting

### Empty directories instead of model files

If `make run` was executed before `make setup`, Docker may have created empty
directories for bind-mount paths. Fix:

```bash
make down
sudo rm -rf Warmer_Testbed_YTHD.mp4 model_artifacts models_rppg
make setup
make run
```

### Proxy configuration

If behind a corporate proxy, set environment variables before running:

```bash
export HTTP_PROXY=http://proxy.example.com:port
export HTTPS_PROXY=http://proxy.example.com:port
export http_proxy=$HTTP_PROXY
export https_proxy=$HTTPS_PROXY
```

The compose file forwards these to all containers automatically.
