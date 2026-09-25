# Demo/PoC mode

When Question 0 selects `demo`, build **one single-modality lightweight app**
proving either the vision model or the sensor pattern works on Intel
hardware — no Compose topology, no Telegraf/InfluxDB/Fusion
Analytics/Grafana/Nginx/SeaweedFS/MediaMTX/Coturn.

Ask which sub-path (no default — the user must pick, since the two paths
produce unrelated artifacts):

## Vision-only

- Delegate to `dlstreamer-coding-agent` for a from-scratch GStreamer/DL
  Streamer pipeline, or to `dlsps-user` for a REST-driven single pipeline
  server instance (`docker compose up` the DLSPS image alone + one `POST
  /pipelines/{name}/{version}` call).
- Model: reuse `{{DEFAULT_MODEL}}` if the invoking prompt named one;
  otherwise pick a sensible OpenVINO/ONNX classifier for the vertical.
- Output: annotated RTSP or a JSON-lines metadata file — no WebRTC/S3/MQTT
  stack required.

## Sensor-only

- Delegate to `time-series-analytics-user` end-to-end: bring up the bare
  Time Series Analytics Microservice, pick a pattern from its
  `references/patterns.md`, author the UDF + TICKscript, package, deploy,
  and feed test points.
- No Telegraf/InfluxDB wiring needed — feed points directly via the
  microservice's `POST /input` REST endpoint as that skill documents.

## Lightweight completion criteria (demo mode only — production criteria 1–11 do NOT apply)

1. The chosen delegate skill's own container(s) start successfully.
2. One inference/UDF call round-trips end-to-end (a detection/classification
   result, or a flagged/non-flagged UDF point) with evidence quoted verbatim
   (log line, REST response body, or MQTT message) in the final summary.
3. No literal `{{...}}` template variables remain in any generated file.
4. The final summary states plainly that this was a demo/PoC single-modality
   app, not the full fusion stack, and names the one command to bring it
   down.
