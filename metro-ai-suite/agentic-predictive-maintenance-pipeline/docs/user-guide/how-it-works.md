# How It Works

The Agentic Predictive Maintenance (APM) blueprint follows an on-demand **detect-then-reason** model: clicking "Run Pipeline" starts the DL Streamer video-inference pipeline, waits for it to finish processing the (finite) source video, and then triggers a single multi-agent reasoning pass over exactly the detections that the run produced, generating structured maintenance tickets. Detection and reasoning are two independent, decoupled services connected only by a shared `run_id` and an event-driven MQTT handoff. This section describes each stage so you can understand, verify, and debug the pipeline independently.

## System Overview

```
Web UI (browser)
    │  HTTP :8080 (via apm-nginx)
    ▼
UI Service (apm-ui)
    │  REST: POST /run  ──▶ Detection Service (apm-detection): POST /detection/run
    │  REST: GET  /api/detection/status/{id}, GET /api/agents/status/{id} (merged view)
    ▼
Detection Service (apm-detection)
    │
    ├─ REST: POST /pipelines/user_defined_pipelines/<pipeline_name>  ──▶ DL Streamer (apm-dlstreamer)
    │  REST: GET  /pipelines/status                                  (start + poll to completion)
    │
    ├─ MQTT subscriber (topic: apm/detections) ◀── DL Streamer publishes raw detections
    │  REST: POST /detections (batch) ──▶ Storage Service (apm-storage)
    │
    └─ On terminal state (success or failure), publishes one "batch-complete"
       MQTT event (topic: apm/batch-complete) carrying the run_id and the
       id-window (start_id/end_id) of detections this run produced.
       This is the *only* handoff between detection and reasoning — the
       detection layer never calls the agent directly.

Agent Service (apm-agent) — external EAL "agent-quality-handler" image
    │
    ├─ MQTT subscriber (topic: apm/batch-complete) ◀── reacts to the event above
    │  Skips reasoning entirely if status != "completed" (no stale-data reasoning)
    │
    └─ Runs the 4-agent LangGraph pipeline bounded to the event's id-window:
         Policy Agent → Analysis Agent → Evidence Agent → Ticketing Agent
       (each agent reads detections from Storage Service via GET /detections,
        bounded by min_id/max_id — never the whole history)
```

Detection and reasoning are fully decoupled processes: the detection layer
owns DL Streamer control and raw-detection persistence; the agent layer is
detection-agnostic and only reacts to the terminal "batch-complete" event.
The UI service is the only component that talks to both, merging their two
independent run states into one `phase` for display.

## Stage 1 — Startup

Run the setup script with a use case:

```bash
source setup.sh --use-case pipeline-defect-detection
```

- Validates the environment and resolves `USE_CASE_*` paths from `apps/<use-case>/`.
- Sources `.env_<use-case>` for model, device, and mode settings.
- Runs `docker compose up -d` for all services.

Services started:

| Container | Role |
|-----------|------|
| `apm-mqtt-broker` | Mosquitto MQTT broker |
| `apm-model-download` | Downloads detection model on first run |
| `apm-dlstreamer` | Video inference (DL Streamer Pipeline Server) |
| `apm-storage` | REST API + SQLite storage for detections |
| `apm-detection` | Owns DL Streamer control, raw-detection ingestion, and the batch-complete event |
| `apm-agent` | Multi-agent reasoning orchestrator (external EAL image, reacts to batch-complete) |
| `apm-ui` | Web dashboard (Run Pipeline form, results, detections) |
| `apm-nginx` | Reverse proxy (`localhost:8080`) |
| `apm-llm` *(LLM mode only)* | LLM service (OpenVINO model server) for agent reasoning |

**Verify all containers are running:**

```bash
docker ps --format "table {{.Names}}\t{{.Status}}"
```

## Stage 2 — Trigger a Detect-Then-Reason Run

Clicking **Run Pipeline** in the UI (or `POST`ing to the detection-service
directly) starts one full detect-then-reason cycle:

1. **Detect** — the detection-service starts the DL Streamer pipeline matching
   the selected **Device** (CPU, GPU, or NPU — each maps to its own pipeline
   definition in `configs/pipeline-server-config.json`), optionally overriding
   the source **Video** with the file selected in the UI, and blocks until the
   pipeline reaches a terminal state.
2. **Handoff** — once the pipeline reaches a terminal state (success or
   failure), the detection-service publishes a single `apm/batch-complete`
   MQTT event carrying the outcome and the exact `start_id` or `end_id`
   detection window this run produced.
3. **Reason** — the agent-service, subscribed to that topic independently,
   picks up the event under its own `run_id` correlation and runs the four-agent
   pipeline bounded to exactly that ID window, never any earlier history.
   If the event's `status` is `error` (for example, an NPU device is selected
   but is not physically available), the agent-service records the run as
   **failed** immediately and skips reasoning entirely — it never reasons
   over stale or previously-stored detections.

Because detection and reasoning are separate services, only the
detection-service enforces "one run at a time": a concurrent
`POST /detection/run` call is rejected with `409` and the id of the
currently running run. The agent-service reacts to events as they arrive
and has no concept of "a run in progress" beyond that.

### Run Pipeline Inputs (UI)

| Field | Description |
|-------|--------------|
| Use Case | Read-only; identifies the deployed use case (`pipeline-defect-detection`) |
| Device | `CPU`, `GPU`, or `NPU` — selects which DL Streamer pipeline definition to run |
| Video | Source video file populated from the shared `resources/videos/` directory |

### Manual Trigger

```bash
curl -X POST http://localhost:8080/run \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d 'device=CPU&video_filename=sample.mp4'
```

Or call the detection-service directly through the proxy:

```bash
curl -X POST http://localhost:8080/api/detection/run \
  -H "Content-Type: application/json" \
  -d '{"device": "CPU", "video_filename": "sample.mp4"}'
# {"run_id": "abc123", "status": "running"}
```

Poll progress — the UI merges the two services' independent states into one
`phase` that moves `detecting` → `reasoning` → `completed`/`error`:

```bash
curl http://localhost:8080/api/detection/status/abc123
# {"run_id": "abc123", "status": "running", "phase": "detecting"}

# once detection completes, the agent-service takes over:
curl http://localhost:8080/api/agents/status/abc123
# {"run_id": "abc123", "status": "running", "phase": "reasoning"}
```

List available source videos:

```bash
curl http://localhost:8080/api/detection/videos
```

> Note: this release runs one bounded detect-then-reason cycle per click over
> a finite source video. True live and continuous background detection
> (independent of the "Run Pipeline" click) is a possible future direction;
> see the scalable architecture diagram (`docs/apm-scalable-arch.drawio`) for
> a proposed decoupled design. Detection and reasoning are already decoupled
> services today; extending to live streams would mean periodic "checkpoint"
> batch-complete events instead of a single terminal one, not a re-architecture.

## Stage 3 — Video Inference (DL Streamer → MQTT)

DL Streamer runs the configured pipeline (CPU, GPU, or NPU) against the selected
video and publishes each detection to MQTT.

**Verify inference is running:**

```bash
docker logs -f apm-dlstreamer
```

**Verify MQTT messages are flowing:**

```bash
docker exec apm-mqtt-broker mosquitto_sub -t 'apm/detections'
```

Each message is a JSON payload with `label`, `confidence`, `bbox`, `frame_id`, and `timestamp`.

## Stage 4 — Detection Storage and the Batch-Complete Handoff

The detection-service subscribes to the `apm/detections` MQTT topic on
startup and writes every detection to the storage service. Once its DL
Streamer run reaches a terminal state, it publishes one `apm/batch-complete`
event — the sole contract between detection and reasoning.

**Verify detections are being stored:**

```bash
# Recent detections
curl http://localhost:8080/api/storage/detections?limit=5

# Aggregate summary
curl http://localhost:8080/api/storage/detections/summary

# Current watermark (max detection id + total count)
curl http://localhost:8080/api/storage/detections/max_id
```

**Verify the batch-complete event:**

```bash
docker exec apm-mqtt-broker mosquitto_sub -t 'apm/batch-complete'
```

```json
{
  "run_id": "abc123",
  "status": "completed",
  "device": "CPU",
  "video_filename": "sample.mp4",
  "start_id": 1204,
  "end_id": 1339,
  "pipeline_status": {"state": "COMPLETED", "avg_fps": 24.7}
}
```

See the [agent-service integration guide](agent-service-integration-guide.md)
for the full contract any application needs to satisfy for plugging its own
detection layer into the agent-service, or vice versa.

## Stage 5 — Multi-Agent Reasoning (LangGraph)

The agent-service's meta-agent runs four agents via a LangGraph state
machine, bounded to the `start_id`/`end_id` window of the batch-complete
event. All agents read from the storage service.

### Agent 1 — Policy Agent

Reads `agents.yaml` thresholds and the run's detections. Determines which defect classes triggered policy violations.

- `Rupture` or `Disconnect` above threshold: **HIGH** priority alert.
- Uses `policy_fallback.json` rules in fallback mode; no LLM calls.

### Agent 2 — Analysis Agent

Filters detections by `min_confidence` (default `0.5`). Produces:
- Dominant defect class and counts
- Confidence distribution
- Temporal trend across frame IDs
- Clustering of bounding box regions

### Agent 3 — Evidence Agent

Builds a formal audit trail:
- Total frames inspected versus frames with detections.
- Per-class counts and confidence statistics.
- Top five highest-confidence detections per class.
- Compliance status: **PASS** or **FAIL**.

### Agent 4 — Ticketing Agent

Synthesises outputs from Policy and Analysis agents. Produces a structured JSON maintenance ticket:

```json
{
  "priority": "HIGH",
  "title": "Rupture detected in pipeline segment A3",
  "description": "...",
  "affected_component": "segment-A3",
  "recommended_action": "HALT_PIPELINE",
  "estimated_resolution_time": "4 hours",
  "tags": "Rupture, Disconnect"
}
```

### LLM versus Fallback Mode

| Mode | How Agents Reason |
|------|-------------------|
| `LLM_MODE=llm` | Agents send prompts to the LLM service (served via OVMS); responses are LLM-generated |
| `LLM_MODE=fallback` | Agents apply rule-based logic from `policy_fallback.json`; no LLM service needed |

Set the mode when starting:

```bash
# Fallback (rule-based, no GPU or LLM required)
LLM_MODE=fallback source setup.sh --use-case pipeline-defect-detection

# LLM mode (requires the apm-llm/OVMS service)
source setup.sh --use-case pipeline-defect-detection
```

## Stage 6 — View Results

### Check a Specific Run

```bash
# List all runs known to the detection layer
curl http://localhost:8080/api/detection/runs

# List all runs the agent-service has processed
curl http://localhost:8080/api/agents/runs

# Get the merged detection + reasoning status/phase for a run
curl http://localhost:8080/api/detection/status/<run_id>
curl http://localhost:8080/api/agents/status/<run_id>

# Get the completed run's result (ticket + agent outputs)
curl http://localhost:8080/api/agents/results/<run_id>
```

### Web UI

Open `http://localhost:8080` in a browser. The dashboard shows:
- Run pipeline form (Use Case, Device, or Video).
- Detection summary and browsing (`/detections`).
- Run history with status, and generated maintenance tickets (`/results/<run_id>`).

## Quick Verification Checklist

Run these commands in order, after the startup to verify each stage:

```bash
# 1. All containers healthy?
docker ps --format "table {{.Names}}\t{{.Status}}"

# 2. Detection and agent services reachable?
curl http://localhost:8080/api/detection/runs
curl http://localhost:8080/api/agents/runs

# 3. Trigger one detect-then-reason run
RUN_ID=$(curl -s -X POST http://localhost:8080/api/detection/run \
  -H "Content-Type: application/json" \
  -d '{"device": "CPU"}' | python3 -c "import sys,json; print(json.load(sys.stdin)['run_id'])")
echo "Run ID: $RUN_ID"

# 4. Poll detection phase until it reaches completed/error
curl http://localhost:8080/api/detection/status/$RUN_ID

# 5. Once detection completes, poll the agent-service for reasoning phase
curl http://localhost:8080/api/agents/status/$RUN_ID

# 6. Check detections stored during the run
curl http://localhost:8080/api/storage/detections/summary

# 7. View the ticket in the run result
curl http://localhost:8080/api/agents/results/$RUN_ID | python3 -m json.tool
```

## Troubleshooting

| Symptom | Check |
|---------|-------|
| No detections in storage | `docker logs apm-dlstreamer` and `docker logs apm-detection` — is the pipeline running? Is the source video present under `resources/videos/`? |
| Run stays in `detecting` phase | `docker logs apm-dlstreamer` and `docker logs apm-detection` — is the selected device (e.g. NPU) actually available? |
| Run is stuck in `reasoning` phase or never appears in agent runs | `docker logs apm-agent` — did it receive the `apm/batch-complete` event? `docker exec apm-mqtt-broker mosquitto_sub -t apm/batch-complete` to check the broker is delivering it |
| Run reports `status: error` | `curl http://localhost:8080/api/agents/results/<run_id>` — the detection run failed (`ERROR`/`ABORTED`) or timed out; reasoning is correctly skipped in this case |
| UI shows no runs | `curl http://localhost:8080/api/detection/runs` and `curl http://localhost:8080/api/agents/runs` — is the NGINX proxy, detection-service, or agent-service reachable? |
| LLM/OpenVINO model server service is unhealthy | Use `LLM_MODE=fallback` to bypass the LLM service for testing |
| `apm-storage` unhealthy | `docker logs apm-storage` — check port 5001 |
| `apm-agent` unhealthy or unreachable | `docker logs apm-agent` — it is an externally pulled image (not built from this repo); confirm `REGISTRY`/`TAG` resolve to a real published image |

For data preparation (creating a source video under `resources/videos/`):

```bash
python scripts/download_and_prep_data.py <dataset_url> --use-case pipeline-defect-detection
```
