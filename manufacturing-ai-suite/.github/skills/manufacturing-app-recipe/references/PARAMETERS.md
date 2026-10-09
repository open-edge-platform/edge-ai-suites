# Parameters (from invoking prompt)

| Param | Purpose | Modes |
|---|---|---|
| `{{DEPLOYMENT}}` | `vision` \| `ts` \| `multimodal` \| `vllm` \| `agentic` — Question 0's answer | all |
| `{{MODE}}` | `demo` \| `production` (default `production`) — sub-mode within `vision`/`ts`; `multimodal`/`vllm`/`agentic` are production-only | `vision`, `ts` |
| `{{OBJECT}}` | defect/anomaly label in dashboard/alerts (e.g. `weld_defect`, `tool_wear`, `wind_turbine`); any MQTT/Grafana/InfluxDB-safe string | all |
| `{{STACK_DIR}}` | absolute parent path for a new, flat, standalone stack directory (e.g. `weld-defect-stack`) — `multimodal`/`vllm`/`agentic` only; never assumed from the current working directory | `multimodal`, `vllm`, `agentic` |
| `{{TS_REPO_DIR}}` | absolute path to an existing `industrial-edge-insights-time-series` checkout to add `apps/{{APP_NAME}}/` into (or where to clone it fresh) — `ts` production only | `ts` |
| `{{APP_NAME}}` | the new `apps/<name>/` folder name, kebab-case (e.g. `wind-turbine-anomaly-detection`) | `ts` |
| `{{DEFAULT_MODEL}}`, `{{OTHER_MODELS}}` | vision classifier/detector options for DLSPS | `vision`, `multimodal`, `vllm`, `agentic` |
| `{{PIPELINE_NAME}}` | canonical DLSPS pipeline `name` (e.g. `weld_defect_classification`); variants `<name>`/`_gpu`/`_npu` | `vision`, `multimodal`, `vllm`, `agentic` |
| `{{VISION_TOPIC}}` | MQTT topic DLSPS publishes classification/detection metadata to | `multimodal`, `vllm`, `agentic` |
| `{{SENSOR_UDF_NAME}}` | Time Series Analytics UDF name; backed by a pretrained model or a threshold/rate-of-change rule (time-series-analytics-user's `references/patterns.md` patterns) | `ts`, `multimodal`, `vllm`, `agentic` |
| `{{SENSOR_MEASUREMENT}}` | InfluxDB measurement / MQTT topic the raw sensor stream lands on | `ts`, `multimodal`, `vllm`, `agentic` |
| `{{SENSOR_TAGS}}` | OPC-UA node IDs / MQTT field names to ingest | `ts` |
| `{{INGEST_TRANSPORT}}` | `opcua` \| `mqtt` (default `opcua` for `ts`) — which simulator/Telegraf input plugin drives ingestion | `ts`, `multimodal`, `vllm`, `agentic` |
| `{{TS_TOPIC}}` | MQTT topic the Time Series Analytics UDF publishes **every** flagged point to | `multimodal`, `vllm`, `agentic` |
| `{{SENSOR_ALERT_TOPIC}}` | MQTT topic for the sensor-only crit alert | `multimodal`, `vllm`, `agentic` |
| `{{ALERT_CHANNEL}}` | `mqtt` (default) \| `opcua` — **enable only one** | `ts` |
| `{{ALERT_TOPIC}}` | MQTT topic for crit alerts, only when `{{ALERT_CHANNEL}}=mqtt` | `ts` |
| `{{FUSION_TOPIC}}` | MQTT topic Fusion Analytics publishes the fused verdict to | `multimodal`, `vllm`, `agentic` |
| `{{FUSION_MODE}}` | `AND` \| `OR` (default `OR`) — both vs either modality must flag anomaly | `multimodal`, `vllm`, `agentic` |
| `{{TOLERANCE_NS}}` | timestamp-matching tolerance in nanoseconds (default `50e6` = 50 ms) | `multimodal`, `vllm`, `agentic` |
| `{{DASHBOARD_SLUG}}` / `{{DASHBOARD_TITLE}}` | Grafana dashboard identifier | all production modes |
| `{{INPUT_TYPE}}` | `simulator` (default) \| `rtsp`/`device` (real camera) + `mqtt`/`opcua` (real sensor feed) | `vision`, `multimodal`, `vllm`, `agentic` |
| `{{LLM_MODEL_NAME}}`, `{{LLM_DEVICE}}`, `{{LLM_WEIGHT_FORMAT}}` | VLM/LLM model + device + OpenVINO weight format | `vllm`, `agentic` |
| `{{BATCH_TRIGGER_MODE}}`, `{{BATCH_SIZE}}`/`{{BATCH_INTERVAL_S}}` | `size` (default, `{{BATCH_SIZE}}=10`) \| `time` (`{{BATCH_INTERVAL_S}}=30`) — when Fusion Analytics flushes its `batch-complete` MQTT event | `vllm`, `agentic` |
| `{{AGENT_METRICS}}` | `yes` \| `no` (default `no`) — include the optional `metrics-manager`/Prometheus overlay | `agentic` |
| `{{HOST_IP}}` | host IP for Nginx/Grafana/WebRTC (default `localhost`) | all production modes |
| `{{TURN_USER}}`, `{{TURN_PASS}}` | Coturn / MediaMTX ICE credentials (default `turnuser` / a generated secret) | `multimodal`, `vllm`, `agentic` |
| `{{GENERATE_TESTS}}` | `yes` \| `no` (no default — ask explicitly) — whether to author the `tests/` pytest suite; skip `tests/` entirely and its pytest completion criteria when `no` | `ts`, `multimodal`, `vllm`, `agentic` |
