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

# 2) (Optional but recommended) run the pre-flight check.
make doctor      # itemised host readiness report (docker, /dev/dri, NPU,
                 # cached IR, videos, port 8080). Non-zero exit on fatals only.

# 3) Build images + first-boot train (~20-35 min on Arc iGPU).
make up
make logs        # follow the train pipeline

# 4) Once backend HEALTHCHECK passes, open the UI.
open http://localhost:8080

# --- EVERY TIME AFTER ---------------------------------------------------
# Fast path: no rebuild, no train (trained IR is cached under ./models/).
make run
open http://localhost:8080
```

`make up` and `make run` both **auto-detect** any `/dev/video*` devices on
the host and layer in a compose override that makes them available to the
pipeline container. The UI's Settings modal is the primary runtime picker for
choosing between the recorded video and any attached camera — see [Runtime
configuration](#runtime-configuration) below.

### Dev workflow (no Docker)

```bash
make backend-venv       # one-time: build .venv-backend with torch+xpu
make backend-bootstrap  # first-boot only: cache-first train + export
make backend-serve      # Flask on :5001
make ui-dev             # Vite dev server proxied at http://localhost:5173
```

See [docs/user-guide/quickstart.md](docs/user-guide/quickstart.md) for the full dataset-drop procedure, GPU passthrough troubleshooting, and health-gating details.

## Runtime configuration

Everything reconfigurable at runtime lives in the **Settings** modal —
opened via the `⚙ Settings` button in the top action bar, next to Start/Stop.

**First launch.** The app opens with a one-time **research-use disclaimer**
that must be acknowledged before the main UI is interactive. The ack is
stored in `localStorage` under `surgical_disclaimer_ack_v1` and does not
survive a browser-profile wipe.

### Input Source tab

Pick where frames come from without editing config files or restarting
compose. Three source kinds are supported; kinds with no detected devices
are visible but disabled so it's obvious what the app supports.

| Kind | Argument | Populated by |
|---|---|---|
| **Video file** | basename under `./videos/` | `GET /api/videos` — lists everything with `.mp4 .mkv .avi .mov .ts` |
| **USB / v4l2 camera** | `/dev/videoN` | `GET /api/devices/cameras` — reads `/sys/class/video4linux` |
| **Basler camera** | serial number | `GET /api/devices/cameras` — pypylon enumeration (ships in Slice E) |

- **Upload** a new video with the "Choose file…" button (max 500 MB, extension whitelist enforced server-side). New uploads land in the same `./videos/` volume and appear in the dropdown immediately.
- **Apply** persists the selection client-side. It takes effect on the **next** Start — the pipeline rejects source changes mid-stream. If a pipeline is running, the modal shows a banner and blocks changes until you Stop.
- **Cameras** are compose-time devices. Hot-plugging after `make up` requires
  `make run` (or the equivalent `docker compose up -d`) so the container can
  see the new node — the UI's picker only surfaces what's already mounted.

### Devices tab

Single-row table (`Workload · Model · Device`) with a dropdown for the
polyp-detection accelerator: `CPU`, `GPU` (Intel Arc iGPU — recommended),
`NPU` (Intel AI Boost). Save applies the change on the next Start; Reset
session clears the last inference session's aggregates without stopping the
backend process.

### Backend contract (for scripting / smoke tests)

The UI is a thin wrapper over these endpoints, so any of them can be driven
from `curl` for automation.

| Endpoint | Purpose |
|---|---|
| `GET /api/videos` | List `{name, size_bytes, mtime}` under `VIDEOS_DIR` (default `/videos`) |
| `POST /api/videos` | Multipart upload (`file` field). `415` for wrong ext, `409` for duplicate, `413` for oversize |
| `GET /api/devices/cameras` | `{v4l2:[…], basler:[…], basler_note?}` |
| `GET /api/config` | Reflects live source: `{video_file, default_video, source:{kind,arg}, devices:{detect}}` |
| `POST /api/start` | Optional body: `{device?, source?:{kind,arg}}` — persisted to `ServerState` for subsequent Starts |
| `POST /api/stop` · `POST /api/reset` | Lifecycle |
| `POST /api/device` | Set active accelerator for the polyp-detection workload |

### Pre-flight: `make doctor`

Read-only diagnostic that checks the host before you run `make up`. Reports
each item as `[ OK ]`, `[WARN]`, or `[FAIL]`; exits non-zero only on genuine
fatals (missing Docker, no video assets, port collision with a foreign
process). Own-stack aware — if `surgical-ui` is already running on
`UI_HOST_PORT`, that's reported as OK, not as a conflict.

Sections: host prerequisites · accelerator visibility · cameras · assets ·
port availability · compose config. Sample output:

```
[doctor] --- accelerator visibility ---
  [ OK ] /dev/dri present (renderD* count: 1)
  [ OK ] /dev/accel/accel0 present (NPU visible)
[doctor] --- assets ---
  [ OK ] cached IR : models/yolo11n_polyp/best_openvino_model (5.4M)
  [ OK ] 2 demo video(s) under ./videos/
[doctor] --- port availability ---
  [ OK ] port 8080 free
[doctor] all critical checks passed — 'make up' should succeed.
```

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
