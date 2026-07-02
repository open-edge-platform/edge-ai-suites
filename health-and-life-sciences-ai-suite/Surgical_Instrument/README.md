# Surgical Instrument Sample App

Real-time polyp detection on endoscopic video using Intel hardware acceleration (CPU / Intel Arc iGPU / Intel NPU) via DL Streamer.

> **⚠️ Not for clinical use.** This is a developer reference implementation for evaluating Intel inference performance on edge hardware. It is **not** a medical device and must not be used for diagnosis, treatment, or any patient-care decision.

## At a glance

| | |
|---|---|
| **Model** | YOLO11n (FP16 OpenVINO IR) — trained in-container on CVC-ColonDB (mAP@50 ≈ 0.98 on val) |
| **Inference** | Ultralytics (train/export) + OpenVINO 2026.2 (serve) on Intel Arc iGPU via torch+xpu |
| **Backend** | Flask 3.0 — bootstrap orchestrator + REST + SSE + MJPEG streaming (`backend/main_server.py`) |
| **UI** | React + Vite + nginx |
| **Target latency** | < 30 ms end-to-end at 1080p (validated: 18.04 ms end-to-end @ 25 fps on Arc iGPU) |
| **First-boot time** | 20–35 min while YOLO11n trains on the iGPU (subsequent boots: seconds — IR is cached) |

## Topology

Two services on a private Docker bridge. Only the UI (:8080) is published to the host — the backend is reachable only through the UI's nginx reverse-proxy.

```
HOST :8080 ─→ surgical-ui        (nginx + React SPA + /api reverse-proxy)
            INTERNAL surgical-internal bridge
                └─ surgical-backend   Flask 3.0
                                      · bootstrap: fetch → train → export IR
                                      · serve:     REST + SSE + MJPEG on :5001
                                      · devices:   /dev/dri (Intel Arc iGPU)
```

The UI does **not** unblock until `surgical-backend` reports `/api/readiness → ready`. On first boot this includes the full train pipeline; the browser tab simply won't answer until the model is trained and served. This is the "gate UI on BE ready" contract — no user-visible bootstrap UX.

## Quickstart (Docker)

```bash
# --- FIRST TIME ---------------------------------------------------------
# 1) Drop CVC-ColonDB archive into ./datasets/CVC-ColonDB/raw/
#    (research use only — download from the CVC lab, accept their terms)
#    See docs/user-guide/quickstart.md for the exact URL.
#    (Skip if you seeded a pre-trained IR via `make assets`.)

# 2) Build images + first-boot train (~20-35 min on Arc iGPU).
make up
make logs        # follow the train pipeline

# 3) Once backend HEALTHCHECK passes, open the UI.
open http://localhost:8080

# --- EVERY TIME AFTER ---------------------------------------------------
# Fast path: no rebuild, no train (trained IR is cached under ./models/).
make run
open http://localhost:8080
```

### Dev workflow (no Docker)

```bash
make backend-venv       # one-time: build .venv-backend with torch+xpu
make backend-bootstrap  # first-boot only: cache-first train + export
make backend-serve      # Flask on :5001
make ui-dev             # Vite dev server proxied at http://localhost:5173
```

See [docs/user-guide/quickstart.md](docs/user-guide/quickstart.md) for the full dataset-drop procedure, GPU passthrough troubleshooting, and health-gating details.

## JIRA

ITEP-90933 (parent) · ITEP-93671 (POC, done) · ITEP-93672 (DLS pipeline) · ITEP-93673 (UI) · ITEP-93674 (E2E + metrics)
