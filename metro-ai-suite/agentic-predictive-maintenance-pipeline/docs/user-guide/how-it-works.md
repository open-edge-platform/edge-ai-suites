# How It Works

The Agentic Predictive Maintenance (APM) blueprint follows an on-demand **detect-then-reason** model: clicking "Run Pipeline" starts the DL Streamer video-inference pipeline, waits for it to finish processing the (finite) source video, and then triggers a single multi-agent reasoning pass over exactly the detections that run produced, generating structured maintenance tickets. This page describes each stage so you can understand, verify, and debug the pipeline independently.

## System Overview

```
Web UI (browser)
    │  HTTP :8080 (via apm-nginx)
    ▼
UI Service (apm-ui)
    │  REST: POST /agents/run, GET /agents/status/{id}, GET /agents/results/{id}
    ▼
Agent Service (apm-agent)
    │
    ├─ REST: POST /pipelines/user_defined_pipelines/<pipeline_name>  ──▶ DL Streamer (apm-dlstreamer)
    │  REST: GET  /pipelines/status                                  (start + poll to completion)
    │
    ├─ MQTT subscriber (topic: apm/detections) ◀── DL Streamer publishes detections
    │  REST: POST /detections (batch) ──▶ Storage Service (apm-storage)
    │
    └─ On successful completion, runs the 4-agent LangGraph pipeline
       bounded to the detections produced by this run:
         Policy Agent → Analysis Agent → Evidence Agent → Ticketing Agent
       (each agent reads from Storage Service via GET /detections)
```

Control communication (start a run, poll its state) between the Agent Service
and DL Streamer is REST-based; detection *data* flows over MQTT, published by
DL Streamer and consumed by a subscriber thread inside the Agent Service,
which persists each detection to the Storage Service.

## Stage 1 — Startup

Run the setup script with a use case:

```bash
source setup.sh --use-case pipeline-defect-detection
```

- Validates the environment and resolves `USE_CASE_*` paths from `apps/<use-case>/`
- Sources `.env_<use-case>` for model/device/mode settings
- Runs `docker compose up -d` for all services

Services started:

| Container | Role |
|-----------|------|
| `apm-mqtt-broker` | Mosquitto MQTT broker |
| `apm-model-download` | Downloads detection model on first run |
| `apm-dlstreamer` | Video inference (DL Streamer Pipeline Server) |
| `apm-storage` | REST API + SQLite storage for detections |
| `apm-agent` | Multi-agent orchestrator (detect-then-reason runs) |
| `apm-ui` | Web dashboard (Run Pipeline form, results, detections) |
| `apm-nginx` | Reverse proxy (`localhost:8080`) |
| `apm-llm` *(LLM mode only)* | LLM service (OVMS) for agent reasoning |

**Verify all containers are running:**

```bash
docker ps --format "table {{.Names}}\t{{.Status}}"
```

## Stage 2 — Triggering a Detect-Then-Reason Run

Clicking **Run Pipeline** in the UI (or calling `POST /agents/run` on the
agent-service directly) starts one full detect-then-reason cycle:

1. **Detect** — the agent-service starts the DL Streamer pipeline matching the
   selected **Device** (CPU/GPU/NPU — each maps to its own pipeline
   definition in `configs/pipeline-server-config.json`), optionally overriding
   the source **Video** with the file selected in the UI, and blocks until the
   pipeline reaches a terminal state.
2. **Reason** — only if that run **completes successfully**, the agent-service
   runs the 4-agent pipeline bounded to exactly the detections produced by
   this run (via an id-based `min_id`/`max_id` window on the Storage Service),
   never any earlier history.

If the detection run ends in `ERROR` or `ABORTED` (for example, an NPU device
is selected but not physically available), the whole run is reported as
**failed** and reasoning is **skipped** — the agent-service does not reason
over stale/previously-stored detections.

Only one detect-then-reason run may be in flight at a time — a concurrent
`POST /agents/run` call is rejected with `409` and the id of the currently
running run.

### Run Pipeline inputs (UI)

| Field | Description |
|-------|--------------|
| Use Case | Read-only; identifies the deployed use case (`pipeline-defect-detection`) |
| Device | `CPU` / `GPU` / `NPU` — selects which DL Streamer pipeline definition to run |
| Video | Source video file, populated from the shared `resources/videos/` directory |

### Manual trigger

```bash
curl -X POST http://localhost:8080/api/agents/run \
  -H "Content-Type: application/json" \
  -d '{"device": "CPU", "video_filename": "sample.mp4"}'
```

Returns:

```json
{"run_id": "abc123", "status": "running"}
```

Poll progress (the `phase` field moves `detecting` → `reasoning` → `completed`/`error`):

```bash
curl http://localhost:8080/api/agents/status/abc123
# {"run_id": "abc123", "status": "running", "phase": "detecting"}
```

List available source videos:

```bash
curl http://localhost:8080/api/agents/videos
```

> Note: this release runs one bounded detect-then-reason cycle per click over
> a finite source video. True live/continuous background detection
> (independent of the "Run Pipeline" click) is a possible future direction —
> see the scalable architecture diagram (`docs/apm-scalable-arch.drawio`) for
> a proposed decoupled design.

## Stage 3 — Video Inference (DL Streamer → MQTT)

DL Streamer runs the configured pipeline (CPU/GPU/NPU) against the selected
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

## Stage 4 — Detection Storage (MQTT → Storage Service)

The agent-service subscribes to the `apm/detections` MQTT topic on startup
and writes every detection to the storage service.

**Verify detections are being stored:**

```bash
# Recent detections
curl http://localhost:8080/api/storage/detections?limit=5

# Aggregate summary
curl http://localhost:8080/api/storage/detections/summary

# Current watermark (max detection id + total count)
curl http://localhost:8080/api/storage/detections/max_id
```

## Stage 5 — Multi-Agent Reasoning (LangGraph)

The meta-agent runs four agents **sequentially** via a LangGraph state
machine, bounded to the `min_id`/`max_id` window of the current run. All
agents read from the storage service.

### Agent 1 — Policy Agent

Reads `agents.yaml` thresholds and the run's detections. Determines which defect classes triggered policy violations.

- `Rupture` or `Disconnect` above threshold → **HIGH** priority alert
- Uses `policy_fallback.json` rules in fallback mode (no LLM call)

### Agent 2 — Analysis Agent

Filters detections by `min_confidence` (default `0.5`). Produces:
- Dominant defect class and counts
- Confidence distribution
- Temporal trend across frame IDs
- Clustering of bounding box regions

### Agent 3 — Evidence Agent

Builds a formal audit trail:
- Total frames inspected vs. frames with detections
- Per-class counts and confidence statistics
- Top-5 highest-confidence detections per class
- Compliance status: **PASS** / **FAIL**

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

### LLM vs. Fallback Mode

| Mode | How agents reason |
|------|-------------------|
| `LLM_MODE=llm` | Agents send prompts to the LLM service (served via OVMS); responses are LLM-generated |
| `LLM_MODE=fallback` | Agents apply rule-based logic from `policy_fallback.json`; no LLM service needed |

Set the mode when starting:

```bash
# Fallback (rule-based, no GPU/LLM required)
LLM_MODE=fallback source setup.sh --use-case pipeline-defect-detection

# LLM mode (requires the apm-llm/OVMS service)
source setup.sh --use-case pipeline-defect-detection
```

## Stage 6 — Viewing Results

### Check a specific run

```bash
# List all runs
curl http://localhost:8080/api/agents/runs

# Get run status/phase
curl http://localhost:8080/api/agents/status/<run_id>

# Get the completed run's result (ticket + pipeline_status)
curl http://localhost:8080/api/agents/results/<run_id>
```

### Web UI

Open `http://localhost:8080` in a browser. The dashboard shows:
- Run Pipeline form (Use Case / Device / Video)
- Detection summary and browsing (`/detections`)
- Run history with status, and generated maintenance tickets (`/results/<run_id>`)

## Quick Verification Checklist

Run these commands in order after startup to verify each stage:

```bash
# 1. All containers healthy?
docker ps --format "table {{.Names}}\t{{.Status}}"

# 2. Agent service reachable?
curl http://localhost:8080/api/agents/runs

# 3. Trigger one detect-then-reason run
RUN_ID=$(curl -s -X POST http://localhost:8080/api/agents/run \
  -H "Content-Type: application/json" \
  -d '{"device": "CPU"}' | python3 -c "import sys,json; print(json.load(sys.stdin)['run_id'])")
echo "Run ID: $RUN_ID"

# 4. Poll status until phase reaches completed/error
curl http://localhost:8080/api/agents/status/$RUN_ID

# 5. Check detections stored during the run
curl http://localhost:8080/api/storage/detections/summary

# 6. View the ticket in the run result
curl http://localhost:8080/api/agents/results/$RUN_ID | python3 -m json.tool
```

## Troubleshooting

| Symptom | Check |
|---------|-------|
| No detections in storage | `docker logs apm-dlstreamer` — is the pipeline running? Is the source video present under `resources/videos/`? |
| Run stays in `detecting` phase | `docker logs apm-dlstreamer` and `docker logs apm-agent` — is the selected device (e.g. NPU) actually available? |
| Run reports `status: error` | `curl http://localhost:8080/api/agents/results/<run_id>` — the detection run failed (`ERROR`/`ABORTED`) or timed out; reasoning is correctly skipped in this case |
| UI shows no runs | `curl http://localhost:8080/api/agents/runs` — is the nginx proxy / agent-service reachable? |
| LLM/OVMS service unhealthy | Use `LLM_MODE=fallback` to bypass the LLM service for testing |
| `apm-storage` unhealthy | `docker logs apm-storage` — check port 5001 |

For data preparation (creating a source video under `resources/videos/`):

```bash
python scripts/download_and_prep_data.py <dataset_url> --use-case pipeline-defect-detection
```
