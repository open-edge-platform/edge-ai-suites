# Surgical Instrument Sample App

Real-time polyp detection on endoscopic video using Intel hardware acceleration (CPU / Intel Arc iGPU / Intel NPU) via DL Streamer.

> **⚠️ Not for clinical use.** This is a developer reference implementation for evaluating Intel inference performance on edge hardware. It is **not** a medical device and must not be used for diagnosis, treatment, or any patient-care decision.

## At a glance

| | |
|---|---|
| **Model** | YOLOv11n (FP16 OpenVINO IR) — trained on polyp-detection dataset (mAP@50 0.98) |
| **Pipeline** | DL Streamer (`intel/dlstreamer:2026.1.0-ubuntu24`) |
| **Event bus** | MQTT (`eclipse-mosquitto:2`, internal-only, password-authenticated) |
| **Backend** | Flask 3.0 (REST + SSE + MJPEG passthrough) |
| **UI** | React + Vite + nginx (NICU-derived layout) |
| **Source** | Recorded video today (Basler USB3 via `gencamsrc` in follow-up) |
| **Target latency** | < 30 ms camera → screen, 1080p @ 60 fps |
| **Validated POC** | yolo11n / iGPU p99 = 13.9 ms (DL Streamer `latency_tracer`) |

## Topology

Only `ui:8080` is published to the host. All inter-service traffic runs on the private `surgical-internal` Docker bridge.

```
HOST :8080 ─→ surgical-ui  (nginx + React)
            INTERNAL surgical-internal bridge
                ├─ surgical-backend   Flask 3.0
                ├─ surgical-pipeline  DL Streamer (Gst.parse_launch)
                ├─ surgical-mqtt      eclipse-mosquitto:2 (password auth)
                └─ surgical-metrics   intel/hl-ai-metrics-collector
```

## Quickstart

```bash
make mqtt-passwd        # generate configs/mqtt_passwd (one-time)
make assets             # fetch/validate model + sample video
make up                 # bring up the stack
open http://localhost:8080
```

See `docs/user-guide/` for full setup instructions.

## JIRA

ITEP-90933 (parent) · ITEP-93671 (POC, done) · ITEP-93672 (DLS pipeline) · ITEP-93673 (UI) · ITEP-93674 (E2E + metrics)
