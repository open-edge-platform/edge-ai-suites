# DLSPS pipeline reference

## Required env

- `REST_SERVER_PORT=8080`, `RUN_MODE=EVA`,
  `APPEND_PIPELINE_NAME_TO_PUBLISHER_TOPIC=true`,
  `EMIT_SOURCE_AND_DESTINATION=true`, `SERVICE_NAME=dlstreamer-pipeline-server`,
  `MQTT_HOST=broker`, `MQTT_PORT=1883`.
- NPU also: `ZE_ENABLE_ALT_DRIVERS=libze_intel_npu.so`.
- Do NOT set `ENABLE_WEBRTC` / `WEBRTC_SIGNALING_SERVER` / `ENABLE_OPEN_TELEMETRY`.
- Blank proxy: `http_proxy=`, `https_proxy=`, `HTTP_PROXY=`, `HTTPS_PROXY=`;
  `no_proxy=${no_proxy},${HOST_IP}`.

## Volumes and permissions

- Pipeline root: tmpfs named volume `uid=1999,gid=1999`
  (`dlstreamer-pipeline-server-pipeline-root:/var/cache/pipeline_root`).
  Do NOT run the container as root.
- Frames volume: shared tmpfs named volume `frames`, mounted `/tmp/frames`
  in DLSPS (rw) and `/usr/share/nginx/html/frames` in Nginx (ro).
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

## Pipeline shape (with per-REST frame-path injection)

Pipeline ends in a `tee`: one branch → `appsink` (metadata → MQTT), the
other → `gvawatermark` → throttle to `{{MJPEG_FPS}}` → `jpegenc` →
`multifilesink name=frame_sink`. Expose `multifilesink.location` as a
top-level `parameters.frame-sink-location`. **One config entry serves
all sources** — path is set per REST launch, no per-source config
duplication, no `{peer-id}` UUID mystery.

```
{auto_source} name=source ! decodebin3 !
  gvadetect model=/home/pipeline-server/models/<detect>.xml device=CPU
            threshold=0.3 inference-interval=1 inference-region=0
            model-instance-id=inst0 name=detection !
  queue ! gvaclassify model=/home/pipeline-server/models/<classify>.xml device=CPU
            inference-interval=1 model-instance-id=inst1 inference-region=1
            name=classification !                              # omit if CLASSIFIER=none
  queue ! gvametaconvert add-empty-results=true name=metaconvert !
  queue ! gvafpscounter !
  tee name=t
    t. ! queue leaky=downstream max-size-buffers=1 ! appsink name=destination
    t. ! queue leaky=downstream max-size-buffers=2 !
         gvawatermark ! videorate ! video/x-raw,framerate={{MJPEG_FPS}}/1 !
         videoconvert ! jpegenc quality=75 !
         multifilesink name=frame_sink location=/tmp/frames/default.jpg post-messages=false
```

Parameter mapping (same entry):
```json
"parameters": {
  "type": "object",
  "properties": {
    "frame-sink-location":       { "element": { "name": "frame_sink",     "property": "location", "format": "string" } },
    "detection-properties":      { "element": { "name": "detection",      "format": "element-properties" } },
    "classification-properties": { "element": { "name": "classification", "format": "element-properties" } }
  }
}
```

Notes:
- `threshold` is a knob. YOLO11 rescales to 640×640; on the 640×480
  reference video vehicles score 0.3–0.45. `threshold≥0.5` → empty stream.
  Ship `0.3`, raise for higher-res feeds.
- `multifilesink` (no `%d` in `location`) overwrites in place — NOT atomic.
  A very fast poll can occasionally see a partial JPEG. The Grafana
  `<img onerror>` handler retries after 1 s; at `MJPEG_FPS=5` and ~50 KB
  frames the race window is <1 ms, artifacts are rare.
- `leaky=downstream` on both branches: MQTT slowdown doesn't stall
  inference, frame branch doesn't back-pressure detection.

## GPU/NPU variants

Replace `decodebin3` with:
```
parsebin ! decodebin3 ! vapostproc ! video/x-raw(memory:VAMemory) ! gvafpsthrottle target-fps=30
```
Codec-agnostic (H.264/H.265/AV1 via VAAPI). Do NOT hardcode `vah264dec`.
Set `device=GPU`/`NPU` on `gvadetect`/`gvaclassify` with `nireq>=1` (NPU:
`nireq=4`) and `ie-config="GPU_THROUGHPUT_STREAMS=1"` on GPU. On the
JPEG branch, add `vapostproc ! video/x-raw` before `jpegenc` to pull
frames back to system memory.

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
  "destination": { "metadata": { "type": "mqtt",
                                 "topic": "{{DETECTIONS_TOPIC_PREFIX}}_X",
                                 "publish_frame": false } },
  "parameters":  { "frame-sink-location": "/tmp/frames/{{DETECTIONS_TOPIC_PREFIX}}_X.jpg" }
}
```
- `<pipeline_name>` = one of the three variants; all N POSTs use the same
  variant per device flag.
- Use `curl -k --noproxy '*'`. Poll `GET /api/pipelines/status` until no
  instance is `QUEUED`.
- With `APPEND_PIPELINE_NAME_TO_PUBLISHER_TOPIC=true`, MQTT topic becomes
  `{{DETECTIONS_TOPIC_PREFIX}}_X/{{PIPELINE_NAME}}` (or `_gpu`/`_npu`).

## File-source watchdog (required when `source.uri` is `file://`)

DLSPS with `file://` is one-shot: EOS → `COMPLETED` → MQTT/frame output
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
      -d '{"source":{"uri":"file:///home/pipeline-server/videos/new_video_'"$idx"'.mp4","type":"uri"},"destination":{"metadata":{"type":"mqtt","topic":"{{DETECTIONS_TOPIC_PREFIX}}_'"$idx"'","publish_frame":false}},"parameters":{"frame-sink-location":"/tmp/frames/{{DETECTIONS_TOPIC_PREFIX}}_'"$idx"'.jpg"}}' \
      "$BASE" >/dev/null || true
  done
  sleep 3
done
```
