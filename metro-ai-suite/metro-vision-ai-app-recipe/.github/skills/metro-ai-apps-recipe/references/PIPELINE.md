# DLSPS pipeline reference

> **Skill pointer:** for deploying, configuring, and operating DL Streamer
> Pipeline Server (container startup, `config.json` pipeline definitions, REST
> API launch/stop/status, MQTT/publisher wiring, GPU/NPU device access), invoke
> the external `dlsps-user` skill (open-edge-platform/skills) when available.
> The settings below are the recipe-specific overrides this stack requires.

## Required env

- `REST_SERVER_PORT=8080`, `RUN_MODE=EVA`,
  `APPEND_PIPELINE_NAME_TO_PUBLISHER_TOPIC=true`,
  `EMIT_SOURCE_AND_DESTINATION=true`, `SERVICE_NAME=dlstreamer-pipeline-server`,
  `MQTT_HOST=broker`, `MQTT_PORT=1883`.
- **WebRTC (required):** `ENABLE_WEBRTC=true`,
  `WEBRTC_SIGNALING_SERVER=http://mediamtx-server:8889`. DLSPS pushes each
  annotated stream to MediaMTX via WHIP using the per-launch `peer-id`.
- NPU also: `ZE_ENABLE_ALT_DRIVERS=libze_intel_npu.so`.
- Do NOT set `ENABLE_OPEN_TELEMETRY` (this stack drops OTel/Prometheus).
- Blank proxy: `http_proxy=`, `https_proxy=`, `HTTP_PROXY=`, `HTTPS_PROXY=`;
  `no_proxy=${no_proxy},${HOST_IP},mediamtx-server` (MUST include
  `mediamtx-server` or WHIP signalling routes through the corporate proxy
  and the WebRTC publish silently fails).

## Volumes and permissions

- Pipeline root: tmpfs named volume `uid=1999,gid=1999`
  (`dlstreamer-pipeline-server-pipeline-root:/var/cache/pipeline_root`).
  Do NOT run the container as root.
- No shared frames volume is needed — video leaves DLSPS over WebRTC, not
  as JPEG files.
- Device access needs ALL of: `devices: ["/dev:/dev"]`,
  `volumes: ["/run/udev:/run/udev:ro","/dev:/dev","/tmp:/tmp"]`,
  `device_cgroup_rules: ["c 189:* rmw", "c 209:* rmw", "a 189:* rwm"]`,
  `group_add: ["${VIDEO_GID}", "${RENDER_GID}"]`. Do NOT append a
  duplicate GID (e.g. `vpl` sharing `render`) — Compose rejects duplicate
  strings.

## Three pipeline variants

Config at `/home/pipeline-server/config.json`: exactly three variants
named `{{PIPELINE_NAME}}`, `{{PIPELINE_NAME}}_gpu`,
`{{PIPELINE_NAME}}_npu`. These names are load-bearing — REST path + MQTT
topic suffix use them.

**CRITICAL — `name`/`version` schema (verified 2026.1.0):** in each
`config.json` pipeline object set the variant as the **`name`** field and
DO NOT add a `version` field. DLSPS reinterprets that `name` as the
pipeline **version** and ALWAYS groups every pipeline under the fixed
group name `user_defined_pipelines`. So:

- `GET /api/pipelines` returns objects shaped
  `{"name":"user_defined_pipelines", "version":"{{PIPELINE_NAME}}", ...}`
  — the variant lives in **`version`**, not `name`.
- Launch/DELETE path stays
  `/api/pipelines/user_defined_pipelines/<variant>`.
- **Mistake that silently collapses all three variants into one:** giving
  the config objects `name: user_defined_pipelines` + `version: <variant>`.
  DLSPS ignores the input `version`, so all three become
  `user_defined_pipelines/user_defined_pipelines` and every launch returns
  HTTP 400 `"Pipeline not found"`. Always author config `name: <variant>`
  with no `version` key.
- After editing `config.json` you MUST `docker compose up -d
  --force-recreate dlstreamer-pipeline-server` (NOT `restart`) — the
  pipeline definitions are copied into the `pipeline_root` tmpfs at
  startup, and a plain `restart` keeps the stale tmpfs and reloads the old
  pipelines.

## Pipeline shape (WebRTC frame branch handled by DLSPS)

The pipeline ends in `appsink name=destination` (metadata → MQTT). The
annotated **video is emitted over WebRTC by DLSPS itself** when the REST
launch supplies a `frame` destination of `type: webrtc` — DLSPS taps the
watermarked frames internally and WHIP-publishes them to MediaMTX. There
is NO `tee`, NO `jpegenc`, NO `multifilesink`, and no `frame-sink-location`
parameter. Add `gvawatermark` before `gvametaconvert` so bounding boxes
are burned into the WebRTC stream.

```
{auto_source} name=source ! decodebin3 !
  gvadetect model=/home/pipeline-server/models/<detect>.xml device=CPU
            threshold=0.3 inference-interval=1 inference-region=0
            model-instance-id=inst0 name=detection !
  queue ! gvaclassify model=/home/pipeline-server/models/<classify>.xml device=CPU
            inference-interval=1 model-instance-id=inst1 inference-region=1
            name=classification !                              # omit if CLASSIFIER=none
  queue ! gvawatermark !
  queue ! gvametaconvert add-empty-results=true name=metaconvert !
  queue ! gvafpscounter !
  appsink name=destination
```

Parameter mapping (same entry — no frame-sink property):
```json
"parameters": {
  "type": "object",
  "properties": {
    "detection-properties":      { "element": { "name": "detection",      "format": "element-properties" } },
    "classification-properties": { "element": { "name": "classification", "format": "element-properties" } }
  }
}
```

Notes:
- `threshold` is a knob. YOLO11 rescales to 640×640; on the 640×480
  reference video vehicles score 0.3–0.45. `threshold≥0.5` → empty stream.
  Ship `0.3`, raise for higher-res feeds.
- The WebRTC branch is internal to DLSPS — you do NOT wire it in the
  GStreamer string. Just include `gvawatermark` so overlays are visible,
  and supply the `frame.type=webrtc` destination at REST launch.
- Keep `appsink` non-blocking: DLSPS drops frames rather than stalling
  inference under back-pressure.

## GPU/NPU variants

Replace `decodebin3` with:
```
parsebin ! decodebin3 ! vapostproc ! video/x-raw(memory:VAMemory) ! gvafpsthrottle target-fps=30
```
Codec-agnostic (H.264/H.265/AV1 via VAAPI). Do NOT hardcode `vah264dec`.
Set `device=GPU`/`NPU` on `gvadetect`/`gvaclassify` with `nireq>=1` (NPU:
`nireq=4`) and `ie-config="GPU_THROUGHPUT_STREAMS=1"` on GPU. Add
`vapostproc ! video/x-raw` before `gvawatermark` to pull frames back to
system memory for the overlay + WebRTC encode.

## Class filtering — where and how

- DLSPS publishes ALL classes (bare `gvadetect`, no model-proc filter).
- **Filter in Node-RED** by `label_id ∈ {{CLASS_FILTER_IDS}}` (`[]` = keep all).
- OMZ single-class models (e.g. `person-detection-retail-0013`,
  `vehicle-detection-0202`) emit `label_id:1` with empty label; treat
  labelless / `label_id==1` as target — see `{{LABEL_RULE_NOTE}}`.

## Starting pipelines (per source, via REST through Nginx)

For `X in 1..{{NUM_SOURCES}}` POST to
`https://<HOST>/api/pipelines/user_defined_pipelines/<pipeline_name>`:
```json
{
  "source":      { "uri": "file:///home/pipeline-server/videos/new_video_X.mp4", "type": "uri" },
  "destination": {
    "metadata": { "type": "mqtt", "topic": "{{DETECTIONS_TOPIC_PREFIX}}_X", "publish_frame": false },
    "frame":    { "type": "webrtc", "peer-id": "{{DETECTIONS_TOPIC_PREFIX}}_X" }
  }
}
```
- The `frame` block makes DLSPS WHIP-publish the annotated stream to
  MediaMTX under path `= peer-id`. Grafana's iframe reads it back from
  `/mediamtx/{{DETECTIONS_TOPIC_PREFIX}}_X/` (WHEP). Keep `peer-id`
  identical to the MQTT `topic` so panels/streams line up per source.
- `<pipeline_name>` = one of the three variants; all N POSTs use the same
  variant per device flag.
- Use `curl -k --noproxy '*'`. Poll `GET /api/pipelines/status` until no
  instance is `QUEUED`.
- With `APPEND_PIPELINE_NAME_TO_PUBLISHER_TOPIC=true`, MQTT topic becomes
  `{{DETECTIONS_TOPIC_PREFIX}}_X/{{PIPELINE_NAME}}` (or `_gpu`/`_npu`).

## File-source watchdog (required when `source.uri` is `file://`)

DLSPS with `file://` is one-shot: EOS → `COMPLETED` → MQTT/WebRTC output
stops. `multifilesrc loop=true` / `urisourcebin` do NOT provide a working
loop past `qtdemux`/MP4 — do not attempt.

Ship `sample_watchdog.sh`: started at end of `sample_start.sh` (nohup, PID
→ `.watchdog.pid`, logs → `watchdog.log`), killed first thing by
`sample_stop.sh`.

1. Poll `GET /api/pipelines/status` every ~3 s.
2. For each instance in `{COMPLETED, ABORTED, ERROR}`:
   - Read topic from `GET /api/pipelines/{id}` at
     **`params.request.destination.metadata.topic`** (NOT the top-level
     `request…topic` — that's the internal expanded dict).
   - Extract source index from `{{DETECTIONS_TOPIC_PREFIX}}_(\d+)`,
     DELETE the finished id, POST a fresh one with same
     source/destination/parameters.
3. **Deduplicate by id** (`declare -A HANDLED`). DLSPS keeps `COMPLETED`
   entries in status forever (they don't disappear on DELETE); without
   the guard the watchdog spawns dozens/minute and pins CPU.

```sh
#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")"; source .env
HOST="${HOST_IP:-localhost}"; DEVICE="${1:-cpu}"
case "$DEVICE" in cpu) PIPE="{{PIPELINE_NAME}}";; gpu) PIPE="{{PIPELINE_NAME}}_gpu";; npu) PIPE="{{PIPELINE_NAME}}_npu";; *) exit 1;; esac
BASE="https://${HOST}/api/pipelines/user_defined_pipelines/${PIPE}"
declare -A HANDLED
trap 'exit 0' TERM INT
while :; do
  status=$(curl --noproxy '*' -sk "https://${HOST}/api/pipelines/status" || echo '[]')
  finished=$(echo "$status" | python3 -c 'import json,sys;[print(p["id"]) for p in json.load(sys.stdin) if p.get("state") in ("COMPLETED","ABORTED","ERROR")]')
  for id in $finished; do
    [ -n "${HANDLED[$id]:-}" ] && continue
    HANDLED[$id]=1
    detail=$(curl --noproxy '*' -sk "https://${HOST}/api/pipelines/${id}")
    idx=$(echo "$detail" | python3 -c 'import json,sys,re; d=json.load(sys.stdin); req=(d.get("params") or {}).get("request") or {}; t=(((req.get("destination") or {}).get("metadata") or {})).get("topic",""); m=re.match(r"{{DETECTIONS_TOPIC_PREFIX}}_(\d+)",t); print(m.group(1)) if m else None')
    [ -z "$idx" ] && continue
    curl --noproxy '*' -sk -X DELETE "https://${HOST}/api/pipelines/${id}" >/dev/null || true
    curl --noproxy '*' -sk -X POST -H 'Content-Type: application/json' \
      -d '{"source":{"uri":"file:///home/pipeline-server/videos/new_video_'"$idx"'.mp4","type":"uri"},"destination":{"metadata":{"type":"mqtt","topic":"{{DETECTIONS_TOPIC_PREFIX}}_'"$idx"'","publish_frame":false},"frame":{"type":"webrtc","peer-id":"{{DETECTIONS_TOPIC_PREFIX}}_'"$idx"'"}}}' \
      "$BASE" >/dev/null || true
  done
  sleep 3
done
```
