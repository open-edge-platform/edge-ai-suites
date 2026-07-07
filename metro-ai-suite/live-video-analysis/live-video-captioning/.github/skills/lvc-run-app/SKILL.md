---
name: lvc-run-app
description: Run, start, or smoke-test the Live Video Captioning app (Docker Compose stack with dashboard on :4173). Use to launch the stack, start a captioning run against an RTSP stream or simulator, verify captions flow, or check the dashboard.
---

# Run Live Video Captioning

All paths relative to `live-video-captioning/`. Driver: `.github/skills/lvc-run-app/smoke.sh` — use it instead of raw commands.

## Mandatory

- One-time model download before first launch (confirm license prompt interactively):
  ```bash
  ./model_download_scripts/download_models.sh --model OpenGVLab/InternVL2-1B --type vlm --weight-format int8
  ```
- Launch + wait healthy: `.github/skills/lvc-run-app/smoke.sh up` (runs `scripts/setup_env.sh` + `docker compose up -d`).
- Video source must be `rtsp://` or `/dev/videoN` — the API rejects `file://`. If the user has a real RTSP camera, ask for its URL and pass it: `smoke.sh start-run GenAI_Pipeline_on_CPU rtsp://<camera>`. Otherwise simulate: `smoke.sh start-sim` — with no argument it downloads the Intel sample video (`worker-zone-detection.mp4` from intel-iot-devkit/sample-videos) to `/tmp/lvc-smoke.mp4`; pass a local `.mp4` path to use your own.
- Full end-to-end check (launch → simulate → run → caption → UI check → cleanup):
  ```bash
  .github/skills/lvc-run-app/smoke.sh all
  ```
- Always `smoke.sh stop-run && smoke.sh stop-sim` when done.

## Driver commands

```text
up | status | start-sim [video.mp4] | start-run [pipeline] [rtsp_url]
wait-captions [secs] | check-ui [secs] | stop-run | stop-sim | all [video.mp4]
```

## Gotchas

- GPU pipeline (`GenAI_Pipeline_on_GPU`, the product default) fails instantly with `no element "vah264dec"` when VA-API is missing in the container → driver defaults to `GenAI_Pipeline_on_CPU`. `stream-ready` returning `"state":"error"` right after POST = pipeline failed to build; check `docker logs dlstreamer-pipeline-server`.
- The stack's `mediamtx` has RTSP disabled (`MTX_RTSP=no`); the simulator runs a second `mediamtx-server` container on :8554.
- First caption on CPU takes ~2–4 min (model load + first inference); ~20 s each afterwards. SSE `/api/metadata-stream` emits only `{"type":"status"}` heartbeats until then — not a hang.
- Always `curl --noproxy '*'` — corporate proxy env breaks localhost calls.
- Canonical router: `.github/copilot-instructions.md`. Real API: `GET /api/health`, `/api/vlm-models`, `/api/pipelines`, `POST|GET|DELETE /api/generate_captions_alerts[/{run_id}]`, `GET /api/generate_captions_alerts/{run_id}/stream-ready`, SSE `GET /api/generate_captions_alerts/metadata-stream`.
- `modelName` must match a directory name in `ov_models/` (see `GET /api/vlm-models`).
- `docker compose` warns about unset `EMBEDDING_*`/`VDMS_*`/`LLM_*` vars — harmless (EMBEDDING profile only).

## Validation

- `smoke.sh status` → all containers Up, `{"status":"healthy"}`.
- `smoke.sh wait-captions` prints a `"result": "<caption>"` line.
- `smoke.sh check-ui` prints "caption event reached UI stream" (heartbeats-only means no caption landed in the watch window — lengthen it or run wait-captions first).

## Stop stack

```bash
docker compose down
```
