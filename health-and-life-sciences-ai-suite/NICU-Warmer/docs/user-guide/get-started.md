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

## 2. Manual Model Staging

Before running `make run`, stage the workload models in these locations:

- Repository root:
  - patient detection model files: `.xml` and `.bin`
  - person detection model files: `.xml` and `.bin`
  - latch detection model files: `.xml` and `.bin`
  - action recognition encoder model files: `.xml` and `.bin`
  - action recognition decoder model files: `.xml` and `.bin`
- `models_rppg/`:
  - rPPG workload source model: `.hdf5`

`make run` expects these files to exist.

### Example Models

1. Patient Detection Model - [patient-present](https://huggingface.co/Intel/patient-present/tree/main)\*

2. Person Detection Model - [people-present](https://huggingface.co/Intel/people-present/tree/main)\*

3. Latch Detection Model - [latch-detect](https://huggingface.co/Intel/latch-detect/tree/main)\*

   > \*Download the above model artifacts (`.xml` and `.bin`) from Hugging Face and place them in the appropriate    model directory structure. Only these files are required for inference; downloading the remaining repository    contents is optional.

4. RPPG Model - [MTTS-CAN](https://github.com/xliucs/MTTS-CAN/raw/main/mtts_can.hdf5)

5. Action Recognition Models -

   - Action Recognition Encoder (.xml)

     ```bash
     wget https://storage.openvinotoolkit.org/repositories/open_model_zoo/temp/action-recognition-0001/action-recognition-0001-encoder/FP16/action-recognition-0001-encoder.xml
     ```

   - Action Recognition Encoder (.bin)

     ```bash
     wget https://storage.openvinotoolkit.org/repositories/open_model_zoo/temp/action-recognition-0001/action-recognition-0001-encoder/FP16/action-recognition-0001-encoder.bin
     ```

   - Action Recognition Decoder (.xml)

     ```bash
     wget https://storage.openvinotoolkit.org/repositories/open_model_zoo/temp/action-recognition-0001/action-recognition-0001-decoder/FP16/action-recognition-0001-decoder.xml
     ```

   - Action Recognition Decoder (.bin)

     ```bash
     wget https://storage.openvinotoolkit.org/repositories/open_model_zoo/temp/action-recognition-0001/action-recognition-0001-decoder/FP16/action-recognition-0001-decoder.bin
     ```

> **Third-Party Content**
>
> *In the course of using these Intel-provided instruction, users may choose to download content (e.g., models, dataset, etc.) created and distributed by third parties. In doing so, these users acknowledge and agree that they have done so after reviewing background information about the content and agreeing to the license governing the content they select.*
>
> ***Notice**: Intel does not create the content and does not warrant its accuracy or quality. By accessing the third-party content, or using materials trained on or with such content, you are indicating your acceptance of the terms associated with that content and warranting that your use complies with the applicable license.*


## 3. Prepare Local Assets

Run setup to verify local assets and generate the rPPG OpenVINO IR when needed:

```bash
make setup
```

This step:

- checks the staged model files already present in the repo
- converts `.hdf5` to `.{xml,bin}`
- preserves existing local assets on repeated runs

> **Important**: `make setup` must complete before `make run`. If `docker compose up`
> runs first, Docker creates empty directories for missing bind-mount sources, causing
> pipeline failures.

## 4. Run the Application

Start all services (default mixed-optimized device profile):

```bash
make run
```

By default, `make run` pulls the prebuilt images from Docker Hub.

To build the images locally instead:

```bash
make run REGISTRY=false
```

To pull a specific release tag:

```bash
make run TAG=2026.1.0-rc2
```

This pulls and starts 5 containers:

| Service                  | Port | Purpose                                  |
| ------------------------ | ---- | ---------------------------------------- |
| `nicu-backend`           | 5001 | Flask API + SSE stream + MQTT subscriber |
| `nicu-ui`                | 3001 | React dashboard (nginx reverse proxy)    |
| `nicu-dlsps`             | 8080 | DL Streamer Pipeline Server (GStreamer)  |
| `nicu-mqtt`              | 1883 | Eclipse Mosquitto MQTT broker            |
| `nicu-metrics-collector` | 9100 | Hardware telemetry (CPU/GPU/NPU/Memory)  |

### Device Profiles

Select a specific device profile at launch:

```bash
make run           # Mixed-optimized (GPU detect, CPU rPPG, NPU action)
make run-cpu       # All workloads on CPU
make run-gpu       # All workloads on GPU
make run-npu       # All workloads on NPU
```

## 5. Open the Dashboard

Navigate to `http://localhost:3001` in a browser.

Click **Prepare & Run** to start the AI pipeline. The system will:

1. Start the GStreamer pipeline with all 5 models
2. Process video at ~15 FPS
3. Stream detections and vitals via MQTT
4. Display results in real-time on the dashboard

## 6. Stop the Application

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

<!--hide_directive
:::{toctree}
:hidden:

get-started/system-requirements.md

:::
hide_directive-->
