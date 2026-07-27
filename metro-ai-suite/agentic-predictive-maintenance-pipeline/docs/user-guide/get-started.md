# Get Started

The Agentic Predictive Maintenance (APM) blueprint lets you deploy an end-to-end industrial defect
detection pipeline with AI-driven analysis on Intel® edge hardware. This section shows how to set up, configure, and run the application.

## Prerequisites

Before you start, ensure the following:

- Docker Engine version 24.0 or higher, and Docker Compose tool version 2.20 or higher.
- Intel® processor with at least 16 GB of RAM; Intel recommends 32 GB for Large Language
  Models (LLMs).
- Python programming language version 3.10 or later: only needed to prepare sample data.
- `opencv-python` Python package: only needed for the data preparation script.
- A Hugging Face account and API token if you use a gated model such as
  `microsoft/Phi-4-mini-instruct`.

Verify that your system meets the
[hardware and software requirements](./get-started/system-requirements.md) before continuing.

## Project Structure

```text
agentic-predictive-maintenance/
├── apps/
│   └── pipeline-defect-detection/     # Use-case configuration directory
│       ├── configs/
│       │   ├── agents.yaml            # Agent pipeline settings and defect thresholds
│       │   ├── pipeline-server-config.json  # DL Streamer pipeline and model paths
│       │   └── policy_fallback.json   # Rule-based fallback logic
│       ├── prompts/
│       │   └── pipeline-defect-detection.txt  # LLM prompt sections per agent
│       ├── models/                    # Model artifacts directory
│       ├── resources/
│       │   └── videos/                # Input video files (place sample.mp4 here)
│       └── .env_pipeline-defect-detection  # Environment configuration for this use case
├── docker/                            # Docker Compose files
│   ├── compose.base.yaml              # Core services (nginx, storage, DL Streamer, MQTT)
│   ├── compose.detection.yaml         # Detection service (DL Streamer orchestration)
│   ├── compose.agents.yaml            # Agent service (pulled EAL image — reasoning only)
│   ├── compose.llm.yaml               # VLM or LLM inference service
│   ├── compose.ui.yaml                # Web dashboard
│   └── compose.telemetry.yaml         # Prometheus metrics collection
├── services/                          # Source code for this repo's microservices
│   ├── storage-service/
│   ├── detection-service/
│   └── ui-service/
│                                       # (the reasoning agent is a separate, external
│                                       #  EAL image — see docker/compose.agents.yaml)
├── scripts/                           # Helper scripts
├── config/                            # Nginx and MQTT broker configuration
├── docs/                              # Documentation
├── Makefile                           # Build and test targets
└── setup.sh                           # Main deployment script
```

> **Note**: Each use case ships with its own `.env_<use-case>` file already populated
> with working defaults at `apps/<use-case>/.env_<use-case>` — you do not need to create
> it yourself; `setup.sh` reads it from that location automatically.

## Step 1 — Clone the Repository

```bash
git clone https://github.com/open-edge-platform/edge-ai-suites.git
cd edge-ai-suites/metro-ai-suite/agentic-predictive-maintenance
```

## Step 2 — Configure the Environment

Open the use-case environment file and review the settings:

```bash
vi apps/pipeline-defect-detection/.env_pipeline-defect-detection
```

The most important variables are:

| Variable | Default | Description |
|----------|---------|-------------|
| `LLM_MODE` | `llm` | Set to `fallback` to run without an LLM (rule-based mode) |
| `LLM_MODEL_NAME` | `microsoft/Phi-4-mini-instruct` | Language model used by the agent pipeline |
| `LLM_DEVICE` | `CPU` | Inference device: `CPU`, `GPU`, or `NPU` |
| `LLM_WEIGHT_FORMAT` | `int4` | Model quantization format: `fp32`, `fp16`, `int8`, or `int4` |

If you are using a gated Hugging Face model, set your API token:

```bash
# In .env_pipeline-defect-detection, uncomment and set:
HUGGINGFACEHUB_API_TOKEN=hf_your_token_here
```

> **Note**: Accept the model license agreement on the
> [Hugging Face model page](https://huggingface.co/microsoft/Phi-4-mini-instruct) before using
> the gated models.

## Step 3 — Prepare Sample Data

The Deep Learning Streamer (DL Streamer) pipeline needs a video file to run. Use the included script to download the Kaggle
pipeline-defect dataset and build a sample video automatically:

```bash
pip install opencv-python ffmpeg
```

```bash
python scripts/download_and_prep_data.py \
    "https://www.kaggle.com/api/v1/datasets/download/simplexitypipeline/pipeline-defect-dataset" \
    --use-case pipeline-defect-detection
```

This script:
- Downloads and extracts the dataset, which is around 300 MB.
- Splits it into training and validation sets.
- Builds `apps/pipeline-defect-detection/resources/videos/sample.mp4` for use by DL Streamer.

> **Note**: Skip this step if you have your own video, or if you plan to run in
> `LLM_MODE=fallback` where no video or DL Streamer inference is required.

> **Disclaimer**: By running this script you acknowledge that you are solely responsible for the
> rights, permissions, and licenses associated with the dataset at the provided URL.

## Step 4 — Download the LLM Model (LLM mode only)

`setup.sh` mounts a local, OpenVINO™ model server-formatted copy of the LLM into the
`apm-llm` service — it does not download or convert the model for you. Use the
[model-download microservice](https://github.com/open-edge-platform/edge-ai-libraries/tree/main/microservices/model-download)
(already defined as `apm-model-download` in `docker/compose.base.yaml`) to fetch and convert the
model configured via `LLM_MODEL_NAME`/`LLM_DEVICE`/`LLM_WEIGHT_FORMAT`:

```bash
source ./scripts/download_llm_model.sh --use-case pipeline-defect-detection
```

This script starts `apm-model-download`, submits a download and conversion request for the Hugging Face
model to OpenVINO model server's Intermediate Representation (IR) format, waits for the job to complete, and
writes the resulting local path back into
`apps/pipeline-defect-detection/.env_pipeline-defect-detection`
as `LLM_MODEL_PATH`. `setup.sh` mounts this path read-only into the `apm-llm` container.

> **Note**: Skip this step entirely if `LLM_MODE=fallback` — the script detects this and exits
> immediately without downloading anything.

## Step 5 — Launch the Application

**LLM mode** (requires the LLM and OpenVINO model server service; uses AI-generated analysis):

```bash
source ./setup.sh --use-case pipeline-defect-detection
```

**Fallback mode** (rule-based; no GPU or LLM service required):

```bash
LLM_MODE=fallback source ./setup.sh --use-case pipeline-defect-detection
```

The setup script validates your environment, sources the use-case `.env` file, and starts all
required services via the Docker Compose tool.

### Verify the Deployment

Check that all containers have started successfully:

```bash
docker ps --format "table {{.Names}}\t{{.Status}}"
```

If successful, you will see the following containers running:

| Container | Role |
|-----------|------|
| `apm-nginx` | Reverse proxy |
| `apm-ui` | Web dashboard |
| `apm-agent` | Multi-agent orchestrator |
| `apm-storage` | Detection data store |
| `apm-dlstreamer` | Video inference |
| `apm-mqtt-broker` | Message Queuing Telemetry Transport (MQTT) broker |
| `apm-model-download` | Model download utility |
| `apm-llm` | LLM service (OpenVINO model server) *(LLM mode only)* |

## Step 6 — Open the Dashboard

Navigate to `http://localhost:8080` in your browser. The dashboard displays:

- A "Run Pipeline" button that runs one full detect-then-reason cycle: the DL Streamer pipeline
  processes the source video once, then the agent pipeline (policy → analysis → evidence →
  ticketing) reasons over exactly the detections it produced.
- Live phase status ("Detecting…" / "Analyzing…") while a run is in progress.
- A log of all agent runs with status indicators.
- Generated maintenance tickets with priority, description, and recommended action.

## Stop and Clean Up

Stop all running containers:

```bash
source ./setup.sh --stop
```

Stop containers and remove all stored detection data:

```bash
source ./setup.sh --clean-data
```

## Configuration Reference

Four files in `apps/<use-case>/` control all use-case behaviors:

| File | Purpose |
|------|---------|
| `configs/agents.yaml` | Agent pipeline settings, defect classes, and confidence thresholds |
| `configs/pipeline-server-config.json` | DL Streamer pipeline definition and model paths |
| `configs/policy_fallback.json` | Rule-based fallback thresholds and escalation actions |
| `prompts/<use-case>.txt` | LLM prompt sections for each agent |

### agents.yaml

The `agents.yaml` file controls which defect classes are monitored and what confidence levels
trigger alerts:

```yaml
use_case_id: pipeline-defect-detection   # must match the prompt file name
analysis:
  min_confidence: 0.5                    # detections below this threshold are filtered
policy:
  defect_classes: [Rupture, Deformation, Disconnect, Obstacle]
  alert_threshold: 0.7                   # confidence threshold for policy violations
  critical_classes: [Rupture, Disconnect]
```

### Prompt File Sections

Prompt sections that are delimited by `[SECTION_NAME]` headers, define the LLM behavior:

```
[SYSTEM]    — shared system role for all agents
[POLICY]    — instructions for the Policy Agent
[ANALYSIS]  — instructions for the Analysis Agent
[EVIDENCE]  — instructions for the Evidence Agent
[TICKETING] — instructions for the Ticketing Agent
```

## Create a New Use Case

To adapt the blueprint to a different inspection scenario, for example, Weld Defect Detection:

```bash
# Copy the existing use-case directory
cp -r apps/pipeline-defect-detection apps/weld-defect-detection

# Edit the four configuration files
vi apps/weld-defect-detection/configs/agents.yaml       # update use_case_id and defect classes
vi apps/weld-defect-detection/configs/policy_fallback.json
vi apps/weld-defect-detection/prompts/weld-defect-detection.txt

# Launch with the new use case
source ./setup.sh --use-case weld-defect-detection
```

The blueprint needs no code changes; it reads all behaviors from the configuration
files at startup.

<!--hide_directive
:::{toctree}
:hidden:

get-started/system-requirements
:::
hide_directive-->
