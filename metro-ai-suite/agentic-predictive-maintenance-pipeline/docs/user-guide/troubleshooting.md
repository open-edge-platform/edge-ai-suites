# Troubleshooting

## Containers Started but Detections Do Not Appear

**Symptom**: The dashboard shows no detection events and `GET /detections/summary` returns zero totals.

**Steps to diagnose:**

1. Check that the DL Streamer container is running and processing the video:

   ```bash
   docker logs -f apm-dlstreamer
   ```

   Look for log lines showing inference results. If the container exited, the video file may be
   missing.

2. Confirm that `datastream.mp4` exists in the expected location:

   ```bash
   ls apps/pipeline-defect-detection/resources/videos/
   ```

   If the file is missing, run the data preparation script described in
   [Get Started](./get-started.md#step-3--prepare-sample-data).

3. Check that MQTT messages are flowing from DL Streamer to
   the broker:

   ```bash
   docker exec apm-mqtt-broker mosquitto_sub -t 'dlstreamer/detections'
   ```

   If no messages appear, the DL Streamer pipeline may not have been triggered. Start it manually:

   ```bash
   docker exec apm-dlstreamer curl -X POST \
     http://localhost:8554/pipelines/user_defined_pipelines/pipeline_defect_detection \
     -H "Content-Type: application/json" -d '{}'
   ```

   The pipeline server port is available only inside the Compose network and is not published on
   the host.

## Agent Run Stays in `in_progress` and Never Completes

**Symptom**: A run triggered via `POST /api/agents/runs` shows `status: in_progress` indefinitely.

**Steps to diagnose:**

1. Check the agent service logs:

   ```bash
   docker logs apm-agent
   ```

2. If `LLM_MODE=llm`, check that the LLM service served via the OpenVINO Model
   Server is healthy:

   ```bash
   docker exec apm-ui python3 -c \
     "import urllib.request; print(urllib.request.urlopen('http://apm-llm:8000/v1/config').status)"
   ```

   If the OpenVINO model server service is unhealthy or is still loading the model, wait for it to finish.
   The first
   startup can take several minutes while it loads the model.

3. To test the pipeline without the LLM service, switch to the fallback mode:

   ```bash
   ./setup.sh --stop
   LLM_MODE=fallback ./setup.sh --use-case pipeline-defect-detection
   ```

## Dashboard Shows No Runs or Returns an Error

**Symptom**: The UI displays no run history, or `GET /api/agents/runs` returns an error.

**Check**: Verify that the NGINX proxy is routing requests correctly:

```bash
curl http://localhost:8080/api/agents/runs
```

If that fails, check the NGINX container:

```bash
docker logs apm-nginx
```

Also confirm that the agent service itself is healthy:

```bash
curl http://localhost:8080/api/agents/health
```

## Ask & Analyze Is Unavailable or Returns an Error

**Symptom**: The chat page reports that LLM-backed analysis is disabled, cannot reach the model, or
cannot gather supporting data.

1. Confirm the deployment mode:

   ```bash
   docker inspect apm-ui --format '{{range .Config.Env}}{{println .}}{{end}}' \
     | grep -E '^(LLM_BASE_URL|LLM_MODEL_NAME)='
   ```

   `LLM_MODE=fallback` omits `apm-llm`, leaving Ask & Analyze unavailable while preserving the
   dashboard and rule-based detect-then-reason workflow.

2. In LLM mode, verify that the shared OVMS service is healthy:

   ```bash
   docker inspect apm-llm --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}'
   docker logs apm-llm
   ```

3. Verify internal DNS/connectivity from the UI container:

   ```bash
   docker exec apm-ui python3 -c \
     "import urllib.request; print(urllib.request.urlopen('http://apm-llm:8000/v1/config').status)"
   ```

   `apm-llm` must remain in the UI's `no_proxy` list. Do not replace the internal URL with
   `localhost`; inside `apm-ui`, `localhost` refers to the UI container itself.

4. If an answer cannot be grounded, check the relevant source:

   ```bash
   curl http://localhost:8080/api/agents/runs
   curl http://localhost:8080/api/storage/detections/summary
   ```

   Analysis mode needs completed agent output. Detection mode needs stored detections. A specified
   run ID must exist, have completed, and include a valid detection ID window.

5. If the services are healthy but chat repeatedly returns an LLM or invalid-query error, try a
   larger instruction model. Smaller models can be less reliable at following the structured query
   schema used by Detection and Combined modes. In
   `apps/pipeline-defect-detection/.env_pipeline-defect-detection`, set `LLM_MODEL_NAME` to the
   Hugging Face model ID of a larger model supported by your OpenVINO model server release, such as
   a supported Qwen3 instruction model.

   Ensure the target system has enough memory for the larger model. Keep
   `LLM_WEIGHT_FORMAT=int4` on memory-constrained systems, then download, convert, and redeploy it:

   ```bash
   source ./scripts/download_llm_model.sh --use-case pipeline-defect-detection
   source ./setup.sh --use-case pipeline-defect-detection
   ```

   Wait for `apm-llm` to become healthy before retrying chat. The agent pipeline and Ask & Analyze
   share this model, so the change applies to Analysis, Detection, and Combined modes.

Questions longer than 4,000 characters, malformed run IDs, unsupported modes/control characters,
extra request fields, and invalid structured-query plans are rejected. General upstream requests
have a 15-second timeout; LLM generation requests allow 60 seconds by default. On constrained
hardware, wait until `apm-llm` is healthy, shorten the question, and retry.

Application APIs are exposed only through NGINX at `http://localhost:8080`. The model-download
service is the only other service with a published host port (`http://localhost:8200` by default).
Use container logs, health status, or `docker exec` for services that are internal to the Compose
network.

## OpenVINO Model Server Service is Unhealthy after Startup

**Symptom**: `apm-llm` shows as unhealthy in `docker ps` even after several minutes.

**Cause**: Model loading on the first startup can take several minutes depending on model size and
hardware.

**Steps:**

1. Check the progress in the OpenVINO model server logs:

   ```bash
   docker logs -f apm-llm
   ```

2. If you need to run quickly without waiting, use the fallback mode:

   ```bash
   ./setup.sh --stop
   LLM_MODE=fallback ./setup.sh --use-case pipeline-defect-detection
   ```

3. If you see permission errors related to `/model`, remove the model cache volume and restart:

   ```bash
   ./setup.sh --stop
   docker volume rm apm_model_cache
   ./setup.sh --use-case pipeline-defect-detection
   ```

## Storage Service is Unhealthy

**Symptom**: `apm-storage` shows as unhealthy and detections are not being persisted.

**Check the storage service logs:**

```bash
docker logs apm-storage
```

Common causes:
- Port 5001 is already in use on the host. Change the `STORAGE_PORT` in the `.env` file.
- The `apm_sqlite_data` volume has a permission issue. Remove the volume and restart:

  ```bash
  ./setup.sh --clean-data
  ./setup.sh --use-case pipeline-defect-detection
  ```

## Quick Verification Checklist

Run these commands in order after startup to verify each stage of the pipeline:

```bash
# 1. All containers healthy?
docker ps --format "table {{.Names}}\t{{.Status}}"

# 2. Detections stored?
curl http://localhost:8080/api/storage/detections/summary

# 3. Agent service reachable?
curl http://localhost:8080/api/agents/runs

# 4. Trigger one agent run manually
RUN_ID=$(curl -s -X POST http://localhost:8080/api/agents/runs \
  -H "Content-Type: application/json" -d '{}' | python3 -c "import sys,json; print(json.load(sys.stdin)['run_id'])")
echo "Run ID: $RUN_ID"

# 5. Wait for completion and check the result
sleep 15
curl http://localhost:8080/api/agents/runs/$RUN_ID | python3 -m json.tool
```

## Common Error Summary

| Symptom | Likely Cause | Action |
|---------|-------------|--------|
| No detections in storage | `datastream.mp4` is missing or pipeline is not triggered | Prepare data and trigger the DL Streamer pipeline |
| Agent run is stuck in `in_progress` | OpenVINO model server service is unhealthy or is still loading | Check `docker logs apm-llm` or switch to the fallback mode |
| UI shows no runs | NGINX proxy issue or agent service is down | Check `docker logs apm-nginx` and `docker logs apm-agent` |
| Ask & Analyze is disabled | `LLM_MODE=fallback` | Restart in LLM mode after preparing the configured model |
| Ask & Analyze cannot reach the model | `apm-llm` is unhealthy, still loading, or incorrectly proxied | Check `apm-llm`, `LLM_BASE_URL`, and the UI `no_proxy` value |
| Ask & Analyze has no grounding data | Requested run is incomplete/missing or storage has no detections | Check agent runs and the detection summary |
| `apm-storage` is unhealthy | Container startup or volume permission issue | Check `docker logs apm-storage`, query `http://localhost:8080/api/storage/health`, or run `./setup.sh --clean-data` |
| OpenVINO model server container restarts repeatedly | GPU out of memory or the model is not supported | Switch to CPU inference or use a smaller model |
