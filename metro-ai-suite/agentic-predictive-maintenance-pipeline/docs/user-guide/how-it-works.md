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

Run history is scoped to the current application session. The Compose deployment clears stored
detections when the detection service starts, before subscribing to new detection events, so a
restarted application does not show detections without corresponding run IDs.

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

Both `apm-agent` and `apm-ui` use `LLM_MODEL_NAME` and the same OpenAI-compatible OVMS endpoint
(`http://apm-llm:8000/v3`). Ask & Analyze therefore does not introduce, download, or serve another
model. All services communicate over the existing `apm_network`; `apm-llm` is included in the UI
container's `no_proxy` list so internal model requests do not leave the Compose network.

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
  -d 'device=CPU&video_filename=datastream.mp4'
```

Or call the detection-service directly through the proxy:

```bash
curl -X POST http://localhost:8080/api/detection/run \
  -H "Content-Type: application/json" \
  -d '{"device": "CPU", "video_filename": "datastream.mp4"}'
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
  "video_filename": "datastream.mp4",
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
- Ask & Analyze (`/chat`) for grounded natural-language questions.

## Ask & Analyze

Ask & Analyze sends a question to the UI service, which gathers bounded supporting data before
asking the existing OVMS-hosted model to explain it. The browser never calls OVMS or the storage
database directly.

### Modes and grounding

| Mode | Source behavior |
|------|-----------------|
| `analysis` | Grounds the answer in completed analysis output. An optional `run_id` selects a specific completed run. |
| `detections` | Translates the question into an allowlisted structured storage query and grounds the answer in its returned rows or aggregates. An optional `run_id` scopes the query to that completed run. Raw SQL is never accepted or generated at the storage boundary. |
| `combined` | Uses both agent output and structured detection results, allowing the model to relate recommendations to detection evidence. |

Detection queries use only allowlisted fields, filters, sort keys, and aggregate functions. The
storage API permits up to 500 rows, but Ask & Analyze further caps returned rows and lists at 100.
Storage plans permit up to 20 filters, 3 sort keys, and an offset of 10,000. These limits bound the
amount of data supplied to the model. The response exposes the validated query object and supporting
data so users can inspect the basis for an answer. The model can still make mistakes; the supporting
data and original run result remain the authoritative sources.

Before planning a detection query, the UI service loads the labels that are actually present in
storage. For a selected run, this label catalog uses the same detection ID window as the final
query. OVMS then produces one schema-constrained query plan using those canonical labels. Label
variants are matched case-insensitively with spaces, underscores, and hyphens treated as equivalent,
so `shipping_label` can resolve to `Shipping Label`. If the model omits a label that is explicitly
present in the question, the UI service adds that canonical label filter before execution. Questions
without a label produce no label filter and therefore include all labels. Unknown or ambiguous
labels are rejected with the available label list.

Every plan is validated before storage executes it, and the selected run's ID window is always
enforced by the UI service. The full detection dataset is not sent to the LLM because large runs
would exceed the bounded model context and make counts or aggregates incomplete. Generated SQL is
never accepted.

### Chat API contract

The browser posts to `POST http://localhost:8080/api/chat`:

```json
{
  "message": "Which detections need immediate attention, and why?",
  "mode": "combined",
  "run_id": "optional-completed-run-id"
}
```

- `message` is required, non-blank, and limited to 4,000 characters.
- `mode` is required and must be `analysis`, `detections`, or `combined`.
- `run_id` is optional, 1-128 characters when supplied, and must match
  `^[A-Za-z0-9][A-Za-z0-9._:-]*$`.
- Extra fields and unsupported control characters are rejected.

A successful response has this shape:

```json
{
  "answer": "Rupture detections require immediate attention ...",
  "mode": "combined",
  "query": {
    "operation": "group_by",
    "group_by": ["label"],
    "metrics": [{"function": "count", "alias": "detections"}],
    "limit": 100
  },
  "data": {
    "analysis": {
      "run_id": "...",
      "analysis": {},
      "window": {"start_id": 1204, "end_id": 1339}
    },
    "detections": {
      "data": [],
      "meta": {"operation": "group_by", "returned": 0, "has_more": false}
    }
  }
}
```

`answer` is the generated explanation, capped at 4,000 characters. `mode` is the mode actually used.
`query` is the validated structured detection plan for `detections` and `combined`, and `null` for
`analysis`. `data.analysis` contains only the selected run's bounded analysis and detection window;
`data.detections` contains the storage query response.

Analysis mode uses the requested completed run, or the latest completed run when `run_id` is omitted.
Detection mode queries all stored detections unless `run_id` is supplied. Combined mode and
run-scoped detection mode enforce the completed run's `id > start_id` and `id <= end_id` window
server-side, even if the generated plan omits those filters.
The chat page lists completed runs by their full ID and the dashboard links each completed run
directly to a preselected, run-scoped chat. With multiple runs, selecting a run isolates analysis
and detection evidence to that run; leaving the selector at its default uses the latest completed
run for analysis/combined mode or all stored detections for detection mode.
The planner and final answer each use a 15-second HTTP timeout. Planner output is limited to 700
tokens; the final answer is limited to 500 tokens with temperature `0`. Model content is capped at
16,000 characters and grounded prompt context at 12,000 characters.

Expected errors are:

| Status | Meaning |
|--------|---------|
| `422` | Invalid request, extra field, unsupported mode/control character, or malformed run ID |
| `404` | Requested run does not exist, or no completed run is available |
| `409` | Requested run exists but is not completed |
| `503` | Required LLM endpoint or model configuration is absent |
| `502` | Safe generic upstream error, including OVMS timeout/unavailability, an invalid generated query plan, or storage/agent failure |

Errors expose a safe, human-readable `detail`, not internal exception text. Questions, retrieved
results, and raw prompts are not logged. The UI keeps failed questions available for retry and
limits one request at a time per browser page. The endpoint does not create a persistent chat
session: each request is independently grounded.

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
| `apm-storage` unhealthy | `docker logs apm-storage` and `curl http://localhost:8080/api/storage/health` |
| `apm-agent` unhealthy or unreachable | `docker logs apm-agent` — it is an externally pulled image (not built from this repo); confirm `REGISTRY`/`TAG` resolve to a real published image |

For data preparation (creating a source video under `resources/videos/`):

```bash
python scripts/download_and_prep_data.py <dataset_url> --use-case pipeline-defect-detection
```
