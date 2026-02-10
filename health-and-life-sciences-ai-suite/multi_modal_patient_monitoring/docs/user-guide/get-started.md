## Get Started

This guide walks you through building and running the multi‑modal patient monitoring reference application, including the RPPG (remote photoplethysmography) service running on Intel CPU, GPU, or NPU.

> Prerequisites and basic usage here are intentionally high‑level. Adapt paths, proxies, and hardware configuration to your environment as needed.

### Prerequisites

- **Host OS:** Ubuntu 22.04 (or compatible Linux distribution).
- **Docker and Docker Compose:**
	- Docker Engine 24.x or newer.
	- Docker Compose plugin (`docker compose` CLI) or standalone `docker-compose`.
- **Intel hardware:**
	- Intel CPU (required).
	- Intel integrated GPU and/or Intel NPU (optional, for accelerator‑backed inference).
- **Proxy configuration (optional):**
	- If your environment uses HTTP/HTTPS proxies, export `HTTP_PROXY`, `HTTPS_PROXY`, and `NO_PROXY` before building.

### Clone the Repository

If you have not already cloned the repository that contains this workload, do so now:

```bash
git clone <your-hl-ai-suite-repo-url>
cd edge-ai-suites/health-and-life-sciences-ai-suite/multi_modal_patient_monitoring
```

Make sure you are in the `multi_modal_patient_monitoring` directory before running the commands in this guide.

### Configure Hardware Target

The RPPG service uses an environment variable to select the OpenVINO target device:

- `RPPG_DEVICE=CPU` – run the MTTS‑CAN model on CPU.
- `RPPG_DEVICE=GPU` – use Intel integrated GPU.
- `RPPG_DEVICE=NPU` – use Intel NPU when available.

You can set this in the shell before starting the application with `make`:

```bash
export RPPG_DEVICE=NPU    # or GPU, CPU
```

The `docker-compose.yaml` (invoked by the Makefile) passes this value into the `rppg` service so that the inference engine compiles the OpenVINO model on the requested device, with automatic fallback to CPU if the chosen accelerator is not available or unsupported for the model.

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

If you prefer to build the images locally instead of pulling from a registry, run the following commands from the `multi_modal_patient_monitoring` directory:

```bash
# Initialize MDPnP submodule
make init-mdpnp

# Build MDPnP services
make build-mdpnp

# Build DDS bridge
make build-dds-bridge

# Build and run all containers locally (no registry pulls)
make run REGISTRY=false
```

The Makefile wraps the underlying `docker compose` commands and ensures that all dependent components (MDPnP, DDS bridge, AI services, and UI) are started with the correct configuration.

To tear everything down when you are done:

```bash
make down
```

### Access the UI

By default, the UI service exposes port 3000 on the host:

- Open a browser and go to: `http://localhost:3000`

From there you can observe heart rate and respiratory rate estimates, along with waveforms produced by the RPPG service and aggregated by the patient‑monitoring‑aggregator.

### Control RPPG Streaming

The RPPG service provides a simple HTTP control API (hosted by an internal FastAPI server) to start and stop streaming:

- **Start streaming:**
	- Send a request to the `/start` endpoint on the RPPG control port (default 8084).
- **Stop streaming:**
	- Send a request to the `/stop` endpoint on the same port.

Exact URLs and endpoints may differ slightly depending on how the control API is exposed in your environment; refer to the RPPG service documentation for details.

### View Hardware Metrics

The metrics-collector service writes telemetry (GPU, NPU, CPU, power, and other metrics) into the `metrics` directory on the host, and may also expose summarized metrics via its own API:

- Inspect raw logs under the `metrics` directory mounted in the compose file.
- Combine these metrics with the RPPG output and UI dashboards to evaluate accelerator utilization and end‑to‑end performance.

### Next Steps

Once you have the system running:

- Read the [System Design](System-design.md) document for a deeper architectural overview.
- Experiment with different `RPPG_DEVICE` values to compare CPU, GPU, and NPU behavior.
- Replace the sample video or models with your own assets by updating the `models` and `videos` volumes and configuration.

