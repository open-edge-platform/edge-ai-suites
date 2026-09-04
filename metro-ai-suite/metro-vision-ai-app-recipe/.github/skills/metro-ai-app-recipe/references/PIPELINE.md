# DLSPS pipeline reference

> **Skill pointer:** for DL Streamer Pipeline Server deployment/operation (startup, `config.json`, REST launch/stop/status, MQTT/publisher wiring, GPU/NPU access), invoke external `dlsps-user` (open-edge-platform/skills) when available. Below are recipe-specific overrides.

## Required env

- `REST_SERVER_PORT=8080`, `RUN_MODE=EVA`, `APPEND_PIPELINE_NAME_TO_PUBLISHER_TOPIC=true`, `EMIT_SOURCE_AND_DESTINATION=true`, `SERVICE_NAME=dlstreamer-pipeline-server`, `MQTT_HOST=broker`, `MQTT_PORT=1883`.
- **WebRTC (required):** `ENABLE_WEBRTC=true`, `WEBRTC_SIGNALING_SERVER=http://mediamtx-server:8889`; DLSPS WHIP-pushes annotated streams to MediaMTX using launch `peer-id`.
- NPU also: `ZE_ENABLE_ALT_DRIVERS=libze_intel_npu.so`.
- Do NOT set `ENABLE_OPEN_TELEMETRY` (no OTel/Prometheus).
- Blank proxy: `http_proxy=`, `https_proxy=`, `HTTP_PROXY=`, `HTTPS_PROXY=`; `no_proxy=${no_proxy},${HOST_IP},mediamtx-server` (MUST include `mediamtx-server` or WHIP uses corporate proxy and WebRTC publish silently fails).

## Volumes and permissions

- Pipeline root: tmpfs named volume `uid=1999,gid=1999` (`dlstreamer-pipeline-server-pipeline-root:/var/cache/pipeline_root`). Do NOT run as root.
- No shared frames volume — video leaves over WebRTC, not JPEG files.
- Device access needs ALL: `devices: ["/dev:/dev"]`, `volumes: ["/run/udev:/run/udev:ro","/dev:/dev","/tmp:/tmp"]`, `device_cgroup_rules: ["c 189:* rmw", "c 209:* rmw", "a 189:* rwm"]`, `group_add: ["${VIDEO_GID}", "${RENDER_GID}"]`. Do NOT add duplicate GID (e.g. `vpl` sharing `render`) — Compose rejects duplicates.

## Three pipeline variants

`/home/pipeline-server/config.json` must define exactly `{{PIPELINE_NAME}}`, `{{PIPELINE_NAME}}_gpu`, `{{PIPELINE_NAME}}_npu`; names drive REST path + MQTT suffix.

**CRITICAL — `name`/`version` schema (verified 2026.1.0):** set variant as **`name`** and omit `version`. DLSPS treats `name` as pipeline **version** and groups all under `user_defined_pipelines`:

- `GET /api/pipelines` returns `{"name":"user_defined_pipelines", "version":"{{PIPELINE_NAME}}", ...}` — variant is **`version`**.
- Launch/DELETE path: `/api/pipelines/user_defined_pipelines/<variant>`.
- **Bad collapse:** `name: user_defined_pipelines` + `version: <variant>`; DLSPS ignores `version`, all become `user_defined_pipelines/user_defined_pipelines`, launch returns HTTP 400 `"Pipeline not found"`. Use `name: <variant>` and no `version`.
- After editing `config.json` MUST `docker compose up -d --force-recreate dlstreamer-pipeline-server` (NOT `restart`): definitions copy into `pipeline_root` tmpfs only at startup.

## Pipeline shape (WebRTC frame branch handled by DLSPS)

Pipeline ends in `appsink name=destination` (metadata → MQTT). Annotated **video is emitted over WebRTC by DLSPS** when REST launch supplies `frame.type=webrtc`; DLSPS taps watermarked frames and WHIP-publishes to MediaMTX. There is NO `tee`, `jpegenc`, `multifilesink`, or `frame-sink-location`. Put `gvawatermark` before `gvametaconvert` so boxes appear.

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
- `threshold` is a knob. YOLO11 rescales to 640×640; on 640×480 reference video vehicles score 0.3–0.45. `threshold≥0.5` → empty stream. Ship `0.3`, raise for higher-res feeds.
- WebRTC is internal to DLSPS — do NOT wire it in GStreamer. Include `gvawatermark`; supply `frame.type=webrtc` at REST launch.
- Keep `appsink` non-blocking: DLSPS drops frames rather than stalling under back-pressure.

## GPU/NPU variants

Replace `decodebin3` with:
```
parsebin ! decodebin3 ! vapostproc ! video/x-raw(memory:VAMemory) ! gvafpsthrottle target-fps=30
```
Codec-agnostic (H.264/H.265/AV1 via VAAPI). Do NOT hardcode `vah264dec`. Set `device=GPU`/`NPU` on `gvadetect`/`gvaclassify` with `nireq>=1` (NPU: `nireq=4`) and `ie-config="GPU_THROUGHPUT_STREAMS=1"` on GPU. Add `vapostproc ! video/x-raw` before `gvawatermark` to return frames to system memory for overlay + WebRTC encode.

## Class filtering — where and how

- DLSPS publishes ALL classes (bare `gvadetect`, no model-proc filter).
- **Filter in Node-RED** by `label_id ∈ {{CLASS_FILTER_IDS}}` (`[]` = keep all).
- OMZ single-class models (e.g. `person-detection-retail-0013`, `vehicle-detection-0202`) emit `label_id:1` with empty label; treat labelless / `label_id==1` as target — see `{{LABEL_RULE_NOTE}}`.

## Secondary classifier (`gvaclassify`) — concrete wiring

When `{{CLASSIFIER}} != none` (e.g. PPE compliant/non-compliant), wire a second inference stage on the **detected regions**:

- `install.sh` downloads the classifier IR to `models/{{CLASSIFIER}}/{{CLASSIFIER_XML}}` (`.xml`+`.bin`) from `{{CLASSIFIER_URL}}`. Example PPE model families: an OMZ head/attribute classifier or a project-supplied hardhat/vest IR — resolve the concrete `{{CLASSIFIER_URL}}`/`{{CLASSIFIER_XML}}` from the invoking prompt or the model download skill.
- Pipeline element (already in the shape above; keep on detected regions):
  ```
  queue ! gvaclassify model=/home/pipeline-server/models/{{CLASSIFIER}}/{{CLASSIFIER_XML}}
            device={{DEVICE}} inference-region=1 model-instance-id=inst1
            name=classification !
  ```
  `inference-region=1` = run per detected object (ROI), NOT full frame. On GPU/NPU set `device=GPU`/`NPU` and `nireq>=1` here too.
- **Class filtering with a classifier:** the detector's `tensor[0].label_id` is the *object* class (e.g. person/worker); the classifier appends a second tensor with the attribute (e.g. `hardhat`/`no-hardhat`). In Node-RED, match the **classifier** tensor label:
  ```js
  const tens = det.tensor || [];
  const isTarget = tens.some(t =>
    t.label === '{{OBJECT}}' || {{CLASS_FILTER_IDS}}.indexOf(t.label_id) !== -1);
  ```
  Populate `{{CLASS_FILTER_IDS}}` with the concrete attribute class IDs the prompt names (e.g. hardhat/vest IDs); `[]` keeps all. For a `count<1` "no-PPE" rule, count the **compliant** class and alert when it drops below the threshold (see [`references/NODE_RED.md`](references/NODE_RED.md) step 6).

## Starting pipelines (per source, via REST through Nginx)

For `X in 1..{{NUM_SOURCES}}` POST to `https://<HOST>/api/pipelines/user_defined_pipelines/<pipeline_name>`:
```json
{
  "source":      { "uri": "file:///home/pipeline-server/videos/new_video_X.mp4", "type": "uri" },
  "destination": {
    "metadata": { "type": "mqtt", "topic": "{{DETECTIONS_TOPIC_PREFIX}}_X", "publish_frame": false },
    "frame":    { "type": "webrtc", "peer-id": "{{DETECTIONS_TOPIC_PREFIX}}_X" }
  }
}
```
- **`host`/`port` in `destination.metadata` are REQUIRED (verified 2026.1.0).** Per-request MQTT publisher ignores container `MQTT_HOST`/`MQTT_PORT`; if omitted, it defaults to `localhost:1883` inside DLSPS, so detections never reach `broker` and downstream MQTT checks time out with no log errors. Put `"host":"broker","port":1883` in launch and watchdog bodies. `MQTT_HOST=broker` still matters elsewhere — set both.
- `frame` makes DLSPS WHIP-publish to MediaMTX path `= peer-id`; Grafana reads `/mediamtx/{{DETECTIONS_TOPIC_PREFIX}}_X/` (WHEP). Keep `peer-id` identical to MQTT `topic`.
- `<pipeline_name>` = one variant; all N POSTs use same variant per device flag.
- `curl --noproxy '*'` reaches local DLSPS REST. Trust the deploy-time self-signed cert with `--cacert src/nginx/ssl/server.crt` (generated by `install.sh`); for remote/production pin the real CA. Poll `GET /api/pipelines/status` until no `QUEUED`.
- With `APPEND_PIPELINE_NAME_TO_PUBLISHER_TOPIC=true`, MQTT usually becomes `{{DETECTIONS_TOPIC_PREFIX}}_X/{{PIPELINE_NAME}}` (or `_gpu`/`_npu`), but suffix is unreliable; bare `{{DETECTIONS_TOPIC_PREFIX}}_X` occurs. Consumers/tests MUST subscribe to `{{DETECTIONS_TOPIC_PREFIX}}_X/#` (also matches bare parent), not assume suffix.

## Input sources — file:// vs RTSP vs /dev/video

The launch body's `source.uri` is driven by the invoking prompt's **Inputs** answer; `sample_start.sh` builds it per source index `X`:

- **Sample video / local file** (default): `"uri":"file:///home/pipeline-server/videos/new_video_X.mp4","type":"uri"`. `install.sh` downloads the videos; the **file-source watchdog is REQUIRED** (file:// is one-shot — see below).
- **RTSP cameras** (`rtsp://…`, one URL per source): `"uri":"rtsp://<user>:<pass>@<cam-X-host>/<path>","type":"uri"`. RTSP is a **continuous** stream — DLSPS never emits EOS, so **do NOT download sample videos** and **do NOT run the file:// watchdog** (no `COMPLETED` respawn needed). Store the URLs in `.env` as `RTSP_URL_1..N` (quote values) and read them in `sample_start.sh`.
- **USB/CSI device** (`/dev/videoN`): `"uri":"/dev/videoN","type":"device"`; also continuous — no video download, no watchdog.

`sample_start.sh` selects behaviour from an `INPUT_TYPE` (`file`|`rtsp`|`device`) written to `.env` by `install.sh`, e.g.:
```sh
case "$INPUT_TYPE" in
  file)   SRC='{"uri":"file:///home/pipeline-server/videos/new_video_'"$X"'.mp4","type":"uri"}' ;;
  rtsp)   eval 'U=$RTSP_URL_'"$X"; SRC='{"uri":"'"$U"'","type":"uri"}' ;;
  device) eval 'U=$DEV_VIDEO_'"$X"; SRC='{"uri":"'"$U"'","type":"device"}' ;;
esac
```
Only start `sample_watchdog.sh` when `INPUT_TYPE=file`.

## File-source watchdog (required when `source.uri` is `file://`)

DLSPS `file://` is one-shot: EOS → `COMPLETED` → MQTT/WebRTC stops. `multifilesrc loop=true` / `urisourcebin` do NOT loop past `qtdemux`/MP4.

Ship `sample_watchdog.sh`: start after `sample_start.sh` (nohup, PID → `.watchdog.pid`, logs → `watchdog.log`); kill first in `sample_stop.sh`.

1. Poll `GET /api/pipelines/status` every ~3 s.
2. For each `{COMPLETED, ABORTED, ERROR}` instance:
   - Read topic from `GET /api/pipelines/{id}` at **`params.request.destination.metadata.topic`** (NOT top-level `request…topic`, the expanded dict).
   - Extract source index from `{{DETECTIONS_TOPIC_PREFIX}}_(\d+)`, DELETE id, POST same source/destination/parameters.
3. **Deduplicate by id** (`declare -A HANDLED`). DLSPS keeps `COMPLETED` entries forever; without guard, watchdog spawns dozens/minute and pins CPU.

```sh
#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")"; ENVF=.env; . "./$ENVF"
HOST="${HOST_IP:-localhost}"; DEVICE="${1:-cpu}"
case "$DEVICE" in cpu) PIPE="{{PIPELINE_NAME}}";; gpu) PIPE="{{PIPELINE_NAME}}_gpu";; npu) PIPE="{{PIPELINE_NAME}}_npu";; *) exit 1;; esac
BASE="https://${HOST}/api/pipelines/user_defined_pipelines/${PIPE}"
declare -A HANDLED
trap 'exit 0' TERM INT
CACERT=src/nginx/ssl/server.crt
while :; do
  status=$(curl --noproxy '*' -s --cacert "$CACERT" "https://${HOST}/api/pipelines/status" || echo '[]')
  finished=$(python3 <<<"$status" -c 'import json,sys;[print(p["id"]) for p in json.load(sys.stdin) if p.get("state") in ("COMPLETED","ABORTED","ERROR")]')
  for id in $finished; do
    [ -n "${HANDLED[$id]:-}" ] && continue
    HANDLED[$id]=1
    detail=$(curl --noproxy '*' -s --cacert "$CACERT" "https://${HOST}/api/pipelines/${id}")
    idx=$(python3 <<<"$detail" -c 'import json,sys,re; d=json.load(sys.stdin); req=(d.get("params") or {}).get("request") or {}; t=(((req.get("destination") or {}).get("metadata") or {})).get("topic",""); m=re.match(r"{{DETECTIONS_TOPIC_PREFIX}}_(\d+)",t); print(m.group(1)) if m else None')
    [ -z "$idx" ] && continue
    curl --noproxy '*' -s --cacert "$CACERT" -X DELETE "https://${HOST}/api/pipelines/${id}" >/dev/null || true
    curl --noproxy '*' -s --cacert "$CACERT" -X POST -H 'Content-Type: application/json' \
      -d '{"source":{"uri":"file:///home/pipeline-server/videos/new_video_'"$idx"'.mp4","type":"uri"},"destination":{"metadata":{"type":"mqtt","topic":"{{DETECTIONS_TOPIC_PREFIX}}_'"$idx"'","publish_frame":false},"frame":{"type":"webrtc","peer-id":"{{DETECTIONS_TOPIC_PREFIX}}_'"$idx"'"}}}' \
      "$BASE" >/dev/null || true
  done
  sleep 3
done
```
