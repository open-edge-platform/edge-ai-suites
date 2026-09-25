# DLSPS vision pipeline reference (the video half)

> **Skill pointer:** for DL Streamer Pipeline Server deployment/operation
> (startup, REST launch/stop/status, MQTT/S3/publisher wiring, GPU/NPU device
> access), invoke external `dlsps-user` when available; for authoring a novel
> GStreamer element chain, invoke `dlstreamer-coding-agent`. Below are
> recipe-specific overrides for the vision half of the fusion pipeline.

## Required env

- `REST_SERVER_PORT=8080`, `SERVICE_NAME=dlstreamer-pipeline-server`,
  `MQTT_HOST=ia-mqtt-broker`, `MQTT_PORT=1883`.
- **RTSP source (required):** `ENABLE_RTSP=true` — the source video always
  arrives over RTSP from MediaMTX (simulator-published) or a real camera, not
  a local file.
- **WebRTC (required for the dashboard):** `ENABLE_WEBRTC=true`,
  `WEBRTC_SIGNALING_SERVER=http://mediamtx:8889`.
- **S3 storage (required for stored-frame review):** `S3_STORAGE_HOST`,
  `S3_STORAGE_PORT`, `S3_STORAGE_USER`, `S3_STORAGE_PASS` — point at the
  SeaweedFS S3 gateway (`seaweedfs-s3:8333`).
- Blank proxy for internal hosts: `no_proxy`/`NO_PROXY` MUST list
  `mediamtx`, `${S3_STORAGE_HOST}`, `ia-mqtt-broker`, `otel-collector` (if
  OTel is enabled) — otherwise WHIP/S3 writes silently fail through a
  corporate proxy.

## Volumes and permissions

- Pipeline root: named volume `vol_pipeline_root:/var/cache/pipeline_root`
  (`uid=1999,gid=1999`). Do NOT run as root.
- Mount the model directory read-only:
  `./configs/dlstreamer-pipeline-server/models:/home/pipeline-server/resources/models`.
- Device access (GPU/NPU only, skip on CPU-only hosts): `devices:
  ["${DRI_MOUNT_PATH:-/dev/null}:/dev/dri", "${ACCEL_MOUNT_PATH:-/dev/null}:/dev/accel"]`,
  `device_cgroup_rules: ["c 189:* rmw", "c 209:* rmw", "a 189:* rwm"]`,
  `group_add: ["109","110","992","993"]` (covers render GID across Ubuntu
  20.04/22.04/24.04 hosts — Compose rejects a duplicate GID, so don't also add
  `${RENDER_GID}` if it resolves to one already listed).

## Pipeline shape — classification (default: whole-frame quality verdict)

Use `gvaclassify inference-region=full-frame` when the vision task is a
single per-frame label (e.g. weld-seam quality) rather than localizing
objects:

```
rtspsrc add-reference-timestamp-meta=true location="rtsp://mediamtx:8554/live.stream" latency=100 name=source !
  rtph264depay ! h264parse ! decodebin ! videoconvert ! video/x-raw,format=BGR !
  gvaclassify inference-region=full-frame name=classification !
  gvawatermark !
  gvametaconvert add-empty-results=true add-rtp-timestamp=true name=metaconvert !
  queue ! gvafpscounter !
  appsink name=destination
```

- `add-reference-timestamp-meta=true` on `rtspsrc` + `add-rtp-timestamp=true`
  on `gvametaconvert` are **required** — Fusion Analytics matches vision and
  sensor messages by the RTP sender timestamp
  (`metadata.rtp.sender_ntp_unix_timestamp_ns`); omitting either flag means
  the vision message has no timestamp to fuse on and Fusion Analytics will
  never flag a vision-side event.
- **Known startup caveat:** DLSPS may not emit RTP sender timestamps for the
  first ~300 packets after a pipeline (re)start — expect a short warm-up
  before Fusion Analytics output appears; do not treat this as a failure in
  tests, just allow a grace period.
- Include `gvawatermark` before `gvametaconvert` even for a full-frame
  classification (no boxes to draw, but keeps the pipeline shape consistent
  and lets WebRTC/S3 outputs carry the label overlay if the model's
  `model-proc` adds one).

## Pipeline shape — detection (when the vertical needs localized defects)

Swap `gvaclassify inference-region=full-frame` for
`gvadetect model-instance-id=inst0 name=detection ! queue ! gvaclassify
inference-region=1 name=classification` (classifier optional) exactly as in
`metro-ai-app-recipe`'s [PIPELINE.md](../metro-ai-app-recipe/references/PIPELINE.md)
— reuse that skill's GPU/NPU `vapostproc` guidance verbatim if this vertical
needs bounding-box localization instead of a whole-frame label.

## Destination configuration — three sinks, all required

```json
"destination": {
  "metadata": { "type": "mqtt", "topic": "{{VISION_TOPIC}}" },
  "frame": [
    { "type": "webrtc", "peer-id": "{{STACK_DIR}}-stream", "overlay": true },
    { "type": "s3_write", "bucket": "dlstreamer-pipeline-results",
      "folder_prefix": "{{OBJECT}}", "block": false }
  ]
}
```

- `frame` is an **array** here (not a single object like in `metro-ai-app-recipe`)
  — DLSPS 2026.2.0 supports multiple simultaneous frame destinations; keep
  both WebRTC (dashboard) and `s3_write` (stored-frame review/audit trail).
- `overlay: true` draws the `gvawatermark` box/label on the WebRTC stream;
  set `false` only if the model-proc already burns in an overlay.
- `s3_write.block: false` means metadata (MQTT) may arrive before the S3
  write completes — acceptable for dashboards; set `true` only if a
  downstream consumer must read the S3 object the instant it sees the MQTT
  message.
- `metadata.topic` = `{{VISION_TOPIC}}` — this is the topic Fusion Analytics
  subscribes to as its vision-side input; keep it in sync with
  `FUSION.md`'s `VISION_TOPIC` env var.

## GPU/NPU variants

Same as `metro-ai-app-recipe`: replace `decodebin` with
`parsebin ! decodebin3 ! vapostproc ! video/x-raw(memory:VAMemory)`,
set `device=GPU`/`NPU` + `nireq>=1` on `gvaclassify`/`gvadetect`, add
`vapostproc ! video/x-raw` before `gvawatermark` to return frames to system
memory for overlay + WebRTC encode.

## Starting/switching device at runtime

DLSPS pipelines are started via REST, not `auto_start` alone, when swapping
device:

```bash
for id in $(curl -k --noproxy '*' https://<HOST_IP>:${GRAFANA_PORT}/dsps-api/pipelines/status | grep -oP '"id":\s*"\K[^"]+'); do
  curl -k --noproxy '*' -X DELETE "https://<HOST_IP>:${GRAFANA_PORT}/dsps-api/pipelines/$id"
done
curl -k --noproxy '*' https://<HOST_IP>:${GRAFANA_PORT}/dsps-api/pipelines/user_defined_pipelines/{{PIPELINE_NAME}} \
  -X POST -H 'Content-Type: application/json' \
  -d "$(sed 's/"device": "CPU"/"device": "GPU"/' pipeline-request-cpu.json)"
```

Ship a `pipeline-request-cpu.json` request body per vertical alongside
`config.json` so device swaps are a one-line `sed`, not hand-edited JSON.
