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
| **Target latency** | < 30 ms end-to-end at 1080p (validated: ~23 ms mean, ~28 ms p99 on Arc iGPU) |
| **First-boot time** | 20–35 min while YOLO11n trains on the iGPU (subsequent boots: seconds — IR is cached) |

## What the UI shows

Open http://localhost:8080 (or the LAN URL printed by `make up`/`make run`). After clicking **Start** the left panel begins streaming inference frames and the right column exposes the KPIs a reviewer typically asks for:

- **Video feed** — 1080p H.264 loop with per-frame polyp bounding boxes.
- **Detection Status card** (hero, under the video)
  - Live pill: `DETECTED` / `NOT DETECTED` + confidence
  - `SESSION` sub-bar: cumulative polyp instances, % of frames with a detection, positive-frame count
- **Pipeline Performance table** — `Workload | Model | Device | FPS | Infer | P99 | Status`. `Infer` is the mean per-frame model latency; `P99` is the true 99th percentile over the last 120 frames (rolling deque + `np.percentile`).
- **Model & Input block** — model name, precision (`FP16 OpenVINO IR`), task/dataset, video source resolution, model input tensor size, target device (`GPU` / `CPU` / `NPU`).
- **Platform accordion** — CPU / GPU / NPU utilization from `intel-npu-info` + `nvidia-smi`-style samplers.

All of the above is driven by a single Server-Sent Events stream at `/api/events` (~1 Hz snapshot) and an MJPEG stream at `/api/video_feed`, both proxied through nginx with `proxy_buffering off`.

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

## Repo layout (short)

```
Surgical_Instrument/
├── backend/
│   ├── main_server.py         # bootstrap FSM entrypoint
│   ├── pipeline/inference.py  # OpenVINO inference worker + rolling p99 stats
│   └── server/app.py          # Flask REST + SSE snapshot builder
├── ui/
│   └── src/
│       ├── components/DetectionPanel/   # video + hero detection card
│       ├── components/RightPanel/       # Pipeline Performance + Model & Input + Platform accordions
│       ├── redux/slices/detectionSlice.ts
│       ├── redux/middleware/sseMiddleware.ts
│       └── types/detection.ts
├── docker-compose.yaml
├── Makefile                   # up / run / down / logs / clean
└── docs/user-guide/quickstart.md
```

> The UI panel + Redux slice were previously named `Nicu*` (layout was ported from the NICU-Warmer reference); as of commit `5f1b3fe2` everything is renamed to `Detection*` for consistency with this app.

## JIRA

ITEP-90933 (parent) · ITEP-93671 (POC, done) · ITEP-93672 (DLS pipeline) · ITEP-93673 (UI) · ITEP-93674 (E2E + metrics)
