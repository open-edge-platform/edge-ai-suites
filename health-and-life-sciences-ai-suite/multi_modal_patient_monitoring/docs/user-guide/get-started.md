# Get Started

This guide walks you through building and running the multi‑modal patient monitoring reference
application, including the rPPG (remote photoplethysmography) service running on Intel CPU,
GPU, or NPU.

Before you begin, review the [System Requirements](./get-started/system-requirements.md) to
ensure your environment meets the recommended hardware and software prerequisites.

## Clone the Repository

> **Note:** Make sure you are in the `multi_modal_patient_monitoring` directory before running
> the commands in this guide.

If you have not already cloned the repository that contains this workload, do so now:

```bash
git clone <your-hl-ai-suite-repo-url>
cd edge-ai-suites/health-and-life-sciences-ai-suite/multi_modal_patient_monitoring
```

## Configure Hardware Target

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

## Run Using Pre‑Built Images (Registry Mode)

If you want to use pre‑built images from a container registry, run:

```bash
make run
```

This will:

- Pull the required images from the configured registry.
- Start all services defined in `docker-compose.yaml` in detached mode.
- Print the URL of the UI (for example, `http://<HOST_IP>:3000`).

## Run Using Locally Built Images

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

To tear everything down when you are done:

```bash
make down
```

## Access the UI

By default, the UI service exposes port 3000 on the host:

- Open a browser and go to: `http://localhost:3000`

From there you can observe heart rate and respiratory rate estimates, along with waveforms
produced by the rPPG service and aggregated by the patient‑monitoring‑aggregator.

## Control RPPG Streaming

The rPPG service provides a simple HTTP control API (hosted by an internal FastAPI server) to
start and stop streaming:

- **Start streaming:**
	- Send a request to the `/start` endpoint on the rPPG control port (default 8084).
- **Stop streaming:**
	- Send a request to the `/stop` endpoint on the same port.

Exact URLs and endpoints may differ slightly depending on how the control API is exposed in
your environment; refer to the rPPG service documentation for details.

## View Hardware Metrics

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
