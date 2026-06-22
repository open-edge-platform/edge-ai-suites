# Get Started

This guide walks you through building and running the multi‑modal patient monitoring reference
application, including the rPPG (remote photoplethysmography) service running on Intel CPU,
GPU, or NPU.

## Prerequisites

Ensure your environment meets the [System Requirements](./get-started/system-requirements.md) before proceeding.

## 1. Clone the Repository

Go to the target directory of your choice and clone the suite.
If you want to clone a specific release branch, replace `main` with the desired tag.
To learn more on partial cloning, check the [Repository Cloning guide](https://docs.openedgeplatform.intel.com/dev/OEP-articles/contribution-guide.html#repository-cloning-partial-cloning).

```bash
git clone --filter=blob:none --sparse --branch main https://github.com/open-edge-platform/edge-ai-suites.git
cd edge-ai-suites
git sparse-checkout set health-and-life-sciences-ai-suite
cd health-and-life-sciences-ai-suite/multi_modal_patient_monitoring
```

## 2. Configure Hardware Target

Each AI workload uses a device environment variable to select its OpenVINO target device.
These are defined in `configs/device.env`:

- `ECG_DEVICE` – device for the AI‑ECG workload (for example, `GPU`).
- `RPPG_DEVICE` – device for the rPPG workload (`CPU`, `GPU`, or `NPU`).
- `MDPNP_DEVICE` – device for MDPnP processing (for example, `CPU`).
- `POSE_3D_DEVICE` – device for the 3D‑pose estimation workload (for example, `GPU`).

To configure these:

1. Open `configs/device.env` in a text editor.
2. Locate the entries for `ECG_DEVICE`, `RPPG_DEVICE`, `MDPNP_DEVICE`, and `POSE_3D_DEVICE`.
3. Set each to the appropriate device string supported on your system (typically `CPU` or
   `GPU`, and `NPU` where available and supported).

When you run `make run` or `make run REGISTRY=false`, the compose file reads
`configs/device.env` and passes these values into the corresponding services so that each
inference engine compiles its OpenVINO model on the requested device, with automatic fallback
to CPU when necessary.

## 3. Configure Proxy (Optional)

If your environment requires a proxy to access external networks, export the proxy settings in
the same shell before running any `make` command that pulls or builds Docker images:

```bash
export HTTP_PROXY=http://proxy-address:PORT
export HTTPS_PROXY=http://proxy-address:PORT
export NO_PROXY=localhost,127.0.0.1
```

The Makefile reads these variables and passes them to Docker Compose during image pulls,
builds, and container startup. If your environment also defines lowercase proxy variables,
set `http_proxy`, `https_proxy`, and `no_proxy` to the same values.

## 4. Stage Models Manually

Before running the stack, place source models under the repository-local folder:

```bash
models/downloads/
├── ai-ecg/
├── rppg/
└── 3d-pose/
```


### Example Models

1. RPPG Model - [MTTS-CAN](https://github.com/xliucs/MTTS-CAN/raw/main/mtts_can.hdf5)

   Place the model file at: `models/downloads/rppg/mtts_can.hdf5`
   
2. 3D Pose Model - [Human Pose Estimation 3D 0001](https://storage.openvinotoolkit.org/repositories/open_model_zoo/public/2022.1/human-pose-estimation-3d-0001/human-pose-estimation-3d.tar.gz)

   Place the archive at: `models/downloads/3d-pose/human-pose-estimation-3d.tar.gz`
   
3. AI-ECG Model - HuBERT-ECG Small
   
   a. Create and activate a Python virtual environment:
   ```bash
   python3 -m venv hf-venv
   source hf-venv/bin/activate
   ```
   b. Install the Hugging Face Hub CLI:
   ```bash
   pip install --upgrade pip
   pip install huggingface_hub
   ```
   c. Download the model repository into the staging directory:
   ```bash
   hf download Edoardo-BS/hubert-ecg-small \
   --local-dir models/downloads/ai-ecg/hubert-ecg-small
   ```


> **Third-Party Content**
> 
> *In the course of using these Intel-provided instruction, users may choose to download content (e.g., models, dataset, etc.) created and distributed by third parties. In doing so, these users acknowledge and agree that they have done so after reviewing background information about the content and agreeing to the license governing the content they select.*
> 
> ***Notice**: Intel does not create the content and does not warrant its accuracy or quality. By accessing the third-party content, or using materials trained on or with such content, you are indicating your acceptance of the terms associated with that content and warranting that your use complies with the applicable license.*

### Verify the contents:

```bash
ls models/downloads/ai-ecg/hubert-ecg-small
```

The directory should contain the model weights, configuration files, and any custom model implementation files required.

The `make run` target validates these paths first. If any artifact is missing, startup fails
with an actionable error before containers are launched.


## 5. Run the Sample

### Run Using Pre‑Built Images (Registry Mode)

If you want to use pre‑built images from a container registry, run:

```bash
make run
```

This will:

- Pull the required images from the configured registry.
- Start all services defined in `docker-compose.yaml` in detached mode.
- Print the URL of the UI (for example, `http://<HOST_IP>:3000`).

### Run Using Locally Built Images

If you prefer to build the images locally instead of pulling from a registry, run the following
commands from the `multi_modal_patient_monitoring` directory:

```bash
# Initialize MDPnP submodule
make init-mdpnp

# Build and run all containers locally (no registry pulls)
make run REGISTRY=false
```

The Makefile wraps the underlying `docker compose` commands and ensures that all dependent
components (MDPnP, DDS bridge, AI services, and UI) are started with the correct configuration.

To stop and remove all containers when you are done:

```bash
make down
```

## 6. Access the UI

By default, the UI service exposes port 3000 on the host:

- Open a browser and go to: `http://localhost:3000`

From there you can observe heart rate and respiratory rate estimates, along with waveforms
produced by the rPPG service and aggregated by the patient‑monitoring‑aggregator.

## 7. Control RPPG Streaming

The rPPG service provides a simple HTTP control API (hosted by an internal FastAPI server) to
start and stop streaming:

- **Start streaming:**
  - Send a request to the `/start` endpoint on the rPPG control port (default 8084).
- **Stop streaming:**
  - Send a request to the `/stop` endpoint on the same port.

Exact URLs and endpoints may differ slightly depending on how the control API is exposed in
your environment; refer to the rPPG service documentation for details.

## 8. View Hardware Metrics

The metrics-collector service writes telemetry (GPU, NPU, CPU, power, and other metrics) into
the `metrics` directory on the host, and may also expose summarized metrics via its own API:

- Inspect raw logs under the `metrics` directory mounted in the compose file.
- Combine these metrics with the rPPG output and UI dashboards to evaluate accelerator
  utilization and end‑to‑end performance.

## Next Steps

- Learn more about [How It Works](./how-it-works.md) for a high-level architectural overview.
- Experiment with different `RPPG_DEVICE` values to compare CPU, GPU, and NPU behavior.
- Replace the sample video or models with your own assets by updating the `models` and `videos`
  volumes and configuration.

<!--hide_directive
:::{toctree}
:hidden:

get-started/system-requirements.md
:::
hide_directive-->
